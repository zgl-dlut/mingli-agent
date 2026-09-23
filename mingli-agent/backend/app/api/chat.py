import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings, PROMPT_VERSION
from app.core.exceptions import PermissionDenied, ResourceNotFound
from app.core.lunar_utils import get_display_birth_date
from app.db.session import get_db, async_session
from app.models.message import ChatMessage
from app.models.session import ChatSession
from app.models.usage_log import AiUsageLog
from app.models.user import User
from app.services.ai_service import generate_first_reading_structured
from app.services.followup_structured import generate_followup_structured
from app.services.date_select_agent import generate_date_select, is_date_select_intent_async
from app.services.payment_service import deduct_points
from app.services.skill_prompts import validate_user_question
from app.services.format_normalizer import normalize_output  # 首次报告仍用
from app.skills.orchestrator import generate_full_analysis
from app.services.chart_validator import validate_chart_data_with_values

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 追问生成异常记录到 followup_check.log，便于排查
_logger = logging.getLogger("followup_check")
_handler = logging.FileHandler("logs/followup_check.log", encoding="utf-8")
_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
_logger.addHandler(_handler)
_logger.propagate = False

# 追问生成的后台任务表：session_id -> asyncio.Task
# 任务独立于 SSE 连接运行，客户端断开（刷新）后任务继续，完成后存库并从表中移除
_generating_tasks: "dict[int, asyncio.Task]" = {}
# 任务开始时间戳：用于超时兜底，防止任务卡住导致用户永远无法发新问题
_generating_start: "dict[int, float]" = {}
# 超时阈值（秒）：超过此时间认为任务卡住，允许新请求强制清理
_GENERATING_TIMEOUT = 900
# 任务异常时存错误信息，供 generating-status 接口返回给前端提示
_generating_errors: "dict[int, str]" = {}


class MessageRequest(BaseModel):
    content: str


@router.get("/sessions")
async def get_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    from app.models.person import Person
    
    result = await db.execute(
        select(ChatSession).join(Person, ChatSession.person_id == Person.id).where(Person.user_id == current_user.id)
    )
    sessions = result.scalars().all()
    
    session_list = []
    for session in sessions:
        person_result = await db.execute(select(Person).where(Person.id == session.person_id))
        person = person_result.scalar_one_or_none()
        
        session_list.append({
            "id": session.id,
            "person_id": session.person_id,
            "person_name": person.name if person else "",
            "title": session.title,
            "bazi_data": session.bazi_data_json,
            "astro_data": session.astro_data_json,
            "updated_at": session.updated_at.isoformat(),
        })
    
    return session_list


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise ResourceNotFound("会话不存在")
    
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    
    message_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    messages = message_result.scalars().all()
    
    return [{
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
    } for msg in messages]


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    request: MessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise ResourceNotFound("会话不存在")
    
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    
    # 择日意图提前检查：命中择日关键词直接放行，跳过 validate_user_question（择日本身就是命理服务）
    from app.services.date_select_agent import _keyword_match as _is_date_select_kw
    if _is_date_select_kw(request.content):
        is_valid, error_msg = True, ""
    else:
        # 关键词没命中但可能是择日的口语表达，先用 validate 拦截无关问题
        is_valid, error_msg = validate_user_question(request.content)
        # 如果被拦截了，再让 LLM 做最后一道择日语义判定（1-2秒）
        if not is_valid:
            from app.services.date_select_agent import is_date_select_intent_async as _is_ds_async
            if await _is_ds_async(request.content):
                is_valid, error_msg = True, ""
    if not is_valid:
        print(f"[chat][拦截] 开始落库 session_id={session_id} question={request.content!r}", flush=True)
        print(f"[chat][拦截] 拦截回复文案={error_msg[:80]!r}", flush=True)
        # 去重：10秒内相同 user 消息不重复存（与正常发送一致）
        dedup_cutoff = datetime.utcnow() - timedelta(seconds=10)
        recent_user_msg = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user",
                ChatMessage.content == request.content,
                ChatMessage.created_at > dedup_cutoff,
            ).order_by(ChatMessage.created_at.desc()).limit(1)
        )
        existing_user = recent_user_msg.scalar_one_or_none()
        if not existing_user:
            user_message = ChatMessage(session_id=session_id, role="user", content=request.content)
            db.add(user_message)
            await db.commit()
            await db.refresh(user_message)
            print(f"[chat][拦截] user消息已写入 id={user_message.id} session_id={session_id} role=user content_len={len(request.content)}", flush=True)
        else:
            print(f"[chat][拦截] user消息去重跳过（10秒内已存在）existing_id={existing_user.id}", flush=True)
        # 存 assistant 拦截文案，作为对应回复记录
        reject_message = ChatMessage(session_id=session_id, role="assistant", content=error_msg)
        db.add(reject_message)
        await db.commit()
        await db.refresh(reject_message)
        print(f"[chat][拦截] assistant拦截文案已写入 id={reject_message.id} session_id={session_id} role=assistant content_len={len(error_msg)}", flush=True)
        print(f"[chat][拦截] 落库完成 session_id={session_id} 已记录 user提问+assistant拒绝回复", flush=True)

        async def reject_stream() -> AsyncGenerator[str, None]:
            yield error_msg
            yield "\n\n__SAVED__"

        return StreamingResponse(reject_stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    # 重试判定：上一条消息是相同内容的 user 消息（中断后重问），免重复扣费、不存重复 user 消息
    last_msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    last_msg = last_msg_result.scalar_one_or_none()
    is_retry_unanswered = (
        last_msg is not None
        and last_msg.role == "user"
        and (last_msg.content or "").strip() == (request.content or "").strip()
    )

    if not is_retry_unanswered:
        await deduct_points(
            db, current_user.id, settings.POINTS_FOLLOW_UP,
            f"追问: {request.content[:30]}...",
            biz_type="followup",
        )

        # 去重检查：10秒内相同的用户消息不重复保存（防止前端双击/竞态重复提交）
        # 超过10秒后允许用户合法重复追问相同问题，避免吞掉用户消息导致前端不显示
        dedup_cutoff = datetime.utcnow() - timedelta(seconds=10)
        recent_user_msg = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user",
                ChatMessage.content == request.content,
                ChatMessage.created_at > dedup_cutoff,
            ).order_by(ChatMessage.created_at.desc()).limit(1)
        )
        existing_msg = recent_user_msg.scalar_one_or_none()
        if not existing_msg:
            user_message = ChatMessage(
                session_id=session_id,
                role="user",
                content=request.content,
            )
            db.add(user_message)
            await db.commit()
    # else: 重试未回答的上一条问题，不扣费、不存重复 user 消息，直接用已有消息生成

    history_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    history_messages = history_result.scalars().all()

    history_list = [{
        "role": msg.role,
        "content": msg.content,
    } for msg in history_messages]

    # 结构化追问：LLM 输出 JSON，前端直渲染（不走 Markdown 中间层）
    # 任务化：后台任务独立运行，SSE 断开（刷新）不影响生成，完成后存库并从任务表移除
    # 如果该 session 正在生成，拒绝新请求；超时兜底防止任务卡住导致用户永远无法发新问题
    if session_id in _generating_tasks:
        old_task = _generating_tasks[session_id]
        start = _generating_start.get(session_id, 0)
        if old_task.done() or (time.time() - start > _GENERATING_TIMEOUT):
            # 任务已完成但未清理（异常）或超时卡住，强制清理，允许新请求
            if not old_task.done():
                old_task.cancel()
            _generating_tasks.pop(session_id, None)
            _generating_start.pop(session_id, None)
            _generating_errors.pop(session_id, None)
        else:
            # 正在生成且未超时，拒绝新请求
            raise HTTPException(status_code=409, detail="正在生成中，请稍候完成后再发送新问题")
    # 提取 ORM 属性到普通变量，避免后台任务访问已关闭的请求级 session
    # 优先从 Person 读取已持久化的排盘数据
    if person.bazi_data_json:
        bazi_data = person.bazi_data_json
        # 数据库 JSON 字段可能是字符串，需要反序列化
        if isinstance(bazi_data, str):
            import json as _json
            try:
                bazi_data = _json.loads(bazi_data)
            except (TypeError, ValueError):
                bazi_data = None
        # 旧版排盘落库数据缺流月十神字段（shishen_tian/shishen_di），双重危害：
        # ①评测端基准（person.bazi_data_json 构建）无十神名，LLM 正确引用生成端
        #   现算十神也会被误判"自行推演十神"（编造误报）；
        # ②若生成链路复用此数据，prompt明细无十神名会诱发LLM自行推演（编造高发点）。
        # 校验缺失则现场重算并回写，一次性修复（后续轮次直接命中新数据）。
        _lys = (bazi_data or {}).get("重点流年") or []
        _first_lm = {}
        if _lys and isinstance(_lys[0], dict):
            _ly_list = _lys[0].get("liuyue") or []
            if _ly_list and isinstance(_ly_list[0], dict):
                _first_lm = _ly_list[0]
        if not _first_lm.get("shishen_tian"):
            print(f"[chat] 落库排盘数据缺流月十神字段，现场重算并回写 session_id={session_id}", flush=True)
            bazi_data = generate_full_analysis(
                birth_date=person.birth_date,
                birth_time=person.birth_time,
                longitude=person.birth_lng,
                latitude=person.birth_lat,
                gender=person.gender,
                location=person.birth_location,
            )
            person.bazi_data_json = bazi_data
            session.bazi_data_json = bazi_data
            await db.commit()
            print(f"[chat] 排盘数据已重算升级并持久化 session_id={session_id}", flush=True)
        # 同步到 session（如果 session 没有）
        if not session.bazi_data_json:
            session.bazi_data_json = bazi_data
            await db.commit()
        print(f"[chat] 排盘数据来源: person.bazi_data_json, session_id={session_id}", flush=True)
    elif session.bazi_data_json:
        # Person 没有，但 session 有，同步回 Person
        bazi_data = session.bazi_data_json
        # 数据库 JSON 字段可能是字符串
        if isinstance(bazi_data, str):
            import json as _json2
            try:
                bazi_data = _json2.loads(bazi_data)
            except (TypeError, ValueError):
                bazi_data = None
        person.bazi_data_json = bazi_data
        await db.commit()
        print(f"[chat] 排盘数据来源: session.bazi_data_json, session_id={session_id}", flush=True)
    else:
        # 都没有，生成并持久化到 Person 和 Session
        print(f"[chat] 追问报告排盘数据缺失，自动生成 session_id={session_id}", flush=True)
        bazi_data = generate_full_analysis(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            gender=person.gender,
            location=person.birth_location,
        )
        person.bazi_data_json = bazi_data
        session.bazi_data_json = bazi_data
        await db.commit()
        print(f"[chat] 追问报告排盘数据生成完成并已持久化 session_id={session_id}", flush=True)

    # 输出排盘数据关键字段检查
    if bazi_data:
        has_shensha = '神煞' in bazi_data and bazi_data['神煞'] is not None
        has_kongwang = '空亡' in bazi_data and bazi_data['空亡'] is not None
        has_changsheng = '长生十二宫' in bazi_data and bazi_data['长生十二宫'] is not None
        has_tiangan_he = '天干五合' in bazi_data and bazi_data['天干五合'] is not None
        print(f"[chat] 排盘数据字段检查: 神煞={'✅' if has_shensha else '❌'}, 空亡={'✅' if has_kongwang else '❌'}, 长生十二宫={'✅' if has_changsheng else '❌'}, 天干五合={'✅' if has_tiangan_he else '❌'}", flush=True)
        if has_shensha:
            print(f"[chat] 神煞数据: {bazi_data['神煞']}", flush=True)

        # 排盘数据值正确性校验
        is_valid, errors = validate_chart_data_with_values(bazi_data)
        if not is_valid:
            print(f"[chat] ️ 排盘数据值校验失败: {errors}", flush=True)
        else:
            print(f"[chat] ✅ 排盘数据值校验通过", flush=True)
    else:
        print(f"[chat] ⚠️ 排盘数据为空!", flush=True)

    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        _generate_and_save(
            session_id=session_id,
            bazi_data=bazi_data,
            gender=person.gender,
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            location=person.birth_location,
            question=request.content,
            history=history_list,
            queue=queue,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            user_id=current_user.id,
        )
    )
    _generating_tasks[session_id] = task
    _generating_start[session_id] = time.time()

    async def stream_response() -> AsyncGenerator[str, None]:
        # 从队列读 chunk 推送给前端；客户端断开后任务继续，队列堆积直到任务完成
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(stream_response(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


async def _record_usage_log(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    biz_type: str,
    holder: dict,
    t0: float,
) -> None:
    """AI 请求用量落库（字数/token/模型/成败/用时）；失败仅打印日志，不影响主流程。"""
    try:
        log = AiUsageLog(
            user_id=user_id,
            session_id=session_id,
            biz_type=biz_type,
            input_chars=holder.get("input_chars", 0),
            input_tokens=holder.get("input_tokens", 0),
            output_chars=holder.get("output_chars", 0),
            output_tokens=holder.get("output_tokens", 0),
            total_tokens=holder.get("total_tokens", 0),
            cached_tokens=holder.get("cached_tokens", 0),
            model=holder.get("model", ""),
            success=bool(holder.get("success", False)),
            duration_ms=int((time.time() - t0) * 1000),
        )
        db.add(log)
        await db.commit()
    except Exception as e:
        print(f"[_record_usage_log] 用量落库失败（不影响主流程）session_id={session_id} {type(e).__name__}: {e}", flush=True)


async def _generate_and_save(
    session_id: int,
    bazi_data,
    gender: str,
    birth_date: str,
    birth_time: str,
    location: str,
    question: str,
    history: list,
    queue: asyncio.Queue,
    longitude: float,
    latitude: float,
    user_id: int,
) -> None:
    """后台生成追问报告并存库，独立于 SSE 连接。客户端断开后任务继续运行。

    意图分流：用户问题含择日关键词时走 date_select_agent（Agent 链路），
    否则走 generate_followup_structured（常规追问）。
    """
    import traceback
    is_date_select = await is_date_select_intent_async(question)
    print(f"[_generate_and_save] 开始 session_id={session_id} question={question[:30]} is_date_select={is_date_select}", flush=True)
    t0 = time.time()
    usage_holder: dict = {}
    try:
        # 独立 db session，不依赖请求级 session（请求结束后请求级 session 会关闭）
        async with async_session() as db:
            full_json = ""
            if is_date_select:
                # 择日 Agent 链路：立即推一个前置进度标记，避免 LLM 首次调用前的空窗期
                await queue.put("__PROGRESS__正在分析需求\n")
                async for chunk in generate_date_select(
                    user_question=question,
                    analysis_data=bazi_data,
                    usage_holder=usage_holder,
                ):
                    # 过滤 progress 标记：只进 SSE 推给前端，不进存库的 full_json
                    if chunk.startswith("__PROGRESS__"):
                        await queue.put(chunk)
                    else:
                        full_json += chunk
                        await queue.put(chunk)
            else:
                # 临时生辰抽取+排盘：用户消息里临时提"别人生辰"时真实排盘注入，
                # 避免 LLM 拿不到命盘自行编造五行/十神（如"满盘是水"）。
                from app.services.birth_extractor import build_extra_chart_block
                extra_chart_block = build_extra_chart_block(
                    question, exclude_birth_date=birth_date, exclude_birth_time=birth_time
                )
                if extra_chart_block:
                    print(f"[chat] 检测到临时生辰，已排盘注入 session_id={session_id}", flush=True)
                # 进度标记由 generate_followup_structured 内部 yield，这里过滤：
                # __PROGRESS__ 标记只推送给前端，不进存库的 full_json
                async for chunk in generate_followup_structured(
                    analysis_data=bazi_data,
                    gender=gender,
                    birth_date=birth_date,
                    birth_time=birth_time,
                    location=location,
                    user_question=question,
                    history=history,
                    longitude=longitude,
                    latitude=latitude,
                    usage_holder=usage_holder,
                    extra_chart_block=extra_chart_block,
                ):
                    if chunk.startswith("__PROGRESS__"):
                        await queue.put(chunk)
                    else:
                        full_json += chunk
                        await queue.put(chunk)
            # 存库：content 存 JSON 字符串（前端解析后用 React 组件渲染）
            assistant_message = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_json,
            )
            db.add(assistant_message)
            await db.commit()
            await queue.put("\n\n__SAVED__")  # 存库完成标记，前端收到后拉取消息
            print(f"[_generate_and_save] 完成 session_id={session_id} json_len={len(full_json)}", flush=True)

            # ─ 生产监控：智能采样（择日 Agent 跳过常规报告评测） ──
            if not is_date_select:
              try:
                from app.services.eval.production_monitor import should_deep_eval, save_monitor_result
                import json as _json

                gen_time = time.time() - t0
                report_data = _json.loads(full_json) if full_json else {}

                need_eval, trigger_reason = should_deep_eval(
                    report=report_data,
                    user_question=question,
                    is_first_report=False,
                    generation_time=gen_time,
                )
                # 历史用户问题原文：评测端时间锚点继承用（与生成端同源），
                # 无时间词追问（如"新组业务适合我吗"）靠上轮问题确定流月年份
                _hist_qs = [
                    str(m.get("content") or "") for m in (history or [])
                    if m.get("role") == "user" and str(m.get("content") or "").strip()
                ]
                await save_monitor_result(
                    report=report_data,
                    user_question=question,
                    user_id=user_id,
                    session_id=session_id,
                    trigger_reason=trigger_reason if need_eval else "no_trigger",
                    is_first_report=False,
                    generation_time=gen_time,
                    # 用生成端重建的完整命盘（含大运列表+当前大运）作评测基准，
                    # 与生成端同源，避免评测端用 person 旧版命盘导致大运等数据不一致→误判编造
                    chart_data=usage_holder.get("analysis_data") or bazi_data,
                    prompt_version=PROMPT_VERSION,
                    history_user_qs=_hist_qs,
                )
              except Exception as mon_e:
                print(f"[_generate_and_save] 生产监控异常: {mon_e}", flush=True)
    except Exception as e:
        import traceback as _tb
        _err_msg = f"{type(e).__name__}: {e}"
        _tb_str = _tb.format_exc()
        print(f"[_generate_and_save] 异常 session_id={session_id} {_err_msg}\n{_tb_str}", flush=True)
        _logger.error(f"[chat.py追问异常] session_id={session_id} 错误={_err_msg}\n{_tb_str}")
        _generating_errors[session_id] = _err_msg
        await queue.put(f"\n\n__ERROR__:{_err_msg}")
    finally:
        # 用量落库（成功/失败都记录，失败时 success=False、token 缺失为 0），独立 session 不影响主流程
        try:
            async with async_session() as usage_db:
                await _record_usage_log(usage_db, user_id, session_id, "followup", usage_holder, t0)
        except Exception as e:
            print(f"[_generate_and_save] 用量落库异常 session_id={session_id} {type(e).__name__}: {e}", flush=True)
        await queue.put(None)  # 结束标记，stream_response 收到后停止
        _generating_tasks.pop(session_id, None)
        _generating_start.pop(session_id, None)
        print(f"[_generate_and_save] 结束 session_id={session_id}", flush=True)


@router.get("/sessions/{session_id}/generating-status")
async def get_generating_status(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """查询该会话是否正在后台生成追问报告（用于刷新后恢复进度条）。"""
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise ResourceNotFound("会话不存在")
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    # 任务异常时返回 error（一次性 pop，前端轮询发现后显示提示）
    error = _generating_errors.pop(session_id, None)
    generating = session_id in _generating_tasks
    # 超时兜底：任务卡住超过阈值时，标记为失败，不再显示进度条
    if generating:
        start = _generating_start.get(session_id, 0)
        task = _generating_tasks.get(session_id)
        if task and (task.done() or time.time() - start > _GENERATING_TIMEOUT):
            # 任务已完成但未清理，或超时卡住 → 清理并标记失败
            if not task.done():
                task.cancel()
            _generating_tasks.pop(session_id, None)
            _generating_start.pop(session_id, None)
            generating = False
            if not error:
                error = "生成超时，请重新发送问题"
    # 返回已耗时秒数：前端刷新后按真实耗时恢复进度条，避免从10%重置
    elapsed_seconds = int(time.time() - _generating_start.get(session_id, time.time())) if generating else 0
    return {"generating": generating, "error": error, "elapsed_seconds": elapsed_seconds}


@router.get("/sessions/{session_id}/first-reading")
async def get_first_reading(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise ResourceNotFound("会话不存在")
    
    from app.models.person import Person
    person_result = await db.execute(select(Person).where(Person.id == session.person_id))
    person = person_result.scalar_one_or_none()
    
    if not person or person.user_id != current_user.id:
        raise PermissionDenied("无权访问")

    # 优先从 Person 读取已持久化的排盘数据
    if person.bazi_data_json:
        bazi_data = person.bazi_data_json
        if isinstance(bazi_data, str):
            import json as _json3
            try: bazi_data = _json3.loads(bazi_data)
            except (TypeError, ValueError): bazi_data = None
        # 同步到 session（如果 session 没有）
        if not session.bazi_data_json:
            session.bazi_data_json = bazi_data
            await db.commit()
    elif session.bazi_data_json:
        # Person 没有，但 session 有，同步回 Person
        bazi_data = session.bazi_data_json
        if isinstance(bazi_data, str):
            import json as _json4
            try: bazi_data = _json4.loads(bazi_data)
            except (TypeError, ValueError): bazi_data = None
        person.bazi_data_json = bazi_data
        await db.commit()
    else:
        # 都没有，生成并持久化到 Person 和 Session
        print(f"[chat] 首次报告排盘数据缺失，自动生成 session_id={session_id}", flush=True)
        bazi_data = generate_full_analysis(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            gender=person.gender,
            location=person.birth_location,
        )
        person.bazi_data_json = bazi_data
        session.bazi_data_json = bazi_data
        await db.commit()
        print(f"[chat] 首次报告排盘数据生成完成并已持久化 session_id={session_id}", flush=True)

    # 排盘数据值正确性校验
    if bazi_data:
        is_valid, errors = validate_chart_data_with_values(bazi_data)
        if not is_valid:
            print(f"[chat][首次] ⚠️ 排盘数据值校验失败: {errors}", flush=True)
        else:
            print(f"[chat][首次] ✅ 排盘数据值校验通过", flush=True)
    else:
        print(f"[chat][首次] ⚠️ 排盘数据为空!", flush=True)

    # 确保命盘信息用户消息存在（首次报告的"发送内容"）
    existing_user_msg = await db.execute(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user"
        ).limit(1)
    )
    if not existing_user_msg.scalar_one_or_none():
        calendar_label = "公历" if person.calendar_type == "solar" else "农历"
        display_date = get_display_birth_date(person.birth_date, person.calendar_type)
        user_content = f"出生时间：{display_date} {person.birth_time}({calendar_label})\n出生地点：{person.birth_location}\n性别：{'男' if person.gender == 'male' else '女'}"
        user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content=user_content,
        )
        db.add(user_message)
        await db.commit()

    message_result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "assistant"
        ).order_by(ChatMessage.created_at)
    )
    assistant_messages = message_result.scalars().all()
    
    if assistant_messages:
        return {"content": assistant_messages[0].content}

    # 任务化：后台任务独立运行，SSE 断开（刷新）不影响生成，完成后存库并从任务表移除
    # 如果该 session 正在生成，拒绝重复请求（防止刷新后重复点击触发第二次生成）
    if session_id in _generating_tasks:
        old_task = _generating_tasks[session_id]
        start = _generating_start.get(session_id, 0)
        if old_task.done() or (time.time() - start > _GENERATING_TIMEOUT):
            # 任务已完成但未清理（异常）或超时卡住，强制清理，允许新请求
            if not old_task.done():
                old_task.cancel()
            _generating_tasks.pop(session_id, None)
            _generating_start.pop(session_id, None)
            _generating_errors.pop(session_id, None)
        else:
            # 正在生成且未超时，拒绝重复请求
            raise HTTPException(status_code=409, detail="首次报告正在生成中，请稍候")

    # 提取 ORM 属性到普通变量，避免后台任务访问已关闭的请求级 session
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        _generate_and_save_first_reading(
            session_id=session_id,
            gender=person.gender,
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            location=person.birth_location,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            queue=queue,
            user_id=current_user.id,
            bazi_data=bazi_data,
        )
    )
    _generating_tasks[session_id] = task
    _generating_start[session_id] = time.time()

    async def stream_response() -> AsyncGenerator[str, None]:
        # 从队列读 chunk 推送给前端；客户端断开后任务继续，队列堆积直到任务完成
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(stream_response(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


async def _generate_and_save_first_reading(
    session_id: int,
    gender: str,
    birth_date: str,
    birth_time: str,
    location: str,
    longitude: float,
    latitude: float,
    queue: asyncio.Queue,
    user_id: int,
    bazi_data: dict,
) -> None:
    """后台生成首次报告并存库，独立于 SSE 连接。客户端断开（刷新）后任务继续运行。"""
    import traceback
    print(f"[_generate_and_save_first_reading] 开始 session_id={session_id}", flush=True)
    t0 = time.time()
    usage_holder: dict = {}
    try:
        # 独立 db session，不依赖请求级 session（请求结束后请求级 session 会关闭）
        async with async_session() as db:
            # 二次检查：防止并发生成导致重复存库
            recheck = await db.execute(
                select(ChatMessage).where(
                    ChatMessage.session_id == session_id,
                    ChatMessage.role == "assistant"
                ).limit(1)
            )
            if recheck.scalar_one_or_none():
                print(f"[_generate_and_save_first_reading] 已有 assistant 消息，跳过 session_id={session_id}", flush=True)
                return

            full_content = ""
            async for chunk in generate_first_reading_structured(
                gender=gender,
                birth_date=birth_date,
                birth_time=birth_time,
                location=location,
                longitude=longitude,
                latitude=latitude,
                usage_holder=usage_holder,
            ):
                full_content += chunk
                await queue.put(chunk)

            # 存库：content 存 JSON 字符串（前端 isStructuredReport 自动识别 JSON 走结构化渲染）
            assistant_message = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_content,
            )
            db.add(assistant_message)
            await db.commit()
            await queue.put("\n\n__SAVED__")  # 存库完成标记，前端收到后拉取消息
            print(f"[_generate_and_save_first_reading] 完成 session_id={session_id} json_len={len(full_content)}", flush=True)

            # ─ 生产监控：智能采样 ──
            try:
                from app.services.eval.production_monitor import should_deep_eval, save_monitor_result
                import json as _json

                gen_time = time.time() - t0
                report_data = _json.loads(full_content) if full_content else {}

                # 获取用户问题（从同 session 的 user 消息中取最后一条）
                user_q_result = await db.execute(
                    select(ChatMessage).where(
                        ChatMessage.session_id == session_id,
                        ChatMessage.role == "user"
                    ).order_by(ChatMessage.created_at.desc()).limit(1)
                )
                user_q_row = user_q_result.scalar_one_or_none()
                user_question = user_q_row.content if user_q_row else ""

                # 历史用户问题原文：评测端时间锚点继承用（与生成端同源）
                _hist_rows = (await db.execute(
                    select(ChatMessage.content).where(
                        ChatMessage.session_id == session_id,
                        ChatMessage.role == "user",
                    ).order_by(ChatMessage.created_at.asc())
                )).scalars().all()
                _hist_qs = [str(c or "") for c in _hist_rows if str(c or "").strip()]

                need_eval, trigger_reason = should_deep_eval(
                    report=report_data,
                    user_question=user_question,
                    is_first_report=True,
                    generation_time=gen_time,
                )
                await save_monitor_result(
                    report=report_data,
                    user_question=user_question,
                    user_id=user_id,
                    session_id=session_id,
                    trigger_reason=trigger_reason if need_eval else "no_trigger",
                    is_first_report=True,
                    generation_time=gen_time,
                    chart_data=bazi_data,
                    prompt_version=PROMPT_VERSION,
                    history_user_qs=_hist_qs,
                )
            except Exception as mon_e:
                print(f"[_generate_and_save_first_reading] 生产监控异常: {mon_e}", flush=True)
    except Exception as e:
        print(f"[_generate_and_save_first_reading] 异常 session_id={session_id} {type(e).__name__}: {e}\n{traceback.format_exc()}", flush=True)
        _generating_errors[session_id] = f"{type(e).__name__}: {e}"
        await queue.put(f"\n\n__ERROR__:{type(e).__name__}: {e}")
    finally:
        # 用量落库（成功/失败都记录，失败时 success=False、token 缺失为 0），独立 session 不影响主流程
        try:
            async with async_session() as usage_db:
                await _record_usage_log(usage_db, user_id, session_id, "first_reading", usage_holder, t0)
        except Exception as e:
            print(f"[_generate_and_save_first_reading] 用量落库异常 session_id={session_id} {type(e).__name__}: {e}", flush=True)
        await queue.put(None)  # 结束标记，stream_response 收到后停止
        _generating_tasks.pop(session_id, None)
        _generating_start.pop(session_id, None)
        print(f"[_generate_and_save_first_reading] 结束 session_id={session_id}", flush=True)
