"""评测新生成的报告 #5 (msg_id=380)"""
import asyncio, json, sys
sys.path.insert(0, '.')
from app.db.session import async_session
from app.models.message import ChatMessage
from app.models.session import ChatSession
from app.models.person import Person
from sqlalchemy import select

async def main():
    async with async_session() as db:
        r = await db.execute(select(ChatMessage).where(ChatMessage.id == 380))
        msg = r.scalar_one()
        data = json.loads(msg.content)

        s = await db.execute(select(ChatSession).where(ChatSession.id == msg.session_id))
        session = s.scalar_one()

        p = await db.execute(select(Person).where(Person.id == session.person_id))
        person = p.scalar_one()

        uq = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.role == 'user'
            ).order_by(ChatMessage.created_at.desc()).limit(1)
        )
        user_q = uq.scalar_one()

        print(f'用户问题: {user_q.content}')
        print()

        # Run hard checks
        from app.services.eval.structure_checker import check_structure
        from app.services.eval.narrative_checker import check_narrative
        from app.services.eval.chart_usage_checker import check_chart_usage

        struct_v = check_structure(data, user_q.content)
        narr_v = check_narrative(data)
        chart_v = check_chart_usage(data, person.bazi_data_json)

        total = len(struct_v) + len(narr_v) + len(chart_v)
        print(f'硬性检查:')
        print(f'  结构违规: {len(struct_v)}')
        print(f'  叙事违规: {len(narr_v)}')
        print(f'  命盘使用违规: {len(chart_v)}')
        print(f'  总计: {total} {"✅ 通过" if total == 0 else "❌ 未通过"}')
        for v in struct_v + narr_v + chart_v:
            print(f'    - [{v["type"]}] {v["detail"]}')

        if total == 0:
            print('\n进入 LLM 软性评分...')
            from app.services.eval.llm_scorer import evaluate_report
            # Force to plain string
            uq_text = user_q.content
            if not isinstance(uq_text, str):
                uq_text = bytes(uq_text).decode('utf-8') if isinstance(uq_text, (bytes, memoryview)) else str(uq_text)
            print(f'  user_question type={type(uq_text)} len={len(uq_text)} repr={repr(uq_text[:50])}')
            result = await evaluate_report(data, uq_text, person.bazi_data_json)
            print(f'  overall_pass: {result.get("overall_pass")}')
            print(f'  avg_soft_score: {result.get("avg_soft_score")}')
            for k, v in result.get("scores", {}).items():
                print(f'    {k}: {v}')
            fabric = result.get("fabrication_check", {})
            print(f'  编造检测: 编造={fabric.get("has_fabrication")}, 严重程度={fabric.get("severity")}')

asyncio.run(main())
