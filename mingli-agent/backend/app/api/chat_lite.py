"""
轻量级 AI 对话路由 - 无数据库依赖
直接接收 bazi 分析数据，调用 AI 生成报告，SSE 流式返回
新增：支持 job_id 的异步任务，断线后可重连拉取结果
"""
import asyncio
import logging
from typing import Annotated, Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.entitlement_service import consume_usage
from app.services.ai_service import generate_ai_response
from app.services.prompt_builder import build_commercial_prompt
from app.services.skill_prompts import validate_user_question
from app.services.feedback_service import save_feedback as fb_save
from app.services.format_normalizer import normalize_output
from app.services.job_store import create_job, get_job, run_job, stream_job_result

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat-lite"])


class AnalyzeStreamRequest(BaseModel):
    """前端发送的分析请求"""
    birth_date: str
    birth_time: str
    longitude: float = 116.4
    latitude: float = 39.9
    gender: str = "男"
    location: str = ""
    bazi_data: Any = {}  # orchestrator 的完整分析结果
    is_first_reading: bool = True
    question: str = ""  # 追问内容，首次为空
    history: list = []  # 历史对话 [{"role": "user/assistant", "content": "..."}]


class ValidateRequest(BaseModel):
    question: str


@router.post("/validate-question")
async def validate_question(request: ValidateRequest):
    """
    验证用户问题是否有效（不扣除积分）
    前端在扣积分前调用此接口，验证通过后再发送正式请求
    """
    is_valid, message = validate_user_question(request.question)
    return {"valid": is_valid, "message": message}


@router.post("/analyze-stream")
async def analyze_stream(
    request: AnalyzeStreamRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    无状态的 AI 报告生成端点
    - 首次解读：用 build_commercial_prompt 构建完整报告 prompt
    - 追问：基于历史 + 新问题继续对话
    """
    if not request.bazi_data:
        raise HTTPException(status_code=400, detail="缺少 bazi_data 命理分析数据")

    if not request.is_first_reading:
        is_valid, _ = validate_user_question(request.question)
        if is_valid:
            await consume_usage(db, current_user.id, "qa_daily")
            await db.commit()

    try:
        if request.is_first_reading:
            # 首次解读：使用商业化报告 prompt
            system_prompt = build_commercial_prompt(
                analysis_data=request.bazi_data,
                gender=request.gender,
                birth_date=request.birth_date,
                birth_time=request.birth_time,
                location=request.location,
            )
            messages = [{"role": "user", "content": "请为我生成完整的命理分析报告"}]
        else:
            # 追问：先验证问题是否有效
            is_valid, error_msg = validate_user_question(request.question)
            if not is_valid:
                async def invalid_response() -> AsyncGenerator[str, None]:
                    yield f"\n\n⚠️ {error_msg}"
                return StreamingResponse(
                    invalid_response(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )
            
            # 使用专项 skill prompt
            from app.services.skill_prompts import build_skill_prompt
            system_prompt = build_skill_prompt(
                analysis_data=request.bazi_data,
                gender=request.gender,
                birth_date=request.birth_date,
                birth_time=request.birth_time,
                location=request.location,
                user_question=request.question,
                history=request.history,
            )
            messages = [{"role": "user", "content": request.question}]

        async def stream_response() -> AsyncGenerator[str, None]:
            full_answer = ""
            try:
                async for chunk in generate_ai_response(system_prompt, messages, stream=True):
                    full_answer += chunk
            except Exception as e:
                logger.error(f"AI 生成失败: {e}")
                yield f"\n\n⚠️ 生成中断：{str(e)}"
                return

            # 所有回答统一进行格式归一化，再统一流式输出
            # 追问场景下 LLM 也容易输出不规范的 ### 标题、未加粗关键词等
            full_answer = normalize_output(full_answer)

            # 分块输出，保留流式效果
            chunk_size = 8
            for i in range(0, len(full_answer), chunk_size):
                yield full_answer[i:i + chunk_size]
                await asyncio.sleep(0.02)

            # 流式完成后，异步保存反馈（不阻塞响应）
            if full_answer.strip():
                question_text = request.question if not request.is_first_reading else "请为我生成完整的命理分析报告"
                person_name = request.bazi_data.get("name", "") if isinstance(request.bazi_data, dict) else ""
                try:
                    async def _save():
                        try:
                            fb_save(
                                question=question_text,
                                answer=full_answer,
                                person_name=person_name,
                                model_name="qwen",
                                is_first_reading=request.is_first_reading,
                            )
                        except Exception as e:
                            logger.error(f"[Feedback] 保存失败: {e}")
                    asyncio.create_task(_save())
                except Exception:
                    pass

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.error(f"analyze_stream 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-jobs/{job_id}")
async def analyze_job_stream(
    job_id: str,
    request: AnalyzeStreamRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    基于 job_id 的异步分析任务流式接口
    - 首次调用会创建后台任务并立即返回流式响应
    - 即使客户端断开，后台任务仍会继续生成并将结果保存到任务中
    - 使用相同 job_id 重新连接时，若任务已完成则直接输出完整结果
    """
    if not request.bazi_data:
        raise HTTPException(status_code=400, detail="缺少 bazi_data 命理分析数据")

    existing_job = get_job(job_id)
    if existing_job:
        if existing_job.request_data.get("_user_id") != current_user.id:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        job = existing_job
    else:
        if not request.is_first_reading:
            is_valid, _ = validate_user_question(request.question)
            if is_valid:
                await consume_usage(db, current_user.id, "qa_daily")
                await db.commit()
        payload = request.model_dump()
        payload["_user_id"] = current_user.id
        job = create_job(job_id, payload)

    # 若任务尚未开始或仍在运行，启动后台生成（幂等）
    if job.status in ("pending",):
        asyncio.create_task(run_job(job))

    async def _stream() -> AsyncGenerator[str, None]:
        async for chunk in stream_job_result(job):
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analyze-jobs/{job_id}")
async def analyze_job_result(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    查询异步分析任务状态/结果
    用于断线重连后前端轮询或主动拉取已完成的任务
    """
    job = get_job(job_id)
    if not job or job.request_data.get("_user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "result": job.result if job.status in ("completed", "failed") else "",
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
