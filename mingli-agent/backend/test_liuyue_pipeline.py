"""
验证流月数据链路：从排盘算法到 prompt 传入
"""
import sys
sys.path.insert(0, '/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend')

from app.services.bazi_service import calculate_bazi
from app.skills.orchestrator import generate_full_analysis
from app.services.skill_prompts import _extract_liuyue_data
import json


def test_liuyue_data_pipeline():
    """测试流月数据从排盘到 prompt 的完整链路"""
    
    # 1. 排盘
    print("=== 1. 排盘 ===")
    bazi_result = calculate_bazi(
        birth_date="1990-11-10",
        birth_time="08:00",
        longitude=112.75,
        gender="女"
    )
    bazi_data = bazi_result.dict() if hasattr(bazi_result, 'dict') else bazi_result.__dict__
    
    print(f"四柱: {bazi_data['pillars']['年']['tian']}{bazi_data['pillars']['年']['di']} "
          f"{bazi_data['pillars']['月']['tian']}{bazi_data['pillars']['月']['di']} "
          f"{bazi_data['pillars']['日']['tian']}{bazi_data['pillars']['日']['di']} "
          f"{bazi_data['pillars']['时']['tian']}{bazi_data['pillars']['时']['di']}")
    print(f"日主: {bazi_data.get('日主', 'N/A')}")
    print()
    
    # 2. 生成完整分析数据
    print("=== 2. 生成完整分析数据 ===")
    analysis_data = generate_full_analysis(
        birth_date="1990-11-10",
        birth_time="08:00",
        longitude=112.75,
        latitude=37.69,
        gender="女",
        location="山西省晋中市"
    )
    
    # 3. 检查重点流年
    print("=== 3. 检查重点流年 ===")
    key_liunian = analysis_data.get("重点流年", [])
    
    print(f"重点流年总数: {len(key_liunian)}")
    print(f"前5年: {[ly.get('year') for ly in key_liunian[:5]]}")
    print()
    
    # 找到2027年
    liu_2027 = None
    for ly in key_liunian:
        if ly.get('year') == 2027:
            liu_2027 = ly
            break
    
    if not liu_2027:
        print("❌ 未找到2027年流年数据")
        return
    
    print(f"2027年流年干支: {liu_2027.get('ganzhi')}")
    print(f"2027年流年吉凶: {liu_2027.get('judge')}")
    print(f"2027年流月数据: {liu_2027.get('liuyue', [])}")
    print()
    
    # 4. 检查流月数据
    print("=== 4. 检查2027年流月数据 ===")
    liuyue = liu_2027.get('liuyue', [])
    
    if not liuyue:
        print("❌ 2027年没有流月数据")
        return
    
    print(f"流月数据条数: {len(liuyue)}")
    print()
    
    # 5. 验证关键月份的干支
    print("=== 5. 验证关键月份干支 ===")
    # 2027年丁未年，根据五虎遁：丁年正月是壬寅
    # 正月(2月): 壬寅, 二月(3月): 癸卯, 三月(4月): 甲辰, 四月(5月): 乙巳
    # 五月(6月): 丙午, 六月(7月): 丁未, 七月(8月): 戊申, 八月(9月): 己酉
    # 九月(10月): 庚戌, 十月(11月): 辛亥, 十一月(12月): 壬子, 十二月(1月): 癸丑
    expected_months = {
        9: "己酉",   # 八月（公历9月）
        10: "庚戌",  # 九月（公历10月）
        11: "辛亥",  # 十月（公历11月）
        12: "壬子",  # 十一月（公历12月）
    }
    
    for lm in liuyue:
        solar_month = lm.get('solar_month')
        month_ganzhi = lm.get('month_ganzhi')
        
        if solar_month in expected_months:
            expected = expected_months[solar_month]
            status = "✓" if month_ganzhi == expected else "✗"
            print(f"{status} {solar_month}月: {month_ganzhi} (期望: {expected})")
    
    print()
    
    # 6. 检查 _extract_liuyue_data 提取结果
    print("=== 6. 检查 _extract_liuyue_data 提取结果 ===")
    liuyue_data = _extract_liuyue_data(key_liunian)
    
    if 2027 not in liuyue_data:
        print("❌ _extract_liuyue_data 未提取到2027年流月数据")
        return
    
    liuyue_2027 = liuyue_data[2027]
    print(f"提取到的2027年流月数据条数: {len(liuyue_2027)}")
    
    # 验证提取的数据
    for lm in liuyue_2027:
        solar_month = lm.get('solar_month')
        month_ganzhi = lm.get('month_ganzhi')
        
        if solar_month in expected_months:
            expected = expected_months[solar_month]
            status = "✓" if month_ganzhi == expected else "✗"
            print(f"{status} 提取的{solar_month}月: {month_ganzhi} (期望: {expected})")
    
    print()
    print("=== 结论 ===")
    print("如果所有验证都通过，说明传入的流月数据是正确的。")
    print("如果报告中的流月干支与传入数据不一致，说明是 LLM 编造了干支。")


if __name__ == "__main__":
    test_liuyue_data_pipeline()
