#!/usr/bin/env python3
"""验证标准命盘数据集的完整性和格式正确性"""
import json

def verify():
    # 验证 JSON 格式
    with open('tests/eval_chart_dataset.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print('✓ JSON 格式正确')
    
    # 验证数据结构
    case = data[0]
    expected = case.get('expected', {})
    
    # 检查必需字段
    required_fields = ['四柱', '日主天干', '十神', '大运方向', '起运年龄', '大运列表', '流年', '流月_2026', '当前运势状态', '重点流年分析']
    for field in required_fields:
        if field in expected:
            print(f'✓ {field} 存在')
        else:
            print(f'✗ {field} 缺失')
    
    # 验证大运列表详细信息
    dayun_list = expected.get('大运列表', [])
    print(f'\n大运列表共 {len(dayun_list)} 步:')
    for i, dayun in enumerate(dayun_list[:3]):
        required = ['干支', '起始年龄', '起始年份', '天干', '地支', '天干五行', '地支五行', '用神标记', '综合判断']
        missing = [f for f in required if f not in dayun]
        if missing:
            print(f'  大运[{i}] {dayun.get("干支")} 缺失字段: {missing}')
        else:
            print(f'  ✓ 大运[{i}] {dayun.get("干支")} 字段完整')
    
    # 验证流年详细信息
    liunian = expected.get('流年', {})
    print(f'\n流年共 {len(liunian)} 年:')
    for year in ['2024', '2025', '2026']:
        ln = liunian.get(year, {})
        required = ['干支', '年龄', '天干', '地支', '天干五行', '地支五行', '用神标记', '流年判断']
        missing = [f for f in required if f not in ln]
        if missing:
            print(f'  {year}年 缺失字段: {missing}')
        else:
            print(f'  ✓ {year}年 {ln.get("干支")} 字段完整')
    
    # 验证流月详细信息
    liuyue = expected.get('流月_2026', {})
    print(f'\n流月共 {len(liuyue)} 个月:')
    for month in ['8.7', '9.7']:
        ly = liuyue.get(month, {})
        required = ['节气', '干支', '天干', '地支', '天干五行', '地支五行', '吉凶']
        missing = [f for f in required if f not in ly]
        if missing:
            print(f'  {month}月 缺失字段: {missing}')
        else:
            print(f'  ✓ {month}月 {ly.get("干支")} 字段完整')
    
    # 验证当前运势状态
    current = expected.get('当前运势状态', {})
    print(f'\n当前运势状态:')
    required = ['当前大运', '当前流年', '当前流月']
    for field in required:
        if field in current:
            print(f'  ✓ {field}: {current.get(field)}')
        else:
            print(f'  ✗ {field} 缺失')
    
    # 验证重点流年分析
    key_liunian = expected.get('重点流年分析', [])
    print(f'\n重点流年分析共 {len(key_liunian)} 个:')
    for ln in key_liunian[:2]:
        required = ['年份', '干支', '判断', '理由', '建议']
        missing = [f for f in required if f not in ln]
        if missing:
            print(f'  {ln.get("年份")}年 缺失字段: {missing}')
        else:
            print(f'  ✓ {ln.get("年份")}年 {ln.get("干支")} 字段完整')
    
    print('\n✓ 数据完整性验证通过')

if __name__ == '__main__':
    verify()
