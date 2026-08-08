"""
异步命理分析任务存储
支持：创建任务、后台生成、结果持久化、断线重连后拉取
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, Optional

from app.services.ai_service import generate_ai_response
from app.services.format_normalizer import normalize_output
from app.services.prompt_builder import build_commercial_prompt
from app.services.skill_prompts import build_skill_prompt, validate_user_question

logger = logging.getLogger(__name__)


@dataclass
class AnalysisJob:
    job_id: str
    request_data: dict
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    _event: asyncio.Event = field(default_factory=asyncio.Event)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_jobs: Dict[str, AnalysisJob] = {}


def create_job(job_id: str, request_data: dict) -> AnalysisJob:
    """创建新任务；如果已存在则返回已有任务"""
    if job_id in _jobs:
        return _jobs[job_id]
    job = AnalysisJob(job_id=job_id, request_data=request_data)
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[AnalysisJob]:
    return _jobs.get(job_id)


def _build_prompt_and_messages(request_data: dict):
    """根据请求数据构造 system_prompt 和 messages"""
    is_first = request_data.get("is_first_reading", True)
    if is_first:
        system_prompt = build_commercial_prompt(
            analysis_data=request_data.get("bazi_data", {}),
            gender=request_data.get("gender", "男"),
            birth_date=request_data.get("birth_date", ""),
            birth_time=request_data.get("birth_time", ""),
            location=request_data.get("location", ""),
        )
        messages = [{"role": "user", "content": "请为我生成完整的命理分析报告"}]
    else:
        question = request_data.get("question", "")
        is_valid, error_msg = validate_user_question(question)
        if not is_valid:
            return None, None, error_msg
        system_prompt = build_skill_prompt(
            analysis_data=request_data.get("bazi_data", {}),
            gender=request_data.get("gender", "男"),
            birth_date=request_data.get("birth_date", ""),
            birth_time=request_data.get("birth_time", ""),
            location=request_data.get("location", ""),
            user_question=question,
            history=request_data.get("history", []),
        )
        messages = [{"role": "user", "content": question}]
    return system_prompt, messages, None


async def run_job(job: AnalysisJob):
    """在后台运行分析任务"""
    async with job._lock:
        if job.status in ("running", "completed", "failed"):
            return
        job.status = "running"
        job.updated_at = time.time()

    try:
        system_prompt, messages, error = _build_prompt_and_messages(job.request_data)
        if error:
            job.status = "failed"
            job.error = error
            job.result = f"\n\n⚠️ {error}"
            job.updated_at = time.time()
            job._event.set()
            return

        full_answer = ""
        async for chunk in generate_ai_response(system_prompt, messages, stream=True):
            full_answer += chunk

        full_answer = normalize_output(full_answer)
        job.result = full_answer
        job.status = "completed"
    except Exception as e:
        logger.error(f"[Job {job.job_id}] 生成失败: {e}")
        job.status = "failed"
        job.error = str(e)
        job.result = f"\n\n⚠️ 生成中断：{str(e)}"
    finally:
        job.updated_at = time.time()
        job._event.set()


async def stream_job_result(
    job: AnalysisJob, chunk_size: int = 8, sleep_ms: float = 20
) -> AsyncGenerator[str, None]:
    """
    流式输出任务结果。
    - 若任务未完成，等待完成后再输出。
    - 已完成的任务直接分块输出保存的完整结果。
    """
    if job.status not in ("completed", "failed"):
        try:
            await asyncio.wait_for(job._event.wait(), timeout=300)
        except asyncio.TimeoutError:
            yield "\n\n⚠️ 生成超时，请稍后重试"
            return

    full_answer = job.result
    for i in range(0, len(full_answer), chunk_size):
        yield full_answer[i : i + chunk_size]
        await asyncio.sleep(sleep_ms / 1000)


def cleanup_old_jobs(max_age_seconds: float = 3600):
    """清理过期的已完成/失败任务，防止内存无限增长"""
    now = time.time()
    expired = [
        job_id
        for job_id, job in _jobs.items()
        if job.status in ("completed", "failed")
        and now - job.updated_at > max_age_seconds
    ]
    for job_id in expired:
        del _jobs[job_id]
    if expired:
        logger.info(f"[JobStore] 清理 {len(expired)} 个过期任务")
