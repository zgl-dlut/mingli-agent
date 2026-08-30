"""临时脚本：检查1992-12-19人物的排盘数据状态"""
import asyncio
import json
from sqlalchemy import select
from app.db.session import async_session
from app.models.person import Person

async def check():
    async with async_session() as db:
        result = await db.execute(
            select(Person).where(Person.birth_date == '1992-12-19')
        )
        persons = result.scalars().all()
        for p in persons:
            print(f'ID: {p.id}, 姓名: {p.name}, 性别: {p.gender}')
            print(f'出生日期: {p.birth_date}, 出生时间: {p.birth_time}')
            has_bazi = p.bazi_data_json is not None
            print(f'bazi_data_json 是否存在: {has_bazi}')
            if has_bazi and isinstance(p.bazi_data_json, dict):
                keys = list(p.bazi_data_json.keys())
                print(f'bazi_data_json keys: {keys}')
                motto = p.bazi_data_json.get('命格箴言', 'N/A')
                print(f'命格箴言: {motto}')
                # 检查关键字段
                for k in ['四柱', '日主', '用神', '格局', '大运方向', '起运年龄']:
                    print(f'  {k}: {p.bazi_data_json.get(k, "N/A")}')
            print('---')

asyncio.run(check())
