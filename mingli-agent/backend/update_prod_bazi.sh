#!/bin/bash
# 在生产服务器上更新 18610351374 用户的排盘数据

cd /opt/mingli-agent

# 获取该用户的所有人物
PERSONS=$(docker compose exec mysql mysql -umingli -pmingli123 mingli --batch --skip-column-names -e "SELECT p.id, p.birth_date, p.birth_time, p.gender, p.birth_location, p.birth_lat, p.birth_lng FROM persons p JOIN users u ON p.user_id = u.id WHERE u.phone = '18610351374'")

echo "======================================================================"
echo "更新生产服务器 18610351374 用户的排盘数据"
echo "======================================================================"

while IFS=$'\t' read -r id birth_date birth_time gender birth_location lat lng; do
    echo ""
    echo "──────────────────────────────────────────────────────────────────────"
    echo "person_id=$id, 生辰=$birth_date $birth_time, $gender, $birth_location"
    echo "──────────────────────────────────────────────────────────────────────"
    
    # 获取旧数据摘要
    OLD_BAZI=$(docker compose exec mysql mysql -umingli -pmingli123 mingli --batch --raw -e "SELECT bazi_data_json FROM persons WHERE id = $id")
    
    # 提取旧数据关键字段
    OLD_SIZHU=$(echo "$OLD_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('四柱','N/A'))" 2>/dev/null || echo "N/A")
    OLD_WANGSHUAI=$(echo "$OLD_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('旺衰结论','N/A'))" 2>/dev/null || echo "N/A")
    OLD_MOTTO=$(echo "$OLD_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('命格箴言','N/A'))" 2>/dev/null || echo "N/A")
    OLD_KONGWANG=$(echo "$OLD_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('空亡','N/A'))" 2>/dev/null || echo "N/A")
    OLD_SHENSHA=$(echo "$OLD_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print('有' if d.get('神煞') else '无')" 2>/dev/null || echo "无")
    OLD_TIANGAN=$(echo "$OLD_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print('有' if d.get('天干五合') else '无')" 2>/dev/null || echo "无")
    OLD_CHANGSHENG=$(echo "$OLD_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('长生十二宫','N/A'))" 2>/dev/null || echo "N/A")
    
    echo ""
    echo "【更新前】"
    echo "  四柱: $OLD_SIZHU"
    echo "  旺衰结论: $OLD_WANGSHUAI"
    echo "  命格箴言: $OLD_MOTTO"
    echo "  空亡: $OLD_KONGWANG"
    echo "  长生十二宫: $OLD_CHANGSHENG"
    echo "  神煞: $OLD_SHENSHA"
    echo "  天干五合: $OLD_TIANGAN"
    
    # 调用 generate_full_analysis 重新生成
    NEW_BAZI=$(docker compose exec backend python3 -c "
import sys, json
sys.path.insert(0, '/app')
from app.skills.orchestrator import generate_full_analysis
result = generate_full_analysis(
    birth_date='$birth_date',
    birth_time='$birth_time',
    longitude=$lng,
    latitude=$lat,
    gender='$gender',
    location='$birth_location',
)
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null)
    
    if [ -z "$NEW_BAZI" ]; then
        echo "  ❌ 生成失败"
        continue
    fi
    
    # 提取新数据关键字段
    NEW_SIZHU=$(echo "$NEW_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('四柱','N/A'))" 2>/dev/null || echo "N/A")
    NEW_WANGSHUAI=$(echo "$NEW_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('旺衰结论','N/A'))" 2>/dev/null || echo "N/A")
    NEW_MOTTO=$(echo "$NEW_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('命格箴言','N/A'))" 2>/dev/null || echo "N/A")
    NEW_KONGWANG=$(echo "$NEW_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('空亡','N/A'))" 2>/dev/null || echo "N/A")
    NEW_SHENSHA=$(echo "$NEW_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('神煞','N/A'))" 2>/dev/null || echo "N/A")
    NEW_TIANGAN=$(echo "$NEW_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('天干五合','N/A'))" 2>/dev/null || echo "N/A")
    NEW_CHANGSHENG=$(echo "$NEW_BAZI" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('长生十二宫','N/A'))" 2>/dev/null || echo "N/A")
    
    echo ""
    echo "【更新后】"
    echo "  四柱: $NEW_SIZHU"
    echo "  旺衰结论: $NEW_WANGSHUAI"
    echo "  命格箴言: $NEW_MOTTO"
    echo "  空亡: $NEW_KONGWANG"
    echo "  长生十二宫: $NEW_CHANGSHENG"
    echo "  神煞: $NEW_SHENSHA"
    echo "  天干五合: $NEW_TIANGAN"
    
    # 差异对比
    echo ""
    echo "【差异】"
    if [ "$OLD_WANGSHUAI" != "$NEW_WANGSHUAI" ]; then
        echo "  ⚠️  旺衰结论: $OLD_WANGSHUAI → $NEW_WANGSHUAI"
    fi
    if [ "$OLD_MOTTO" != "$NEW_MOTTO" ]; then
        echo "  🔄 命格箴言: $OLD_MOTTO → $NEW_MOTTO"
    fi
    if [ "$OLD_KONGWANG" = "N/A" ] && [ "$NEW_KONGWANG" != "N/A" ]; then
        echo "  ➕ 空亡: 新增 $NEW_KONGWANG"
    fi
    if [ "$OLD_CHANGSHENG" = "N/A" ] && [ "$NEW_CHANGSHENG" != "N/A" ]; then
        echo "  ➕ 长生十二宫: 新增"
    fi
    if [ "$OLD_SHENSHA" = "无" ] && [ "$NEW_SHENSHA" != "N/A" ]; then
        echo "  ➕ 神煞: 新增"
    elif [ "$OLD_SHENSHA" != "$NEW_SHENSHA" ] && [ "$NEW_SHENSHA" != "N/A" ]; then
        echo "  🔄 神煞: 已更新"
    fi
    if [ "$OLD_TIANGAN" = "无" ] && [ "$NEW_TIANGAN" != "N/A" ]; then
        echo "  ➕ 天干五合: 新增 $NEW_TIANGAN"
    elif [ "$OLD_TIANGAN" != "$NEW_TIANGAN" ] && [ "$NEW_TIANGAN" != "N/A" ]; then
        echo "  🔄 天干五合: 已更新"
    fi
    
    # 更新数据库（使用临时文件避免转义问题）
    echo "$NEW_BAZI" > /tmp/bazi_${id}.json
    docker compose exec mysql mysql -umingli -pmingli123 mingli -e "UPDATE persons SET bazi_data_json = LOAD_FILE('/tmp/bazi_${id}.json') WHERE id = $id" 2>/dev/null
    
    # 如果 LOAD_FILE 不行，用 Python 方式更新
    if [ $? -ne 0 ]; then
        docker compose exec backend python3 -c "
import pymysql, json
conn = pymysql.connect(host='mysql', user='mingli', password='mingli123', database='mingli', charset='utf8mb4')
cursor = conn.cursor()
with open('/tmp/bazi_${id}.json', 'r') as f:
    data = json.load(f)
cursor.execute('UPDATE persons SET bazi_data_json = %s WHERE id = $id', (json.dumps(data, ensure_ascii=False),))
conn.commit()
conn.close()
print('✅ 数据库已更新')
" 2>/dev/null
    else
        echo "  ✅ 数据库已更新"
    fi
    
    rm -f /tmp/bazi_${id}.json
    
done <<< "$PERSONS"

echo ""
echo "======================================================================"
echo "✅ 全部更新完成"
echo "======================================================================"
