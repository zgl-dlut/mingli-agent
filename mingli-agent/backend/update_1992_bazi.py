"""
更新 1992 年 12 月 19 日 19:35 真实用户的排盘数据

四柱：壬申 壬子 己巳 甲戌
对比测测 App 数据，输出更新前后差异
"""
import sys
import os
import json
import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.bazi_service import calculate_kongwang, calculate_changsheng
from app.skills.divination.shensha_skill import calculate_shensha, calculate_tiangan_he
from app.skills.divination.wangshuai_skill import calculate_wangshuai

# 四柱数据
pillars = {
    "年": {"tian": "壬", "di": "申"},
    "月": {"tian": "壬", "di": "子"},
    "日": {"tian": "己", "di": "巳"},
    "时": {"tian": "甲", "di": "戌"},
}

day_tian = "己"
day_di = "巳"
month_di = "子"
year_di = "申"
year_tian = "壬"
year_nayin = "剑锋金"

# 藏干
canggan = {
    "年": ["庚", "壬", "戊"],
    "月": ["癸"],
    "日": ["丙", "庚", "戊"],
    "时": ["戊", "辛", "丁"],
}

# 五行统计
wuxing = {"金": 2, "木": 1, "水": 3, "火": 1, "土": 3}


def main():
    print("=" * 70)
    print("1992年12月19日 19:35 排盘数据更新")
    print("四柱：壬申 壬子 己巳 甲戌")
    print("=" * 70)

    # 1. 计算新排盘数据
    kongwang = calculate_kongwang(day_tian, day_di)
    changsheng = calculate_changsheng(day_tian, pillars)
    shensha = calculate_shensha(pillars, day_tian, day_di, month_di, year_di, year_tian, year_nayin, kongwang)
    tiangan_he = calculate_tiangan_he(pillars)
    wangshuai = calculate_wangshuai(day_tian, day_di, month_di, pillars, canggan, wuxing)

    print("\n【新排盘数据】")
    print(f"  空亡: {kongwang}")
    print(f"  长生十二宫: {changsheng}")
    print(f"  神煞:")
    for pos in ["年", "月", "日", "时"]:
        print(f"    {pos}: {shensha.get(pos, [])}")
    print(f"  天干五合: {tiangan_he}")
    print(f"  旺衰结论: {wangshuai.get('conclusion')}")
    print(f"  旺衰总分: {wangshuai.get('total_score')}")

    # 2. 查询数据库旧数据
    conn = pymysql.connect(
        host='localhost', user='mingli', password='mingli123',
        database='mingli', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, bazi_data_json FROM persons WHERE bazi_data_json IS NOT NULL"
        )
        rows = cursor.fetchall()

        # 找到四柱匹配的记录
        target_rows = []
        for row in rows:
            bazi_data = json.loads(row['bazi_data_json'])
            if bazi_data.get("四柱") == "壬申 壬子 己巳 甲戌":
                target_rows.append(row)
            elif bazi_data.get("四柱") == "甲戌 甲戌 壬申 己酉":
                # 也处理这个（之前的测试数据）
                pass

        if not target_rows:
            print("\n️  数据库中未找到四柱为「壬申 壬子 己巳 甲戌」的记录")
            print("   该用户可能尚未创建人物，跳过更新")
            return

        print(f"\n找到 {len(target_rows)} 条匹配记录")

        for row in target_rows:
            person_id = row['id']
            user_id = row['user_id']
            old_bazi = json.loads(row['bazi_data_json'])

            print(f"\n{'─' * 70}")
            print(f"person_id={person_id}, user_id={user_id}")
            print(f"{'─' * 70}")

            # 对比旧数据
            print(f"\n【更新前】")
            print(f"  旺衰结论: {old_bazi.get('旺衰结论', 'N/A')}")
            print(f"  用神: {old_bazi.get('用神', 'N/A')}")
            print(f"  喜神: {old_bazi.get('喜神', 'N/A')}")
            print(f"  忌神: {old_bazi.get('忌神', 'N/A')}")
            print(f"  空亡: {old_bazi.get('空亡', 'N/A')}")
            print(f"  长生十二宫: {old_bazi.get('长生十二宫', 'N/A')}")
            print(f"  神煞: {old_bazi.get('神煞', 'N/A')}")
            print(f"  天干五合: {old_bazi.get('天干五合', 'N/A')}")

            # 更新数据
            old_bazi['空亡'] = kongwang
            old_bazi['长生十二宫'] = changsheng
            old_bazi['神煞'] = shensha
            old_bazi['天干五合'] = tiangan_he

            # 更新旺衰结论
            old_bazi['旺衰结论'] = wangshuai.get('conclusion', '')
            old_bazi['旺衰详情'] = wangshuai

            new_json = json.dumps(old_bazi, ensure_ascii=False)

            # 执行更新
            cursor.execute(
                "UPDATE persons SET bazi_data_json = %s WHERE id = %s",
                (new_json, person_id)
            )

            print(f"\n【更新后】")
            print(f"  旺衰结论: {old_bazi.get('旺衰结论')}")
            print(f"  用神: {old_bazi.get('用神')}")
            print(f"  喜神: {old_bazi.get('喜神')}")
            print(f"  忌神: {old_bazi.get('忌神')}")
            print(f"  空亡: {old_bazi.get('空亡')}")
            print(f"  长生十二宫: {old_bazi.get('长生十二宫')}")
            print(f"  神煞:")
            for pos in ["年", "月", "日", "时"]:
                print(f"    {pos}: {old_bazi.get('神煞', {}).get(pos, [])}")
            print(f"  天干五合: {old_bazi.get('天干五合')}")

            # 差异总结
            print(f"\n【差异总结】")
            old_conclusion = old_bazi.get('旺衰结论', '')
            new_conclusion = wangshuai.get('conclusion', '')
            if old_conclusion != new_conclusion:
                print(f"  ️  旺衰结论: {old_conclusion} → {new_conclusion}")
            else:
                print(f"  ✅ 旺衰结论: {old_conclusion}（未变）")

            if old_bazi.get('空亡') != 'N/A' and old_bazi.get('空亡'):
                print(f"  ✅ 空亡: 已更新")
            else:
                print(f"  ➕ 空亡: 新增字段")

            if old_bazi.get('长生十二宫') != 'N/A' and old_bazi.get('长生十二宫'):
                print(f"  ✅ 长生十二宫: 已更新")
            else:
                print(f"  ➕ 长生十二宫: 新增字段")

            if old_bazi.get('神煞') != 'N/A' and old_bazi.get('神煞'):
                print(f"  ✅ 神煞: 已更新")
            else:
                print(f"  ➕ 神煞: 新增字段")

            if old_bazi.get('天干五合') != 'N/A' and old_bazi.get('天干五合'):
                print(f"  ✅ 天干五合: 已更新")
            else:
                print(f"  ➕ 天干五合: 新增字段")

        conn.commit()
        print(f"\n✅ 成功更新 {len(target_rows)} 条记录")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
