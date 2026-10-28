import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import select

from app.db.session import async_session
from app.models.person import Person
from app.models.report import Report
from app.services.followup_structured import generate_followup_structured


logger = logging.getLogger(__name__)
_generation_tasks: Dict[int, asyncio.Task] = {}


def _question_for(report: Report, primary: Person, secondary: Optional[Person]) -> str:
    if report.report_type == "base_report":
        return "请从性格优势、事业方向、关系模式和成长建议生成基础解读。"
    if report.report_type == "monthly_brief":
        return f"请生成 {report.period_key} 的月度节律简报，重点说明阶段重点、行动建议和需要留意的压力。"
    if report.report_type == "annual_brief":
        return f"请生成 {report.period_key} 年度趋势报告，说明全年节奏、关键阶段和可执行建议。"
    if report.report_type == "relation_report" and secondary:
        return (
            f"请从沟通方式、相处节奏、互补优势和边界建议分析"
            f"{primary.name}与{secondary.name}的关系视角。"
        )
    return "请生成这份命理解读报告。"


async def generate_and_save_report(report_id: int) -> None:
    try:
        async with async_session() as db:
            report = await db.get(Report, report_id)
            if not report or report.status == "ready":
                return
            primary = await db.get(Person, report.primary_person_id)
            secondary = (
                await db.get(Person, report.secondary_person_id)
                if report.secondary_person_id
                else None
            )
            if not primary:
                raise ValueError("primary_person_missing")

            report.status = "generating"
            report.failure_code = None
            report.failure_message = None
            report.updated_at = datetime.utcnow()
            await db.commit()

            bazi_data = primary.bazi_data_json or {}
            history = []
            if secondary:
                history.append(
                    {
                        "role": "user",
                        "content": (
                            f"关系对象：{secondary.name}，出生于"
                            f"{secondary.birth_date} {secondary.birth_time}，"
                            f"命盘快照：{json.dumps(secondary.chart_snapshot_json or {}, ensure_ascii=False)}"
                        ),
                    }
                )
            full_json = ""
            async for chunk in generate_followup_structured(
                analysis_data=bazi_data,
                gender=primary.gender,
                birth_date=primary.birth_date,
                birth_time=primary.birth_time,
                location=primary.birth_location,
                user_question=_question_for(report, primary, secondary),
                history=history,
                longitude=primary.birth_lng,
                latitude=primary.birth_lat,
            ):
                if not chunk.startswith("__PROGRESS__"):
                    full_json += chunk
            content = json.loads(full_json)
            content.setdefault(
                "payload",
                {
                    "report_type": report.report_type,
                    "period_key": report.period_key,
                    "secondary_person_id": report.secondary_person_id,
                },
            )

            report.content_json = content
            report.preview_json = {
                "subtitle": primary.name,
                "lead": (content.get("opening") or {}).get("verdict")
                or (content.get("opening") or {}).get("lead"),
            }
            report.status = "ready"
            report.generated_at = datetime.utcnow()
            report.updated_at = datetime.utcnow()
            await db.commit()
    except Exception as exc:
        logger.exception("Report generation failed: report_id=%s", report_id)
        async with async_session() as db:
            report = await db.get(Report, report_id)
            if report:
                report.status = "failed"
                report.failure_code = type(exc).__name__
                report.failure_message = "生成失败，请稍后重试"
                report.updated_at = datetime.utcnow()
                await db.commit()
    finally:
        _generation_tasks.pop(report_id, None)


def schedule_report_generation(report_id: int) -> None:
    task = _generation_tasks.get(report_id)
    if task and not task.done():
        return
    _generation_tasks[report_id] = asyncio.create_task(generate_and_save_report(report_id))
