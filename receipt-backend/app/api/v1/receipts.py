import hashlib
import uuid
import math
import logging
import traceback
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from app.utils.auth_utils import get_current_user
from app.utils.image_utils import compress_image, validate_image
from app.utils.text_utils import generate_product_key
from app.database import get_service_client
from app.config import settings
from app.utils.plan_utils import check_scan_limit, increment_scan_count, is_pro
from app.models.receipt import (
    ReceiptUploadResponse,
    ReceiptListResponse,
    ReceiptResponse,
    ReceiptDetailResponse,
    ReceiptItemResponse,
    ReceiptStatusResponse,
    PaginationMeta,
    CollectiveComparison,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/upload", response_model=ReceiptUploadResponse, status_code=202)
async def upload_receipt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str = Form("photo"),
    user_id: str = Depends(get_current_user),
):
    content = await file.read()
    error = validate_image(file.content_type or "", len(content), settings.MAX_IMAGE_SIZE_MB)
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Check plan scan limit
    db = get_service_client()
    profile_row = (
        db.table("profiles")
        .select("plan, plan_expires_at, scans_this_month, scans_month_reset")
        .eq("id", user_id)
        .single()
        .execute()
    )
    check_scan_limit(db, user_id, profile_row.data or {})

    # Compress if needed
    if file.content_type and file.content_type.startswith("image/") and len(content) > 2 * 1024 * 1024:
        content = compress_image(content)

    receipt_id = str(uuid.uuid4())
    ext = "pdf" if source == "pdf" else "jpg"
    storage_path = f"{user_id}/{receipt_id}.{ext}"

    # Upload to Supabase Storage
    db.storage.from_(settings.RECEIPT_IMAGES_BUCKET).upload(storage_path, content)
    image_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.RECEIPT_IMAGES_BUCKET}/{storage_path}"

    # Create receipt record
    db.table("receipts").insert({
        "id": receipt_id,
        "user_id": user_id,
        "store_name": "Processing...",
        "purchased_at": datetime.now(timezone.utc).isoformat(),
        "total_amount": 0,
        "image_url": image_url,
        "status": "processing",
        "source": source,
    }).execute()

    # Process in background
    background_tasks.add_task(process_receipt_async, receipt_id, user_id, content, image_url)

    return ReceiptUploadResponse(receipt_id=uuid.UUID(receipt_id))


async def process_receipt_async(
    receipt_id: str, user_id: str, image_bytes: bytes, image_url: str
) -> None:
    """Background task: OCR → extract → normalize → save → contribute prices."""
    from app.services.ocr_service import extract_text_from_image
    from app.services.extraction_service import extract_receipt_data
    from app.services.price_service import contribute_anonymous_price
    from app.services.embedding_service import store_item_embedding

    db = get_service_client()

    try:
        log.info(f"[{receipt_id}] Starting processing (user={user_id}, {len(image_bytes)} bytes)")

        # 0. LAYER 1 — Image hash duplicate check (before OCR to save tokens)
        img_hash = hashlib.sha256(image_bytes).hexdigest()
        existing_hash = (
            db.table("receipts")
            .select("id")
            .eq("user_id", user_id)
            .eq("image_hash", img_hash)
            .neq("id", receipt_id)
            .limit(1)
            .execute()
        )
        if existing_hash.data:
            log.warning(f"[{receipt_id}] Duplicate image hash detected")
            db.table("receipts").update({
                "status": "failed",
                "image_hash": img_hash,
                "error_reason": "Duplicate receipt — this photo has already been scanned.",
            }).eq("id", receipt_id).execute()
            return

        # Store the image hash
        db.table("receipts").update({
            "image_hash": img_hash,
        }).eq("id", receipt_id).execute()

        # 1. OCR — try direct text extraction for PDFs first
        source_row = db.table("receipts").select("source").eq("id", receipt_id).single().execute()
        receipt_source = source_row.data.get("source", "photo") if source_row.data else "photo"
        log.info(f"[{receipt_id}] Source: {receipt_source}")

        if receipt_source == "pdf":
            from app.utils.pdf_utils import extract_text_from_pdf
            direct_text = extract_text_from_pdf(image_bytes)
            if len(direct_text) > 100:
                log.info(f"[{receipt_id}] PDF — using direct text extraction (pdfplumber, {len(direct_text)} chars)")
                raw_text = direct_text
            else:
                log.info(f"[{receipt_id}] PDF — falling back to OCR (pdfplumber got {len(direct_text)} chars)")
                raw_text = await extract_text_from_image(image_bytes)
                log.info(f"[{receipt_id}] Gemini OCR done ({len(raw_text)} chars)")
        else:
            log.info(f"[{receipt_id}] Calling Gemini OCR...")
            raw_text = await extract_text_from_image(image_bytes)
            log.info(f"[{receipt_id}] Gemini OCR done ({len(raw_text)} chars)")

        # 1b. Check if it's actually a receipt from a supported store
        if raw_text.strip().upper().startswith("NOT_A_RECEIPT"):
            log.warning(f"[{receipt_id}] Image is not a valid grocery receipt")
            db.table("receipts").update({
                "status": "failed",
                "raw_text": "NOT_A_RECEIPT",
                "error_reason": (
                    "Not a supported Irish supermarket receipt. "
                    "Supported: Tesco, Lidl, Aldi, Dunnes, SuperValu."
                ),
            }).eq("id", receipt_id).execute()
            return

        # 2. Extract structured data
        log.info(f"[{receipt_id}] Calling OpenAI extraction...")
        data = await extract_receipt_data(raw_text)
        items = data.get("items", [])
        log.info(
            f"[{receipt_id}] Extraction done — store={data.get('store_name')}, "
            f"total={data.get('total_amount')}, items={len(items)}"
        )

        # 2b. LAYER 2 — Data fingerprint duplicate check
        purchased_at = data.get("purchased_at") or datetime.now(timezone.utc).isoformat()
        store_name = data.get("store_name", "Unknown")
        total_amount = data.get("total_amount", 0)

        fingerprint_str = (
            f"{store_name}"
            f"{str(purchased_at)[:10]}"
            f"{round(float(total_amount), 2)}"
        )
        data_hash = hashlib.sha256(fingerprint_str.encode()).hexdigest()

        thirty_days_ago = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat()
        existing_fp = (
            db.table("receipts")
            .select("id, store_name, purchased_at, total_amount")
            .eq("user_id", user_id)
            .eq("data_hash", data_hash)
            .eq("status", "done")
            .neq("id", receipt_id)
            .gte("purchased_at", thirty_days_ago)
            .limit(1)
            .execute()
        )
        if existing_fp.data:
            dup = existing_fp.data[0]
            dup_date = str(dup.get("purchased_at", ""))[:10]
            dup_total = dup.get("total_amount", 0)
            dup_store = dup.get("store_name", "Unknown")
            msg = (
                f"Duplicate receipt — a receipt from {dup_store} "
                f"on {dup_date} for €{dup_total:.2f} already exists."
            )
            log.warning(f"[{receipt_id}] {msg}")
            db.table("receipts").update({
                "status": "failed",
                "data_hash": data_hash,
                "raw_text": raw_text,
                "error_reason": msg,
            }).eq("id", receipt_id).execute()
            return

        # 2c. Check receipt age against plan limits
        if data.get("purchased_at"):
            try:
                from dateutil import parser as dateutil_parser

                receipt_dt = dateutil_parser.isoparse(purchased_at)
                if receipt_dt.tzinfo is None:
                    receipt_dt = receipt_dt.replace(tzinfo=timezone.utc)
                days_old = (datetime.now(timezone.utc) - receipt_dt).days

                profile_plan = (
                    db.table("profiles")
                    .select("plan, plan_expires_at")
                    .eq("id", user_id)
                    .single()
                    .execute()
                )
                user_is_pro = is_pro(profile_plan.data or {})

                max_days = 5 if user_is_pro else 2
                if days_old > max_days:
                    plan_label = "Pro" if user_is_pro else "Free"
                    upgrade_hint = (
                        " Upgrade to Pro for up to 5 days."
                        if not user_is_pro
                        else ""
                    )
                    msg = (
                        f"Receipt too old ({days_old} days). "
                        f"{plan_label} plan accepts receipts up to "
                        f"{max_days} days old.{upgrade_hint}"
                    )
                    log.warning(f"[{receipt_id}] {msg}")
                    db.table("receipts").update({
                        "status": "failed",
                        "raw_text": raw_text,
                        "error_reason": msg,
                    }).eq("id", receipt_id).execute()
                    return
            except (ValueError, TypeError):
                pass  # Could not parse date — accept the receipt

        # 3. Update receipt
        db.table("receipts").update({
            "store_name": store_name,
            "store_branch": data.get("store_branch"),
            "purchased_at": purchased_at,
            "total_amount": total_amount,
            "subtotal": data.get("subtotal"),
            "discount_total": data.get("discount_total", 0),
            "raw_text": raw_text,
            "data_hash": data_hash,
            "status": "done",
        }).eq("id", receipt_id).execute()
        log.info(f"[{receipt_id}] Receipt record updated (status=done)")

        # 4. Insert items
        profile = db.table("profiles").select("home_area").eq("id", user_id).single().execute()
        home_area = profile.data.get("home_area") if profile.data else None

        for idx, item in enumerate(items):
            item_id = str(uuid.uuid4())
            db.table("receipt_items").insert({
                "id": item_id,
                "receipt_id": receipt_id,
                "user_id": user_id,
                "raw_name": item.get("raw_name", ""),
                "normalized_name": item.get("normalized_name", item.get("raw_name", "")),
                "category": item.get("category", "Other"),
                "brand": item.get("brand"),
                "quantity": item.get("quantity", 1),
                "unit": item.get("unit"),
                "unit_price": item.get("unit_price", 0),
                "total_price": item.get("total_price", 0),
                "discount_amount": item.get("discount_amount", 0),
                "is_on_offer": item.get("is_on_offer", False),
                "barcode": item.get("barcode"),
            }).execute()

            # 5. Contribute to collective prices (anonymous)
            try:
                await contribute_anonymous_price(
                    db, item,
                    store_name=data.get("store_name", "Unknown"),
                    store_branch=data.get("store_branch"),
                    home_area=home_area,
                    observed_at=datetime.fromisoformat(purchased_at) if isinstance(purchased_at, str) else purchased_at,
                )
            except Exception as price_err:
                log.warning(f"[{receipt_id}] Failed to contribute price for item {idx}: {price_err}")

            # 6. Generate embedding for RAG
            embed_text = f"{item.get('normalized_name', '')} {item.get('category', '')} {item.get('brand', '')}"
            try:
                await store_item_embedding(item_id, embed_text)
            except Exception:
                pass  # Non-critical

        # 7. Increment scan counter and award points
        try:
            increment_scan_count(db, user_id)
            profile_pts = (
                db.table("profiles")
                .select("points, plan, plan_expires_at")
                .eq("id", user_id)
                .single()
                .execute()
            )
            pts_data = profile_pts.data or {}
            current_pts = pts_data.get("points") or 0
            award = 25 if is_pro(pts_data) else 10
            db.table("profiles").update(
                {"points": current_pts + award}
            ).eq("id", user_id).execute()
            log.info(f"[{receipt_id}] Awarded {award} points (total: {current_pts + award})")
        except Exception as pts_err:
            log.warning(f"[{receipt_id}] Failed to award points: {pts_err}")

        # 8. Check savings attribution (alert → purchase matching)
        try:
            from app.services.attribution_service import check_attribution

            attributions = await check_attribution(db, user_id, receipt_id)
            if attributions:
                total_saving = sum(a["saving"] for a in attributions)
                log.info(
                    f"[{receipt_id}] Savings attributed: "
                    f"{len(attributions)} items, €{total_saving:.2f}"
                )
        except Exception as attr_err:
            log.warning(f"[{receipt_id}] Attribution check failed: {attr_err}")

        # 9. Record shopping analytics
        try:
            from app.services.price_service import record_shopping_analytics

            purchased_at_dt = (
                datetime.fromisoformat(purchased_at)
                if isinstance(purchased_at, str)
                else purchased_at
            )
            await record_shopping_analytics(
                db=db,
                receipt_id=receipt_id,
                user_id=user_id,
                store_name=store_name,
                purchased_at=purchased_at_dt,
                total_amount=float(total_amount),
                items_count=len(items),
            )
        except Exception as analytics_err:
            log.warning(f"[{receipt_id}] Analytics recording failed: {analytics_err}")

        log.info(f"[{receipt_id}] Processing complete — {len(items)} items saved")

    except Exception as e:
        log.error(f"[{receipt_id}] FAILED: {e}\n{traceback.format_exc()}")
        try:
            db.table("receipts").update({"status": "failed"}).eq("id", receipt_id).execute()
        except Exception as db_err:
            log.error(f"[{receipt_id}] Could not update status to failed: {db_err}")


@router.get("", response_model=ReceiptListResponse)
async def list_receipts(
    page: int = 1,
    per_page: int = 20,
    store: str | None = None,
    month: str | None = None,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()

    # Check plan for history limit
    profile_row = (
        db.table("profiles")
        .select("plan, plan_expires_at")
        .eq("id", user_id)
        .single()
        .execute()
    )
    user_is_pro = is_pro(profile_row.data or {})
    plan_limit_header = None

    query = (
        db.table("receipts")
        .select("*, receipt_items(count)", count="exact")
        .eq("user_id", user_id)
        .order("purchased_at", desc=True)
    )

    # Free users: last 30 days only
    if not user_is_pro:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        query = query.gte("purchased_at", cutoff)
        plan_limit_header = "history-30-days"

    if store:
        query = query.eq("store_name", store)
    if month:
        query = query.gte("purchased_at", f"{month}-01T00:00:00").lt(
            "purchased_at", f"{month}-31T23:59:59"
        )

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)
    result = query.execute()

    total = result.count or 0
    receipts = []
    for r in result.data or []:
        items_count = 0
        if "receipt_items" in r and r["receipt_items"]:
            items_count = r["receipt_items"][0].get("count", 0) if isinstance(r["receipt_items"], list) else 0
        receipts.append(ReceiptResponse(
            id=r["id"],
            user_id=r["user_id"],
            store_name=r["store_name"],
            store_branch=r.get("store_branch"),
            store_address=r.get("store_address"),
            purchased_at=r["purchased_at"],
            total_amount=r["total_amount"],
            subtotal=r.get("subtotal"),
            discount_total=r.get("discount_total", 0),
            image_url=r.get("image_url"),
            status=r.get("status", "done"),
            source=r.get("source", "photo"),
            items_count=items_count,
            error_reason=r.get("error_reason"),
            created_at=r["created_at"],
        ))

    response_data = ReceiptListResponse(
        data=receipts,
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=math.ceil(total / per_page) if per_page > 0 else 0,
        ),
    )

    if plan_limit_header:
        return JSONResponse(
            content=response_data.model_dump(mode="json"),
            headers={"X-Plan-Limit": plan_limit_header},
        )
    return response_data


@router.get("/{receipt_id}", response_model=ReceiptDetailResponse)
async def get_receipt_detail(
    receipt_id: str,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    receipt = (
        db.table("receipts")
        .select("*")
        .eq("id", receipt_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not receipt.data:
        raise HTTPException(status_code=404, detail="Receipt not found")

    r = receipt.data
    items_resp = (
        db.table("receipt_items")
        .select("*")
        .eq("receipt_id", receipt_id)
        .execute()
    )

    items = []
    for item in items_resp.data or []:
        # Get collective comparison
        collective = None
        product_key = generate_product_key(item["normalized_name"], item.get("unit"))
        best = (
            db.table("collective_prices")
            .select("store_name, unit_price")
            .eq("product_key", product_key)
            .gte("expires_at", datetime.now(timezone.utc).isoformat())
            .order("unit_price")
            .limit(1)
            .execute()
        )
        if best.data and best.data[0]["store_name"] != r["store_name"]:
            diff = best.data[0]["unit_price"] - item["unit_price"]
            collective = CollectiveComparison(
                cheapest_store=best.data[0]["store_name"],
                cheapest_price=best.data[0]["unit_price"],
                difference=round(diff, 2),
            )

        items.append(ReceiptItemResponse(
            id=item["id"],
            receipt_id=item["receipt_id"],
            raw_name=item["raw_name"],
            normalized_name=item["normalized_name"],
            category=item["category"],
            brand=item.get("brand"),
            quantity=item.get("quantity", 1),
            unit=item.get("unit"),
            unit_price=item["unit_price"],
            total_price=item["total_price"],
            discount_amount=item.get("discount_amount", 0),
            is_on_offer=item.get("is_on_offer", False),
            barcode=item.get("barcode"),
            collective_price=collective,
        ))

    return ReceiptDetailResponse(
        id=r["id"],
        user_id=r["user_id"],
        store_name=r["store_name"],
        store_branch=r.get("store_branch"),
        store_address=r.get("store_address"),
        purchased_at=r["purchased_at"],
        total_amount=r["total_amount"],
        subtotal=r.get("subtotal"),
        discount_total=r.get("discount_total", 0),
        image_url=r.get("image_url"),
        status=r.get("status", "done"),
        source=r.get("source", "photo"),
        items=items,
        raw_text=r.get("raw_text"),
        created_at=r["created_at"],
    )


@router.get("/{receipt_id}/status", response_model=ReceiptStatusResponse)
async def get_receipt_status(
    receipt_id: str,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    result = (
        db.table("receipts")
        .select("id, status, error_reason")
        .eq("id", receipt_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Receipt not found")

    status = result.data["status"]
    progress_map = {"pending": 10, "processing": 50, "done": 100, "failed": 0}
    message_map = {
        "pending": "Waiting to process...",
        "processing": "Extracting products...",
        "done": "Receipt processed successfully!",
        "failed": "Processing failed. Please try again.",
    }

    # Use specific error_reason if available for failed receipts
    message = message_map.get(status, "")
    if status == "failed" and result.data.get("error_reason"):
        message = result.data["error_reason"]

    return ReceiptStatusResponse(
        receipt_id=result.data["id"],
        status=status,
        progress=progress_map.get(status, 0),
        message=message,
    )


@router.delete("/{receipt_id}", status_code=204)
async def delete_receipt(
    receipt_id: str,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    result = (
        db.table("receipts")
        .select("id")
        .eq("id", receipt_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Receipt not found")

    db.table("receipt_items").delete().eq("receipt_id", receipt_id).execute()
    db.table("receipts").delete().eq("id", receipt_id).execute()
