"""
批量更新所有内测用户的排盘数据

使用 generate_full_analysis 重新生成完整排盘（含命格箴言、神煞、空亡等），
对比更新前后差异，更新数据库。
"""
import sys
import os
import json
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.skills.orchestrator import generate_full_analysis


def main():
    conn = pymysql.connect(
        host='localhost', user='mingli', password='mingli123',
        database='mingli', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, name, gender, birth_date, birth_time, "
            "birth_location, birth_lat, birth_lng, bazi_data_json "
            "FROM persons WHERE bazi_data_json IS NOT NULL"
        )
        rows = cursor.fetchall()

        print("=" * 70)
        print(f"批量更新排盘数据 ({len(rows)}条)")
        print("=" * 70)

        updated_count = 0
        error_count = 0

        for row in rows:
            person_id = row['id']
            user_id = row['user_id']
            name = row['name']
            gender = row['gender']
            birth_date = row['birth_date']
            birth_time = row['birth_time']
            birth_location = row['birth_location']
            lat = row['birth_lat'] or 0.0
            lng = row['birth_lng'] or 0.0

            old_bazi = json.loads(row['bazi_data_json']) if row['bazi_data_json'] else {}

            print(f"\n{'─' * 70}")
            print(f"person_id={person_id}, user_id={user_id}, name={name}")
            print(f"生辰: {birth_date} {birth_time}, {gender}, {birth_location}")
            print(f"{'─' * 70}")

            # 打印旧数据摘要
            old_sizhu = old_bazi.get("四柱", "N/A")
            old_wangshuai = old_bazi.get("旺衰结论", "N/A")
            old_motto = old_bazi.get("命格箴言", "N/A")
            old_yongshen = old_bazi.get("用神", "N/A")
            old_xishen = old_bazi.get("喜神", "N/A")
            old_jishen = old_bazi.get("忌神", "N/A")
            old_kongwang = old_bazi.get("空亡", "N/A")
            old_shensha = old_bazi.get("神煞", "N/A")
            old_tiangan_he = old_bazi.get("天干五合", "N/A")
            old_changsheng = old_bazi.get("长生十二宫", "N/A")

            print(f"\n【更新前】")
            print(f"  四柱: {old_sizhu}")
            print(f"  旺衰结论: {old_wangshuai}")
            print(f"  命格箴言: {old_motto}")
            print(f"  用神: {old_yongshen}")
            print(f"  喜神: {old_xishen}")
            print(f"  忌神: {old_jishen}")
            print(f"  空亡: {old_kongwang}")
            print(f"  长生十二宫: {old_changsheng}")
            print(f"  神煞: {old_shensha}")
            print(f"  天干五合: {old_tiangan_he}")

            # 重新生成排盘数据
            try:
                new_bazi = generate_full_analysis(
                    birth_date=birth_date,
                    birth_time=birth_time,
                    longitude=lng,
                    latitude=lat,
                    gender=gender,
                    location=birth_location,
                )
            except Exception as e:
                print(f"\n  ❌ 重新生成失败: {e}")
                import traceback
                traceback.print_exc()
                error_count += 1
                continue

            # 打印新数据摘要
            new_sizhu = new_bazi.get("四柱", "N/A")
            new_wangshuai = new_bazi.get("旺衰结论", "N/A")
            new_motto = new_bazi.get("命格箴言", "N/A")
            new_yongshen = new_bazi.get("用神", "N/A")
            new_xishen = new_bazi.get("喜神", "N/A")
            new_jishen = new_bazi.get("忌神", "N/A")
            new_kongwang = new_bazi.get("空亡", "N/A")
            new_shensha = new_bazi.get("神煞", "N/A")
            new_tiangan_he = new_bazi.get("天干五合", "N/A")
            new_changsheng = new_bazi.get("长生十二宫", "N/A")

            print(f"\n【更新后】")
            print(f"  四柱: {new_sizhu}")
            print(f"  旺衰结论: {new_wangshuai}")
            print(f"  命格箴言: {new_motto}")
            print(f"  用神: {new_yongshen}")
            print(f"  喜神: {new_xishen}")
            print(f"  忌神: {new_jishen}")
            print(f"  空亡: {new_kongwang}")
            print(f"  长生十二宫: {new_changsheng}")
            print(f"  神煞: {new_shensha}")
            print(f"  天干五合: {new_tiangan_he}")

            # 差异对比
            print(f"\n【差异对比】")
            changes = []
            if old_wangshuai != new_wangshuai:
                changes.append(f"  ⚠️  旺衰结论: {old_wangshuai} → {new_wangshuai}")
            if old_motto != new_motto:
                changes.append(f"  ️  命格箴言: {old_motto} → {new_motto}")
            if old_yongshen != new_yongshen:
                changes.append(f"  ⚠️  用神: {old_yongshen} → {new_yongshen}")
            if old_xishen != new_xishen:
                changes.append(f"  ⚠️  喜神: {old_xishen} → {new_xishen}")
            if old_jishen != new_jishen:
                changes.append(f"  ⚠️  忌神: {old_jishen} → {new_jishen}")
            if old_kongwang == "N/A" and new_kongwang != "N/A":
                changes.append(f"  ➕ 空亡: 新增 {new_kongwang}")
            if old_changsheng == "N/A" and new_changsheng != "N/A":
                changes.append(f"  ➕ 长生十二宫: 新增 {new_changsheng}")
            if old_shensha == "N/A" and new_shensha != "N/A":
                changes.append(f"   神煞: 新增")
            elif old_shensha != new_shensha:
                changes.append(f"  🔄 神煞: 已更新")
            if old_tiangan_he == "N/A" and new_tiangan_he != "N/A":
                changes.append(f"  ➕ 天干五合: 新增 {new_tiangan_he}")
            elif old_tiangan_he != new_tiangan_he:
                changes.append(f"   天干五合: 已更新")

            if changes:
                for c in changes:
                    print(c)
            else:
                print(f"  ✅ 无变化")

            # 更新数据库
            new_json = json.dumps(new_bazi, ensure_ascii=False)
            cursor.execute(
                "UPDATE persons SET bazi_data_json = %s WHERE id = %s",
                (new_json, person_id)
            )
            updated_count += 1

        conn.commit()
        print(f"\n{'=' * 70}")
        print(f"✅ 成功更新 {updated_count} 条记录")
        if error_count > 0:
            print(f"❌ 失败 {error_count} 条记录")
        print(f"{'=' * 70}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 批量更新失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
