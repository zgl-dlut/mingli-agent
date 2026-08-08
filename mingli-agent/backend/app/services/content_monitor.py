import re
from typing import Dict, List, Optional
from app.core.logger import logger


class ContentQualityChecker:
    def __init__(self):
        self.required_patterns = [
            r"\*\*核心结论",
            r"\【[^】]{2,20}\】",
        ]
        self.forbidden_patterns = [
            r"未来的剧本已经写好",
            r"站在2026年X月的节点",
            r"动态标题",
        ]

    def check_content(self, content: str) -> Dict[str, Any]:
        results = {
            "overall_score": 100,
            "checks": [],
            "issues": []
        }

        if not content or len(content.strip()) < 100:
            results["overall_score"] = 0
            results["issues"].append("内容过短或为空")
            return results

        length_score = min(100, len(content.strip()) // 14)
        results["checks"].append({
            "name": "内容长度",
            "score": length_score,
            "detail": f"{len(content.strip())} 字符"
        })
        results["overall_score"] -= max(0, 100 - length_score)

        for pattern in self.required_patterns:
            found = bool(re.search(pattern, content))
            if not found:
                results["issues"].append(f"缺少必要格式: {pattern}")
                results["overall_score"] -= 10

        for pattern in self.forbidden_patterns:
            found = bool(re.search(pattern, content))
            if found:
                results["issues"].append(f"包含禁止内容: {pattern}")
                results["overall_score"] -= 20

        keywords = re.findall(r"\【([^】]{2,20})\】", content)
        keyword_count = len(keywords)
        keyword_score = min(100, keyword_count * 20)
        results["checks"].append({
            "name": "关键词数量",
            "score": keyword_score,
            "detail": f"{keyword_count} 个关键词"
        })

        if keyword_count > 1:
            unique_keywords = len(set(keywords))
            duplicate_count = keyword_count - unique_keywords
            duplicate_rate = duplicate_count / keyword_count * 100 if keyword_count > 0 else 0
            if duplicate_rate > 50:
                results["issues"].append(f"关键词重复率过高: {duplicate_rate:.1f}%")
                results["overall_score"] -= 20
            results["checks"].append({
                "name": "关键词重复率",
                "score": 100 if duplicate_rate <= 50 else 0,
                "detail": f"重复率 {duplicate_rate:.1f}% ({duplicate_count}/{keyword_count} 重复)"
            })

        markdown_title_count = len(re.findall(r"^##\s", content, re.MULTILINE))
        results["checks"].append({
            "name": "子问题标题",
            "score": 100 if markdown_title_count > 0 else 0,
            "detail": f"{markdown_title_count} 个子问题"
        })
        if markdown_title_count == 0:
            results["issues"].append("缺少子问题标题")
            results["overall_score"] -= 15

        results["overall_score"] = max(0, results["overall_score"])

        if results["overall_score"] < 60:
            logger.warning("内容质量不合格", extra={
                "score": results["overall_score"],
                "issues": results["issues"]
            })

        return results


content_checker = ContentQualityChecker()