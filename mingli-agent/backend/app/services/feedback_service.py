"""
反馈服务：数据存储、自动标签、模型自评打分
使用 SQLite 独立存储，轻量零依赖
"""
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.services.skill_prompts import _match_skill_type, SKILL_PROMPTS

logger = logging.getLogger(__name__)

DB_PATH = "feedback.db"

# 标签中文名映射
TAG_LABELS = {
    "career": "事业财运",
    "wealth": "财运投资",
    "marriage": "婚姻感情",
    "health": "健康运势",
    "fate": "流年大运",
    "general": "综合命理",
}


def _get_db() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """初始化数据库表"""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            skill_tag TEXT NOT NULL,
            custom_tags TEXT DEFAULT '[]',
            model_score INTEGER,
            model_reason TEXT,
            human_score INTEGER,
            human_comment TEXT,
            model_name TEXT,
            is_first_reading INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_skill_tag 
        ON feedback_records(skill_tag)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_model_score 
        ON feedback_records(model_score)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_created_at 
        ON feedback_records(created_at)
    """)
    conn.commit()
    conn.close()


# 自动初始化
_init_db()


def auto_tag_question(question: str) -> str:
    """自动为问题打标签"""
    matched = _match_skill_type(question)
    return matched if matched else "general"


def get_tag_label(tag: str) -> str:
    """获取标签中文名称"""
    return TAG_LABELS.get(tag, tag)


def save_feedback(
    question: str,
    answer: str,
    person_name: str = "",
    model_name: str = "",
    is_first_reading: bool = False,
    model_score: Optional[int] = None,
    model_reason: Optional[str] = None,
) -> int:
    """保存反馈记录，返回记录ID"""
    skill_tag = auto_tag_question(question)
    conn = _get_db()
    cursor = conn.execute(
        """INSERT INTO feedback_records 
           (person_name, question, answer, skill_tag, model_score, model_reason, 
            model_name, is_first_reading, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            person_name,
            question,
            answer,
            skill_tag,
            model_score,
            model_reason,
            model_name,
            1 if is_first_reading else 0,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    logger.info(f"[Feedback] 保存记录 id={record_id}, tag={skill_tag}")
    return record_id


def update_feedback_score(
    record_id: int,
    human_score: Optional[int] = None,
    human_comment: Optional[str] = None,
) -> bool:
    """更新人工打分和评论"""
    conn = _get_db()
    updates = []
    params = []
    if human_score is not None:
        updates.append("human_score = ?")
        params.append(human_score)
    if human_comment is not None:
        updates.append("human_comment = ?")
        params.append(human_comment)
    if not updates:
        conn.close()
        return False
    params.append(record_id)
    conn.execute(
        f"UPDATE feedback_records SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()
    conn.close()
    return True


def get_feedback(
    record_id: int,
) -> Optional[Dict[str, Any]]:
    """获取单条反馈记录"""
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM feedback_records WHERE id = ?", (record_id,)
    ).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["tag_label"] = get_tag_label(result["skill_tag"])
        result["custom_tags"] = json.loads(result["custom_tags"] or "[]")
        return result
    return None


def list_feedback(
    tag: Optional[str] = None,
    min_model_score: Optional[int] = None,
    max_model_score: Optional[int] = None,
    min_human_score: Optional[int] = None,
    max_human_score: Optional[int] = None,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> Dict[str, Any]:
    """查询反馈列表，支持多条件筛选"""
    conditions = []
    params = []

    if tag:
        conditions.append("skill_tag = ?")
        params.append(tag)
    if min_model_score is not None:
        conditions.append("model_score >= ?")
        params.append(min_model_score)
    if max_model_score is not None:
        conditions.append("model_score <= ?")
        params.append(max_model_score)
    if min_human_score is not None:
        conditions.append("human_score >= ?")
        params.append(min_human_score)
    if max_human_score is not None:
        conditions.append("human_score <= ?")
        params.append(max_human_score)
    if keyword:
        conditions.append("(question LIKE ? OR answer LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    conn = _get_db()

    # 总数
    total = conn.execute(
        f"SELECT COUNT(*) FROM feedback_records WHERE {where_clause}",
        params,
    ).fetchone()[0]

    # 列表
    rows = conn.execute(
        f"""SELECT * FROM feedback_records 
            WHERE {where_clause} 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        item["tag_label"] = get_tag_label(item["skill_tag"])
        item["custom_tags"] = json.loads(item["custom_tags"] or "[]")
        # 截断 answer 用于列表展示
        if len(item.get("answer", "")) > 200:
            item["answer_preview"] = item["answer"][:200] + "..."
        else:
            item["answer_preview"] = item.get("answer", "")
        items.append(item)

    return {"total": total, "items": items, "offset": offset, "limit": limit}


def get_feedback_stats() -> Dict[str, Any]:
    """获取反馈统计数据"""
    conn = _get_db()

    # 按标签统计
    tag_stats = conn.execute("""
        SELECT 
            skill_tag,
            COUNT(*) as count,
            AVG(model_score) as avg_model_score,
            AVG(human_score) as avg_human_score
        FROM feedback_records
        GROUP BY skill_tag
        ORDER BY count DESC
    """).fetchall()

    # 总体统计
    total = conn.execute("SELECT COUNT(*) FROM feedback_records").fetchone()[0]
    avg_model = conn.execute(
        "SELECT AVG(model_score) FROM feedback_records WHERE model_score IS NOT NULL"
    ).fetchone()[0]
    avg_human = conn.execute(
        "SELECT AVG(human_score) FROM feedback_records WHERE human_score IS NOT NULL"
    ).fetchone()[0]
    scored_count = conn.execute(
        "SELECT COUNT(*) FROM feedback_records WHERE human_score IS NOT NULL"
    ).fetchone()[0]

    # 模型分数分布
    model_dist = conn.execute("""
        SELECT 
            CASE 
                WHEN model_score IS NULL THEN '未打分'
                WHEN model_score >= 90 THEN '90-100'
                WHEN model_score >= 80 THEN '80-89'
                WHEN model_score >= 70 THEN '70-79'
                WHEN model_score >= 60 THEN '60-69'
                ELSE '0-59'
            END as range,
            COUNT(*) as count
        FROM feedback_records
        GROUP BY range
    """).fetchall()

    conn.close()

    tags = []
    for row in tag_stats:
        tags.append({
            "tag": row["skill_tag"],
            "label": get_tag_label(row["skill_tag"]),
            "count": row["count"],
            "avg_model_score": round(row["avg_model_score"] or 0, 1),
            "avg_human_score": round(row["avg_human_score"] or 0, 1),
        })

    return {
        "total": total,
        "avg_model_score": round(avg_model or 0, 1),
        "avg_human_score": round(avg_human or 0, 1),
        "scored_count": scored_count,
        "unscored_count": total - scored_count,
        "tags": tags,
        "model_score_distribution": [dict(r) for r in model_dist],
    }


def delete_feedback(record_id: int) -> bool:
    """删除反馈记录"""
    conn = _get_db()
    conn.execute("DELETE FROM feedback_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return True


async def model_self_score(
    question: str,
    answer: str,
    system_prompt: str = "",
) -> Dict[str, Any]:
    """
    模型自评打分：让 AI 对自己的回答进行打分
    返回 {"score": int, "reason": str}
    """
    try:
        from app.services.ai_service import generate_ai_response

        scoring_prompt = f"""你是一个命理回答质量评审专家。请对以下命理咨询的AI回答进行打分。

评分标准（1-100分）：
- 100-90: 精准、全面、可操作、语言通俗易懂、给出明确结论和时间点
- 89-75: 基本准确，有参考价值，但不够深入或缺乏具体时间/数字
- 74-60: 大致方向正确，但内容空泛、缺乏细节
- 59-40: 有一些参考性内容，但核心问题未解决
- 39-0: 答非所问或完全无关

用户问题：{question}

AI回答：
{answer[:3000]}

请以JSON格式输出：
{{"score": 分数, "reason": "打分理由，简明扼要"}}
"""

        messages = [{"role": "user", "content": scoring_prompt}]
        result_text = ""
        async for chunk in generate_ai_response(system_prompt or "你是命理评审专家。", messages, stream=False):
            result_text += chunk

        # 解析 JSON
        try:
            import re
            # 尝试提取 JSON
            json_match = re.search(r'\{[^}]+\}', result_text)
            if json_match:
                data = json.loads(json_match.group())
                score = max(0, min(100, int(data.get("score", 60))))
                reason = data.get("reason", "")
                return {"score": score, "reason": reason}
        except Exception:
            pass

        # 降级：从文本中提取数字
        numbers = re.findall(r'(\d+)', result_text)
        if numbers:
            score = max(0, min(100, int(numbers[0])))
            return {"score": score, "reason": "自动提取打分"}

        return {"score": 60, "reason": "默认打分"}

    except Exception as e:
        logger.error(f"[Feedback] 模型自评失败: {e}")
        return {"score": 50, "reason": f"自评失败: {str(e)[:50]}"}