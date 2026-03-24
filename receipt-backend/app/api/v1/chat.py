import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.utils.auth_utils import get_current_user
from app.database import get_service_client
from app.services.chat_service import chat_stream
from app.models.chat import ChatMessageRequest, ChatSessionsResponse, ChatSession

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message")
async def send_message(
    body: ChatMessageRequest,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    session_id = str(body.session_id) if body.session_id else str(uuid.uuid4())

    # Load history
    history_resp = (
        db.table("chat_messages")
        .select("role, content")
        .eq("user_id", user_id)
        .eq("session_id", session_id)
        .order("created_at")
        .limit(10)
        .execute()
    )
    history = [{"role": m["role"], "content": m["content"]} for m in (history_resp.data or [])]

    # Save user message
    db.table("chat_messages").insert({
        "user_id": user_id,
        "session_id": session_id,
        "role": "user",
        "content": body.message,
    }).execute()

    async def event_generator():
        yield f'data: {json.dumps({"type": "session_id", "value": session_id})}\n\n'

        full_response = ""
        async for token in chat_stream(user_id, body.message, session_id, history):
            full_response += token
            yield f'data: {json.dumps({"type": "token", "value": token})}\n\n'

        # Save assistant response
        db.table("chat_messages").insert({
            "user_id": user_id,
            "session_id": session_id,
            "role": "assistant",
            "content": full_response,
        }).execute()

        yield f'data: {json.dumps({"type": "done", "context": {}})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/sessions", response_model=ChatSessionsResponse)
async def list_sessions(user_id: str = Depends(get_current_user)):
    db = get_service_client()

    # Get distinct sessions with latest message
    messages = (
        db.table("chat_messages")
        .select("session_id, content, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    sessions_map: dict[str, dict] = {}
    for m in messages.data or []:
        sid = m["session_id"]
        if sid not in sessions_map:
            sessions_map[sid] = {
                "session_id": sid,
                "last_message": m["content"],
                "messages_count": 0,
                "created_at": m["created_at"],
                "updated_at": m["created_at"],
            }
        sessions_map[sid]["messages_count"] += 1
        if m["created_at"] < sessions_map[sid]["created_at"]:
            sessions_map[sid]["created_at"] = m["created_at"]

    sessions = [ChatSession(**s) for s in sessions_map.values()]
    sessions.sort(key=lambda x: x.updated_at, reverse=True)
    return ChatSessionsResponse(sessions=sessions[:20])


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    db.table("chat_messages").delete().eq("user_id", user_id).eq("session_id", session_id).execute()
