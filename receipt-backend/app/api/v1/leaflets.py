from fastapi import APIRouter, HTTPException, Header
from app.database import get_service_client
from app.config import settings

router = APIRouter(prefix="/leaflets", tags=["leaflets"])


@router.post("/trigger-fetch", status_code=202)
async def trigger_fetch(x_admin_key: str = Header(...)):
    if x_admin_key != settings.SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    from app.services.leaflet_service import fetch_and_process_leaflets
    import asyncio

    db = get_service_client()
    asyncio.create_task(fetch_and_process_leaflets(db))

    return {
        "message": "Leaflet fetch triggered",
        "stores": ["Lidl", "Aldi", "SuperValu"],
    }


@router.get("/status")
async def get_leaflet_status():
    db = get_service_client()
    result = (
        db.table("leaflets")
        .select("*")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return {"leaflets": result.data or []}
