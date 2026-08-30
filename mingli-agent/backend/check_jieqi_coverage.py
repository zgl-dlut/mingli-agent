"""检查数据库中用户出生年份分布，评估节气数据缺失影响"""
import sys
sys.path.insert(0, '.')
from sqlalchemy import select, func
from app.db.session import async_session
from app.models.person import Person
import asyncio

async def check():
    async with async_session() as db:
        # 获取所有用户的出生年份分布
        result = await db.execute(
            select(Person.birth_date, func.count()).group_by(Person.birth_date)
        )
        rows = result.all()
        
        # 按年份统计
        year_counts = {}
        for birth_date, count in rows:
            if birth_date:
                year = int(birth_date.split('-')[0])
                year_counts[year] = year_counts.get(year, 0) + count
        
        # 覆盖范围
        covered_years = list(range(1988, 1994)) + list(range(2023, 2046))
        uncovered_years = [y for y in range(1950, 2050) if y not in covered_years]
        
        covered_users = sum(v for k, v in year_counts.items() if k in covered_years)
        uncovered_users = sum(v for k, v in year_counts.items() if k in uncovered_years)
        total_users = sum(year_counts.values())
        
        print(f"总用户数: {total_users}")
        print(f"节气数据覆盖年份: {covered_years}")
        print(f"节气数据缺失年份: {uncovered_years}")
        print(f"\n覆盖范围内的用户: {covered_users}")
        print(f"缺失范围内的用户: {uncovered_users}")
        
        print(f"\n=== 按年份分布 ===")
        for year in sorted(year_counts.keys()):
            status = "✅" if year in covered_years else "❌"
            print(f"  {year}年: {year_counts[year]}人 {status}")

asyncio.run(check())
