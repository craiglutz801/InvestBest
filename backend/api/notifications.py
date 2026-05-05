"""REST API for notifications: list log, send test, future: preferences."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_session
from backend.models import NotificationLog
from backend.services.notifications import NotificationService

router = APIRouter()


class NotificationOut(BaseModel):
    id: int
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    status: str
    created_at: str

    class Config:
        from_attributes = True


class SendTestRequest(BaseModel):
    channel: str  # email, slack, telegram
    message: str = "InvestBest test notification"


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    session: AsyncSession = Depends(get_session),
    channel: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    q = select(NotificationLog).order_by(NotificationLog.id.desc()).limit(limit)
    if channel:
        q = q.where(NotificationLog.channel == channel)
    result = await session.execute(q)
    rows = result.scalars().all()
    return [
        NotificationOut(
            id=r.id,
            channel=r.channel,
            subject=r.subject,
            body=r.body,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.post("/send-test")
async def send_test(body: SendTestRequest, session: AsyncSession = Depends(get_session)):
    """Send a test notification to the given channel."""
    service = NotificationService(session)
    ok, error = await service.send_test(body.channel, body.message)
    if not ok:
        return {"success": False, "error": error}
    return {"success": True}
