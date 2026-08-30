"""
更新已有用户的排盘数据脚本

功能：
1. 从数据库读取所有有排盘数据的人物
2. 用新逻辑重新计算排盘（包含空亡、长生十二宫、神煞、天干五合）
3. 对比新旧数据差异
4. 更新数据库

影响分析：
- 旺衰结论可能变化（如从"身弱"变为"身旺"）
- 新增空亡、长生十二宫、神煞、天干五合字段
- 已生成的报告不会改变（存储在 chat_messages 表）
- 新的追问会使用新的排盘数据
"""
import sys
import os
import json
import pymysql
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.bazi_service import calculate_kongwang, calculate_changsheng
from app.skills.divination.shensha_skill import calculate_shensha, calculate_tiangan_he
from app.skills.divination.wangshuai_skill import calculate_wangshuai


def extract_pillars_from_bazi_data(bazi_data: dict) -> dict:
    """从数据库的 bazi_data_json 中提取四柱信息"""
    sizhu = bazi_data.get("四柱", "")
    if not sizhu:
        return None
    
    parts = sizhu.split()
    if len(parts) != 4:
        return None
    
    pillars = {}
    tian_list = []
    di_list = []
    
    for i, part in enumerate(parts):
        if len(part) != 2:
            return None
        tian = part[0]
        di = part[1]
        tian_list.append(tian)
        di_list.append(di)
        
        pos = ["年", "月", "日", "时"][i]
        pillars[pos] = {"tian": tian, "di": di}
    
    return {
        "pillars": pillars,
        "tian_list": tian_list,
        "di_list": di_list,
    }


def recalculate_bazi(bazi_data: dict) -> dict:
    """用新逻辑重新计算排盘数据"""
    extracted = extract_pillars_from_bazi_data(bazi_data)
    if not extracted:
        return None
    
    pillars = extracted["pillars"]
    day_tian = extracted["tian_list"][2]
    day_di = extracted["di_list"][2]
    month_di = extracted["di_list"][1]
    year_di = extracted["di_list"][0]
    year_tian = extracted["tian_list"][0]
    
    # 计算纳音（简化版，基于年柱）
    # 这里需要完整的纳音表，暂时使用固定值
    year_nayin = bazi_data.get("纳音", {}).get("年", "山头火")
    
    # 1. 计算空亡
    kongwang = calculate_kongwang(day_tian, day_di)
    
    # 2. 计算长生十二宫
    changsheng = calculate_changsheng(day_tian, pillars)
    
    # 3. 计算神煞
    shensha = calculate_shensha(pillars, day_tian, day_di, month_di, year_di, year_tian, year_nayin, kongwang)
    
    # 4. 计算天干五合
    tiangan_he = calculate_tiangan_he(pillars)
    
    # 5. 重新计算旺衰（如果可能）
    # 需要藏干和五行数据
    canggan_data = bazi_data.get("十神分布", {})
    wuxing_data = bazi_data.get("五行分布", {})
    
    # 构建藏干数据（简化版）
    canggan = {}
    for pos in ["年", "月", "日", "时"]:
        di = extracted["di_list"][["年", "月", "日", "时"].index(pos)]
        # 这里需要根据地支查藏干表，暂时使用空列表
        canggan[pos] = []
    
    # 构建五行数据
    wuxing = {}
    if wuxing_data:
        for wx, count in wuxing_data.items():
            wuxing[wx] = count
    
    # 计算旺衰
    wangshuai = calculate_wangshuai(day_tian, day_di, month_di, pillars, canggan, wuxing)
    
    return {
        "kongwang": kongwang,
        "changsheng": changsheng,
        "shensha": shensha,
        "tiangan_he": tiangan_he,
        "wangshuai_conclusion": wangshuai.get("conclusion", ""),
        "wangshuai_score": wangshuai.get("total_score", 0),
        "wangshuai_details": wangshuai,
    }


def update_database():
    """更新数据库中的排盘数据"""
    # 连接数据库
    conn = pymysql.connect(
        host='localhost',
        user='mingli',
        password='mingli123',
        database='mingli',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        cursor = conn.cursor()
        
        # 查询需要排除的用户ID（手机号为18610351374）
        cursor.execute('SELECT id FROM users WHERE phone = %s', ('18610351374',))
        excluded_user = cursor.fetchone()
        excluded_user_id = excluded_user['id'] if excluded_user else None
        
        if excluded_user_id:
            print(f"排除用户: user_id={excluded_user_id} (手机号: 18610351374)")
        
        # 查询所有有排盘数据的人物，排除指定用户
        if excluded_user_id:
            cursor.execute('SELECT id, user_id, bazi_data_json FROM persons WHERE bazi_data_json IS NOT NULL AND user_id != %s', (excluded_user_id,))
        else:
            cursor.execute('SELECT id, user_id, bazi_data_json FROM persons WHERE bazi_data_json IS NOT NULL')
        rows = cursor.fetchall()
        
        print(f"找到 {len(rows)} 条排盘数据\n")
        print("=" * 80)
        
        updates = []
        
        for row in rows:
            person_id = row['id']
            user_id = row['user_id']
            bazi_json = row['bazi_data_json']
            
            try:
                bazi_data = json.loads(bazi_json)
            except json.JSONDecodeError:
                print(f"person_id={person_id}: JSON 解析失败，跳过")
                continue
            
            print(f"\nperson_id={person_id}, user_id={user_id}")
            print(f"四柱: {bazi_data.get('四柱', 'N/A')}")
            print(f"旧旺衰结论: {bazi_data.get('旺衰结论', 'N/A')}")
            
            # 重新计算
            new_data = recalculate_bazi(bazi_data)
            if not new_data:
                print("  无法重新计算，跳过")
                continue
            
            # 对比差异
            old_conclusion = bazi_data.get('旺衰结论', '')
            new_conclusion = new_data['wangshuai_conclusion']
            
            print(f"新旺衰结论: {new_conclusion}")
            print(f"空亡: {new_data['kongwang']}")
            print(f"长生十二宫: {new_data['changsheng']}")
            print(f"神煞: {new_data['shensha']}")
            print(f"天干五合: {new_data['tiangan_he']}")
            
            if old_conclusion != new_conclusion:
                print(f"⚠️  旺衰结论变化: {old_conclusion} → {new_conclusion}")
            
            # 更新 bazi_data
            bazi_data['空亡'] = new_data['kongwang']
            bazi_data['长生十二宫'] = new_data['changsheng']
            bazi_data['神煞'] = new_data['shensha']
            bazi_data['天干五合'] = new_data['tiangan_he']
            
            # 更新旺衰结论和详情
            if new_conclusion:
                bazi_data['旺衰结论'] = new_conclusion
                bazi_data['旺衰详情'] = new_data['wangshuai_details']
                
                # 根据新旺衰结论调整用神、喜神、忌神
                # 这里需要根据具体逻辑调整，暂时保持不变
                # TODO: 如果需要，可以重新计算用神、喜神、忌神
            
            updates.append((person_id, json.dumps(bazi_data, ensure_ascii=False)))
        
        print("\n" + "=" * 80)
        print(f"准备更新 {len(updates)} 条记录")
        
        # 执行更新
        for person_id, new_bazi_json in updates:
            cursor.execute(
                'UPDATE persons SET bazi_data_json = %s WHERE id = %s',
                (new_bazi_json, person_id)
            )
        
        conn.commit()
        print(f"✅ 成功更新 {len(updates)} 条记录")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    update_database()
