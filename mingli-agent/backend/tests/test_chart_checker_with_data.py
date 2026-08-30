#!/usr/bin/env python3
"""
测试 chart_checker.py 验证补充的大运和流年数据
"""
import sys
import json
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.eval.chart_checker import check_chart_correctness
from app.skills.orchestrator import generate_full_analysis


def test_chart_checker():
    """测试排盘正确性检查器"""
    print("=" * 60)
    print("开始测试 chart_checker.py")
    print("=" * 60)
    
    # 1. 读取标准数据集
    dataset_path = backend_dir / "tests" / "eval_chart_dataset.json"
    print(f"\n1. 读取标准数据集: {dataset_path}")
    
    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    print(f"   ✓ 成功加载 {len(dataset)} 个命盘数据")
    
    # 2. 遍历每个命盘进行验证
    for idx, case in enumerate(dataset):
        print(f"\n{'=' * 60}")
        print(f"2. 验证命盘 [{idx + 1}]: {case.get('description', 'N/A')}")
        print(f"{'=' * 60}")
        
        birth_info = case['birth']
        expected = case['expected']
        
        # 3. 调用排盘系统生成命盘数据
        print(f"\n3. 调用排盘系统生成命盘数据...")
        print(f"   出生信息: {birth_info['year']}-{birth_info['month']:02d}-{birth_info['day']:02d} "
              f"{birth_info['hour']:02d}:{birth_info['minute']:02d}")
        print(f"   性别: {birth_info['gender']}")
        print(f"   地点: {birth_info.get('location', 'N/A')}")
        
        try:
            generated = generate_full_analysis(
                birth_date=f"{birth_info['year']}-{birth_info['month']:02d}-{birth_info['day']:02d}",
                birth_time=f"{birth_info['hour']:02d}:{birth_info['minute']:02d}",
                longitude=birth_info['longitude'],
                latitude=birth_info['latitude'],
                gender=birth_info['gender'],
                location=birth_info.get('location', '')
            )
            print(f"   ✓ 排盘成功")
        except Exception as e:
            print(f"   ✗ 排盘失败: {e}")
            continue
        
        # 4. 使用 chart_checker 进行验证
        print(f"\n4. 使用 chart_checker 进行验证...")
        violations = check_chart_correctness(generated, expected)
        
        # 5. 输出验证结果
        print(f"\n5. 验证结果:")
        if not violations:
            print(f"   ✓ 所有检查项通过！")
        else:
            print(f"   ✗ 发现 {len(violations)} 个违规项:")
            for v in violations:
                print(f"\n   - 类型: {v.get('type')}")
                print(f"     位置: {v.get('location')}")
                print(f"     期望: {v.get('expected')}")
                print(f"     实际: {v.get('actual')}")
                if 'position' in v:
                    print(f"     位置索引: {v.get('position')}")
                if 'year' in v:
                    print(f"     年份: {v.get('year')}")
                if 'month' in v:
                    print(f"     月份: {v.get('month')}")
        
        # 6. 输出关键数据对比
        print(f"\n6. 关键数据对比:")
        
        # 四柱对比
        print(f"\n   【四柱】")
        print(f"   期望: {expected.get('四柱')}")
        print(f"   实际: {generated.get('四柱')}")
        
        # 大运方向对比
        print(f"\n   【大运方向】")
        print(f"   期望: {expected.get('大运方向')}")
        print(f"   实际: {generated.get('大运方向')}")
        
        # 起运年龄对比
        print(f"\n   【起运年龄】")
        print(f"   期望: {expected.get('起运年龄')}")
        print(f"   实际: {generated.get('起运年龄')}")
        
        # 大运列表对比（前3个）
        print(f"\n   【大运列表（前3个）】")
        exp_dayun = expected.get('大运列表', [])
        gen_dayun = generated.get('大运列表', [])
        for i in range(min(3, len(exp_dayun), len(gen_dayun))):
            exp_dy = exp_dayun[i]
            gen_dy = gen_dayun[i]
            exp_gz = exp_dy.get('干支', '') if isinstance(exp_dy, dict) else exp_dy
            gen_gz = gen_dy.get('ganzhi', '') if isinstance(gen_dy, dict) else gen_dy
            match = "✓" if exp_gz == gen_gz else "✗"
            print(f"   {match} 大运[{i}]: 期望={exp_gz}, 实际={gen_gz}")
            
            # 如果有详细信息，也输出
            if isinstance(gen_dy, dict):
                print(f"      天干五行: {gen_dy.get('tian_wuxing', 'N/A')}")
                print(f"      地支五行: {gen_dy.get('di_wuxing', 'N/A')}")
                print(f"      综合判断: {gen_dy.get('overall_judge', 'N/A')}")
        
        # 流年对比（前3个）
        print(f"\n   【流年（前3个）】")
        exp_liunian = expected.get('流年', {})
        gen_liunian = generated.get('重点流年', [])
        
        # 将生成的流年转换为字典便于查找
        gen_liunian_dict = {}
        for ln in gen_liunian:
            if isinstance(ln, dict):
                year = ln.get('year', '')
                gen_liunian_dict[str(year)] = ln
        
        for i, (year, exp_ln) in enumerate(list(exp_liunian.items())[:3]):
            exp_gz = exp_ln.get('干支', '') if isinstance(exp_ln, dict) else exp_ln
            gen_ln = gen_liunian_dict.get(year, {})
            gen_gz = gen_ln.get('ganzhi', '') if isinstance(gen_ln, dict) else ''
            match = "✓" if exp_gz == gen_gz else "✗"
            print(f"   {match} {year}年: 期望={exp_gz}, 实际={gen_gz}")
            
            # 如果有详细信息，也输出
            if isinstance(gen_ln, dict):
                print(f"      天干五行: {gen_ln.get('tian_wuxing', 'N/A')}")
                print(f"      地支五行: {gen_ln.get('di_wuxing', 'N/A')}")
                print(f"      综合判断: {gen_ln.get('overall_judge', 'N/A')}")
    
    print(f"\n{'=' * 60}")
    print("测试完成")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    test_chart_checker()
