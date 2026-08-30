#!/usr/bin/env python3
"""
检查生产数据库中指定用户的排盘数据是否包含新增的神煞字段

使用方法：
1. 修改下方的数据库连接配置为生产环境配置
2. 运行：python3 check_shensha_field.py
"""
import pymysql
import json
from datetime import datetime

# 生产数据库连接配置（请根据实际情况修改）
DB_CONFIG = {
    'host': 'localhost',  # 生产服务器IP或域名
    'port': 3306,
    'user': 'mingli',
    'password': 'mingli123',
    'database': 'mingli',
    'charset': 'utf8mb4'
}

def check_person_bazi_data(birth_date_str):
    """检查指定出生日期的人物的排盘数据"""
    print(f"\n{'='*80}")
    print(f"查询出生日期: {birth_date_str}")
    print(f"{'='*80}\n")
    
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    
    try:
        cursor = conn.cursor()
        
        # 查询指定出生日期的人物
        cursor.execute("""
            SELECT 
                p.id, 
                p.user_id, 
                p.name, 
                p.birth_date, 
                p.birth_time, 
                p.gender,
                p.bazi_data_json,
                u.phone as user_phone
            FROM persons p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.birth_date LIKE %s
            ORDER BY p.id
        """, (f'%{birth_date_str}%',))
        
        persons = cursor.fetchall()
        
        if not persons:
            print(f"❌ 未找到出生日期为 {birth_date_str} 的人物记录")
            return
        
        print(f"✅ 找到 {len(persons)} 条记录\n")
        
        for person in persons:
            person_id = person['id']
            user_id = person['user_id']
            name = person['name']
            birth_date = person['birth_date']
            birth_time = person['birth_time']
            gender = person['gender']
            user_phone = person.get('user_phone', 'N/A')
            
            print(f"【人物 {person_id}】")
            print(f"  用户ID: {user_id}")
            print(f"  手机号: {user_phone}")
            print(f"  姓名: {name}")
            print(f"  性别: {gender}")
            print(f"  出生日期: {birth_date} {birth_time}")
            
            # 解析排盘数据
            if not person['bazi_data_json']:
                print(f"  ❌ 排盘数据为空")
                continue
            
            try:
                bazi_data = json.loads(person['bazi_data_json'])
            except json.JSONDecodeError as e:
                print(f"  ❌ 排盘数据JSON解析失败: {e}")
                continue
            
            # 检查新增字段
            print(f"\n  【排盘数据检查】")
            
            # 基础信息
            sizhu = bazi_data.get('四柱', '缺失')
            print(f"  四柱: {sizhu}")
            
            wangshuai = bazi_data.get('旺衰结论', '缺失')
            print(f"  旺衰结论: {wangshuai}")
            
            # 新增字段检查
            kongwang = bazi_data.get('空亡')
            if kongwang is not None:
                print(f"  ✅ 空亡: {kongwang}")
            else:
                print(f"  ❌ 空亡: 缺失")
            
            changsheng = bazi_data.get('长生十二宫')
            if changsheng is not None:
                print(f"  ✅ 长生十二宫: {changsheng}")
            else:
                print(f"  ❌ 长生十二宫: 缺失")
            
            shensha = bazi_data.get('神煞')
            if shensha is not None:
                print(f"  ✅ 神煞: {shensha}")
            else:
                print(f"  ❌ 神煞: 缺失")
            
            tiangan_he = bazi_data.get('天干五合')
            if tiangan_he is not None:
                print(f"  ✅ 天干五合: {tiangan_he}")
            else:
                print(f"  ❌ 天干五合: 缺失")
            
            # 统计新增字段完整性
            fields_status = {
                '空亡': kongwang is not None,
                '长生十二宫': changsheng is not None,
                '神煞': shensha is not None,
                '天干五合': tiangan_he is not None
            }
            
            complete_count = sum(fields_status.values())
            total_count = len(fields_status)
            
            print(f"\n  【字段完整性】")
            print(f"  新增字段: {complete_count}/{total_count} 完整")
            
            if complete_count == total_count:
                print(f"  ✅ 排盘数据已完整更新")
            else:
                missing_fields = [k for k, v in fields_status.items() if not v]
                print(f"  ⚠️  缺失字段: {', '.join(missing_fields)}")
            
            print(f"\n{'-'*80}\n")
        
        # 查询该用户最近的追问记录
        if persons:
            first_person = persons[0]
            person_id = first_person['id']
            user_id = first_person['user_id']
            
            print(f"\n{'='*80}")
            print(f"查询用户 {user_id} (人物 {person_id}) 的最近追问记录")
            print(f"{'='*80}\n")
            
            cursor.execute("""
                SELECT 
                    id,
                    question,
                    answer,
                    created_at
                FROM chat_messages
                WHERE person_id = %s 
                  AND message_type = 'followup'
                  AND answer IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 5
            """, (person_id,))
            
            messages = cursor.fetchall()
            
            if not messages:
                print("未找到追问记录")
            else:
                print(f"找到 {len(messages)} 条追问记录\n")
                
                for i, msg in enumerate(messages, 1):
                    print(f"【追问 {i}】")
                    print(f"  时间: {msg['created_at']}")
                    print(f"  问题: {msg['question'][:100]}...")
                    
                    # 检查回答中是否提到神煞相关内容
                    answer = msg['answer'] or ''
                    shensha_keywords = ['神煞', '华盖', '驿马', '桃花', '天乙贵人', '文昌', '魁罡', '空亡', '长生']
                    found_keywords = [kw for kw in shensha_keywords if kw in answer]
                    
                    if found_keywords:
                        print(f"  ✅ 回答中包含神煞相关关键词: {', '.join(found_keywords)}")
                    else:
                        print(f"  ⚠️  回答中未包含神煞相关关键词")
                    
                    print()
        
    finally:
        conn.close()

if __name__ == '__main__':
    # 查询1992-12-19出生的人物
    check_person_bazi_data('1992-12-19')
