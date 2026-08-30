"""分析 3 条偏离报告的具体内容"""
import asyncio, json, sys
sys.path.insert(0, '.')
from app.db.session import async_session
from app.models.message import ChatMessage
from app.models.session import ChatSession
from app.models.person import Person
from sqlalchemy import select

async def main():
    async with async_session() as db:
        for msg_id in [379, 375, 373]:
            r = await db.execute(select(ChatMessage).where(ChatMessage.id == msg_id))
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

            print(f'===== 报告 msg_id={msg_id} =====')
            print(f'用户问题: {user_q.content}')
            print(f'创建时间: {msg.created_at}')
            print()
            print(f'opening: {data.get("opening", {}).get("verdict", "")}')
            print()
            for i, sub in enumerate(data.get('subtopics', [])):
                print(f'  subtopic[{i}] title: {sub.get("title", "")}')
                for j, blk in enumerate(sub.get('blocks', [])):
                    nar = blk.get('narrative', '')
                    kw = blk.get('keyword', '')
                    print(f'    block[{j}] keyword="{kw}"')
                    print(f'    narrative: {nar}')
                    print()
            print('=' * 60)
            print()

asyncio.run(main())
