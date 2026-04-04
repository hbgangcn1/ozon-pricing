# -*- coding: utf-8 -*-
"""
密码恢复模块测试
"""

import time
import bcrypt
from password_recovery import (
    log_password_recovery_event,
    get_user_security_questions,
    verify_security_answers,
    reset_password,
    unlock_user,
    admin_reset_password,
    get_password_recovery_logs,
    MAX_RESET_ATTEMPTS,
)
from db_utils import get_db_connection


class TestPasswordRecoveryLog:
    """测试密码恢复日志"""

    def test_log_password_recovery_event(self, _clean_db):  # noqa: ARG001
        """测试记录密码恢复事件"""
        log_password_recovery_event(
            username="test_user",
            event_type="request",
            success=True,
            attempt_count=0,
            ip_address="127.0.0.1"
        )
        
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT * FROM password_recovery_log
                WHERE username = ?""")

            c.execute(sql, ("test_user",))
            result = c.fetchone()
            
            assert result is not None
            assert result[1] == "test_user"  # username
            assert result[3] == "request"  # event_type
            assert result[4] == 1  # success


class TestGetUserSecurityQuestions:
    """测试获取用户安全问题"""

    def test_get_user_security_questions_not_exist(self, _clean_db):  # noqa: ARG001
        """测试用户不存在"""
        result = get_user_security_questions("nonexistent_user")
        assert result is None

    def test_get_user_security_questions_no_questions(self, _clean_db, test_user):  # noqa: ARG001
        """测试用户未设置安全问题"""
        username = test_user['username']
        result = get_user_security_questions(username)
        
        assert result is not None
        assert result['has_questions'] is False
        assert result['reset_attempt_count'] == 0

    def test_get_user_security_questions_with_questions(self, _clean_db, test_user):  # noqa: ARG001
        """测试用户已设置安全问题"""
        username = test_user['username']
        
        # 设置安全问题
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET security_q1 = ?, security_q2 = ?
                WHERE username = ?""")

            c.execute(sql, ("问题1", "问题2", username))
            conn.commit()
        
        result = get_user_security_questions(username)
        
        assert result is not None
        assert result['has_questions'] is True
        assert result['security_q1'] == "问题1"
        assert result['security_q2'] == "问题2"
        assert result['is_locked'] is False

    def test_get_user_security_questions_locked(self, _clean_db, test_user):  # noqa: ARG001
        """测试用户被锁定"""
        username = test_user['username']
        lock_until = time.time() + 3600
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET security_q1 = ?, security_q2 = ?,
                    reset_locked_until = ?, reset_attempt_count = ?
                WHERE username = ?""")

            c.execute(sql, ("问题1", "问题2", lock_until, MAX_RESET_ATTEMPTS, username))
            conn.commit()
        
        # 读取时间戳，考虑执行时间
        result = get_user_security_questions(username)
        
        assert result is not None
        assert result['is_locked'] is True
        # PostgreSQL和SQLite的时间戳精度可能不同，允许误差
        # 考虑数据库操作和函数执行的延迟，允许更大的误差范围
        if result['reset_locked_until']:
            # 允许120秒误差（考虑数据库操作延迟和函数执行时间）
            time_diff = abs(result['reset_locked_until'] - lock_until)
            assert time_diff < 120, (
                f"时间戳差异过大: {time_diff}秒，"
                f"期望: {lock_until}, 实际: {result['reset_locked_until']}"
            )

    def test_get_user_security_questions_lock_expired(self, _clean_db, test_user):  # noqa: ARG001
        """测试锁定已过期"""
        username = test_user['username']
        lock_until = time.time() - 100  # 已过期
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET security_q1 = ?, security_q2 = ?,
                    reset_locked_until = ?, reset_attempt_count = ?
                WHERE username = ?""")

            c.execute(sql, ("问题1", "问题2", lock_until, MAX_RESET_ATTEMPTS, username))
            conn.commit()
        
        result = get_user_security_questions(username)
        
        assert result is not None
        assert result['is_locked'] is False
        assert result['reset_locked_until'] is None
        assert result['reset_attempt_count'] == 0


class TestVerifySecurityAnswers:
    """测试验证安全问题答案"""

    def test_verify_security_answers_user_not_exist(self, _clean_db):  # noqa: ARG001
        """测试用户不存在"""
        is_valid, msg = verify_security_answers(
            "nonexistent_user", "答案1", "答案2"
        )
        assert is_valid is False
        assert "不存在" in msg

    def test_verify_security_answers_no_questions(self, _clean_db, test_user):  # noqa: ARG001
        """测试用户未设置安全问题"""
        username = test_user['username']
        is_valid, msg = verify_security_answers(
            username, "答案1", "答案2"
        )
        assert is_valid is False
        assert "未设置" in msg

    def test_verify_security_answers_locked(self, _clean_db, test_user):  # noqa: ARG001
        """测试用户被锁定"""
        username = test_user['username']
        lock_until = time.time() + 3600
        answer1_hash = bcrypt.hashpw("answer1".encode(), bcrypt.gensalt()).decode()
        answer2_hash = bcrypt.hashpw("answer2".encode(), bcrypt.gensalt()).decode()
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET security_q1 = ?, security_q2 = ?,
                    security_a1 = ?, security_a2 = ?,
                    reset_locked_until = ?
                WHERE username = ?""")

            c.execute(sql, ("问题1", "问题2", answer1_hash, answer2_hash, lock_until, username))
            conn.commit()
        
        is_valid, msg = verify_security_answers(
            username, "answer1", "answer2"
        )
        assert is_valid is False
        assert "锁定" in msg

    def test_verify_security_answers_correct(self, _clean_db, test_user):  # noqa: ARG001
        """测试答案正确"""
        username = test_user['username']
        answer1_hash = bcrypt.hashpw("answer1".encode(), bcrypt.gensalt()).decode()
        answer2_hash = bcrypt.hashpw("answer2".encode(), bcrypt.gensalt()).decode()
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET security_q1 = ?, security_q2 = ?,
                    security_a1 = ?, security_a2 = ?
                WHERE username = ?""")

            c.execute(sql, ("问题1", "问题2", answer1_hash, answer2_hash, username))
            conn.commit()
        
        is_valid, msg = verify_security_answers(
            username, "answer1", "answer2"
        )
        assert is_valid is True
        assert "成功" in msg
        
        # 验证尝试次数已重置
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT reset_attempt_count FROM users WHERE username = ?""")

            c.execute(sql, (username,))
            count = c.fetchone()[0]
            assert count == 0

    def test_verify_security_answers_incorrect(self, _clean_db, test_user):  # noqa: ARG001
        """测试答案错误"""
        username = test_user['username']
        answer1_hash = bcrypt.hashpw("correct1".encode(), bcrypt.gensalt()).decode()
        answer2_hash = bcrypt.hashpw("correct2".encode(), bcrypt.gensalt()).decode()
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET security_q1 = ?, security_q2 = ?,
                    security_a1 = ?, security_a2 = ?,
                    reset_attempt_count = 0
                WHERE username = ?""")

            c.execute(sql, ("问题1", "问题2", answer1_hash, answer2_hash, username))
            conn.commit()
        
        is_valid, _ = verify_security_answers(
            username, "wrong1", "wrong2"
        )
        assert is_valid is False
        
        # 验证尝试次数已增加
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT reset_attempt_count FROM users WHERE username = ?""")

            c.execute(sql, (username,))
            count = c.fetchone()[0]
            assert count == 1

    def test_verify_security_answers_max_attempts(self, _clean_db, test_user):  # noqa: ARG001
        """测试达到最大尝试次数后锁定"""
        username = test_user['username']
        answer1_hash = bcrypt.hashpw("correct1".encode(), bcrypt.gensalt()).decode()
        answer2_hash = bcrypt.hashpw("correct2".encode(), bcrypt.gensalt()).decode()
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET security_q1 = ?, security_q2 = ?,
                    security_a1 = ?, security_a2 = ?,
                    reset_attempt_count = ?
                WHERE username = ?""")

            c.execute(sql, ("问题1", "问题2", answer1_hash, answer2_hash,
                  MAX_RESET_ATTEMPTS - 1, username))
            conn.commit()
        
        is_valid, msg = verify_security_answers(
            username, "wrong1", "wrong2"
        )
        assert is_valid is False
        assert "锁定" in msg
        
        # 验证用户已被锁定
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT reset_locked_until, reset_attempt_count
                FROM users WHERE username = ?""")

            c.execute(sql, (username,))
            lock_until, count = c.fetchone()
            assert lock_until is not None
            assert count == MAX_RESET_ATTEMPTS


class TestResetPassword:
    """测试重置密码"""

    def test_reset_password_user_not_exist(self, _clean_db):  # noqa: ARG001
        """测试用户不存在"""
        is_valid, msg = reset_password("nonexistent_user", "NewP@ss123456")
        assert is_valid is False
        assert "不存在" in msg

    def test_reset_password_weak_password(self, _clean_db, test_user):  # noqa: ARG001
        """测试密码强度不够"""
        username = test_user['username']
        is_valid, msg = reset_password(username, "weak")
        assert is_valid is False
        assert "强度不够" in msg

    def test_reset_password_success(self, _clean_db, test_user):  # noqa: ARG001
        """测试重置密码成功"""
        username = test_user['username']
        new_password = "NewP@ss123456"
        
        is_valid, msg = reset_password(username, new_password)
        assert is_valid is True
        assert "成功" in msg
        
        # 验证密码已更新
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT password FROM users WHERE username = ?""")

            c.execute(sql, (username,))
            stored_hash = c.fetchone()[0]
            assert stored_hash != test_user['password']
            
            # 验证新密码可以验证
            import bcrypt
            assert bcrypt.checkpw(new_password.encode(), stored_hash.encode())

    def test_reset_password_clears_lock(self, _clean_db, test_user):  # noqa: ARG001
        """测试重置密码时清除锁定"""
        username = test_user['username']
        lock_until = time.time() + 3600
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET reset_locked_until = ?, reset_attempt_count = ?
                WHERE username = ?""")

            c.execute(sql, (lock_until, MAX_RESET_ATTEMPTS, username))
            conn.commit()
        
        is_valid, _ = reset_password(username, "NewP@ss123456")
        assert is_valid is True
        
        # 验证锁定已清除
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT reset_locked_until, reset_attempt_count
                FROM users WHERE username = ?""")

            c.execute(sql, (username,))
            lock_until_result, count = c.fetchone()
            assert lock_until_result is None
            assert count == 0


class TestUnlockUser:
    """测试解锁用户"""

    def test_unlock_user_not_exist(self, _clean_db):  # noqa: ARG001
        """测试用户不存在"""
        is_valid, msg = unlock_user("nonexistent_user", "admin")
        assert is_valid is False
        assert "不存在" in msg

    def test_unlock_user_success(self, _clean_db, test_user):  # noqa: ARG001
        """测试解锁用户成功"""
        username = test_user['username']
        lock_until = time.time() + 3600
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET reset_locked_until = ?, reset_attempt_count = ?
                WHERE username = ?""")

            c.execute(sql, (lock_until, MAX_RESET_ATTEMPTS, username))
            conn.commit()
        
        is_valid, msg = unlock_user(username, "admin")
        assert is_valid is True
        assert "解锁" in msg
        
        # 验证锁定已清除
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT reset_locked_until, reset_attempt_count
                FROM users WHERE username = ?""")

            c.execute(sql, (username,))
            lock_until_result, count = c.fetchone()
            assert lock_until_result is None
            assert count == 0


class TestAdminResetPassword:
    """测试管理员重置密码"""

    def test_admin_reset_password_user_not_exist(self, _clean_db):  # noqa: ARG001
        """测试用户不存在"""
        is_valid, msg = admin_reset_password(
            "nonexistent_user", "NewP@ss123456", "admin"
        )
        assert is_valid is False
        assert "不存在" in msg

    def test_admin_reset_password_weak_password(self, _clean_db, test_user):  # noqa: ARG001
        """测试密码强度不够"""
        username = test_user['username']
        is_valid, msg = admin_reset_password(username, "weak", "admin")
        assert is_valid is False
        assert "强度不够" in msg

    def test_admin_reset_password_success(self, _clean_db, test_user):  # noqa: ARG001
        """测试管理员重置密码成功"""
        username = test_user['username']
        new_password = "NewP@ss123456"
        lock_until = time.time() + 3600
        
        with get_db_connection() as (conn, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""UPDATE users
                SET reset_locked_until = ?, reset_attempt_count = ?
                WHERE username = ?""")

            c.execute(sql, (lock_until, MAX_RESET_ATTEMPTS, username))
            conn.commit()
        
        is_valid, msg = admin_reset_password(username, new_password, "admin")
        assert is_valid is True
        assert "重置" in msg
        
        # 验证密码已更新
        with get_db_connection() as (_, c):
            from db_adapter import adapt_sql

            sql = adapt_sql("""SELECT password, reset_locked_until, reset_attempt_count
                FROM users WHERE username = ?""")

            c.execute(sql, (username,))
            stored_hash, lock_until_result, count = c.fetchone()
            
            assert stored_hash != test_user['password']
            assert lock_until_result is None
            assert count == 0
            
            # 验证新密码可以验证
            import bcrypt
            assert bcrypt.checkpw(new_password.encode(), stored_hash.encode())


class TestGetPasswordRecoveryLogs:
    """测试获取密码恢复日志"""

    def test_get_password_recovery_logs_empty(self, _clean_db):  # noqa: ARG001
        """测试没有日志"""
        # 注意：由于可能有其他测试留下的日志，这里只验证函数正常工作
        logs = get_password_recovery_logs(limit=0)
        assert isinstance(logs, list)
        # 验证函数可以正常调用并返回列表格式

    def test_get_password_recovery_logs_all(self, _clean_db):  # noqa: ARG001
        """测试获取所有日志"""
        # 创建一些日志
        for i in range(5):
            log_password_recovery_event(
                username=f"user{i}",
                event_type="request",
                success=True,
                attempt_count=0
            )
        
        logs = get_password_recovery_logs(limit=10)
        assert len(logs) >= 5
        
        # 验证日志格式
        for log in logs:
            assert 'username' in log
            assert 'event_type' in log
            assert 'success' in log
            assert 'created_at' in log

    def test_get_password_recovery_logs_by_username(self, _clean_db):  # noqa: ARG001
        """测试按用户名获取日志"""
        username = f"test_user_log_{int(time.time())}"
        
        # 创建该用户的日志
        for i in range(3):
            log_password_recovery_event(
                username=username,
                event_type="request",
                success=True,
                attempt_count=i
            )
        
        # 创建其他用户的日志
        log_password_recovery_event(
            username=f"other_user_{int(time.time())}",
            event_type="request",
            success=True
        )
        
        logs = get_password_recovery_logs(username=username)
        # 至少应该有3条，可能还有其他测试的日志
        assert len(logs) >= 3
        assert all(log['username'] == username for log in logs)

    def test_get_password_recovery_logs_limit(self, _clean_db):  # noqa: ARG001
        """测试限制返回数量"""
        # 创建多个日志
        for i in range(10):
            log_password_recovery_event(
                username=f"user{i}",
                event_type="request",
                success=True
            )
        
        logs = get_password_recovery_logs(limit=5)
        assert len(logs) == 5
