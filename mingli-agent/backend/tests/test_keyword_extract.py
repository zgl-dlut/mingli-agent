"""测试关键词提取优化"""
import sys
sys.path.insert(0, '.')

from app.services.eval.structure_checker import extract_question_keywords

q = '27年的10月或者11月底是有一大笔资金入账的吗？资金大概是什么来源'
kw = extract_question_keywords(q)
print(f'问题: {q}')
print(f'关键词: {kw}')
print()

titles = [
    '27年10-11月大额资金确认与来源',
    '拿到这笔钱的关键前置动作',
    '27年年终奖为什么缩水且不必纠结',
    '真正的大头在10月协商补偿里',
    '27年换组后的真实压力与新组求职便利度',
    '27年赔偿金能否拿到及具体到账时间',
    '入职新公司的完整路径与时间节点',
    '27年新领导的性别与性格画像',
    '新领导是否已在公司及资历深浅',
    '2026年换车时机与预算把控',
    '27年换组后新汇报对象画像',
]
for t in titles:
    overlap = len([k for k in kw if k in t])
    status = 'OK' if overlap > 0 else 'FAIL'
    matched = [k for k in kw if k in t]
    print(f'  [{status}] title="{t}" overlap={overlap} matched={matched}')
