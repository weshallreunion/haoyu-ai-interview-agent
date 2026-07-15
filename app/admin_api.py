import asyncio
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field

from app.admin_auth import (
    admin_token_is_configured,
    verify_admin_authorization,
)
from app.feedback_analytics import (
    get_feedback_summary,
    get_recent_feedback,
)


router = APIRouter(
    prefix="/admin/api",
    tags=["admin"],
)


class FeedbackSummaryResponse(BaseModel):
    """反馈总体统计。"""

    total: int
    up_count: int
    down_count: int
    satisfaction_rate: float


class FeedbackRecordResponse(BaseModel):
    """后台显示的一条反馈记录。"""

    message_id: int
    session_id: str
    question: str
    answer: str

    rating: Literal[
        "up",
        "down",
    ]

    comment: str | None = None

    sources: list[str] = Field(
        default_factory=list
    )

    created_at: str
    updated_at: str


async def require_admin(
    authorization: Annotated[
        str | None,
        Header(),
    ] = None,
) -> None:
    """要求请求携带有效管理员密钥。"""

    if not admin_token_is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "管理员后台尚未配置。"
                "请设置 ADMIN_API_TOKEN。"
            ),
        )

    if not verify_admin_authorization(
        authorization
    ):
        raise HTTPException(
            status_code=401,
            detail="管理员密钥无效。",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )


@router.get(
    "/feedback/summary",
    response_model=FeedbackSummaryResponse,
)
async def feedback_summary(
    _: None = Depends(require_admin),
) -> FeedbackSummaryResponse:
    """返回反馈总体统计。"""

    summary = await asyncio.to_thread(
        get_feedback_summary
    )

    return FeedbackSummaryResponse(
        **summary
    )


@router.get(
    "/feedback/recent",
    response_model=list[
        FeedbackRecordResponse
    ],
)
async def recent_feedback(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    rating: Literal[
        "up",
        "down",
    ]
    | None = Query(default=None),
    _: None = Depends(require_admin),
) -> list[FeedbackRecordResponse]:
    """返回最近的反馈问答。"""

    records = await asyncio.to_thread(
        get_recent_feedback,
        limit,
        rating,
    )

    return [
        FeedbackRecordResponse(
            **record
        )
        for record in records
    ]