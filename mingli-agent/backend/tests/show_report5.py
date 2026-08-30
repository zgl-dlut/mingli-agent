"""查看报告 #5 内容"""
import asyncio, json, sys
sys.path.insert(0, '.')
from app.db.session import async_session
from app.models.message import ChatMessage
from app.models.person import Person
from app.models.session import ChatSession
from sqlalchemy import select

async def main():
    async with async_session() as db:
        result = await db.execute(select(ChatMessage).where(ChatMessage.id == 371))
        msg = result.scalar_one()
        data = json.loads(msg.content)

        s_result = await db.execute(select(ChatSession).where(ChatSession.id == msg.session_id))
        session = s_result.scalar_one()

        p_result = await db.execute(select(Person).where(Person.id == session.person_id))
        person = p_result.scalar_one()

        uq_result = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.role == 'user'
            ).order_by(ChatMessage.created_at.desc()).limit(1)
        )
        uq = uq_result.scalar_one()
        print(f'用户问题: {uq.content}')
        print()

        print(f'subtopics: {len(data.get("subtopics", []))}')
        for i, sub in enumerate(data.get('subtopics', [])):
            print(f'  [{i}] title: {sub.get("title", "")}')
            for j, blk in enumerate(sub.get('blocks', [])):
                nar = blk.get('narrative', '')
                print(f'      block[{j}] keyword={blk.get("keyword", "")} len={len(nar)}')
                print(f'        narrative: {nar[:100]}')

        print()
        chart = person.bazi_data_json
        print(f'用神: {chart.get("用神", "")}')
        print(f'忌神: {chart.get("忌神", "")}')
        print(f'当前大运: {chart.get("当前大运", "")}')

asyncio.run(main())
