import asyncio, json, sys
from collections import Counter
sys.path.insert(0, "/app")

TIANGAN_YANG = {'甲', '丙', '戊', '庚', '壬'}


def parse_year_gan(sizhu):
    if not sizhu:
        return None, None
    parts = str(sizhu).split()
    if not parts:
        return None, None
    yz = parts[0]
    return (yz[0] if len(yz) >= 2 else None), yz


def correct_direction(year_gan, gender):
    """用正确逻辑（兼容中英文gender）算应得大运方向。"""
    if not year_gan or not gender:
        return None
    yang = year_gan in TIANGAN_YANG
    g = str(gender).strip().lower()
    is_male = g in ("男", "male", "m", "1")
    is_female = g in ("女", "female", "f", "2", "0")
    if (is_male and yang) or (is_female and not yang):
        return "顺"
    if (is_female and yang) or (is_male and not yang):
        return "逆"
    return None


async def main():
    from app.db.session import async_session
    from app.models.person import Person
    from sqlalchemy import select
    async with async_session() as db:
        persons = (await db.execute(select(Person).order_by(Person.id))).scalars().all()
    print(f"总 person 数: {len(persons)}")

    gdist = Counter(p.gender for p in persons)
    print(f"gender 值分布: {dict(gdist)}")

    wrong = []      # 方向算反
    correct_ids = []  # 方向一致
    no_data = []    # 缺数据

    for p in persons:
        bz = p.bazi_data_json or {}
        sizhu = bz.get("四柱", "")
        db_dir = bz.get("大运方向", "")
        cur_dayun = bz.get("当前大运", "")
        year_gan, yz = parse_year_gan(sizhu)
        should = correct_direction(year_gan, p.gender)
        if not should or not db_dir:
            no_data.append((p.id, p.gender, sizhu, db_dir, cur_dayun, should))
            continue
        if should != db_dir:
            wrong.append((p.id, p.gender, yz, year_gan,
                          "阳" if year_gan in TIANGAN_YANG else "阴",
                          should, db_dir, cur_dayun))
        else:
            correct_ids.append(p.id)

    print(f"\n=== 方向算反: {len(wrong)} 个 ===")
    for pid, g, yz, yg, yy, should, dbd, cur in wrong:
        print(f"  #{pid} gender={g} 年柱={yz}({yy}年) 应={should} DB={dbd} 当前大运={cur}")

    print(f"\n=== 方向一致: {len(correct_ids)} 个 ===")
    print(f"  ids: {correct_ids}")

    print(f"\n=== 缺数据(无四柱/无大运方向): {len(no_data)} 个 ===")
    for pid, g, sz, dbd, cur, sh in no_data:
        print(f"  #{pid} gender={g} 四柱={sz!r} DB方向={dbd!r} 当前大运={cur!r} 应={sh}")

    # 汇总：被算反的按"应顺被逆/应逆被顺"分类
    if wrong:
        print("\n=== 算反类型分布 ===")
        wtype = Counter(f"应{sh}被算成{dbd}" for _, _, _, _, _, sh, dbd, _ in wrong)
        for k, v in wtype.items():
            print(f"  {k}: {v} 个")

asyncio.run(main())
