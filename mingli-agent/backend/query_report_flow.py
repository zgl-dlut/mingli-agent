#!/usr/bin/env python3
"""
查询完整数据流：用户 → 排盘数据 → 首次报告/追问报告的输入输出

数据流：users → persons → chat_sessions(排盘快照) → chat_messages(问答)

使用方法：
  python3 query_report_flow.py --phone 手机号
  python3 query_report_flow.py --birth 1992-12-19
  python3 query_report_flow.py --person-id 123
"""
import pymysql
import json
import argparse
import sys

# ===== 数据库连接配置 =====
# 本地环境
LOCAL_DB = {
    'host': 'localhost',
    'port': 3306,
    'user': 'mingli',
    'password': 'mingli123',
    'database': 'mingli',
    'charset': 'utf8mb4'
}

# 生产环境（通过SSH隧道或直接连接）
# 如果有SSH隧道：ssh -L 3307:生产DB地址:3306 服务器
# 然后改 host='localhost', port=3307
PROD_DB = {
    'host': 'localhost',
    'port': 3306,  # 生产环境改为3307（如果走SSH隧道）
    'user': 'mingli',
    'password': 'mingli123',
    'database': 'mingli',
    'charset': 'utf8mb4'
}

# 选择数据源：'local' 或 'prod'
DB_SOURCE = 'local'


def get_db_config():
    return PROD_DB if DB_SOURCE == 'prod' else LOCAL_DB


def truncate(text, max_len=200):
    """截断长文本"""
    if not text:
        return ''
    if len(text) <= max_len:
        return text
    return text[:max_len] + f'... (共{len(text)}字)'


def check_bazi_fields(bazi_data):
    """检查排盘数据中新增字段的完整性"""
    if not bazi_data:
        return {'complete': False, 'missing': ['全部字段'], 'has': []}
    
    new_fields = ['空亡', '长生十二宫', '神煞', '天干五合']
    has = [f for f in new_fields if f in bazi_data and bazi_data[f] is not None]
    missing = [f for f in new_fields if f not in bazi_data or bazi_data[f] is None]
    
    return {
        'complete': len(missing) == 0,
        'has': has,
        'missing': missing
    }


def print_bazi_check(label, bazi_data):
    """打印排盘数据字段检查结果"""
    check = check_bazi_fields(bazi_data)
    status = '✅ 完整' if check['complete'] else '❌ 不完整'
    print(f"  {label} 新增字段: {status}")
    if check['has']:
        print(f"    ✅ 已有: {', '.join(check['has'])}")
    if check['missing']:
        print(f"    ❌ 缺失: {', '.join(check['missing'])}")


def query_by_person(cursor, person_id):
    """查询指定人物的完整数据流"""
    
    # 1. 查询人物信息
    cursor.execute("""
        SELECT p.id, p.user_id, p.name, p.gender, p.birth_date, p.birth_time,
               p.birth_location, p.province, p.city, p.bazi_data_json,
               u.phone
        FROM persons p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.id = %s
    """, (person_id,))
    person = cursor.fetchone()
    
    if not person:
        print(f"❌ 未找到 person_id={person_id}")
        return
    
    print(f"\n{'='*80}")
    print(f"【人物信息】person_id={person['id']}")
    print(f"{'='*80}")
    print(f"  用户ID: {person['user_id']}")
    print(f"  手机号: {person.get('phone', 'N/A')}")
    print(f"  姓名: {person['name']}")
    print(f"  性别: {person['gender']}")
    print(f"  出生: {person['birth_date']} {person['birth_time']}")
    print(f"  出生地: {person.get('birth_location', '')} {person.get('province', '')} {person.get('city', '')}")
    
    # 2. 检查人物排盘数据
    person_bazi = json.loads(person['bazi_data_json']) if person['bazi_data_json'] else None
    print()
    print_bazi_check("persons.bazi_data_json", person_bazi)
    
    if person_bazi:
        sizhu = person_bazi.get('四柱', 'N/A')
        print(f"  四柱: {sizhu}")
        print(f"  旺衰结论: {person_bazi.get('旺衰结论', 'N/A')}")
        if '神煞' in person_bazi:
            shensha = person_bazi['神煞']
            if isinstance(shensha, dict):
                print(f"  神煞: {json.dumps(shensha, ensure_ascii=False)}")
            else:
                print(f"  神煞: {shensha}")
    
    # 3. 查询该人物的所有会话
    cursor.execute("""
        SELECT id, bazi_data_json, title, created_at, updated_at
        FROM chat_sessions
        WHERE person_id = %s
        ORDER BY created_at DESC
    """, (person_id,))
    sessions = cursor.fetchall()
    
    if not sessions:
        print(f"\n  ⚠️  该人物没有任何会话记录")
        return
    
    print(f"\n  共 {len(sessions)} 个会话")
    
    # 4. 逐个会话查询消息
    for session in sessions:
        session_id = session['id']
        session_created = session['created_at']
        
        print(f"\n{'─'*80}")
        print(f"【会话】session_id={session_id}, 创建时间={session_created}")
        print(f"{'─'*80}")
        
        # 检查会话创建时的排盘快照
        session_bazi = json.loads(session['bazi_data_json']) if session['bazi_data_json'] else None
        print_bazi_check("chat_sessions.bazi_data_json (生成报告时使用的排盘数据)", session_bazi)
        
        if session_bazi:
            print(f"  四柱: {session_bazi.get('四柱', 'N/A')}")
            print(f"  旺衰结论: {session_bazi.get('旺衰结论', 'N/A')}")
            if '神煞' in session_bazi:
                shensha = session_bazi['神煞']
                if isinstance(shensha, dict):
                    # 简要展示
                    for pos, items in shensha.items():
                        if items:
                            print(f"    {pos}柱神煞: {', '.join(items) if isinstance(items, list) else items}")
        
        # 判断报告生成时是否使用了新排盘数据
        if session_bazi and person_bazi:
            session_has_shensha = '神煞' in session_bazi and session_bazi['神煞'] is not None
            person_has_shensha = '神煞' in person_bazi and person_bazi['神煞'] is not None
            
            if session_has_shensha:
                print(f"\n  ✅ 该会话生成报告时，排盘数据已包含神煞字段")
            else:
                print(f"\n  ⚠️  该会话生成报告时，排盘数据尚未包含神煞字段（报告可能未参考神煞）")
        
        # 查询会话消息
        cursor.execute("""
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC
        """, (session_id,))
        messages = cursor.fetchall()
        
        if not messages:
            print(f"  (无消息记录)")
            continue
        
        print(f"\n  消息记录 ({len(messages)} 条):")
        
        for i, msg in enumerate(messages, 1):
            role = msg['role']
            content = msg['content']
            created = msg['created_at']
            
            if role == 'user':
                print(f"\n  📝 [{created}] 用户提问:")
                print(f"     {truncate(content, 300)}")
            elif role == 'assistant':
                # 尝试解析JSON格式的回答
                try:
                    answer_data = json.loads(content)
                    # 首次报告格式（JSON）
                    if 'opening' in answer_data:
                        lead = answer_data.get('opening', {}).get('lead', '')
                        verdict = answer_data.get('opening', {}).get('verdict', '')
                        print(f"\n  🤖 [{created}] AI回答 (首次报告/追问):")
                        if lead:
                            print(f"     开篇: {truncate(lead, 200)}")
                        if verdict:
                            print(f"     结论: {truncate(verdict, 200)}")
                        
                        # 检查回答中是否提到神煞相关内容
                        full_text = json.dumps(answer_data, ensure_ascii=False)
                        shensha_keywords = ['神煞', '华盖', '驿马', '桃花', '天乙贵人', '文昌', 
                                           '魁罡', '天医', '六厄', '童子', '金舆', '学堂',
                                           '十恶大败', '太极贵人', '国印']
                        found = [kw for kw in shensha_keywords if kw in full_text]
                        if found:
                            print(f"     ✅ 回答中包含神煞关键词: {', '.join(found)}")
                        else:
                            print(f"     ⚠️  回答中未包含神煞关键词")
                    else:
                        print(f"\n  🤖 [{created}] AI回答:")
                        print(f"     {truncate(content, 300)}")
                except (json.JSONDecodeError, TypeError):
                    # 纯文本格式
                    print(f"\n  🤖 [{created}] AI回答:")
                    print(f"     {truncate(content, 300)}")
                    
                    # 检查纯文本中的神煞关键词
                    shensha_keywords = ['神煞', '华盖', '驿马', '桃花', '天乙贵人', '文昌', 
                                       '魁罡', '天医', '六厄', '童子', '金舆', '学堂',
                                       '十恶大败', '太极贵人', '国印']
                    found = [kw for kw in shensha_keywords if kw in content]
                    if found:
                        print(f"     ✅ 回答中包含神煞关键词: {', '.join(found)}")
                    else:
                        print(f"     ⚠️  回答中未包含神煞关键词")
            elif role == 'system':
                print(f"\n  ⚙️  [{created}] 系统消息:")
                print(f"     {truncate(content, 150)}")
            else:
                print(f"\n  [{role}] [{created}]:")
                print(f"     {truncate(content, 150)}")


def main():
    parser = argparse.ArgumentParser(description='查询用户→排盘→报告的完整数据流')
    parser.add_argument('--phone', help='用户手机号')
    parser.add_argument('--birth', help='出生日期 (如 1992-12-19)')
    parser.add_argument('--person-id', type=int, help='人物ID')
    parser.add_argument('--source', choices=['local', 'prod'], default='local',
                       help='数据源: local(本地) 或 prod(生产)')
    
    args = parser.parse_args()
    
    global DB_SOURCE
    DB_SOURCE = args.source
    
    db_config = get_db_config()
    
    conn = pymysql.connect(**db_config, cursorclass=pymysql.cursors.DictCursor)
    
    try:
        cursor = conn.cursor()
        
        if args.person_id:
            query_by_person(cursor, args.person_id)
        
        elif args.phone:
            # 通过手机号查找用户和人物
            cursor.execute("""
                SELECT p.id as person_id
                FROM persons p
                JOIN users u ON p.user_id = u.id
                WHERE u.phone = %s
            """, (args.phone,))
            rows = cursor.fetchall()
            
            if not rows:
                print(f"❌ 未找到手机号 {args.phone} 对应的人物")
                return
            
            for row in rows:
                query_by_person(cursor, row['person_id'])
        
        elif args.birth:
            # 通过出生日期查找人物
            cursor.execute("""
                SELECT id FROM persons
                WHERE birth_date LIKE %s
                ORDER BY id
            """, (f'%{args.birth}%',))
            rows = cursor.fetchall()
            
            if not rows:
                print(f"❌ 未找到出生日期为 {args.birth} 的人物")
                return
            
            print(f"找到 {len(rows)} 条记录")
            for row in rows:
                query_by_person(cursor, row['id'])
        
        else:
            # 默认查询所有人物
            cursor.execute("SELECT id FROM persons ORDER BY id")
            rows = cursor.fetchall()
            
            if not rows:
                print("❌ 数据库中没有任何人物记录")
                return
            
            print(f"数据库中共 {len(rows)} 个人物\n")
            for row in rows:
                query_by_person(cursor, row['id'])
    
    finally:
        conn.close()


if __name__ == '__main__':
    main()
