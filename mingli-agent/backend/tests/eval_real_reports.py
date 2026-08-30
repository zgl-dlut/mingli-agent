"""用最近 5 条真实追问报告跑评测"""
import asyncio
import json
import sys
sys.path.insert(0, '.')

from app.db.session import async_session
from app.models.message import ChatMessage
from app.models.session import ChatSession
from sqlalchemy import select, func


async def main():
    async with async_session() as db:
        # 找最近 5 条 assistant 消息（内容为 JSON 的追问报告）
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.role == "assistant")
            .order_by(ChatMessage.created_at.desc())
            .limit(20)  # 多取一些，过滤出 JSON 报告
        )
        messages = result.scalars().all()

        reports = []
        for msg in messages:
            content = msg.content or ""
            if content.startswith("{"):
                try:
                    data = json.loads(content)
                    if "subtopics" in data and "opening" in data:
                        # 获取对应的 session 和 user question
                        session_result = await db.execute(
                            select(ChatSession).where(ChatSession.id == msg.session_id)
                        )
                        session = session_result.scalar_one_or_none()

                        # 找同 session 最后一条 user 消息作为问题
                        user_q_result = await db.execute(
                            select(ChatMessage)
                            .where(
                                ChatMessage.session_id == msg.session_id,
                                ChatMessage.role == "user",
                            )
                            .order_by(ChatMessage.created_at.desc())
                            .limit(1)
                        )
                        user_q_row = user_q_result.scalar_one_or_none()
                        user_question = user_q_row.content if user_q_row else ""

                        reports.append({
                            "msg_id": msg.id,
                            "session_id": msg.session_id,
                            "person_id": session.person_id if session else None,
                            "user_question": user_question,
                            "report": data,
                            "created_at": str(msg.created_at),
                        })
                        if len(reports) >= 5:
                            break
                except json.JSONDecodeError:
                    continue

        if not reports:
            print("❌ 未找到任何追问报告")
            return

        print(f"找到 {len(reports)} 条真实追问报告\n")

        # 获取命盘数据
        from app.models.person import Person

        for i, r in enumerate(reports):
            person_result = await db.execute(
                select(Person).where(Person.id == r["person_id"])
            )
            person = person_result.scalar_one_or_none()
            r["chart_data"] = person.bazi_data_json if person else {}

        # 运行评测
        from app.services.eval.structure_checker import check_structure
        from app.services.eval.narrative_checker import check_narrative
        from app.services.eval.chart_usage_checker import check_chart_usage
        from app.services.eval.llm_scorer import evaluate_report

        for i, r in enumerate(reports):
            print(f"{'='*60}")
            print(f"报告 #{i+1}: msg_id={r['msg_id']}, session_id={r['session_id']}")
            print(f"用户问题: {r['user_question'][:60]}")
            print(f"创建时间: {r['created_at']}")
            print(f"subtopics: {len(r['report'].get('subtopics', []))}")

            # 第一层：硬性检查
            struct_v = check_structure(r["report"], r["user_question"])
            narr_v = check_narrative(r["report"], is_first_reading=False)
            chart_v = check_chart_usage(r["report"], r["chart_data"])
            all_hard = struct_v + narr_v + chart_v

            print(f"\n  硬性检查:")
            print(f"    结构违规: {len(struct_v)}")
            print(f"    叙事违规: {len(narr_v)}")
            print(f"    命盘使用违规: {len(chart_v)}")
            print(f"    总计: {len(all_hard)} {'✅ 通过' if not all_hard else '❌ 未通过'}")

            for v in all_hard[:5]:  # 最多显示 5 条
                print(f"      - [{v['type']}] {v.get('detail', '')[:80]}")
            if len(all_hard) > 5:
                print(f"      ... 还有 {len(all_hard)-5} 条")

            # 第二层：LLM 软性评分（仅硬性通过时）
            if not all_hard and r["chart_data"]:
                print(f"\n  进入 LLM 软性评分...")
                try:
                    llm_result = await evaluate_report(
                        r["report"], r["user_question"], r["chart_data"], False
                    )
                    print(f"    overall_pass: {llm_result.get('overall_pass')}")
                    print(f"    avg_soft_score: {llm_result.get('avg_soft_score')}")
                    print(f"    skip_reason: {llm_result.get('skip_reason')}")
                    if llm_result.get("soft_score"):
                        for k, v in llm_result["soft_score"].items():
                            if k != "问题":
                                print(f"      {k}: {v}")
                    if llm_result.get("fabrication"):
                        fab = llm_result["fabrication"]
                        print(f"    编造检测: 编造={fab.get('编造')}, 严重程度={fab.get('严重程度')}")
                except Exception as e:
                    print(f"    LLM 评测异常: {e}")
            elif not r["chart_data"]:
                print(f"\n  ⚠️ 无命盘数据，跳过 LLM 评测")
            else:
                print(f"\n  ️ 硬性检查未通过，跳过 LLM 评测")

            print()

        # 汇总
        print(f"{'='*60}")
        print("汇总:")
        total = len(reports)
        hard_pass = sum(1 for r in reports
                       if not (check_structure(r["report"], r["user_question"])
                              + check_narrative(r["report"], False)
                              + check_chart_usage(r["report"], r["chart_data"])))
        print(f"  硬性检查通过: {hard_pass}/{total}")
        print(f"  硬性检查未通过: {total - hard_pass}/{total}")


if __name__ == "__main__":
    asyncio.run(main())
