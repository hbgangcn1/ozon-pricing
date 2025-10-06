"""
检查用户状态的临时脚本
"""

import sqlite3
from db_utils import current_user_id, get_user_subscription_info, check_user_subscription_status

def check_current_user_status():
    """检查当前用户的状态"""
    user_id = current_user_id()
    if not user_id:
        print("❌ 用户未登录")
        return
    
    print(f"🔍 检查用户ID: {user_id}")
    
    # 获取用户订阅信息
    user_info = get_user_subscription_info(user_id)
    print(f"📋 用户订阅信息: {user_info}")
    
    # 检查订阅状态
    subscription_status = check_user_subscription_status(user_id)
    print(f"📊 订阅状态: {subscription_status}")
    
    # 直接查询数据库
    with sqlite3.connect('logistics.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, subscription_type, user_type, subscription_expires, expiry_date
            FROM users 
            WHERE id = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        if result:
            print(f"🗄️ 数据库中的用户信息:")
            print(f"   ID: {result[0]}")
            print(f"   用户名: {result[1]}")
            print(f"   subscription_type: {result[2]}")
            print(f"   user_type: {result[3]}")
            print(f"   subscription_expires: {result[4]}")
            print(f"   expiry_date: {result[5]}")
        else:
            print("❌ 未找到用户信息")

if __name__ == "__main__":
    check_current_user_status()
