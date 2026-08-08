"""
validate_user_question 回归测试
确保无效/无关问题被正确拦截，有效命理问题正常通过
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.skill_prompts import validate_user_question


class TestValidateQuestion:
    """问题验证测试集"""

    # ---------- 无效问题 ----------

    @pytest.mark.parametrize("question", [
        "",
        "   ",
    ])
    def test_empty_question(self, question):
        is_valid, msg = validate_user_question(question)
        assert is_valid is False
        assert "不扣除积分" in msg

    @pytest.mark.parametrize("question", [
        "今天北京天气怎么样？",
        "气温多少度",
        "帮我写一个Python代码实现快速排序",
        "帮我预测一下今天的彩票号码",
        "推荐一家好吃的火锅店",
        "帮我翻译这句话成英语",
        "这个游戏攻略怎么走",
        "今天温度多少度",
    ])
    def test_irrelevant_questions(self, question):
        is_valid, msg = validate_user_question(question)
        assert is_valid is False, f"问题「{question}」应被拦截，但通过了"
        assert "不扣除积分" in msg

    @pytest.mark.parametrize("question", [
        "嗯嗯",
        "好的",
    ])
    def test_meaningless_input(self, question):
        is_valid, msg = validate_user_question(question)
        assert is_valid is False
        assert "不扣除积分" in msg

    # ---------- 有效问题 ----------

    @pytest.mark.parametrize("question", [
        "我今年的事业运势如何？适合跳槽吗？",
        "我什么时候能遇到正缘？",
        "我的财运什么时候能好转？",
        "健康方面需要注意什么？",
        "帮我分析下未来几年的流年运势",
        "看看运势",
        "我的手机店生意会好吗？",  # 修饰语豁免：手机(修饰)+店(豁免后缀)
    ])
    def test_valid_questions(self, question):
        is_valid, msg = validate_user_question(question)
        assert is_valid is True, f"问题「{question}」应通过，但被拦截了"

    # ---------- 边界场景 ----------

    def test_weather_with_question_word(self):
        """含疑问词但与命理无关"""
        is_valid, msg = validate_user_question("明天会下雨吗？")
        assert is_valid is False

    def test_lottery_question(self):
        """彩票问题即使含'预测'等通用动词也应拦截"""
        is_valid, msg = validate_user_question("帮我预测彩票号码")
        assert is_valid is False

    def test_modifier_exemption(self):
        """黑名单词作为修饰语时应放行"""
        is_valid, msg = validate_user_question("我的手机店生意会好吗？")
        assert is_valid is True

    def test_modifier_block(self):
        """黑名单词作为主语时应拦截"""
        is_valid, msg = validate_user_question("手机代码怎么写？")
        assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])