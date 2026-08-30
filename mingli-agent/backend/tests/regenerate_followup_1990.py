"""
重新生成追问报告：1990年11月10日8:00（公历，女，山西省晋中市）
问题："27年会离开当前公司吗，几月离开当前公司，离开公司可以获得赔偿金吗，几月陆续收到offer，几月入职新公司"
"""
import asyncio
import sys
import os
import json

# 添加 backend 到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.skills.orchestrator import generate_full_analysis
from app.services.followup_structured import generate_followup_structured
from app.services.report_renderer import render_report


async def main():
    # 1. 命盘参数
    birth_date = "1990-11-10"
    birth_time = "08:00"
    # 山西省晋中市经纬度
    longitude = 112.7528
    latitude = 37.6877
    gender = "女"
    location = "晋中"

    print("=" * 60)
    print("重新生成追问报告")
    print(f"出生：{birth_date} {birth_time}，{location}")
    print(f"性别：{gender}")
    print("=" * 60)

    # 2. 生成命盘数据
    analysis_data = generate_full_analysis(
        birth_date=birth_date,
        birth_time=birth_time,
        longitude=longitude,
        latitude=latitude,
        gender=gender,
        location=location,
    )
    print(f"✓ 命盘数据生成成功, 日主: {analysis_data.get('rizhu', analysis_data.get('日主', '?'))}")

    # 3. 用户问题
    user_question = "27年会离开当前公司吗，几月离开当前公司，离开公司可以获得赔偿金吗，几月陆续收到offer，几月入职新公司"
    print(f"\n用户问题: {user_question}")
    print("-" * 60)

    # 4. 调用结构化追问服务
    full_json = ""
    async for chunk in generate_followup_structured(
        analysis_data=analysis_data,
        gender=gender,
        birth_date=birth_date,
        birth_time=birth_time,
        location=location,
        user_question=user_question,
        history=[],
        longitude=longitude,
        latitude=latitude,
    ):
        full_json += chunk

    # 5. 验证 JSON
    print(f"\n返回JSON长度: {len(full_json)}")

    try:
        data = json.loads(full_json)
        print("✓ JSON解析成功")
    except json.JSONDecodeError as e:
        print(f"✗ JSON解析失败: {e}")
        print(f"原始输出前500字符: {full_json[:500]}")
        return

    # 6. 渲染 Markdown
    print("\n" + "=" * 60)
    print("渲染 Markdown 报告")
    print("=" * 60)
    try:
        markdown = render_report(data)
        print(markdown)
    except Exception as e:
        print(f"渲染失败: {e}")
        # 直接输出 JSON 美化版
        print("\nJSON 美化输出:")
        print(json.dumps(data, ensure_ascii=False, indent=2))

    # 7. 保存 JSON 到文件
    output_path = os.path.join(os.path.dirname(__file__), "followup_1990_jinzhong.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ JSON 已保存到: {output_path}")

    # 8. 保存 Markdown 到文件
    try:
        md_path = os.path.join(os.path.dirname(__file__), "followup_1990_jinzhong.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"✓ Markdown 已保存到: {md_path}")
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
