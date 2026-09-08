"""一次性修复脚本：农历用户生辰展示错误（公历日期挂"农历"标签）。

背景：早期版本创建农历人物时——
1. persons.name 自动名用的是农历转公历后的日期（如农历2000-06-09 → name="2000-07-10 08:15"），
   历史列表/对话头部显示公历日期却挂"农历"标签；
2. 建盘时写入 chat_messages 的首条用户消息同样是
   "出生时间：2000-07-10 08:15(农历)..."，公历日期+农历标签。

本脚本：
- 遍历 calendar_type='lunar' 的人物
- name 仍是公历自动名（"{birth_date} {birth_time}"）的，改为农历日期自动名
  （用户自定义昵称不动）
- 该人物所有会话中 role=user 且 content 以"出生时间："开头的消息，
  把其中的公历日期替换为农历日期（出生地点/性别等其余内容不动）

幂等：已修复过的记录 name 不再匹配公历自动名、消息中也无公历日期前缀，重复跑无副作用。
"""
import asyncio

from sqlalchemy import select

from app.core.lunar_utils import get_display_birth_date
from app.db.session import async_session
from app.models.message import ChatMessage
from app.models.person import Person
from app.models.session import ChatSession


async def fix():
    fixed_persons = 0
    fixed_messages = 0
    skipped_custom_name = 0
    async with async_session() as db:
        result = await db.execute(select(Person).where(Person.calendar_type == "lunar"))
        persons = result.scalars().all()
        print(f"[lunar-fix] 共 {len(persons)} 个农历人物")

        for p in persons:
            lunar_date = get_display_birth_date(p.birth_date, "lunar")
            auto_solar_name = f"{p.birth_date} {p.birth_time}"
            new_name = f"{lunar_date} {p.birth_time}"

            # 1. 修人物自动名（仅公历自动名模式；自定义昵称跳过）
            if p.name == auto_solar_name:
                print(f"[lunar-fix] person#{p.id} name: {p.name} -> {new_name}")
                p.name = new_name
                fixed_persons += 1
            else:
                skipped_custom_name += 1
                print(f"[lunar-fix] person#{p.id} name 非自动名({p.name})，跳过")

            # 2. 修首条/补发的"出生时间"用户消息
            sess_result = await db.execute(
                select(ChatMessage)
                .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                .where(ChatSession.person_id == p.id)
                .where(ChatMessage.role == "user")
                .where(ChatMessage.content.like("出生时间：%"))
            )
            messages = sess_result.scalars().all()
            old_prefix = f"出生时间：{p.birth_date} {p.birth_time}(农历)"
            new_prefix = f"出生时间：{lunar_date} {p.birth_time}(农历)"
            for msg in messages:
                if old_prefix in msg.content:
                    msg.content = msg.content.replace(old_prefix, new_prefix, 1)
                    fixed_messages += 1
                    print(f"[lunar-fix] message#{msg.id} 日期已改为农历 {lunar_date}")

        await db.commit()

    print(
        f"[lunar-fix] 完成：修复人物名 {fixed_persons} 个（自定义昵称跳过 {skipped_custom_name}），"
        f"修复消息 {fixed_messages} 条"
    )


if __name__ == "__main__":
    asyncio.run(fix())
