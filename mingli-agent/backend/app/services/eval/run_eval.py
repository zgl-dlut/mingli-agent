"""评测运行器：加载评测集，逐项运行检查，输出结果报告。

支持两种模式：
1. 批量评测：加载 eval_dataset.json，逐项运行，输出汇总报告
2. 单条评测：传入 report + question + chart_data，返回检查结果

结果存储：写入 eval_results 表，支持后台查看
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.services.eval.structure_checker import check_structure
from app.services.eval.narrative_checker import check_narrative
from app.services.eval.chart_usage_checker import check_chart_usage
from app.services.eval.chart_checker import check_chart_correctness

logger = logging.getLogger(__name__)

# 评测集路径
EVAL_DATASET_PATH = Path(__file__).parent.parent.parent.parent / "tests" / "eval_dataset.json"


def load_eval_dataset() -> List[Dict]:
    """加载评测集"""
    if not EVAL_DATASET_PATH.exists():
        logger.warning(f"评测集不存在：{EVAL_DATASET_PATH}")
        return []
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_single_eval(
    report: Dict,
    user_question: str,
    chart_data: Dict,
    is_first_reading: bool = False,
) -> Dict:
    """运行单条评测（代码层检查）。

    Args:
        report: 报告 JSON
        user_question: 用户问题
        chart_data: 命盘数据
        is_first_reading: 是否首次报告

    Returns:
        {
            "passed": bool,
            "violations": [...],
            "structure": [...],
            "narrative": [...],
            "chart_usage": [...],
            "chart_correctness": [...]
        }
    """
    structure_violations = check_structure(report, user_question)
    narrative_violations = check_narrative(report, is_first_reading)
    chart_usage_violations = check_chart_usage(report, chart_data)

    all_violations = structure_violations + narrative_violations + chart_usage_violations

    return {
        "passed": len(all_violations) == 0,
        "violations": all_violations,
        "structure": structure_violations,
        "narrative": narrative_violations,
        "chart_usage": chart_usage_violations,
    }


def run_chart_eval(generated_chart: Dict, expected_chart: Dict) -> Dict:
    """运行排盘正确性评测。

    Args:
        generated_chart: 排盘系统生成的命盘数据
        expected_chart: 标准答案

    Returns:
        {
            "passed": bool,
            "violations": [...]
        }
    """
    violations = check_chart_correctness(generated_chart, expected_chart)
    return {
        "passed": len(violations) == 0,
        "violations": violations,
    }


def run_question_validation(user_question: str, expected_pass: bool) -> Dict:
    """运行问题验证评测（validate_user_question）。

    Returns:
        {
            "passed": bool,   # validate_user_question 的实际返回值
            "violations": [...]
        }
    """
    from app.services.skill_prompts import validate_user_question
    actual_pass, _ = validate_user_question(user_question)
    return {
        "passed": actual_pass,
        "violations": [] if actual_pass == expected_pass else [{
            "type": "question_validation",
            "detail": f"预期{'通过' if expected_pass else '拒绝'}但实际{'通过' if actual_pass else '拒绝'}: '{user_question}'"
        }],
    }


def run_batch_eval(dataset: Optional[List[Dict]] = None) -> Dict:
    """批量运行评测集。

    Args:
        dataset: 评测集列表，为 None 时自动加载 eval_dataset.json

    Returns:
        {
            "total": int,
            "passed": int,
            "failed": int,
            "pass_rate": float,
            "results": [
                {
                    "id": str,
                    "description": str,
                    "passed": bool,
                    "expected_pass": bool,
                    "match": bool,
                    "violations": [...],
                    "expected_violations": [...]
                }
            ]
        }
    """
    if dataset is None:
        dataset = load_eval_dataset()

    results = []
    passed_count = 0
    failed_count = 0

    for case in dataset:
        case_id = case.get("id", "unknown")
        description = case.get("description", "")
        expected_pass = case.get("expected_pass", True)
        expected_violations = case.get("expected_violations", [])

        # 判断是报告评测、排盘评测还是问题验证
        if "report" in case:
            # 报告评测
            result = run_single_eval(
                report=case["report"],
                user_question=case.get("user_question", ""),
                chart_data=case.get("chart_data", {}),
            )
        elif "generated_chart" in case:
            # 排盘评测
            result = run_chart_eval(
                generated_chart=case["generated_chart"],
                expected_chart=case["expected_chart"],
            )
        elif "user_question" in case and "expected_pass" in case:
            # 问题验证评测
            result = run_question_validation(
                user_question=case["user_question"],
                expected_pass=case["expected_pass"],
            )
        else:
            logger.warning(f"评测 case {case_id} 格式错误，跳过")
            continue

        # 判断是否符合预期
        actual_pass = result["passed"]
        match = actual_pass == expected_pass

        # 报告/排盘评测：统计实际通过数；问题验证：统计匹配数（actual==expected）
        is_question_validation = "user_question" in case and "report" not in case and "generated_chart" not in case
        if is_question_validation:
            if match:
                passed_count += 1
            else:
                failed_count += 1
        else:
            if actual_pass:
                passed_count += 1
            else:
                failed_count += 1

        results.append({
            "id": case_id,
            "description": description,
            "passed": actual_pass,
            "expected_pass": expected_pass,
            "match": match,
            "violations": result.get("violations", []),
            "expected_violations": expected_violations,
        })

    total = len(results)
    pass_rate = passed_count / total if total > 0 else 0

    return {
        "total": total,
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate": round(pass_rate, 4),
        "results": results,
    }


async def save_eval_result(result: Dict, dataset_id: str = "") -> None:
    """保存评测结果到数据库。

    Args:
        result: 评测结果 dict
        dataset_id: 评测集 ID（用于区分不同批次）
    """
    try:
        from app.db.session import async_session
        from app.models.eval_result import EvalResult

        async with async_session() as db:
            # 计算各层级指标
            # L1 技术完成：JSON 解析 + Pydantic 校验通过（无 json_parse_error / pydantic_validation_error）
            # L2 格式完成：结构检查通过（无子问题漏答、block数量异常、keyword为空、narrative过短/过长等）
            # L3 质量完成：叙事检查 + 命盘使用检查通过（无术语、编造等违规）
            # L4 综合：L1×L2×L3 全部通过
            total = len(result.get("results", []))
            l1_pass = l2_pass = l3_pass = l4_pass = 0

            for r in result.get("results", []):
                violations = r.get("violations", [])
                v_types = [v.get("type", "") for v in violations]

                # L1: 无 json_parse_error / pydantic_validation_error
                l1_errors = {"json_parse_error", "pydantic_validation_error"}
                has_l1_error = any(t in l1_errors for t in v_types)

                # L2: 结构检查违规（子问题漏答、block数量异常、keyword/narrative长度、summary关键词泛泛等）
                l2_keywords = {"子问题漏答", "block数量异常", "keyword为空", "narrative过短", "narrative过长",
                               "keyword含加粗标记", "summary关键词泛泛", "标题未贴合用户原话"}
                has_l2_error = any(t in l2_keywords for t in v_types)

                # L3: 叙事检查 + 命盘使用检查违规
                l3_keywords = {"keyword含术语", "keyword元标签", "keyword回避问题",
                               "编造大运", "编造流年", "用神不一致", "忌神不一致",
                               "流年干支不一致", "四柱错误", "日主天干错误", "十神错误",
                               "支神错误", "大运方向错误", "起运年龄错误", "大运列表错误",
                               "大运天干五行错误", "大运地支五行错误", "大运综合判断错误",
                               "流年天干五行错误", "流年地支五行错误", "流年判断错误", "流年缺失",
                               "流月干支错误", "流月吉凶错误", "跨层级推演"}
                has_l3_error = any(t in l3_keywords for t in v_types)

                if not has_l1_error:
                    l1_pass += 1
                if not has_l2_error:
                    l2_pass += 1
                if not has_l3_error:
                    l3_pass += 1
                if not has_l1_error and not has_l2_error and not has_l3_error:
                    l4_pass += 1

            l1_rate = l1_pass / total if total > 0 else 0
            l2_rate = l2_pass / total if total > 0 else 0
            l3_rate = l3_pass / total if total > 0 else 0
            l4_rate = l4_pass / total if total > 0 else 0
            format_pass_rate = l2_rate  # 兼容旧字段名

            eval_record = EvalResult(
                dataset_id=dataset_id,
                total=result.get("total", 0),
                passed=result.get("passed", 0),
                failed=result.get("failed", 0),
                pass_rate=result.get("pass_rate", 0),
                detail=json.dumps(result.get("results", []), ensure_ascii=False),
                format_pass_rate=round(format_pass_rate, 4),
                task_completion_rate={
                    "l1_technical": round(l1_rate, 4),
                    "l2_format": round(l2_rate, 4),
                    "l3_quality": round(l3_rate, 4),
                    "l4_satisfaction": round(l4_rate, 4),
                    "overall": round(l4_rate, 4),
                },
                created_at=datetime.utcnow(),
            )
            db.add(eval_record)
            await db.commit()
            logger.info(
                f"评测结果已保存：dataset_id={dataset_id}, total={result.get('total')}, "
                f"L1={l1_rate:.1%}, L2={l2_rate:.1%}, L3={l3_rate:.1%}, L4={l4_rate:.1%}"
            )
    except Exception as e:
        logger.error(f"保存评测结果失败：{e}")


async def main():
    """命令行入口：运行评测集并输出结果"""
    print("=" * 60)
    print("评测运行器")
    print("=" * 60)

    result = run_batch_eval()

    print(f"\n总计：{result['total']} 条")
    print(f"通过：{result['passed']} 条")
    print(f"失败：{result['failed']} 条")
    print(f"通过率：{result['pass_rate'] * 100:.2f}%")

    print("\n" + "=" * 60)
    print("详细结果：")
    print("=" * 60)

    for r in result["results"]:
        status = "✓" if r["passed"] else ""
        match_status = "✓" if r["match"] else "✗"
        print(f"\n[{status}] {r['id']}: {r['description']}")
        print(f"  预期：{'通过' if r['expected_pass'] else '失败'} | 实际：{'通过' if r['passed'] else '失败'} | 匹配：{match_status}")

        if r["violations"]:
            print(f"  违规项：")
            for v in r["violations"]:
                print(f"    - {v.get('type', 'unknown')}: {v.get('detail', '')}")

    # 保存到数据库
    await save_eval_result(result, dataset_id=f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")

    print("\n" + "=" * 60)
    print("评测完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
