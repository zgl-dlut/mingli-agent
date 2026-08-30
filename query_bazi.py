import pymysql
import json

conn = pymysql.connect(
    host='localhost',
    user='mingli',
    password='mingli123',
    database='mingli',
    charset='utf8mb4'
)
cursor = conn.cursor()

# 先查 persons 表 user_id 和 users 表 id 对应关系
cursor.execute("SELECT p.id, p.user_id, p.name, u.phone FROM persons p LEFT JOIN users u ON p.user_id = u.id WHERE p.bazi_data_json IS NOT NULL")
rows = cursor.fetchall()
print(f"共找到 {len(rows)} 条记录\n")

for row in rows:
    pid, uid, name, phone = row
    print(f"person_id={pid}, user_id={uid}, name={name}, phone={phone}")

# 查所有 users
print("\n=== 所有用户 ===")
cursor.execute("SELECT id, phone, name FROM users")
for r in cursor.fetchall():
    print(r)

# 取第一条 bazi_data_json 看结构
print("\n=== bazi_data_json 结构示例 ===")
cursor.execute("SELECT bazi_data_json FROM persons WHERE bazi_data_json IS NOT NULL LIMIT 1")
row = cursor.fetchone()
if row:
    data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    # 打印四柱结构
    sizhu = data.get('四柱', {})
    print(f"四柱: {json.dumps(sizhu, ensure_ascii=False, indent=2)}")
    # 找空亡相关
    for k in data.keys():
        if '空' in k or '亡' in k or 'kong' in k.lower():
            print(f"{k}: {json.dumps(data[k], ensure_ascii=False)}")
    # 找长生相关
    for k in data.keys():
        if '长' in k or '生' in k or 'chang' in k.lower() or '旺' in k or '衰' in k:
            val = data[k]
            print(f"{k}: {json.dumps(val, ensure_ascii=False)[:500]}")

cursor.close()
conn.close()
