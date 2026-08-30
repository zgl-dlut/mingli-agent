"""删除 1990 和 1992 年出生的人物及其关联数据"""
import asyncio
from sqlalchemy import select
from app.db.session import async_session
from app.models.person import Person
from app.models.session import ChatSession
from app.models.message import ChatMessage


async def delete_persons_by_birth_year(years: list[int]):
    """删除指定年份出生的人物及其关联数据"""
    from sqlalchemy import or_
    
    async with async_session() as db:
        # 查找指定年份出生的人物
        conditions = [Person.birth_date.like(f'{year}%') for year in years]
        result = await db.execute(
            select(Person).where(or_(*conditions))
        )
        persons = result.scalars().all()

        print(f"找到 {len(persons)} 个待删除人物:")
        for p in persons:
            print(f"  ID={p.id}, 姓名={p.name}, 出生={p.birth_date}")

        # 删除每个人物及其关联数据
        for person in persons:
            print(f"\n删除人物 ID={person.id}...")

            # 删除关联的 ChatMessage
            session_result = await db.execute(
                select(ChatSession).where(ChatSession.person_id == person.id)
            )
            session = session_result.scalar_one_or_none()

            if session:
                print(f"  删除会话 ID={session.id} 的消息...")
                await db.execute(
                    ChatMessage.__table__.delete().where(ChatMessage.session_id == session.id)
                )
                await db.delete(session)
                print(f"  已删除会话")

            await db.delete(person)
            print(f"  已删除人物")

        await db.commit()
        print("\n删除完成!")

        # 验证删除结果
        result = await db.execute(select(Person))
        remaining = result.scalars().all()
        print(f"\n剩余人物数: {len(remaining)}")
        for p in remaining:
            print(f"  ID={p.id}, 姓名={p.name}, 出生={p.birth_date}")


if __name__ == "__main__":
    asyncio.run(delete_persons_by_birth_year([1990, 1992]))
