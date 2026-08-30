"""重新生成报告 #5 (msg_id=371)"""
import asyncio, json, sys, time
sys.path.insert(0, '.')
from app.db.session import async_session
from app.models.message import ChatMessage
from app.models.session import ChatSession
from app.models.person import Person
from sqlalchemy import select

async def main():
    async with async_session() as db:
        # Get original message
        r = await db.execute(select(ChatMessage).where(ChatMessage.id == 371))
        msg = r.scalar_one()

        # Get session
        s = await db.execute(select(ChatSession).where(ChatSession.id == msg.session_id))
        session = s.scalar_one()

        # Get person
        p = await db.execute(select(Person).where(Person.id == session.person_id))
        person = p.scalar_one()

        # Get user question
        uq = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.role == 'user'
            ).order_by(ChatMessage.created_at.desc()).limit(1)
        )
        user_q = uq.scalar_one()

        print(f'Session: {session.id}')
        print(f'Person: {person.id}')
        print(f'User question: {user_q.content}')

        # Get conversation history
        history = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == msg.session_id
            ).order_by(ChatMessage.created_at.asc())
        )
        messages = history.scalars().all()
        conv_history = []
        for m in messages:
            if m.id == 371:
                break
            conv_history.append({"role": m.role, "content": m.content})

        print(f'Conversation history: {len(conv_history)} messages')

        # Call followup generation
        from app.services.followup_structured import generate_followup_structured

        full_json = ""
        async for chunk in generate_followup_structured(
            analysis_data=person.bazi_data_json,
            gender=person.gender,
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            location=person.birth_location or "",
            user_question=user_q.content,
            history=conv_history,
            longitude=116.4,
            latitude=39.9,
        ):
            full_json += chunk

        # Parse and show
        data = json.loads(full_json)
        print(f'\n=== New Report ===')
        print(f'Subtopics: {len(data.get("subtopics", []))}')
        for i, sub in enumerate(data.get('subtopics', [])):
            print(f'  [{i}] title: {sub.get("title", "")}')
            for j, blk in enumerate(sub.get('blocks', [])):
                nar = blk.get('narrative', '')
                kw = blk.get('keyword', '')
                print(f'      block[{j}] keyword="{kw}" len={len(nar)}')
                print(f'        narrative: {nar}')
                print()

        # Save new message
        new_msg = ChatMessage(
            session_id=msg.session_id,
            role="assistant",
            content=full_json,
        )
        db.add(new_msg)
        await db.commit()
        await db.refresh(new_msg)
        print(f'\nNew report saved: msg_id={new_msg.id}')

asyncio.run(main())
