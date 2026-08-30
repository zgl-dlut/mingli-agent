"""检查 prompt 中术语风格是否正确"""
import sys
sys.path.insert(0, "/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend")

# 直接读取文件检查
with open('/Users/zhangguangling/Downloads/命理推算/mingli-agent/backend/app/services/followup_structured.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# 1. 检查角色定义行
print("=" * 60)
print("1. 角色定义行检查")
print("=" * 60)
for i, line in enumerate(lines):
    if '职场人生顾问' in line:
        print(f'行{i+1}:')
        print(line[:300])
        print()
        if '括号形式点缀' in line:
            print('❌ 还是旧的括号标签式！')
        elif '融入句子主干' in line:
            print('✅ 融合式！')
        break

# 2. 检查术语管控行
print("\n" + "=" * 60)
print("2. 术语管控行检查")
print("=" * 60)
for i, line in enumerate(lines):
    if '可接受' in line and '括号' in line:
        print(f'行{i+1}:')
        print(line[:200])
        if '✅' in line:
            print('❌ 括号标签式仍标记为可接受！')
        elif '❌' in line:
            print('✅ 括号标签式已标记为禁止！')
        break

# 3. 全局检查
print("\n" + "=" * 60)
print("3. 全局检查")
print("=" * 60)
has_forbidden = '禁止' in content and '括号标签' in content
print(f"{'✅' if has_forbidden else '❌'} 括号标签式被标记为禁止: {has_forbidden}")

has_acceptable = '可接受' in content and '括号标签' in content
print(f"{'❌' if has_acceptable else '✅'} 括号标签式不再标记为可接受: {not has_acceptable}")

# 4. 统计括号标签式出现次数
bracket_count = content.count('（七杀）') + content.count('（命盘喜火土）')
print(f"\n括号标签式示例出现次数：{bracket_count}")
if bracket_count > 0:
    print("⚠️  注意：括号标签式示例仍存在于 prompt 中（作为反面教材是可以的）")
