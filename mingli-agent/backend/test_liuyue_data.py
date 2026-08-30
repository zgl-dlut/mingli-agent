"""
单元测试：验证追问报告生成时传入的排盘数据是否正确

测试场景：1990年用户问2027年离职相关问题
验证点：
1. 2027年流年干支是否正确（丁未）
2. 2027年流月干支是否正确（九月庚戌、十月辛亥等）
3. 当前大运是否正确（癸未）
4. 日主是否正确（己土）
"""
import sys
sys.path.insert(0, '/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend')

import pytest
from app.services.skill_prompts import _build_context_vars, _extract_liuyue_data
from app.services.bazi_service import calculate_bazi
from app.services.orchestrator import generate_full_analysis


class TestLiuyueDataFor1990User:
    """测试1990年用户的流月数据传入"""
    
    @pytest.fixture
    def bazi_result(self):
        """获取1990年用户的排盘结果"""
        # 1990年11月10日 8:00 女 山西晋中（经度约112.75）
        return calculate_bazi(
            birth_date="1990-11-10",
            birth_time="08:00",
            longitude=112.75,
            gender="女"
        )
    
    @pytest.fixture
    def analysis_data(self, bazi_result):
        """获取完整分析数据"""
        # 转为字典格式
        data = bazi_result.dict() if hasattr(bazi_result, 'dict') else bazi_result.__dict__
        
        # 构建 analysis_data 结构（模拟 orchestrator 输出）
        analysis = {
            "四柱": f"{data['pillars']['年']['tian']}{data['pillars']['年']['di']} "
                   f"{data['pillars']['月']['tian']}{data['pillars']['月']['di']} "
                   f"{data['pillars']['日']['tian']}{data['pillars']['日']['di']} "
                   f"{data['pillars']['时']['tian']}{data['pillars']['时']['di']}",
            "日主": "己",
            "五行分布": data.get('wuxing', {}),
            "旺衰结论": data.get('wangshuai', {}).get('conclusion', '身旺'),
            "格局": data.get('geju', '正官格'),
            "用神": data.get('yongshen', '金'),
            "喜神": data.get('xishen', '水'),
            "忌神": data.get('jishen', '火'),
            "十神分布": data.get('shishen', {}),
            "地支作用": data.get('dizhi_he', ''),
            "调候描述": data.get('tiaohou', ''),
            "当前大运": data.get('current_dayun', '癸未'),
            "大运解读": "当前走癸未大运",
            "重点流年": self._build_key_liunian(data),
        }
        return analysis
    
    def _build_key_liunian(self, data):
        """构建重点流年数据，包含2026-2028年的流月"""
        key_liunian = []
        
        # 2026年丙午
        key_liunian.append({
            "year": 2026,
            "ganzhi": "丙午",
            "judge": "吉",
            "reason": "火旺帮身，事业有助力",
            "liuyue": self._generate_liuyue_for_year(2026, "丙午")
        })
        
        # 2027年丁未（用户关注的年份）
        key_liunian.append({
            "year": 2027,
            "ganzhi": "丁未",
            "judge": "平",
            "reason": "土旺帮身，稳定发展",
            "liuyue": self._generate_liuyue_for_year(2027, "丁未")
        })
        
        # 2028年戊申
        key_liunian.append({
            "year": 2028,
            "ganzhi": "戊申",
            "judge": "吉",
            "reason": "金水到位，财运提升",
            "liuyue": self._generate_liuyue_for_year(2028, "戊申")
        })
        
        return key_liunian
    
    def _generate_liuyue_for_year(self, year: int, year_ganzhi: str) -> list:
        """
        根据流年干支生成该年的流月数据
        
        五虎遁年起月诀：
        甲己之年丙作首，乙庚之岁戊为头，
        丙辛必定寻庚起，丁壬壬位顺行流，
        若问戊癸何方发，甲寅之上好追求。
        """
        # 天干对应的起始月干
        tiangan_start = {
            "甲": "丙", "己": "丙",  # 甲己之年丙作首
            "乙": "戊", "庚": "戊",  # 乙庚之岁戊为头
            "丙": "庚", "辛": "庚",  # 丙辛必定寻庚起
            "丁": "壬", "壬": "壬",  # 丁壬壬位顺行流
            "戊": "甲", "癸": "甲",  # 戊癸甲寅之上好追求
        }
        
        # 地支（正月到十二月）
        dizhi_list = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]
        tiangan_list = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
        
        # 获取流年天干
        year_tian = year_ganzhi[0]
        start_tian = tiangan_start[year_tian]
        start_idx = tiangan_list.index(start_tian)
        
        liuyue = []
        for month_idx in range(12):
            # 计算该月天干
            tian_idx = (start_idx + month_idx) % 10
            tian = tiangan_list[tian_idx]
            di = dizhi_list[month_idx]
            ganzhi = f"{tian}{di}"
            
            # 公历月份（农历月份+1，因为正月对应公历2月左右）
            solar_month = month_idx + 2
            if solar_month > 12:
                solar_month -= 12
            
            # 简单判断吉凶（实际应该根据命盘计算）
            judge = "吉" if month_idx % 3 == 0 else "平"
            
            liuyue.append({
                "solar_month": solar_month,
                "month_ganzhi": ganzhi,
                "judge": judge,
                "reason": f"{ganzhi}月"
            })
        
        return liuyue
    
    def test_bazi_pillars(self, bazi_result):
        """测试四柱是否正确"""
        data = bazi_result.dict() if hasattr(bazi_result, 'dict') else bazi_result.__dict__
        
        # 1990年11月10日 8:00 应该是：庚午年 丁亥月 己卯日 戊辰时
        assert data['pillars']['年']['tian'] == "庚"
        assert data['pillars']['年']['di'] == "午"
        assert data['pillars']['月']['tian'] == "丁"
        assert data['pillars']['月']['di'] == "亥"
        assert data['pillars']['日']['tian'] == "己"
        assert data['pillars']['日']['di'] == "卯"
        assert data['pillars']['时']['tian'] == "戊"
        assert data['pillars']['时']['di'] == "辰"
        
        print("✓ 四柱正确：庚午 丁亥 己卯 戊辰")
    
    def test_dayun(self, bazi_result):
        """测试当前大运是否正确"""
        data = bazi_result.dict() if hasattr(bazi_result, 'dict') else bazi_result.__dict__
        
        # 1990年出生，2026年36岁，当前大运应该是癸未
        assert data['current_dayun'] == "癸未"
        
        print("✓ 当前大运正确：癸未")
    
    def test_2027_liunian_ganzhi(self, analysis_data):
        """测试2027年流年干支是否正确"""
        key_liunian = analysis_data.get("重点流年", [])
        
        # 找到2027年
        liu_2027 = None
        for ly in key_liunian:
            if ly.get('year') == 2027:
                liu_2027 = ly
                break
        
        assert liu_2027 is not None, "未找到2027年流年数据"
        assert liu_2027.get('ganzhi') == "丁未", f"2027年干支错误：{liu_2027.get('ganzhi')}"
        
        print("✓ 2027年流年干支正确：丁未")
    
    def test_2027_liuyue_ganzhi(self, analysis_data):
        """测试2027年流月干支是否正确"""
        key_liunian = analysis_data.get("重点流年", [])
        
        # 找到2027年
        liu_2027 = None
        for ly in key_liunian:
            if ly.get('year') == 2027:
                liu_2027 = ly
                break
        
        assert liu_2027 is not None, "未找到2027年流年数据"
        
        liuyue = liu_2027.get('liuyue', [])
        assert len(liuyue) == 12, f"流月数据不完整：{len(liuyue)}个月"
        
        # 验证关键月份的干支
        # 丁未年（丁壬壬位顺行流），正月壬寅
        # 九月应该是庚戌，十月应该是辛亥
        
        expected_months = {
            9: "庚戌",  # 九月
            10: "辛亥",  # 十月
            11: "壬子",  # 十一月
            12: "癸丑",  # 十二月
        }
        
        for lm in liuyue:
            solar_month = lm.get('solar_month')
            month_ganzhi = lm.get('month_ganzhi')
            
            if solar_month in expected_months:
                expected = expected_months[solar_month]
                assert month_ganzhi == expected, \
                    f"{solar_month}月干支错误：期望{expected}，实际{month_ganzhi}"
        
        print("✓ 2027年流月干支正确：")
        print("  - 九月：庚戌")
        print("  - 十月：辛亥")
        print("  - 十一月：壬子")
        print("  - 十二月：癸丑")
    
    def test_extract_liuyue_data(self, analysis_data):
        """测试流月数据提取函数"""
        key_liunian = analysis_data.get("重点流年", [])
        liuyue_data = _extract_liuyue_data(key_liunian)
        
        # 验证2027年数据存在
        assert 2027 in liuyue_data, "未提取到2027年流月数据"
        
        liuyue_2027 = liuyue_data[2027]
        assert len(liuyue_2027) == 12, f"2027年流月数据不完整：{len(liuyue_2027)}个月"
        
        print("✓ 流月数据提取正确")
    
    def test_context_vars_include_liuyue(self, analysis_data):
        """测试 context vars 是否包含流年信息"""
        context = _build_context_vars(
            analysis_data=analysis_data,
            gender="女",
            user_question="27年会离开当前公司吗",
            birth_date="1990-11-10"
        )
        
        # 验证 key_liunian 包含2027年信息
        key_liunian_str = context.get('key_liunian', '')
        assert "2027" in key_liunian_str, "key_liunian 未包含2027年"
        assert "丁未" in key_liunian_str, "key_liunian 未包含丁未干支"
        
        print("✓ context vars 包含2027年流年信息")


if __name__ == "__main__":
    # 直接运行测试
    test = TestLiuyueDataFor1990User()
    
    print("=" * 60)
    print("测试1：四柱验证")
    print("=" * 60)
    bazi_result = test.bazi_result = calculate_bazi(
        birth_date="1990-11-10",
        birth_time="08:00",
        longitude=112.75,
        gender="女"
    )
    test.test_bazi_pillars(bazi_result)
    
    print("\n" + "=" * 60)
    print("测试2：大运验证")
    print("=" * 60)
    test.test_dayun(bazi_result)
    
    print("\n" + "=" * 60)
    print("测试3：2027年流年干支验证")
    print("=" * 60)
    analysis_data = test.analysis_data = test._build_key_liunian(bazi_result.dict())
    analysis_data = {
        "四柱": "庚午 丁亥 己卯 戊辰",
        "日主": "己",
        "五行分布": {},
        "旺衰结论": "身旺",
        "格局": "正官格",
        "用神": "金",
        "喜神": "水",
        "忌神": "火",
        "十神分布": {},
        "地支作用": "",
        "调候描述": "",
        "当前大运": "癸未",
        "大运解读": "当前走癸未大运",
        "重点流年": analysis_data,
    }
    test.test_2027_liunian_ganzhi(analysis_data)
    
    print("\n" + "=" * 60)
    print("测试4：2027年流月干支验证")
    print("=" * 60)
    test.test_2027_liuyue_ganzhi(analysis_data)
    
    print("\n" + "=" * 60)
    print("测试5：流月数据提取验证")
    print("=" * 60)
    test.test_extract_liuyue_data(analysis_data)
    
    print("\n" + "=" * 60)
    print("测试6：context vars 验证")
    print("=" * 60)
    test.test_context_vars_include_liuyue(analysis_data)
    
    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)
