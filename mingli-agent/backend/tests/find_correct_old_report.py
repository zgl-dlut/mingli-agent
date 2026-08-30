"""找到回答资金问题的旧报告"""
import asyncio, json, sys
sys.path.insert(0, '.')
from app.db.session import async_session
from app.models.message import ChatMessage
from sqlalchemy import select

async def main():
    async with async_session() as db:
        # Find all assistant messages in session 21
        r = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == 21,
                ChatMessage.role == 'assistant'
            ).order_by(ChatMessage.created_at.asc())
        )
        msgs = r.scalars().all()

        print(f"Session 21 共有 {len(msgs)} 条 assistant 消息\n")

        for msg in msgs:
            try:
                data = json.loads(msg.content)
                verdict = data.get('opening', {}).get('verdict', '')
                has_fund = '资金' in verdict or '入账' in verdict or '补偿' in verdict
                if has_fund:
                    print(f'--- msg_id={msg.id}, time={msg.created_at} ---')
                    print(f'verdict: {verdict[:100]}')
                    print()
            except:
                pass

asyncio.run(main())
