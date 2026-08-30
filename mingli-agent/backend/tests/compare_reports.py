"""对比新旧报告 #5 的内容差异"""
import asyncio, json, sys
sys.path.insert(0, '.')
from app.db.session import async_session
from app.models.message import ChatMessage
from sqlalchemy import select

async def main():
    async with async_session() as db:
        for label, msg_id in [("旧报告 (msg_id=371)", 371), ("新报告 (msg_id=380)", 380)]:
            r = await db.execute(select(ChatMessage).where(ChatMessage.id == msg_id))
            msg = r.scalar_one()
            data = json.loads(msg.content)

            print(f'\n{"="*70}')
            print(f'  {label}')
            print(f'{"="*70}')

            opening = data.get('opening', {})
            print(f'\n【opening.lead】{opening.get("lead", "")}')
            print(f'\n【opening.verdict】{opening.get("verdict", "")}')

            for i, sub in enumerate(data.get('subtopics', [])):
                print(f'\n【subtopic[{i}]】{sub.get("title", "")}')
                for j, blk in enumerate(sub.get('blocks', [])):
                    nar = blk.get('narrative', '')
                    kw = blk.get('keyword', '')
                    print(f'\n  block[{j}] keyword="{kw}" (len={len(nar)})')
                    print(f'  {nar}')

            summary = data.get('summary', {})
            print(f'\n【summary.title】{summary.get("title", "")}')
            for item in summary.get('items', []):
                print(f'  - {item.get("keyword", "")}: {item.get("text", "")}')
            if summary.get('narrative'):
                print(f'  narrative: {summary.get("narrative")}')

asyncio.run(main())
