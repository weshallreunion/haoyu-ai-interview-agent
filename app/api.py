import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from agents import Runner, SQLiteSession
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import (
    FileResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from openai.types.responses import (
    ResponseTextDeltaEvent,
)
from pydantic import BaseModel, Field

from app.admin_api import router as admin_router
from app.agent import haoyu_agent
from app.chat_store import (
    FeedbackRating,
    StoredMessage,
    append_message,
    append_messages,
    clear_messages,
    get_messages,
    save_feedback,
)
from app.request_guard import (
    RateLimitDecision,
    SessionBusyError,
    request_limiter,
    session_concurrency_guard,
)


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

AGENT_DATABASE_PATH = (
    DATA_DIR / "conversations.db"
)

SESSION_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{1,64}$"
)


TOOL_SOURCE_LABELS = {
    "get_verified_profile":
        "已确认个人资料",

    "get_all_verified_projects":
        "全部项目资料",

    "search_verified_projects":
        "已确认项目资料",

    "get_verified_persona":
        "本人确认的表达资料",
}


DATA_DIR.mkdir(exist_ok=True)


app = FastAPI(
    title="Haoyu AI Interview Agent API",
    description=(
        "Backend API for the Haoyu AI "
        "interview assistant."
    ),
    version="1.0.0",
)

app.include_router(admin_router)

app.mount(
    "/static",
    StaticFiles(
        directory=str(FRONTEND_DIR)
    ),
    name="static",
)


class ChatRequest(BaseModel):
    """招聘者发送的聊天请求。"""

    session_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    message: str = Field(
        min_length=1,
        max_length=1000,
    )


class ChatResponse(BaseModel):
    """普通聊天接口返回的数据。"""

    session_id: str
    message_id: int
    answer: str

    sources: list[str] = Field(
        default_factory=list
    )


class HistoryMessage(BaseModel):
    """前端可以显示的一条历史消息。"""

    message_id: int

    role: Literal[
        "user",
        "assistant",
    ]

    content: str

    sources: list[str] = Field(
        default_factory=list
    )

    feedback: FeedbackRating | None = None


class HistoryResponse(BaseModel):
    """指定会话的历史记录。"""

    session_id: str
    messages: list[HistoryMessage]


class FeedbackRequest(BaseModel):
    """招聘者提交的回答反馈。"""

    session_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    message_id: int = Field(
        gt=0
    )

    rating: FeedbackRating


class FeedbackResponse(BaseModel):
    """反馈保存结果。"""

    message_id: int
    rating: FeedbackRating
    saved: bool


def validate_session_id(
    session_id: str,
) -> None:
    """校验浏览器传入的会话编号。"""

    if not SESSION_ID_PATTERN.fullmatch(
        session_id
    ):
        raise HTTPException(
            status_code=422,
            detail="Invalid session ID.",
        )


def create_session(
    session_id: str,
) -> SQLiteSession:
    """创建或恢复指定的Agent会话。"""

    return SQLiteSession(
        session_id,
        str(AGENT_DATABASE_PATH),
    )


def get_client_ip(
    request: Request,
) -> str:
    """读取访问者IP，优先使用Railway传递的真实IP。"""

    railway_real_ip = request.headers.get(
        "x-real-ip"
    )

    if railway_real_ip:
        return railway_real_ip.strip()

    if request.client is not None:
        return (
            request.client.host
            or "unknown"
        )

    return "unknown"


async def acquire_session_or_raise(
    session_id: str,
) -> None:
    """占用会话，已有请求运行时返回409。"""

    try:
        await session_concurrency_guard.acquire(
            session_id
        )

    except SessionBusyError as error:
        raise HTTPException(
            status_code=409,
            detail=(
                "当前会话已有回答正在生成，"
                "请等待完成后再发送。"
            ),
        ) from error


async def enforce_request_limit(
    request: Request,
    session_id: str,
) -> RateLimitDecision:
    """检查IP和会话请求频率。"""

    client_ip = get_client_ip(request)

    decision = await request_limiter.check(
        ip_address=client_ip,
        session_id=session_id,
    )

    print(
        "[RATE LIMIT CHECK] "
        f"ip={client_ip}, "
        f"session={session_id}, "
        f"allowed={decision.allowed}, "
        f"remaining={decision.remaining}, "
        f"scope={decision.scope}, "
        f"retry_after={decision.retry_after}"
    )

    if decision.allowed:
        return decision

    if decision.scope == "ip":
        detail = (
            "当前访问频率过高，"
            f"请在 {decision.retry_after} 秒后重试。"
        )
    else:
        detail = (
            "当前会话请求次数已达到限制，"
            f"请在 {decision.retry_after} 秒后重试。"
        )

    raise HTTPException(
        status_code=429,
        detail=detail,
        headers={
            "Retry-After": str(
                decision.retry_after
            ),
            "X-RateLimit-Scope":
                decision.scope,
        },
    )


def encode_stream_event(
    event_type: str,
    **payload: Any,
) -> str:
    """把一个流事件转换成一行JSON。"""

    event_data = {
        "type": event_type,
        **payload,
    }

    return (
        json.dumps(
            event_data,
            ensure_ascii=False,
        )
        + "\n"
    )


def extract_tool_name(
    item: Any,
) -> str | None:
    """兼容不同对象结构并提取工具名称。"""

    direct_tool_name = getattr(
        item,
        "tool_name",
        None,
    )

    if isinstance(
        direct_tool_name,
        str,
    ):
        normalized_name = (
            direct_tool_name.strip()
        )

        if normalized_name:
            return normalized_name

    raw_item = getattr(
        item,
        "raw_item",
        None,
    )

    if isinstance(raw_item, dict):
        raw_name = (
            raw_item.get("name")
            or raw_item.get("tool_name")
        )

        if isinstance(raw_name, str):
            normalized_name = (
                raw_name.strip()
            )

            if normalized_name:
                return normalized_name

        return None

    raw_name = (
        getattr(raw_item, "name", None)
        or getattr(
            raw_item,
            "tool_name",
            None,
        )
    )

    if isinstance(raw_name, str):
        normalized_name = raw_name.strip()

        if normalized_name:
            return normalized_name

    return None


def register_source(
    item: Any,
    used_sources: list[str],
) -> str | None:
    """根据工具调用注册回答依据。"""

    tool_name = extract_tool_name(item)

    if not tool_name:
        return None

    source_label = TOOL_SOURCE_LABELS.get(
        tool_name
    )

    if not source_label:
        return None

    if source_label in used_sources:
        return None

    used_sources.append(source_label)

    print(
        "[SOURCE DETECTED] "
        f"tool={tool_name}, "
        f"label={source_label}"
    )

    return source_label


def collect_sources_from_items(
    items: list[Any],
) -> list[str]:
    """从一次运行产生的项目中收集来源。"""

    used_sources: list[str] = []

    for item in items:
        register_source(
            item,
            used_sources,
        )

    return used_sources


def extract_message_text(
    content: Any,
) -> str:
    """从Agent Session消息中提取网页文本。"""

    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []

    for part in content:
        if isinstance(part, str):
            text_parts.append(part)
            continue

        if isinstance(part, dict):
            text = part.get("text")

            if isinstance(text, str):
                text_parts.append(text)

            continue

        text = getattr(
            part,
            "text",
            None,
        )

        if isinstance(text, str):
            text_parts.append(text)

    return "".join(text_parts).strip()


def convert_legacy_items(
    items: list[Any],
) -> list[StoredMessage]:
    """把旧Agent会话转换为网页聊天记录。"""

    messages: list[StoredMessage] = []

    for raw_item in items:
        item = raw_item

        if not isinstance(item, dict):
            model_dump = getattr(
                item,
                "model_dump",
                None,
            )

            if callable(model_dump):
                item = model_dump()

        if not isinstance(item, dict):
            continue

        role = item.get("role")

        if role not in {
            "user",
            "assistant",
        }:
            continue

        content = extract_message_text(
            item.get("content")
        )

        if not content:
            continue

        messages.append(
            {
                "message_id": 0,
                "role": role,
                "content": content,
                "sources": [],
                "feedback": None,
            }
        )

    return messages


@app.get(
    "/",
    include_in_schema=False,
)
async def index_page() -> FileResponse:
    """返回聊天网页首页。"""

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )

@app.get(
    "/admin",
    include_in_schema=False,
)
async def admin_page() -> FileResponse:
    """返回管理员反馈后台。"""

    return FileResponse(
        FRONTEND_DIR / "admin.html"
    )

@app.get("/health")
async def health_check() -> dict[str, str]:
    """检查后端服务是否正常。"""

    return {
        "status": "ok",
        "service":
            "haoyu-ai-interview-agent",
    }


@app.get(
    "/chat/history/{session_id}",
    response_model=HistoryResponse,
)
async def get_chat_history(
    session_id: str,
) -> HistoryResponse:
    """读取消息、回答依据和反馈状态。"""

    validate_session_id(session_id)

    try:
        stored_messages = (
            await asyncio.to_thread(
                get_messages,
                session_id,
            )
        )

    except Exception as error:
        print(
            "[CHAT STORE ERROR] "
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load "
                "chat history."
            ),
        ) from error

    if not stored_messages:
        session = create_session(
            session_id
        )

        try:
            session_items = (
                await session.get_items()
            )

            legacy_messages = (
                convert_legacy_items(
                    session_items
                )
            )

            if legacy_messages:
                await asyncio.to_thread(
                    append_messages,
                    session_id,
                    legacy_messages,
                )

                stored_messages = (
                    await asyncio.to_thread(
                        get_messages,
                        session_id,
                    )
                )

        except Exception as error:
            print(
                "[LEGACY HISTORY ERROR] "
                f"{type(error).__name__}: "
                f"{error}"
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Unable to load "
                    "chat history."
                ),
            ) from error

    return HistoryResponse(
        session_id=session_id,
        messages=[
            HistoryMessage(
                message_id=message[
                    "message_id"
                ],
                role=message["role"],
                content=message["content"],
                sources=message["sources"],
                feedback=message["feedback"],
            )
            for message in stored_messages
        ],
    )


@app.delete(
    "/chat/history/{session_id}",
    status_code=204,
)
async def clear_chat_history(
    session_id: str,
) -> Response:
    """同时清空Agent上下文、消息和反馈。"""

    validate_session_id(session_id)

    await acquire_session_or_raise(
        session_id
    )

    session = create_session(
        session_id
    )

    try:
        await session.clear_session()

        await asyncio.to_thread(
            clear_messages,
            session_id,
        )

    except Exception as error:
        print(
            "[CLEAR HISTORY ERROR] "
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to clear "
                "chat history."
            ),
        ) from error

    finally:
        await session_concurrency_guard.release(
            session_id
        )

    return Response(status_code=204)


@app.post(
    "/chat/feedback",
    response_model=FeedbackResponse,
)
async def submit_feedback(
    payload: FeedbackRequest,
) -> FeedbackResponse:
    """保存或更新招聘者对助手回答的反馈。"""

    validate_session_id(
        payload.session_id
    )

    try:
        saved = await asyncio.to_thread(
            save_feedback,
            payload.session_id,
            payload.message_id,
            payload.rating,
            None,
        )

    except Exception as error:
        print(
            "[FEEDBACK ERROR] "
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail="无法保存反馈。",
        ) from error

    if not saved:
        raise HTTPException(
            status_code=404,
            detail=(
                "没有找到对应的助手回答，"
                "或者该消息不允许评价。"
            ),
        )

    print(
        "[FEEDBACK SAVED] "
        f"session={payload.session_id}, "
        f"message_id={payload.message_id}, "
        f"rating={payload.rating}"
    )

    return FeedbackResponse(
        message_id=payload.message_id,
        rating=payload.rating,
        saved=True,
    )


@app.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    payload: ChatRequest,
    request: Request,
    response: Response,
) -> ChatResponse:
    """一次性返回完整回答，用于Swagger调试。"""

    await acquire_session_or_raise(
        payload.session_id
    )

    try:
        rate_decision = (
            await enforce_request_limit(
                request,
                payload.session_id,
            )
        )

        response.headers[
            "X-RateLimit-Remaining"
        ] = str(rate_decision.remaining)

        session = create_session(
            payload.session_id
        )

        await asyncio.to_thread(
            append_message,
            payload.session_id,
            "user",
            payload.message,
            [],
        )

        result = await Runner.run(
            haoyu_agent,
            payload.message,
            session=session,
            max_turns=5,
        )

        answer = str(
            result.final_output or ""
        ).strip()

        if not answer:
            answer = (
                "没有收到有效回答，"
                "请重新尝试。"
            )

        sources = (
            collect_sources_from_items(
                result.new_items
            )
        )

        assistant_message_id = (
            await asyncio.to_thread(
                append_message,
                payload.session_id,
                "assistant",
                answer,
                sources,
            )
        )

        print(
            "[SOURCE SAVE] "
            f"session={payload.session_id}, "
            f"sources={sources}"
        )

        return ChatResponse(
            session_id=payload.session_id,
            message_id=assistant_message_id,
            answer=answer,
            sources=sources,
        )

    except HTTPException:
        raise

    except Exception as error:
        print(
            "[API ERROR] "
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Agent service is "
                "temporarily unavailable."
            ),
        ) from error

    finally:
        await session_concurrency_guard.release(
            payload.session_id
        )


@app.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
) -> StreamingResponse:
    """流式回答并持久化消息、来源和反馈编号。"""

    await acquire_session_or_raise(
        payload.session_id
    )

    try:
        rate_decision = (
            await enforce_request_limit(
                request,
                payload.session_id,
            )
        )

        session = create_session(
            payload.session_id
        )

        await asyncio.to_thread(
            append_message,
            payload.session_id,
            "user",
            payload.message,
            [],
        )

    except HTTPException:
        await session_concurrency_guard.release(
            payload.session_id
        )
        raise

    except Exception as error:
        await session_concurrency_guard.release(
            payload.session_id
        )

        print(
            "[SAVE USER MESSAGE ERROR] "
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save "
                "user message."
            ),
        ) from error

    async def generate_events() -> AsyncIterator[str]:
        used_sources: list[str] = []
        full_answer = ""
        assistant_saved = False

        try:
            result = Runner.run_streamed(
                haoyu_agent,
                payload.message,
                session=session,
                max_turns=5,
            )

            async for event in (
                result.stream_events()
            ):
                is_tool_call = (
                    event.type
                    == "run_item_stream_event"
                    and event.name
                    == "tool_called"
                )

                if is_tool_call:
                    source_label = (
                        register_source(
                            event.item,
                            used_sources,
                        )
                    )

                    if source_label:
                        yield encode_stream_event(
                            "source",
                            label=source_label,
                        )

                    continue

                is_text_delta = (
                    event.type
                    == "raw_response_event"
                    and isinstance(
                        event.data,
                        ResponseTextDeltaEvent,
                    )
                )

                if is_text_delta:
                    text_delta = (
                        event.data.delta or ""
                    )

                    full_answer += text_delta

                    yield encode_stream_event(
                        "text",
                        delta=text_delta,
                    )

            for run_item in result.new_items:
                source_label = register_source(
                    run_item,
                    used_sources,
                )

                if source_label:
                    yield encode_stream_event(
                        "source",
                        label=source_label,
                    )

            final_output = str(
                result.final_output or ""
            ).strip()

            stored_answer = (
                final_output
                or full_answer.strip()
                or (
                    "没有收到有效回答，"
                    "请重新尝试。"
                )
            )

            assistant_message_id = (
                await asyncio.to_thread(
                    append_message,
                    payload.session_id,
                    "assistant",
                    stored_answer,
                    used_sources,
                )
            )

            assistant_saved = True

            print(
                "[SOURCE SAVE] "
                f"session={payload.session_id}, "
                f"message_id="
                f"{assistant_message_id}, "
                f"sources={used_sources}"
            )

            yield encode_stream_event(
                "done",
                sources=used_sources,
                message_id=(
                    assistant_message_id
                ),
            )

        except Exception as error:
            print(
                "[STREAM ERROR] "
                f"{type(error).__name__}: "
                f"{error}"
            )

            error_message = (
                "服务暂时不可用，"
                "请稍后重新尝试。"
            )

            if full_answer.strip():
                stored_answer = (
                    full_answer
                    + "\n\n> 回答传输中断："
                    + error_message
                )
            else:
                stored_answer = error_message

            if not assistant_saved:
                try:
                    await asyncio.to_thread(
                        append_message,
                        payload.session_id,
                        "assistant",
                        stored_answer,
                        used_sources,
                    )

                except Exception as save_error:
                    print(
                        "[SAVE ASSISTANT ERROR] "
                        f"{type(save_error).__name__}: "
                        f"{save_error}"
                    )

            yield encode_stream_event(
                "error",
                message=error_message,
            )

        finally:
            await session_concurrency_guard.release(
                payload.session_id
            )

    return StreamingResponse(
        generate_events(),
        media_type=(
            "application/x-ndjson; "
            "charset=utf-8"
        ),
        headers={
            "Cache-Control":
                "no-cache, no-store",

            "X-Accel-Buffering":
                "no",

            "X-Content-Type-Options":
                "nosniff",

            "X-RateLimit-Remaining":
                str(rate_decision.remaining),
        },
    )