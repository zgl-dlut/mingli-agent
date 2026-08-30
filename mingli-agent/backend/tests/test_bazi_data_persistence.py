"""
排盘数据持久化测试
验证 Person 和 Session 的排盘数据一致性
"""
import pytest
from datetime import datetime
from sqlalchemy import select
from app.models.person import Person
from app.models.session import ChatSession
from app.skills.orchestrator import generate_full_analysis


class TestBaziDataPersistence:
    """排盘数据持久化测试"""

    def test_person_model_has_bazi_data_field(self):
        """测试 Person 模型包含 bazi_data_json 字段"""
        # 验证字段存在
        assert hasattr(Person, 'bazi_data_json'), "Person 模型应包含 bazi_data_json 字段"
        
        # 验证字段类型
        from sqlalchemy import JSON
        field = Person.__table__.columns['bazi_data_json']
        assert isinstance(field.type, JSON), "bazi_data_json 应为 JSON 类型"
        
        # 验证字段可空
        assert field.nullable is True, "bazi_data_json 应为可空字段"

    def test_generate_full_analysis_returns_complete_data(self):
        """测试 generate_full_analysis 返回完整排盘数据"""
        bazi_data = generate_full_analysis(
            birth_date="1990-01-01",
            birth_time="12:00",
            longitude=116.4,
            latitude=39.9,
            gender="male",
            location="北京",
        )
        
        # 验证基础字段
        assert "四柱" in bazi_data
        assert "日主" in bazi_data
        assert "用神" in bazi_data
        assert "喜神" in bazi_data
        assert "忌神" in bazi_data
        
        # 验证命格箴言
        assert "命格箴言" in bazi_data
        assert "命格箴言标签" in bazi_data
        
        # 验证数据结构
        assert isinstance(bazi_data["四柱"], str)
        assert isinstance(bazi_data["命格箴言"], str)
        assert isinstance(bazi_data["命格箴言标签"], dict)

    def test_bazi_data_consistency(self):
        """测试相同输入生成相同的排盘数据（确定性）"""
        params = {
            "birth_date": "1990-01-01",
            "birth_time": "12:00",
            "longitude": 116.4,
            "latitude": 39.9,
            "gender": "male",
            "location": "北京",
        }
        
        # 生成两次
        bazi_data1 = generate_full_analysis(**params)
        bazi_data2 = generate_full_analysis(**params)
        
        # 验证关键字段一致
        assert bazi_data1["四柱"] == bazi_data2["四柱"]
        assert bazi_data1["日主"] == bazi_data2["日主"]
        assert bazi_data1["用神"] == bazi_data2["用神"]
        assert bazi_data1["命格箴言"] == bazi_data2["命格箴言"]

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
