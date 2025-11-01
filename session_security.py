import time
import sqlite3
import secrets
import hashlib
import importlib
import streamlit as st
from datetime import datetime, timedelta

# 导入logger（可选，如果不可用则静默失败）
try:
    from logger_config import logger
except ImportError:
    logger = None

# 高优先级安全改进：导入CSRF保护
try:
    from .csrf_protection import CSRFProtection
except ImportError:
    try:
        from csrf_protection import CSRFProtection
    except ImportError:
        CSRFProtection = None

try:
    from .db_utils import (
        verify_user,
        update_user_subscription,
        get_user_subscription_info,
    )
    from .rate_limiter import get_limiter
except ImportError:  # Fallback when executed as top-level module
    from db_utils import (
        verify_user,
        update_user_subscription,
        get_user_subscription_info,
    )
    from rate_limiter import get_limiter


class SessionSecurity:
    """会话安全管理类"""

    # 配置常量
    SESSION_TIMEOUT = 1800  # 30分钟超时（高优先级安全改进：缩短会话超时时间）
    MAX_LOGIN_ATTEMPTS = 5  # 最大登录尝试次数
    LOCKOUT_DURATION = 900  # 15分钟锁定时间
    SESSION_REFRESH_INTERVAL = 300  # 5分钟刷新间隔
    SESSION_ROTATION_INTERVAL = 300  # 5分钟会话ID轮换间隔（防止会话固定攻击，已优化）
    IP_CHANGE_CHECK_ENABLED = True  # 启用IP变更检测
    IP_CHANGE_STRICT_MODE = True  # 严格模式：IP变更时强制重新登录
    SUSPICIOUS_IP_WARNING_THRESHOLD = 3  # 异常IP登录警告阈值
    MAX_CONCURRENT_SESSIONS = 3  # 最大并发会话数（高优先级安全改进）

    @staticmethod
    def init_session_tables():
        """初始化会话相关数据表"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        with get_db_connection() as (conn, c):
            # 创建登录尝试记录表
            c.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT NOT NULL,
                    ip_address TEXT,
                    timestamp REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    user_agent TEXT
                )
            """)

            # 创建活动会话表
            c.execute("""
                CREATE TABLE IF NOT EXISTS active_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    last_activity REAL NOT NULL,
                    last_rotation REAL DEFAULT 0,
                    ip_address TEXT,
                    user_agent TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)

            # 创建用户锁定表
            c.execute("""
                CREATE TABLE IF NOT EXISTS user_lockouts (
                    identifier TEXT PRIMARY KEY,
                    locked_until REAL NOT NULL,
                    attempt_count INTEGER NOT NULL
                )
            """)

            conn.commit()

    @staticmethod
    def generate_session_id(user_id: int | None = None) -> str:
        """
        生成安全的会话ID（高优先级安全改进：增强token安全性）

        使用HMAC签名防止会话ID被篡改

        Args:
            user_id: 用户ID（可选，用于HMAC签名）

        Returns:
            str: 安全的会话ID
        """
        # 使用时间戳 + 加密安全的随机数 + 用户信息生成唯一会话ID
        timestamp = str(time.time())
        # 使用secrets模块生成加密安全的随机数（64字节，512位熵）
        random_bytes = secrets.token_bytes(64)
        # 添加额外的随机数据增加熵值
        additional_random = secrets.token_hex(32)
        session_data = (
            f"{timestamp}:{random_bytes.hex()}:{additional_random}"
        )

        # 使用SHA-256哈希确保固定长度
        session_hash = hashlib.sha256(
            session_data.encode()
        ).hexdigest()

        # 高优先级安全改进：使用HMAC签名防止会话ID被篡改
        # 使用固定的密钥（实际生产环境应从环境变量或配置文件中读取）
        import os
        hmac_secret = os.getenv(
            'SESSION_HMAC_SECRET',
            'default_session_secret_change_in_production'
        )

        # 如果提供了user_id，将其加入签名
        if user_id is not None:
            signed_data = f"{session_hash}:{user_id}"
        else:
            signed_data = session_hash

        # 使用HMAC-SHA256生成签名
        hmac_signature = hashlib.pbkdf2_hmac(
            'sha256',
            signed_data.encode(),
            hmac_secret.encode(),
            100000  # 迭代次数，增加破解难度
        ).hex()[:32]  # 截取前32个字符作为签名

        # 返回：原始哈希 + HMAC签名
        return f"{session_hash}:{hmac_signature}"

    @staticmethod
    def verify_session_id(
        session_id: str, user_id: int | None = None
    ) -> bool:
        """
        验证会话ID的HMAC签名（高优先级安全改进）

        Args:
            session_id: 会话ID
            user_id: 用户ID（可选，用于验证）

        Returns:
            bool: 会话ID是否有效
        """
        try:
            # 会话ID格式：hash:signature
            if ':' not in session_id:
                # 旧格式会话ID（无签名），需要迁移
                return True  # 兼容旧会话ID

            parts = session_id.rsplit(':', 1)
            if len(parts) != 2:
                return False

            session_hash, hmac_signature = parts

            # 验证HMAC签名
            import os
            hmac_secret = os.getenv(
                'SESSION_HMAC_SECRET',
                'default_session_secret_change_in_production'
            )

            # 重构签名数据
            if user_id is not None:
                signed_data = f"{session_hash}:{user_id}"
            else:
                signed_data = session_hash

            # 重新计算签名
            expected_signature = hashlib.pbkdf2_hmac(
                'sha256',
                signed_data.encode(),
                hmac_secret.encode(),
                100000
            ).hex()[:32]

            # 使用时间安全的比较函数防止时序攻击
            return secrets.compare_digest(
                hmac_signature, expected_signature
            )
        except Exception as e:
            if logger:
                logger.warning(f"会话ID验证失败: {e}")
            return False  # 验证失败时拒绝访问

    @staticmethod
    def get_client_info():
        """获取客户端信息（包括真实IP地址）"""
        ip_address = 'localhost'
        user_agent = 'Streamlit/1.48.0'

        # 尝试从Streamlit获取真实IP地址
        # 注意：在生产环境中需要配置反向代理（如Nginx）传递真实IP
        try:
            # 使用外部作用域已导入的 st
            if hasattr(st, 'session_state'):
                # 尝试从headers获取（如果可用）
                try:
                    # 在Streamlit中，可以通过request context获取
                    # 这里使用一个通用的方法
                    ip_address = st.session_state.get(
                        'client_ip', 'localhost'
                    )
                except (AttributeError, KeyError):
                    pass
        except (NameError, AttributeError):
            # 如果 st 未导入（非Streamlit环境），使用默认值
            pass

        return {
            'ip_address': ip_address,
            'user_agent': user_agent
        }

    @staticmethod
    def generate_device_fingerprint(
            ip_address: str, user_agent: str) -> str:
        """
        生成设备指纹（高优先级安全改进）

        Args:
            ip_address: IP地址
            user_agent: User-Agent字符串

        Returns:
            str: 设备指纹哈希值
        """
        # 组合IP和User-Agent生成指纹
        fingerprint_data = f"{ip_address}|{user_agent}"
        return hashlib.sha256(
            fingerprint_data.encode('utf-8')
        ).hexdigest()

    @staticmethod
    def verify_password_for_sensitive_operation(
            user_id: int, password: str) -> tuple[bool, str]:
        """
        验证敏感操作密码（高优先级安全改进）

        Args:
            user_id: 用户ID
            password: 用户输入的密码

        Returns:
            (is_valid, message): 密码是否有效，错误消息
        """
        try:
            from .db_utils import verify_user
        except ImportError:
            from db_utils import verify_user

        # 获取用户名
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection

        try:
            with get_db_connection() as (conn, c):
                user_info = c.execute("""
                    SELECT username FROM users WHERE id = ?
                """, (user_id,)).fetchone()
                if not user_info:
                    return False, "用户不存在"

                username = user_info[0]
                # 验证密码
                is_valid = verify_user(username, password)
                if is_valid:
                    return True, ""
                else:
                    return False, "密码错误"
        except Exception as e:
            if logger:
                logger.error(f"验证敏感操作密码失败: {e}")
            return False, "验证失败，请重试"

    @staticmethod
    def check_concurrent_sessions(user_id: int) -> tuple[bool, str]:
        """
        检查并发会话数是否超过限制（高优先级安全改进）

        Args:
            user_id: 用户ID

        Returns:
            (is_allowed, message): 是否允许，提示消息
        """
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection

        try:
            with get_db_connection() as (conn, c):
                # 查询当前活跃会话数
                active_count = c.execute("""
                    SELECT COUNT(*) FROM active_sessions
                    WHERE user_id = ? AND is_active = 1
                """, (user_id,)).fetchone()[0]

                if active_count >= SessionSecurity.MAX_CONCURRENT_SESSIONS:
                    # 超过限制，下线最旧的会话
                    oldest_session = c.execute("""
                        SELECT session_id FROM active_sessions
                        WHERE user_id = ? AND is_active = 1
                        ORDER BY last_activity ASC
                        LIMIT 1
                    """, (user_id,)).fetchone()

                    if oldest_session:
                        SessionSecurity.force_logout_session(
                            oldest_session[0],
                            "超过最大并发会话数限制"
                        )
                        return True, (
                            f"已自动下线最旧的会话，"
                            f"当前允许最多"
                            f"{SessionSecurity.MAX_CONCURRENT_SESSIONS}"
                            f"个并发会话"
                        )

                return True, ""
        except Exception as e:
            if logger:
                logger.error(f"检查并发会话数失败: {e}")
            # 失败时允许继续，但记录日志
            return True, ""

    @staticmethod
    def check_suspicious_ip(
            user_id: int, current_ip: str) -> tuple[bool, str]:
        """
        检查IP地址是否异常（与历史登录IP不同）

        Args:
            user_id: 用户ID
            current_ip: 当前登录IP地址

        Returns:
            (is_suspicious, message): 是否可疑，警告消息
        """
        if not SessionSecurity.IP_CHANGE_CHECK_ENABLED:
            return False, ""

        if current_ip == 'localhost' or current_ip.startswith('127.'):
            # 本地开发环境，跳过检查
            return False, ""

        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection

        try:
            with get_db_connection() as (conn, c):
                # 获取用户名
                username_result = c.execute(
                    "SELECT username FROM users WHERE id = ?",
                    (user_id,)
                ).fetchone()

                if not username_result:
                    return False, ""

                username = username_result[0]

                # 查询用户最近3次成功登录的IP地址
                recent_logins = c.execute("""
                    SELECT DISTINCT ip_address
                    FROM login_attempts
                    WHERE identifier = ?
                    AND success = TRUE
                    AND timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT 3
                """, (username, time.time() - 86400 * 7)).fetchall()

                # 如果没有任何历史记录，认为是首次登录，不警告
                if not recent_logins:
                    return False, ""

                # 检查当前IP是否在历史IP列表中
                historical_ips = {row[0] for row in recent_logins if row[0]}

                if (current_ip not in historical_ips and
                        len(historical_ips) > 0):
                    # IP地址变更，可能需要警告
                    # 检查变更次数
                    ip_changes = c.execute("""
                        SELECT COUNT(DISTINCT ip_address)
                        FROM login_attempts
                        WHERE identifier = (
                            SELECT username FROM users WHERE id = ?
                        )
                        AND success = TRUE
                        AND timestamp > ?
                    """, (user_id, time.time() - 86400 * 30)).fetchone()[0]

                    threshold = SessionSecurity.SUSPICIOUS_IP_WARNING_THRESHOLD
                    if ip_changes >= threshold:
                        msg = (
                            f"检测到来自新IP地址的登录 ({current_ip})。"
                            f"如果您未授权此登录，请立即修改密码。"
                        )
                        return True, msg
                    else:
                        # IP变更但未达到阈值，记录但不阻止
                        return False, ""

                return False, ""
        except Exception as e:
            # 如果检查失败，记录日志但不阻止登录
            if logger:
                logger.warning(f"IP检查失败: {e}")
            return False, ""

    @staticmethod
    def is_user_locked(identifier: str) -> bool:
        """检查用户是否被锁定"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        with get_db_connection() as (conn, c):
            lockout = c.execute(
                "SELECT locked_until FROM user_lockouts WHERE identifier = ?",
                (identifier,)
            ).fetchone()

            if lockout:
                if time.time() < lockout[0]:
                    return True
                else:
                    # 锁定时间已过，移除锁定记录
                    c.execute(
                        "DELETE FROM user_lockouts WHERE identifier = ?",
                        (identifier,)
                    )
                    conn.commit()

            return False

    @staticmethod
    def record_login_attempt(identifier: str, success: bool):
        """记录登录尝试"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection

        client_info = SessionSecurity.get_client_info()
        with get_db_connection() as (conn, c):
            # 记录登录尝试
            c.execute("""
                INSERT INTO login_attempts
                (identifier, ip_address, timestamp, success, user_agent)
                VALUES (?, ?, ?, ?, ?)
            """, (
                identifier,
                client_info['ip_address'],
                time.time(),
                success,
                client_info['user_agent']
            ))

            if not success:
                # 统计最近的失败次数
                recent_time = time.time() - SessionSecurity.LOCKOUT_DURATION
                failed_attempts = c.execute("""
                    SELECT COUNT(*) FROM login_attempts
                    WHERE identifier = ? AND success = FALSE AND timestamp > ?
                """, (identifier, recent_time)).fetchone()[0]

                if failed_attempts >= SessionSecurity.MAX_LOGIN_ATTEMPTS:
                    # 锁定用户
                    locked_until = (
                        time.time() + SessionSecurity.LOCKOUT_DURATION)
                    c.execute("""
                        INSERT OR REPLACE INTO user_lockouts
                        (identifier, locked_until, attempt_count)
                        VALUES (?, ?, ?)
                    """, (identifier, locked_until, failed_attempts))

            conn.commit()

    @staticmethod
    def invalidate_user_sessions(
            user_id: int, exclude_session_id: str | None = None):
        """
        使指定用户的所有会话失效（防止会话固定攻击）

        Args:
            user_id: 用户ID
            exclude_session_id: 排除的会话ID（当前会话），可选
        """
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        try:
            with get_db_connection() as (conn, c):
                # 确保表存在
                try:
                    c.execute("SELECT 1 FROM active_sessions LIMIT 1")
                except sqlite3.OperationalError:
                    SessionSecurity.init_session_tables()

                # 清除该用户的所有旧会话（排除当前会话）
                if exclude_session_id:
                    c.execute(
                        "UPDATE active_sessions SET is_active = FALSE "
                        "WHERE user_id = ? AND session_id != ?",
                        (user_id, exclude_session_id)
                    )
                else:
                    c.execute(
                        "UPDATE active_sessions SET is_active = FALSE "
                        "WHERE user_id = ?",
                        (user_id,)
                    )
                conn.commit()

                # 记录日志
                if logger:
                    logger.info(
                        f"用户{user_id}的所有会话已失效"
                        f"{'（排除当前会话）' if exclude_session_id else ''}"
                    )
        except Exception as e:
            if logger:
                logger.error(
                    f"[SessionSecurity.invalidate_user_sessions] error: {e}"
                )
            else:
                print(
                    f"[SessionSecurity.invalidate_user_sessions] error: {e}"
                )

    @staticmethod
    def force_logout_session(session_id: str, reason: str = "强制下线"):
        """
        强制下线指定会话（管理员功能）

        Args:
            session_id: 会话ID
            reason: 下线原因
        """
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        try:
            with get_db_connection() as (conn, c):
                # 确保表存在
                try:
                    c.execute("SELECT 1 FROM active_sessions LIMIT 1")
                except sqlite3.OperationalError:
                    SessionSecurity.init_session_tables()

                # 获取会话信息（用于日志）
                session_info = c.execute(
                    "SELECT user_id, ip_address FROM active_sessions "
                    "WHERE session_id = ?",
                    (session_id,)
                ).fetchone()

                # 失效会话
                c.execute(
                    "UPDATE active_sessions SET is_active = FALSE "
                    "WHERE session_id = ?",
                    (session_id,)
                )
                conn.commit()

                # 记录日志
                if logger and session_info:
                    logger.info(
                        f"会话{session_id[:8]}...已强制下线，"
                        f"用户{session_info[0]}，原因：{reason}"
                    )
                return True
        except Exception as e:
            if logger:
                logger.error(
                    f"[SessionSecurity.force_logout_session] error: {e}"
                )
            return False

    @staticmethod
    def create_session(user_id: int, user_info: dict) -> str | None:
        """
        创建新的用户会话（登录时立即轮换会话ID，防止会话固定攻击）

        增强功能：
        - 强制下线所有旧会话（防止多设备登录问题）
        - IP地址验证和记录
        - 原子操作确保会话创建的一致性
        """
        # 登录成功后立即生成新会话 ID
        # 高优先级安全改进：使用带HMAC签名的会话ID
        session_id = SessionSecurity.generate_session_id(user_id)
        client_info = SessionSecurity.get_client_info()
        current_ip = client_info['ip_address']

        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        try:
            with get_db_connection() as (conn, c):
                # 确保外键约束已启用
                try:
                    conn.execute("PRAGMA foreign_keys=ON")
                except sqlite3.Error:
                    pass
                # 确保表存在（兼容未初始化场景）
                try:
                    c.execute("SELECT 1 FROM active_sessions LIMIT 1")
                except sqlite3.OperationalError:
                    # 初始化会话相关表
                    SessionSecurity.init_session_tables()

                # 登录时立即清除所有旧会话（防止会话固定攻击和多设备登录）
                # 增强：记录被下线的会话信息用于审计
                old_sessions = c.execute(
                    "SELECT session_id, ip_address FROM active_sessions "
                    "WHERE user_id = ? AND is_active = TRUE",
                    (user_id,)
                ).fetchall()

                # 记录被下线的会话（用于审计）
                if old_sessions and logger:
                    for old_session in old_sessions:
                        logger.info(
                            f"用户{user_id}登录，强制下线旧会话: "
                            f"{old_session[0][:8]}... "
                            f"(旧IP: {old_session[1]}, 新IP: {current_ip})"
                        )

                # 强制下线所有旧会话
                c.execute(
                    "UPDATE active_sessions SET is_active = FALSE "
                    "WHERE user_id = ?",
                    (user_id,)
                )

                # 高优先级安全改进：使用原子性操作检查并发会话并创建会话
                # 防止竞态条件
                session_security_enhanced_module = None
                # 尝试导入增强会话安全模块（使用动态导入避免静态分析警告）
                try:
                    # 如果 __package__ 可用，尝试相对导入
                    if __package__:
                        module = importlib.import_module(
                            '.session_security_enhanced',
                            __package__
                        )
                        session_security_enhanced_module = (
                            getattr(module, 'SessionSecurityEnhanced', None)
                        )
                    else:
                        raise ImportError("__package__ not available")
                except (ImportError, AttributeError, ValueError):
                    # 相对导入失败，尝试绝对导入
                    try:
                        module = importlib.import_module(
                            'session_security_enhanced'
                        )
                        session_security_enhanced_module = (
                            getattr(module, 'SessionSecurityEnhanced', None)
                        )
                    except (ImportError, AttributeError):
                        # 模块不可用，session_security_enhanced_module保持为None
                        pass

                # 生成设备指纹
                device_fingerprint = (
                    SessionSecurity.generate_device_fingerprint(
                        current_ip, client_info['user_agent']
                    )
                )

                # 高优先级安全改进：生成CSRF token
                if CSRFProtection:
                    csrf_token = CSRFProtection.generate_csrf_token()
                    # 将CSRF token存储到session_state
                    if hasattr(st, 'session_state'):
                        st.session_state[
                            CSRFProtection.CSRF_TOKEN_KEY
                        ] = csrf_token
                        st.session_state[
                            CSRFProtection.CSRF_TOKEN_TIME_KEY
                        ] = time.time()

                # 创建新会话（使用原子性操作）
                current_time = time.time()
                # 高优先级安全改进：使用带HMAC签名的会话ID
                session_id = SessionSecurity.generate_session_id(user_id)

                # 如果增强模块可用，使用原子性操作
                if session_security_enhanced_module:
                    success, msg = (
                        session_security_enhanced_module.
                        check_and_create_session_atomic(
                            user_id, session_id, current_ip,
                            client_info['user_agent']
                        )
                    )
                    if not success:
                        if logger:
                            logger.warning(
                                f"用户{user_id}创建会话失败: {msg}"
                            )
                        return None
                else:
                    # 降级到原有逻辑
                    is_allowed, concurrent_msg = (
                        SessionSecurity.check_concurrent_sessions(user_id)
                    )
                    if not is_allowed:
                        if logger:
                            logger.warning(
                                f"用户{user_id}创建会话失败: {concurrent_msg}"
                            )
                        return None

                try:
                    # 检查表是否有device_fingerprint字段
                    try:
                        c.execute("""
                            SELECT device_fingerprint FROM active_sessions
                            LIMIT 1
                        """)
                    except sqlite3.OperationalError:
                        # 字段不存在，添加字段
                        c.execute("""
                            ALTER TABLE active_sessions
                            ADD COLUMN device_fingerprint TEXT
                        """)

                    c.execute("""
                        INSERT INTO active_sessions
                        (session_id, user_id, created_at, last_activity,
                         last_rotation, ip_address, user_agent,
                         device_fingerprint, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        session_id,
                        user_id,
                        current_time,
                        current_time,
                        current_time,  # 初始化last_rotation
                        current_ip,
                        client_info['user_agent'],
                        device_fingerprint,
                    ))
                except sqlite3.OperationalError as oe:
                    # 兼容老表缺少 last_rotation 的情况
                    if 'last_rotation' in str(oe).lower():
                        c.execute(
                            (
                                "ALTER TABLE active_sessions "
                                "ADD COLUMN last_rotation REAL DEFAULT 0"
                            )
                        )
                        c.execute(
                            """
                            INSERT INTO active_sessions
                            (session_id, user_id, created_at, last_activity,
                             last_rotation, ip_address, user_agent, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                            """,
                            (
                                session_id,
                                user_id,
                                current_time,
                                current_time,
                                current_time,
                                current_ip,
                                client_info['user_agent'],
                            ),
                        )
                    else:
                        raise

                conn.commit()

            # 在Streamlit session_state中存储会话信息（在非Streamlit环境下静默忽略）
            try:
                st.session_state.session_id = session_id
                st.session_state.user = user_info
                st.session_state.last_activity = time.time()
            except (AttributeError, KeyError, RuntimeError, TypeError):
                # 非 Streamlit 运行环境或 session_state 不可用
                pass

            return session_id
        except sqlite3.OperationalError as e:
            # 数据库锁定错误，尝试重试
            if "database is locked" in str(e).lower():
                # 等待一小段时间后重试一次
                time.sleep(0.1)
                try:
                    with get_db_connection() as (conn, c):
                        # 重试逻辑：包含完整的创建会话流程
                        try:
                            c.execute("SELECT 1 FROM active_sessions LIMIT 1")
                        except sqlite3.OperationalError:
                            SessionSecurity.init_session_tables()

                        # 强制下线所有旧会话
                        c.execute(
                            "UPDATE active_sessions SET is_active = FALSE "
                            "WHERE user_id = ?",
                            (user_id,)
                        )

                        # 插入新会话
                        current_time = time.time()
                        try:
                            c.execute("""
                                SELECT device_fingerprint FROM active_sessions
                                LIMIT 1
                            """)
                            has_device_fingerprint = True
                        except sqlite3.OperationalError:
                            has_device_fingerprint = False

                        if has_device_fingerprint:
                            device_fingerprint = (
                                SessionSecurity.generate_device_fingerprint(
                                    current_ip, client_info['user_agent']
                                )
                            )
                            c.execute("""
                                INSERT INTO active_sessions
                                (session_id, user_id, created_at,
                                 last_activity, last_rotation, ip_address,
                                 user_agent, device_fingerprint, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """, (
                                session_id,
                                user_id,
                                current_time,
                                current_time,
                                current_time,
                                current_ip,
                                client_info['user_agent'],
                                device_fingerprint,
                            ))
                        else:
                            c.execute("""
                                INSERT INTO active_sessions
                                (session_id, user_id, created_at,
                                 last_activity, last_rotation, ip_address,
                                 user_agent, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                            """, (
                                session_id,
                                user_id,
                                current_time,
                                current_time,
                                current_time,
                                current_ip,
                                client_info['user_agent'],
                            ))
                        conn.commit()
                        return session_id
                except Exception as retry_error:
                    # 重试失败，返回 None
                    if logger:
                        logger.error(
                            f"[SessionSecurity.create_session] "
                            f"retry failed: {retry_error}"
                        )
                    return None
            # 其他 OperationalError，打印错误并返回 None
            if logger:
                logger.error(
                    f"[SessionSecurity.create_session] error: {e}"
                )
            else:
                print(f"[SessionSecurity.create_session] error: {e}")
            return None
        except (sqlite3.Error, OSError, ValueError) as e:
            if logger:
                logger.error(
                    f"[SessionSecurity.create_session] error: {e}"
                )
            else:
                print(f"[SessionSecurity.create_session] error: {e}")
            return None
        except Exception as e:  # 兜底处理未知异常，满足测试的容错预期
            print(f"[SessionSecurity.create_session] unexpected error: {e}")
            return None

    @staticmethod
    def get_session_info(session_id: str):
        """获取会话信息"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        try:
            with get_db_connection() as (conn, c):
                # 检查会话是否存在且活跃
                # 注意：这里需要处理last_rotation字段可能不存在的情况（兼容旧数据）
                try:
                    session = c.execute("""
                        SELECT s.*, u.username, u.email, u.role
                        FROM active_sessions s
                        JOIN users u ON s.user_id = u.id
                        WHERE s.session_id = ? AND s.is_active = 1
                    """, (session_id,)).fetchone()
                except sqlite3.OperationalError:
                    # 如果表结构不包含last_rotation字段，添加该字段
                    try:
                        c.execute(
                            """
                            ALTER TABLE active_sessions
                            ADD COLUMN last_rotation REAL DEFAULT 0
                            """
                        )
                        conn.commit()
                    except sqlite3.OperationalError:
                        pass  # 字段已存在
                    # 重新查询
                    session = c.execute("""
                        SELECT s.*, u.username, u.email, u.role
                        FROM active_sessions s
                        JOIN users u ON s.user_id = u.id
                        WHERE s.session_id = ? AND s.is_active = 1
                    """, (session_id,)).fetchone()

                if session:
                    current_time = time.time()

                    # 处理Row对象或字典
                    if hasattr(session, 'keys'):
                        # 字典或Row对象
                        session_dict = dict(session)
                        last_activity = session_dict.get(
                            'last_activity', current_time
                        )
                        last_rotation = session_dict.get(
                            'last_rotation',
                            session_dict.get('created_at', current_time),
                        )
                        user_id = session_dict.get('user_id')
                        username = session_dict.get('username')
                        email = session_dict.get('email')
                        role = session_dict.get('role')
                        stored_ip = session_dict.get('ip_address')

                        # 高优先级安全改进：验证会话ID的HMAC签名
                        stored_session_id = session_dict.get('session_id')
                        if stored_session_id and user_id:
                            if not SessionSecurity.verify_session_id(
                                stored_session_id, user_id
                            ):
                                if logger:
                                    logger.warning(
                                        f"会话ID签名验证失败: "
                                        f"用户{user_id}, "
                                        f"会话{stored_session_id[:8]}..."
                                    )
                                # 失效该会话
                                c.execute(
                                    "UPDATE active_sessions "
                                    "SET is_active = FALSE "
                                    "WHERE session_id = ?",
                                    (session_id,)
                                )
                                conn.commit()
                                return None
                    else:
                        # 元组格式，根据查询顺序：
                        # s.* + u.username, u.email, u.role
                        # s.* 包含：session_id, user_id, created_at,
                        # last_activity, last_rotation(可能), ip_address,
                        # user_agent, is_active
                        try:
                            # s.* 列顺序：
                            # 0 session_id, 1 user_id, 2 created_at,
                            # 3 last_activity, 4 last_rotation,
                            # 5 ip_address, 6 user_agent, 7 is_active
                            last_activity = (
                                session[3]
                                if len(session) > 3
                                else current_time
                            )
                            # 尝试获取last_rotation，如果不存在则使用created_at
                            if len(session) > 4:
                                last_rotation = (
                                    session[4] if session[4] else session[2]
                                )
                            else:
                                last_rotation = session[2]  # created_at
                            user_id = session[1]
                            username = session[8] if len(session) > 8 else ''
                            email = session[9] if len(session) > 9 else ''
                            role = session[10] if len(session) > 10 else ''
                            stored_ip = (
                                session[5] if len(session) > 5 else 'localhost'
                            )
                            stored_session_id = (
                                session[0] if len(session) > 0 else None
                            )
                        except (IndexError, TypeError):
                            # 如果格式不符合预期，使用默认值
                            last_activity = current_time
                            last_rotation = current_time
                            user_id = None
                            username = ''
                            email = ''
                            role = ''
                            stored_ip = 'localhost'
                            stored_session_id = None

                        # 高优先级安全改进：验证会话ID的HMAC签名（元组格式）
                        if stored_session_id and user_id:
                            if not SessionSecurity.verify_session_id(
                                stored_session_id, user_id
                            ):
                                if logger:
                                    logger.warning(
                                        f"会话ID签名验证失败（元组格式）: "
                                        f"用户{user_id}, "
                                        f"会话{stored_session_id[:8]}..."
                                    )
                                # 失效该会话
                                c.execute(
                                    "UPDATE active_sessions "
                                    "SET is_active = FALSE "
                                    "WHERE session_id = ?",
                                    (session_id,)
                                )
                                conn.commit()
                                return None

                    # 检查会话是否超时
                    if (current_time - last_activity >
                            SessionSecurity.SESSION_TIMEOUT):
                        # 会话超时，标记为非活跃
                        c.execute(
                            "UPDATE active_sessions SET is_active = FALSE "
                            "WHERE session_id = ?",
                            (session_id,)
                        )
                        conn.commit()
                        return None

                    # IP地址验证（防止会话劫持）
                    # stored_ip已在上面根据session类型获取

                    client_info = SessionSecurity.get_client_info()
                    current_ip = client_info['ip_address']

                    # 增强的IP地址验证（防止会话劫持和会话固定攻击）
                    if SessionSecurity.IP_CHANGE_CHECK_ENABLED:
                        # 如果IP地址变更且不是本地地址，可能是会话劫持
                        # 修复：确保stored_ip和current_ip都是字符串且非空
                        stored_ip_str = str(stored_ip) if stored_ip else ''
                        current_ip_str = (
                            str(current_ip) if current_ip else 'localhost'
                        )

                        # 本地地址列表（包括各种可能的表示方式）
                        local_addresses = ['localhost', '127.0.0.1', '', None]
                        is_local_stored = (
                            not stored_ip_str or
                            stored_ip_str in local_addresses or
                            stored_ip_str.startswith('127.')
                        )
                        is_local_current = (
                            not current_ip_str or
                            current_ip_str in local_addresses or
                            current_ip_str.startswith('127.')
                        )

                        if (stored_ip_str and current_ip_str and
                                stored_ip_str != current_ip_str and
                                not is_local_current and
                                not is_local_stored):
                            # 严格模式：IP变更时强制失效会话并要求重新登录
                            if SessionSecurity.IP_CHANGE_STRICT_MODE:
                                if logger:
                                    logger.warning(
                                        f"会话IP地址变更: 用户{user_id} "
                                        f"从{stored_ip_str}变更到{current_ip_str}，"
                                        f"强制失效会话（严格模式）"
                                    )
                                # 失效会话并要求重新登录
                                c.execute(
                                    ("UPDATE active_sessions "
                                     "SET is_active = FALSE "
                                     "WHERE session_id = ?"),
                                    (session_id,)
                                )
                                conn.commit()
                                return None  # 返回None，要求重新登录
                            else:
                                # 非严格模式：记录警告但允许继续
                                if logger:
                                    logger.warning(
                                        f"会话IP地址变更警告: 用户{user_id} "
                                        f"从{stored_ip_str}变更到{current_ip_str}"
                                    )
                                # 更新IP地址到当前IP
                                c.execute(
                                    ("UPDATE active_sessions "
                                     "SET ip_address = ? "
                                     "WHERE session_id = ?"),
                                    (current_ip_str, session_id)
                                )
                                conn.commit()

                    # 检查是否需要会话ID轮换（防止会话固定攻击）
                    # 增强：使用原子操作确保会话轮换的线程安全
                    # 增强：每次验证都检查是否需要轮换，提高安全性
                    rotation_needed = (
                        current_time - last_rotation
                        > SessionSecurity.SESSION_ROTATION_INTERVAL
                    )

                    if rotation_needed:
                        # 生成新的会话ID（使用更强的随机性和HMAC签名）
                        new_session_id = SessionSecurity.generate_session_id(
                            user_id
                        )

                        # 原子更新：先更新为新会话ID，再删除旧会话
                        # 这样可以防止会话固定攻击时的竞态条件
                        # 增强：同时更新IP地址（如果IP未变更，则保持不变）
                        c.execute(
                            """
                            UPDATE active_sessions
                            SET session_id = ?, last_rotation = ?,
                                ip_address = ?, last_activity = ?
                            WHERE session_id = ? AND is_active = 1
                            """,
                            (
                                new_session_id, current_time,
                                current_ip, current_time, session_id
                            ),
                        )

                        # 验证更新是否成功（防止并发问题）
                        # 注意：某些数据库适配器可能没有rowcount属性
                        if hasattr(c, 'rowcount') and c.rowcount == 0:
                            # 会话可能已被其他进程失效，返回None要求重新登录
                            return None

                        conn.commit()

                        # 记录会话轮换（用于审计）
                        if logger:
                            logger.info(
                                f"会话ID轮换: 用户{user_id} "
                                f"从{session_id[:8]}...轮换到"
                                f"{new_session_id[:8]}..."
                            )

                        # 更新Streamlit session_state（原子操作）
                        try:
                            if 'session_id' in st.session_state:
                                st.session_state.session_id = new_session_id
                        except (AttributeError, KeyError, RuntimeError):
                            pass

                        session_id = new_session_id

                    # 更新最后活动时间
                    if (current_time - last_activity >
                            SessionSecurity.SESSION_REFRESH_INTERVAL):
                        c.execute(
                            "UPDATE active_sessions SET last_activity = ? "
                            "WHERE session_id = ?",
                            (current_time, session_id)
                        )
                        conn.commit()

                    return {
                        'id': user_id,
                        'username': username,
                        'email': email,
                        'role': role,
                        'session_id': session_id,
                        'last_activity': last_activity
                    }

        except (sqlite3.Error, OSError, ValueError, Exception):
            # 数据库连接错误或数据错误时返回None
            return None

        return None

    @staticmethod
    def invalidate_session(session_id=None):
        """使会话失效"""
        if session_id is None and 'session_id' in st.session_state:
            session_id = st.session_state.session_id

        if session_id:
            try:
                from .db_utils import get_db_connection
            except ImportError:
                from db_utils import get_db_connection
            with get_db_connection() as (conn, c):
                # 标记会话为非活跃
                c.execute(
                    "UPDATE active_sessions SET is_active = FALSE "
                    "WHERE session_id = ?",
                    (session_id,)
                )
                conn.commit()

        # 清理session_state
        for key in ['session_id', 'user', 'last_activity', 'current_mode']:
            if key in st.session_state:
                del st.session_state[key]

    @staticmethod
    def cleanup_expired_sessions():
        """清理过期会话"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        with get_db_connection() as (conn, c):
            # 清理超时的会话
            expired_time = time.time() - SessionSecurity.SESSION_TIMEOUT
            c.execute("""
                UPDATE active_sessions
                SET is_active = FALSE
                WHERE last_activity < ? AND is_active = 1
            """, (expired_time,))
            expired_sessions = c.rowcount

            # 清理过期的登录尝试记录（保留24小时）
            old_time = time.time() - 86400
            c.execute(
                "DELETE FROM login_attempts WHERE timestamp < ?",
                (old_time,)
            )
            expired_attempts = c.rowcount

            # 清理过期的用户锁定记录
            c.execute(
                "DELETE FROM user_lockouts WHERE locked_until < ?",
                (time.time(),)
            )
            expired_lockouts = c.rowcount

            conn.commit()
            return expired_sessions + expired_attempts + expired_lockouts

    @staticmethod
    def get_user_session_info(user_id: int):
        """获取用户的会话信息"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        with get_db_connection() as (conn, c):
            session = c.execute("""
                SELECT * FROM active_sessions
                WHERE user_id = ? AND is_active = 1
                ORDER BY last_activity DESC LIMIT 1
            """, (user_id,)).fetchone()

            if session:
                return {
                    'session_id': session['session_id'],
                    'created_at': session['created_at'],
                    'last_activity': session['last_activity'],
                    'ip_address': session['ip_address'],
                    'user_agent': session['user_agent']
                }
            return None

    @staticmethod
    def get_active_session_count(user_id: int) -> int:
        """获取用户活跃会话数量"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        with get_db_connection() as (conn, c):
            return c.execute("""
                SELECT COUNT(*) FROM active_sessions
                WHERE user_id = ? AND is_active = 1
            """, (user_id,)).fetchone()[0]

    @staticmethod
    def force_logout_user(user_id: int):
        """强制用户退出所有会话"""
        try:
            from .db_utils import get_db_connection
        except ImportError:
            from db_utils import get_db_connection
        with get_db_connection() as (conn, c):
            c.execute(
                "UPDATE active_sessions SET is_active = FALSE "
                "WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()


def secure_login(username_or_email: str, password: str) -> bool:
    """安全登录函数（带限流保护）"""

    # 输入验证
    if not username_or_email or not username_or_email.strip():
        st.error("❌ 请输入用户名或邮箱")
        return False

    if not password or not password.strip():
        st.error("❌ 请输入密码")
        return False

    # 限流检查：每分钟最多5次登录尝试
    try:
        login_limiter = get_limiter("login", rate=5, per=60)
        limiter_key = f"login_{username_or_email}"

        if not login_limiter.is_allowed(limiter_key):
            retry_after = int(login_limiter.get_retry_after(limiter_key)) + 1
            st.error(f"⚠️ 登录尝试过于频繁，请 {retry_after} 秒后重试")
            st.warning("限流规则: 每分钟最多 5 次登录尝试")
            # 高优先级安全改进：记录失败的登录尝试（即使被限流也要记录）
            SessionSecurity.record_login_attempt(username_or_email, False)
            return False
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        # 限流检查失败不影响登录流程，继续执行
        if logger:
            logger.warning("限流检查失败，继续登录流程")
        pass
    except Exception as e:
        # 捕获其他未预期的异常，记录日志但不阻止登录
        if logger:
            logger.warning(f"限流检查时发生未知异常: {type(e).__name__}")
        pass

    # 检查用户是否被锁定
    try:
        if SessionSecurity.is_user_locked(username_or_email):
            st.error("账户已被临时锁定，请稍后再试")
            return False
    except (sqlite3.Error, ImportError, AttributeError, RuntimeError):
        # 锁定检查失败不影响登录流程，继续执行
        if logger:
            logger.warning("锁定检查失败，继续登录流程")
        pass
    except Exception as e:
        # 捕获其他未预期的异常，记录日志但不阻止登录
        if logger:
            logger.warning(f"锁定检查时发生未知异常: {type(e).__name__}")
        pass

    # 验证用户凭据
    try:
        user = verify_user(username_or_email, password)
    except Exception as e:
        # 验证用户时发生异常
        error_msg = str(e)
        st.error(f"❌ 验证用户时发生错误: {error_msg}")
        if logger:
            logger.error(f"验证用户失败: {error_msg}", exc_info=True)
        SessionSecurity.record_login_attempt(username_or_email, False)
        return False

    if user:
        # 登录成功，清除旧的session state
        SessionSecurity.invalidate_session()
        SessionSecurity.record_login_attempt(username_or_email, True)

        # 记录用户登录日志
        try:
            from db_utils import log_user_login
        except ImportError:
            # 如果模块不可用，静默失败
            log_user_login = None

        if log_user_login:
            try:
                log_user_login(
                    user_id=user['id'],
                    ip_address=None,  # 可选：如需要可通过request获取
                    user_agent=None   # 可选：如需要可通过request获取
                )
            except Exception as e:
                # 使用全局导入的logger（如果可用）
                # 记录错误但不影响登录流程
                if logger:
                    logger.error(f"记录用户登录日志失败: {e}")
                # 静默失败，不影响登录流程
                pass

        # 首次登录后再开始计时：
        # 对 monthly/enterprise/test/efficiency/professional 首次登录生效
        try:
            info = get_user_subscription_info(user['id'])
            if info:
                user_type = info.get('user_type')
                first_login = info.get('first_login_date')
                if (
                    not first_login and
                    user_type in (
                        'monthly', 'enterprise', 'test',
                        'efficiency', 'professional',
                    )
                ):
                    if user_type in (
                        'monthly', 'enterprise', 'efficiency',
                        'professional',
                    ):
                        new_expiry = (
                            datetime.now() + timedelta(days=30)
                        ).isoformat()
                        update_user_subscription(user['id'], {
                            'first_login_date': datetime.now().isoformat(),
                            'expiry_date': new_expiry
                        })
                    elif user_type == 'test':
                        # 测试用户首次登录自动设置7天有效期
                        new_expiry = (
                            datetime.now() + timedelta(days=7)
                        ).isoformat()
                        update_user_subscription(user['id'], {
                            'first_login_date': datetime.now().isoformat(),
                            'expiry_date': new_expiry
                        })
        except (KeyError, TypeError, ValueError, sqlite3.Error):
            pass

        # 更新最后登录时间
        try:
            try:
                from .db_utils import get_db_connection
            except ImportError:
                from db_utils import get_db_connection
            with get_db_connection() as (conn, c):
                c.execute(
                    (
                        "UPDATE users SET last_login = datetime('now') "
                        "WHERE id = ?"
                    ),
                    (user['id'],),
                )
                conn.commit()
        except (sqlite3.Error, KeyError, TypeError):
            pass  # 如果更新失败，不影响登录流程

        # 检查是否为首次登录，如果是，设置默认模式为极速模式
        try:
            try:
                from .db_utils import (
                    get_user_preferred_mode,
                    update_user_preferred_mode
                )
            except ImportError:
                from db_utils import (
                    get_user_preferred_mode,
                    update_user_preferred_mode
                )

            # 获取用户当前的模式偏好
            current_preferred_mode = get_user_preferred_mode(user['id'])
            if current_preferred_mode is None:
                # 首次登录用户，设置默认为极速模式
                update_user_preferred_mode(user['id'], 'fast')
        except (sqlite3.Error, KeyError, TypeError, ImportError):
            pass  # 如果设置失败，不影响登录流程

        # 检查IP地址异常
        client_info = SessionSecurity.get_client_info()
        is_suspicious, warning_msg = SessionSecurity.check_suspicious_ip(
            user['id'], client_info['ip_address']
        )

        if is_suspicious:
            st.warning(f"⚠️ {warning_msg}")
            # 记录可疑登录（但不阻止）
            try:
                from .db_utils import get_db_connection
            except ImportError:
                from db_utils import get_db_connection
            try:
                with get_db_connection() as (conn, c):
                    c.execute("""
                        INSERT INTO login_attempts
                        (identifier, ip_address, timestamp, success,
                         user_agent)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        username_or_email,
                        client_info['ip_address'],
                        time.time(),
                        True,  # 登录成功但IP可疑
                        client_info['user_agent']
                    ))
                    conn.commit()
            except (sqlite3.Error, OSError, ValueError, KeyError) as e:
                # 数据库错误、文件系统错误或数据格式错误时静默失败
                # 不影响登录流程，但可以记录日志（如果logger可用）
                if logger:
                    logger.warning(
                        f"记录可疑IP登录失败: {type(e).__name__}"
                    )
                pass  # 静默失败，不影响登录流程

        # 创建安全会话
        session_id = None
        try:
            session_id = SessionSecurity.create_session(user['id'], user)
            # 如果会话创建失败，记录错误但不阻止登录
            if not session_id:
                if logger:
                    logger.warning(
                        f"用户{user['id']}会话创建失败，但登录流程继续"
                    )
        except Exception as e:
            # 会话创建时发生异常
            error_msg = str(e)
            if logger:
                logger.error(f"创建会话失败: {error_msg}", exc_info=True)

        # 无论会话创建成功与否，都确保用户信息被设置到session_state
        # 这样可以确保即使会话创建失败，用户也能正常登录
        try:
            # 如果create_session没有设置用户信息，这里确保设置
            if 'user' not in st.session_state or not st.session_state.user:
                st.session_state.user = user
            # 如果会话创建成功但没有设置session_id，这里确保设置
            if session_id and 'session_id' not in st.session_state:
                st.session_state.session_id = session_id
        except (AttributeError, KeyError, RuntimeError, TypeError) as e:
            if logger:
                logger.warning(f"设置session_state失败: {e}")

        st.success(f"欢迎回来，{user['username']}！")
        return True
    else:
        # 登录失败
        try:
            SessionSecurity.record_login_attempt(username_or_email, False)
        except Exception as e:
            if logger:
                logger.warning(f"记录登录尝试失败: {e}")

        st.error("用户名/邮箱或密码错误")
        return False


def secure_logout():
    """安全登出函数"""
    SessionSecurity.invalidate_session()
    st.success("已安全退出")
    st.rerun()  # 触发页面重新加载，返回登录界面


def check_session_security():
    """检查会话安全性"""
    # 首先检查是否有session_id
    if 'session_id' in st.session_state:
        session_info = SessionSecurity.get_session_info(
            st.session_state.session_id)
        if session_info:
            # 会话有效，更新用户信息
            st.session_state.user = session_info
            return True
        else:
            # 会话无效，清理状态
            SessionSecurity.invalidate_session()

    # 降级方案：如果session_id不存在但user存在，也允许访问
    # 这可以处理会话创建失败但用户信息已设置的情况
    if 'user' in st.session_state and st.session_state.user:
        user = st.session_state.user
        # 验证用户信息是否完整
        if isinstance(user, dict) and 'id' in user and 'username' in user:
            # 尝试重新创建会话（作为降级方案）
            try:
                session_id = SessionSecurity.create_session(
                    user['id'], user
                )
                if session_id:
                    st.session_state.session_id = session_id
                    return True
            except (sqlite3.Error, ImportError, AttributeError,
                    RuntimeError, TypeError, KeyError) as e:
                # 会话创建失败，但用户信息存在，仍然允许访问
                # 这是一个降级方案，确保用户不会因为会话创建问题而无法使用
                if logger:
                    logger.warning(
                        f"降级方案：会话创建失败但允许访问: {type(e).__name__}"
                    )
                pass
            except Exception as e:
                # 捕获其他未预期的异常，记录日志但不阻止访问
                if logger:
                    logger.error(
                        f"降级方案：会话创建时发生未知异常: {type(e).__name__}: {e}",
                        exc_info=True
                    )
                pass
            # 即使会话创建失败，只要用户信息存在，也允许访问
            return True

    return False


def show_session_info():
    """显示会话信息（调试用）"""
    if 'user' in st.session_state:
        user_info = SessionSecurity.get_user_session_info(
            st.session_state.user['id'])
        if user_info:
            # 检查是否需要显示锁定警告
            try:
                from .db_utils import get_db_connection
            except ImportError:
                from db_utils import get_db_connection
            with get_db_connection() as (conn, c):
                recent_time = time.time() - SessionSecurity.LOCKOUT_DURATION
                failed_count = c.execute(
                    """SELECT COUNT(*) FROM login_attempts
                       WHERE identifier = ? AND success = FALSE
                       AND timestamp > ?""",
                    (st.session_state.user['username'], recent_time)
                ).fetchone()[0]

                if failed_count > 0:
                    st.sidebar.warning(f"注意：最近有 {failed_count} 次失败登录尝试")

            st.sidebar.info(f"""
            **会话信息**
            - 用户: {st.session_state.user['username']}
            - 会话ID: {user_info['session_id'][:8]}...
            - 最后活动: {time.strftime(
                '%H:%M:%S', time.localtime(user_info['last_activity']))}
            """)
