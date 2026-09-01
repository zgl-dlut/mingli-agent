"""
重算大运方向算反的 person（阳年男命/阴年女命应顺排，被 gender bug 算成逆排）。
幂等：方向已正确的跳过；重算后验证方向转顺，失败回滚。
回写 persons.bazi_data_json + 关联 chat_sessions.bazi_data_json。
容器内运行，host='mysql'。
"""
import pymysql
import json
import sys
import traceback

sys.path.insert(0, '/app')
from app.skills.orchestrator import generate_full_analysis

TIANGAN_YANG = {'甲', '丙', '戊', '庚', '壬'}


def parse_year_gan(sizhu):
    if not sizhu:
        return None
    parts = str(sizhu).split()
    return parts[0][0] if parts and len(parts[0]) >= 2 else None


def correct_direction(year_gan, gender):
    """正确逻辑（兼容中英文 gender）算应得大运方向。"""
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


def main():
    conn = pymysql.connect(
        host='mysql', user='mingli', password='mingli123',
        database='mingli', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
    recalc = skipped = failed = 0
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, birth_date, birth_time, gender, birth_location, "
            "birth_lat, birth_lng, bazi_data_json FROM persons ORDER BY id"
        )
        persons = cur.fetchall()
        print(f"总 person: {len(persons)}")

        for row in persons:
            pid = row['id']
            old = json.loads(row['bazi_data_json']) if row['bazi_data_json'] else {}
            sizhu = old.get('四柱', '')
            db_dir = old.get('大运方向', '')
            old_cur = old.get('当前大运', '')
            old_dl3 = [d.get('ganzhi') for d in (old.get('大运列表') or [])[:3]]
            yg = parse_year_gan(sizhu)
            should = correct_direction(yg, row['gender'])

            if not should or not db_dir:
                print(f"  #{pid} 缺数据 跳过")
                skipped += 1
                continue
            if db_dir == should:
                skipped += 1
                continue

            print(f"\n#{pid} gender={row['gender']} {sizhu}({yg}) "
                  f"DB方向={db_dir} 应={should} → 重算")
            print(f"  旧: 当前大运={old_cur} 列表前3={old_dl3}")
            try:
                new = generate_full_analysis(
                    birth_date=row['birth_date'],
                    birth_time=row['birth_time'],
                    longitude=float(row['birth_lng'] or 0),
                    latitude=float(row['birth_lat'] or 0),
                    gender=row['gender'],
                    location=row['birth_location'],
                )
            except Exception as e:
                print(f"  ❌ 重算失败: {e}")
                traceback.print_exc()
                failed += 1
                continue

            new_dir = new.get('大运方向', '')
            new_cur = new.get('当前大运', '')
            new_dl3 = [d.get('ganzhi') for d in (new.get('大运列表') or [])[:3]]
            print(f"  新: 方向={new_dir} 当前大运={new_cur} 列表前3={new_dl3}")
            if new_dir != should:
                print(f"  ⚠️ 重算后方向仍不对! 应={should} 实={new_dir} — 不回写")
                failed += 1
                continue

            # 回写 persons
            new_json = json.dumps(new, ensure_ascii=False)
            cur.execute(
                "UPDATE persons SET bazi_data_json=%s WHERE id=%s",
                (new_json, pid),
            )
            # 回写关联 chat_sessions
            cur.execute(
                "UPDATE chat_sessions SET bazi_data_json=%s WHERE person_id=%s",
                (new_json, pid),
            )
            conn.commit()
            recalc += 1
            print(f"  ✅ 已回写 person#{pid} + 关联 sessions")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 异常: {e}")
        traceback.print_exc()
    finally:
        conn.close()
        print(f"\n=== 完成: 重算 {recalc} 跳过 {skipped} 失败 {failed} ===")


if __name__ == "__main__":
    main()
