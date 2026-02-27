from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Deal, ChatMessage
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse
from app.services.claude_ai import stream_chat_response

router = APIRouter(prefix="/api/v1/deals", tags=["chat"])


@router.post("/{deal_id}/chat", response_class=StreamingResponse)
async def stream_deal_chat(
    deal_id: str,
    message_create: ChatMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Stream chat response for a deal.

    Returns Server-Sent Events (SSE) stream of chat response.
    """
    fund_id = request.state.fund_id

    # Verify deal exists and belongs to fund
    deal = (
        db.query(Deal)
        .filter(Deal.id == deal_id, Deal.fund_id == fund_id)
        .first()
    )

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Save user message
    user_message = ChatMessage(
        deal_id=deal_id,
        fund_id=fund_id,
        role="user",
        content=message_create.message,
    )
    db.add(user_message)
    db.commit()

    # Get conversation history (last 10 messages for context)
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.deal_id == deal_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(10)
        .all()
    )

    conversation_history = [
        (msg.role, msg.content)
        for msg in history
        if msg.id != user_message.id  # Exclude the message we just added
    ]

    async def generate():
        """Generator function for SSE streaming."""
        full_response = ""

        try:
            async for chunk in stream_chat_response(
                deal=deal,
                user_message=message_create.message,
                conversation_history=conversation_history,
            ):
                full_response += chunk
                # Stream each chunk as SSE
                yield f"data: {chunk}\n\n"

            # Save assistant response to database
            assistant_message = ChatMessage(
                deal_id=deal_id,
                fund_id=fund_id,
                role="assistant",
                content=full_response,
            )
            db.add(assistant_message)
            db.commit()

        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

        # Send completion signal
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{deal_id}/chat", response_model=List[ChatMessageResponse])
async def get_chat_history(
    deal_id: str,
    request: Request,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """Get chat history for a deal."""
    fund_id = request.state.fund_id

    # Verify deal exists and belongs to fund
    deal = (
        db.query(Deal)
        .filter(Deal.id == deal_id, Deal.fund_id == fund_id)
        .first()
    )

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.deal_id == deal_id, ChatMessage.fund_id == fund_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [ChatMessageResponse.model_validate(msg) for msg in messages]
