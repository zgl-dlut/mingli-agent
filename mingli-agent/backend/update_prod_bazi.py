"""
在生产服务器上批量更新 18610351374 用户的排盘数据
在容器内运行，host 用 'mysql'
"""
import pymysql
import json
import sys
sys.path.insert(0, '/app')
from app.skills.orchestrator import generate_full_analysis

conn = pymysql.connect(
    host='mysql', user='mingli', password='mingli123',
    database='mingli', charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT p.id, p.birth_date, p.birth_time, p.gender, "
        "p.birth_location, p.birth_lat, p.birth_lng, p.bazi_data_json "
        "FROM persons p JOIN users u ON p.user_id = u.id "
        "WHERE u.phone = '18610351374'"
    )
    rows = cursor.fetchall()

    print("=" * 70)
    print(f"更新 18610351374 用户的排盘数据 ({len(rows)}条)")
    print("=" * 70)

    updated = 0
    errors = 0

    for row in rows:
        pid = row['id']
        bd = row['birth_date']
        bt = row['birth_time']
        g = row['gender']
        loc = row['birth_location']
        lat = float(row['birth_lat'] or 0)
        lng = float(row['birth_lng'] or 0)
        old = json.loads(row['bazi_data_json']) if row['bazi_data_json'] else {}

        print(f"\n{'─' * 70}")
        print(f"person_id={pid}, {bd} {bt}, {g}, {loc}")
        print(f"{'─' * 70}")

        old_sz = old.get('四柱', 'N/A')
        old_ws = old.get('旺衰结论', 'N/A')
        old_mt = old.get('命格箴言', 'N/A')
        old_kw = old.get('空亡', 'N/A')
        old_cs = old.get('长生十二宫', 'N/A')
        old_ss = old.get('神煞', 'N/A')
        old_th = old.get('天干五合', 'N/A')

        print(f"\n【更新前】")
        print(f"  四柱: {old_sz}")
        print(f"  旺衰: {old_ws}")
        print(f"  箴言: {old_mt}")
        print(f"  空亡: {old_kw}")
        print(f"  长生: {old_cs}")
        print(f"  神煞: {old_ss}")
        print(f"  五合: {old_th}")

        try:
            new = generate_full_analysis(
                birth_date=bd, birth_time=bt,
                longitude=lng, latitude=lat,
                gender=g, location=loc,
            )
        except Exception as e:
            print(f"  ❌ 生成失败: {e}")
            import traceback
            traceback.print_exc()
            errors += 1
            continue

        new_sz = new.get('四柱', 'N/A')
        new_ws = new.get('旺衰结论', 'N/A')
        new_mt = new.get('命格箴言', 'N/A')
        new_kw = new.get('空亡', 'N/A')
        new_cs = new.get('长生十二宫', 'N/A')
        new_ss = new.get('神煞', 'N/A')
        new_th = new.get('天干五合', 'N/A')

        print(f"\n【更新后】")
        print(f"  四柱: {new_sz}")
        print(f"  旺衰: {new_ws}")
        print(f"  箴言: {new_mt}")
        print(f"  空亡: {new_kw}")
        print(f"  长生: {new_cs}")
        print(f"  神煞: {new_ss}")
        print(f"  五合: {new_th}")

        print(f"\n【差异】")
        chg = []
        if old_ws != new_ws:
            chg.append(f"  ⚠️ 旺衰: {old_ws} → {new_ws}")
        if old_mt != new_mt:
            chg.append(f"  🔄 箴言: {old_mt} → {new_mt}")
        if old_kw == 'N/A' and new_kw != 'N/A':
            chg.append(f"  ➕ 空亡: 新增 {new_kw}")
        elif old_kw != new_kw:
            chg.append(f"  🔄 空亡: {old_kw} → {new_kw}")
        if old_cs == 'N/A' and new_cs != 'N/A':
            chg.append(f"  ➕ 长生十二宫: 新增")
        elif old_cs != new_cs:
            chg.append(f"  🔄 长生十二宫: 已更新")
        if old_ss == 'N/A' and new_ss != 'N/A':
            chg.append(f"  ➕ 神煞: 新增")
        elif old_ss != new_ss:
            chg.append(f"  🔄 神煞: 已更新")
        if old_th == 'N/A' and new_th != 'N/A':
            chg.append(f"  ➕ 天干五合: 新增 {new_th}")
        elif old_th != new_th:
            chg.append(f"  🔄 天干五合: 已更新")
        if chg:
            for c in chg:
                print(c)
        else:
            print("  ✅ 无变化")

        cursor.execute(
            "UPDATE persons SET bazi_data_json = %s WHERE id = %s",
            (json.dumps(new, ensure_ascii=False), pid)
        )
        updated += 1
        print(f"\n  ✅ 数据库已更新")

    conn.commit()
    print(f"\n{'=' * 70}")
    print(f"✅ 成功 {updated} 条, 失败 {errors} 条")
    print(f"{'=' * 70}")

except Exception as e:
    conn.rollback()
    print(f"\n❌ 批量更新失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()
