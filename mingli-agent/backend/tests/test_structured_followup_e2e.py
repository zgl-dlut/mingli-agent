"""
端到端验证：调用正式的 generate_followup_structured 服务
用真实命盘数据 + 真实问题，验证 JSON 输出 + Pydantic 校验
"""
import asyncio
import sys
import os
import json

# 添加 backend 到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.skills.orchestrator import generate_full_analysis
from app.services.followup_structured import generate_followup_structured


async def main():
    # 1. 生成命盘数据
    birth_date = "1992-12-19"
    birth_time = "19:35"
    longitude = 116.4
    latitude = 39.9
    gender = "男"
    location = "北京"

    print("=" * 60)
    print("端到端验证：结构化追问报告")
    print("=" * 60)

    analysis_data = generate_full_analysis(
        birth_date=birth_date,
        birth_time=birth_time,
        longitude=longitude,
        latitude=latitude,
        gender=gender,
        location=location,
    )
    print(f"✓ 命盘数据生成成功, 日主: {analysis_data.get('rizhu', '?')}")

    # 2. 调用正式服务
    user_question = "26年9月返岗后，在当年是否会换组，27年当前公司是否会给我裁员大礼包，大概什么时间，我最好在什么时间离开当前公司"
    print(f"\n用户问题: {user_question}")
    print("-" * 60)

    full_json = ""
    async for chunk in generate_followup_structured(
        analysis_data=analysis_data,
        gender=gender,
        birth_date=birth_date,
        birth_time=birth_time,
        location=location,
        user_question=user_question,
        history=[],
    ):
        full_json += chunk

    # 3. 验证 JSON
    print(f"\n返回JSON长度: {len(full_json)}")

    try:
        data = json.loads(full_json)
        print("✓ JSON解析成功")
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析失败: {e}")
        print(f"原始输出前500字符: {full_json[:500]}")
        return

    # 4. 验证结构
    print(f"\n顶层keys: {list(data.keys())}")
    print(f"opening: lead={'有' if data.get('opening', {}).get('lead') else '无'}, verdict={'有' if data.get('opening', {}).get('verdict') else '无'}")
    print(f"subtopics数量: {len(data.get('subtopics', []))}")
    for i, sub in enumerate(data.get('subtopics', [])):
        print(f"  [{i+1}] {sub.get('title', '?')}, blocks={len(sub.get('blocks', []))}")
        for j, block in enumerate(sub.get('blocks', [])):
            btype = block.get('type', '?')
            if btype == 'keyword':
                print(f"      block[{j}] keyword: {block.get('keyword', '?')[:30]}")
            elif btype == 'narrative':
                print(f"      block[{j}] narrative: {block.get('text', '?')[:30]}...")
            elif btype == 'group':
                print(f"      block[{j}] group: {block.get('title', '?')[:30]}")

    summary = data.get('summary', {})
    print(f"\nsummary: title={summary.get('title', '?')}")
    print(f"  lead={'有' if summary.get('lead') else '无'}, items={len(summary.get('items', []))}, item_format={summary.get('item_format', 'list')}")
    if summary.get('items'):
        for item in summary['items']:
            print(f"    - {item.get('keyword', '?')}: {item.get('text', '?')[:40]}...")

    # 5. 检查开头是否多样化（不固定"直接回答你"）
    lead = data.get('opening', {}).get('lead', '')
    print(f"\n开篇lead前30字符: {lead[:30]}")
    if "直接回答你" in lead:
        print("⚠ 警告: 开头仍为'直接回答你'")
    else:
        print("✓ 开头多样化")

    # 6. 内容验证（针对本次 prompt 调整）
    print("\n" + "=" * 60)
    print("【内容验证】本次 prompt 调整效果检查")
    print("=" * 60)

    # 6.1 term_explain 残留检查
    has_term_explain = False
    for sub in data.get('subtopics', []):
        for block in sub.get('blocks', []):
            if block.get('type') == 'keyword' and 'term_explain' in block:
                has_term_explain = True
                print(f"  ✗ 残留 term_explain: {block['term_explain'][:40]}")
    if not has_term_explain:
        print("  ✓ 无 term_explain 残留（术语已融入 narrative）")

    # 6.2 子问题拆解数量检查
    sub_count = len(data.get('subtopics', []))
    print(f"  子问题拆解数量: {sub_count}（期望 2-4 个，禁止只输出1个）")
    if sub_count >= 2:
        print("  ✓ 已拆解为多个子问题")
    elif sub_count == 1:
        print("  ✗ 仍只输出1个子问题，未执行拆解")
    else:
        print("  ✗ 无子问题")

    # 6.3 子问题标题展示
    print("\n  子问题标题清单：")
    for i, sub in enumerate(data.get('subtopics', [])):
        print(f"    {i+1}. {sub.get('title', '?')}")

    # 6.4 完整 JSON 美化输出（用于人工审阅术语融合、内容质量）
    print("\n" + "=" * 60)
    print("【完整 JSON 输出】")
    print("=" * 60)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
