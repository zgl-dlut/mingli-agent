"""
排盘数据流程测试
验证人物创建、首次报告、追问报告的排盘数据传递正确性
"""
import pytest
from datetime import datetime
from app.skills.orchestrator import generate_full_analysis


class TestBaziDataFlow:
    """排盘数据流程测试"""

    def test_generate_full_analysis_includes_motto(self):
        """测试 generate_full_analysis 生成的排盘数据包含命格箴言"""
        # 准备测试数据
        birth_date = "1990-01-01"
        birth_time = "12:00"
        longitude = 116.4
        latitude = 39.9
        gender = "male"
        location = "北京"

        # 执行排盘
        bazi_data = generate_full_analysis(
            birth_date=birth_date,
            birth_time=birth_time,
            longitude=longitude,
            latitude=latitude,
            gender=gender,
            location=location,
        )

        # 验证排盘数据结构
        assert bazi_data is not None, "排盘数据不应为空"
        assert isinstance(bazi_data, dict), "排盘数据应为字典类型"

        # 验证命格箴言字段存在
        assert "命格箴言" in bazi_data, "排盘数据应包含命格箴言字段"
        assert "命格箴言标签" in bazi_data, "排盘数据应包含命格箴言标签字段"

        # 验证命格箴言内容
        motto = bazi_data["命格箴言"]
        assert motto is not None, "命格箴言不应为空"
        assert isinstance(motto, str), "命格箴言应为字符串"
        assert len(motto) > 0, "命格箴言应包含内容"

        # 验证命格箴言标签
        motto_tags = bazi_data["命格箴言标签"]
        assert motto_tags is not None, "命格箴言标签不应为空"
        assert isinstance(motto_tags, dict), "命格箴言标签应为字典"

        # 验证其他关键字段
        assert "四柱" in bazi_data, "排盘数据应包含四柱"
        assert "日主" in bazi_data, "排盘数据应包含日主"
        assert "用神" in bazi_data, "排盘数据应包含用神"
        assert "喜神" in bazi_data, "排盘数据应包含喜神"
        assert "忌神" in bazi_data, "排盘数据应包含忌神"

    def test_bazi_data_structure_completeness(self):
        """测试排盘数据结构的完整性"""
        bazi_data = generate_full_analysis(
            birth_date="1995-06-15",
            birth_time="08:30",
            longitude=121.5,
            latitude=31.2,
            gender="female",
            location="上海",
        )

        # 验证所有必需字段
        required_fields = [
            "四柱", "日主", "月令", "旺衰结论", "旺衰详情",
            "格局", "格局详情", "用神", "喜神", "忌神",
            "调候描述", "地支作用", "十神分布", "五行分布",
            "纳音", "大运方向", "起运年龄", "当前大运", "大运解读",
            "重点流年", "五行应用", "占星数据", "生肖",
            "命格箴言", "命格箴言标签"
        ]

        for field in required_fields:
            assert field in bazi_data, f"排盘数据应包含字段: {field}"

    def test_motto_generation_consistency(self):
        """测试相同输入生成相同的命格箴言（确定性）"""
        params = {
            "birth_date": "1988-08-08",
            "birth_time": "20:00",
            "longitude": 113.2,
            "latitude": 23.1,
            "gender": "male",
            "location": "广州",
        }

        # 执行两次排盘
        bazi_data1 = generate_full_analysis(**params)
        bazi_data2 = generate_full_analysis(**params)

        # 验证命格箴言一致
        assert bazi_data1["命格箴言"] == bazi_data2["命格箴言"], \
            "相同输入应生成相同的命格箴言"

    def test_different_gender_different_motto(self):
        """测试不同性别可能生成不同的命格箴言"""
        base_params = {
            "birth_date": "1992-03-15",
            "birth_time": "10:00",
            "longitude": 104.0,
            "latitude": 30.6,
            "location": "成都",
        }

        # 男性排盘
        bazi_male = generate_full_analysis(gender="male", **base_params)
        # 女性排盘
        bazi_female = generate_full_analysis(gender="female", **base_params)

        # 验证排盘数据都包含命格箴言
        assert "命格箴言" in bazi_male, "男性排盘应包含命格箴言"
        assert "命格箴言" in bazi_female, "女性排盘应包含命格箴言"

        # 注意：性别影响大运方向，但不一定影响命格箴言
        # 这里只验证两者都能正常生成


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
