"""检查 prompt 中术语风格是否已改为融合式"""
import sys
sys.path.insert(0, "/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend")

from app.services.followup_structured import build_structured_prompt

prompt = build_structured_prompt(
    analysis_data={'用神': '火', '忌神': '水', '当前大运': '癸未 2021-2030', '日主': '己土'},
    gender='female',
    birth_date='1990-01-01',
    birth_time='12:00',
    location='北京',
    user_question='今年事业运势怎么样？适合跳槽吗？',
    history=[],
    longitude=116.4,
    latitude=39.9,
)

lines = prompt.split('\n')

# 1. 检查是否有融合式风格描述
has_fusion = '融合' in prompt
print(f"{'✅' if has_fusion else '❌'} Prompt 包含融合式描述: {has_fusion}")

# 2. 检查是否还有旧的括号标签式示例
has_old_style = '大白话现象（术语标签）' in prompt or '（术语标签）' in prompt
print(f"{'❌' if has_old_style else '✅'} 旧括号标签式示例已移除: {not has_old_style}")

# 3. 打印术语管控相关段落
print("\n=== 术语管控相关段落 ===")
for i, line in enumerate(lines):
    if '术语' in line and any(kw in line for kw in ['管控', '融合', '风格', '比例']):
        print(f"\n--- 第 {i+1} 行 ---")
        for j in range(max(0, i-1), min(len(lines), i+10)):
            print(f"  {lines[j]}")
        print()
