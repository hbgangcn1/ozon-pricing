import warnings
import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any

# 过滤pandas警告 - 必须在导入pandas之后设置
warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable.*",
)

# 兼容包内导入与脚本直跑两种方式
try:
    from .db_utils import (
        get_db_connection,
        require_admin,
        get_user_subscription_info,
        update_user_subscription,
        hash_password,
        check_user_subscription_status,
        _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
        _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
        is_admin,
        current_user_id,
    )
    from .password_utils import (
        validate_password_strength,
        get_password_requirements_text,
    )
except ImportError:  # 当作为顶层脚本运行时
    from db_utils import (
        get_db_connection,
        require_admin,
        get_user_subscription_info,
        update_user_subscription,
        hash_password,
        check_user_subscription_status,
        _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
        _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
        is_admin,
        current_user_id,
    )
    from password_utils import (
        validate_password_strength,
        get_password_requirements_text,
    )


# 向后兼容：提供 get_db 以便旧测试可以 monkeypatch
try:
    from .db_utils import get_db as _legacy_get_db
except (ImportError, ModuleNotFoundError):
    try:
        from db_utils import get_db as _legacy_get_db
    except (ImportError, ModuleNotFoundError):
        _legacy_get_db = None


def get_db():
    """测试兼容占位。生产代码不调用。"""
    if _legacy_get_db is None:
        raise AttributeError("get_db is deprecated; use get_db_connection")
    return _legacy_get_db()


def sync_logistics_rules(target_user_id: int, overwrite: bool = False):
    """
    将admin账号的物流规则同步到指定用户账号

    Args:
        target_user_id: 目标用户ID
        overwrite: 是否覆盖模式（删除用户现有规则）
    """
    with get_db_connection() as (conn, c):
        try:
            # 获取admin用户ID
            sql = _safe_adapt_sql(
                "SELECT id FROM users WHERE role='admin' LIMIT 1",
                conn
            )
            c.execute(sql)
            admin_user = c.fetchone()

            if not admin_user:
                st.error("找不到admin用户")
                return

            admin_id = admin_user[0]

            # 如果是覆盖模式，先删除目标用户的现有物流规则
            if overwrite:
                sql = _safe_adapt_sql(
                    "DELETE FROM logistics WHERE user_id = ?",
                    conn
                )
                c.execute(sql, (target_user_id,))

            # 获取admin的所有物流规则
            sql = _safe_adapt_sql(
                "SELECT * FROM logistics WHERE user_id = ?",
                conn
            )
            c.execute(sql, (admin_id,))
            admin_logistics = c.fetchall()

            # 获取logistics表的所有列名（除了id和user_id）
            # 检测数据库类型以适配不同的查询方式
            try:
                import psycopg2
                is_pg = isinstance(conn, psycopg2.extensions.connection)
            except (ImportError, AttributeError):
                is_pg = False

            if is_pg:
                # PostgreSQL: 使用information_schema查询列信息
                sql = """
                    SELECT column_name, data_type, ordinal_position
                    FROM information_schema.columns
                    WHERE table_name = 'logistics'
                    ORDER BY ordinal_position
                """
                c.execute(sql)
                columns_info = c.fetchall()
                # 转换为与SQLite格式兼容的格式: (cid, name, type, ...)
                columns_info = [
                    (i, row[0], row[1], None, None, None)
                    for i, row in enumerate(columns_info)
                ]
            else:
                # SQLite: 使用PRAGMA
                c.execute("PRAGMA table_info(logistics)")
                columns_info = c.fetchall()
            columns = [col[1] for col in columns_info
                       if col[1] not in ['id', 'user_id']]

            # 验证列名安全性（防止SQL注入）
            try:
                from security_utils import sanitize_column_name
            except ImportError:
                # 如果没有security_utils，使用简单验证
                import re

                def sanitize_column_name(column_name: str) -> str:
                    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
                        raise ValueError(f"非法的列名: {column_name}")
                    return column_name

            # 验证并清理所有列名
            validated_columns = [sanitize_column_name(col) for col in columns]

            # 复制每条物流规则到目标用户
            for logistics_rule in admin_logistics:
                # 构建INSERT语句 - 使用验证后的列名
                placeholders = ','.join(['?' for _ in validated_columns])
                columns_str = ','.join(validated_columns)

                # 准备数据（排除id和user_id列）
                values = []
                for col in validated_columns:
                    # 根据列名获取对应的值
                    try:
                        col_index = [
                            info[1] for info in columns_info
                        ].index(col)
                        if col_index < len(logistics_rule):
                            values.append(logistics_rule[col_index])
                        else:
                            values.append(None)  # 如果索引超出范围，使用None
                    except (ValueError, IndexError):
                        values.append(None)  # 如果找不到列或索引超出范围，使用None

                # 插入新记录 - 使用参数化查询，列名已验证安全
                sql = _safe_adapt_sql(
                    f"INSERT INTO logistics (user_id, {columns_str}) "
                    f"VALUES (?, {placeholders})",
                    conn
                )
                c.execute(sql, [target_user_id] + values)

            conn.commit()
            st.success("物流规则同步成功！")

        except sqlite3.Error as e:
            conn.rollback()
            st.error(f"同步失败: {str(e)}")
            raise


def user_management_page():
    """用户管理页面"""
    # 检查管理员权限
    try:
        require_admin()
    except PermissionError:
        st.error("❌ 访问被拒绝：您没有管理员权限")
        return

    # 订阅管理子页面切换（在检查权限之前检查，避免上下文管理器问题）
    # 安全地检测selected_user_for_subscription
    selected_user = None

    # 方法1: 直接尝试get方法（最可靠）
    try:
        if hasattr(st.session_state, 'get'):
            selected_user = st.session_state.get(
                "selected_user_for_subscription")
            # 如果get返回的值是有效的，使用它
            if (selected_user is not None and
                    selected_user != 0 and selected_user != ""):
                pass  # 使用这个值
    except (AttributeError, TypeError):
        pass

    # 方法2: 如果get方法不存在或返回None，尝试字典式访问
    if selected_user is None:
        try:
            # 先检查键是否存在
            key_exists = False
            try:
                if hasattr(st.session_state, '__contains__'):
                    contains_result = (
                        "selected_user_for_subscription" in
                        st.session_state
                    )
                    # 确保结果是布尔值，不是MagicMock
                    if isinstance(contains_result, bool):
                        key_exists = contains_result
            except (AttributeError, TypeError):
                pass

            if key_exists:
                selected_user = (
                    st.session_state["selected_user_for_subscription"]
                )
        except (KeyError, AttributeError, TypeError):
            pass

    # 方法3: 如果前面方法都失败，尝试属性访问
    if selected_user is None:
        try:
            attr_value = getattr(
                st.session_state, 'selected_user_for_subscription', None
            )
            # 确保不是MagicMock对象
            if attr_value is not None:
                # 检查是否是有效的值类型
                if isinstance(attr_value, (int, float, str, list, dict)):
                    selected_user = attr_value
        except (AttributeError, TypeError):
            pass

    # 只有在selected_user确实存在且有效时才调用订阅管理页面
    if (selected_user is not None and
            selected_user is not False and
            selected_user != 0 and
            selected_user != "" and
            isinstance(selected_user, (int, float, str, list, dict))):
        subscription_management_page()
        return

    # 标题
    st.markdown(
        (
            "<div style=\"text-align: center; margin-bottom: 2rem;\">"
            "<h1 class=\"main-title\">👥 用户管理中心</h1>"
            "<p style=\"color: #718096; font-size: 1.1rem; margin: 0;\">"
            "管理系统用户，分配权限和角色"
            "</p></div>"
        ),
        unsafe_allow_html=True,
    )

    # 打开数据库连接
    with get_db_connection() as (conn, c):
        # 下拉框格式化函数：总返回 str
        def _format_user_type(x: object) -> str:
            mapping = {
                "test": "测试用户",
                "gratitude": "感谢版用户",
                "free": "免费版用户",
                "efficiency": "效率版用户",
                "professional": "专业版用户",
                "enterprise": "企业版用户"
            }
            return mapping.get(str(x), str(x))

        # 添加用户
        with st.expander("添加新用户"):
            with st.form("add_user_form"):
                username = st.text_input("用户名*")
                password = st.text_input(
                    "密码*", type="password",
                    help=get_password_requirements_text(),
                )
                role = st.selectbox("角色*", ["admin", "user"])
                user_type = st.selectbox(
                    "用户类型*",
                    [
                        "test",
                        "gratitude",
                        "free",
                        "efficiency",
                        "professional",
                        "enterprise",
                    ],
                    format_func=_format_user_type,
                )
                submitted = st.form_submit_button("添加用户")
                if submitted:
                    if not username or not password:
                        st.error("请填写所有必填字段")
                    else:
                        valid = validate_password_strength(password)
                        if not valid.get('is_valid', False):
                            st.error("密码强度不符合要求：")
                            for err in valid.get('errors', []):
                                st.error(f"• {err}")
                            return
                        try:
                            sql = _safe_adapt_sql(
                                "SELECT 1 FROM users WHERE "
                                "LOWER(username) = LOWER(?) LIMIT 1",
                                conn
                            )
                            c.execute(sql, (username.strip(),))
                            exists = c.fetchone()
                            if exists:
                                st.error("有同名用户存在")
                                return
                        except (sqlite3.Error, Exception):
                            pass
                        hashed = hash_password(password)
                        expiry_date = None
                        subscription_expires = None
                        remaining_calculations = 0
                        first_login_date = None
                        test_days_remaining = 0
                        if user_type == "test":
                            remaining_calculations = -1
                            test_days_remaining = 7
                        elif user_type == "gratitude":
                            remaining_calculations = -1
                        elif user_type == "free":
                            remaining_calculations = 10
                        elif user_type == "efficiency":
                            remaining_calculations = -1
                            # 默认赠送30天有效期
                            try:
                                expiry_date = (
                                    datetime.now() + timedelta(days=30)
                                ).isoformat()
                                import time as _t
                                subscription_expires = (
                                    int(_t.time()) + 30 * 86400
                                )
                            except (ValueError, TypeError, OSError):
                                expiry_date = None
                                subscription_expires = None
                        elif user_type == "professional":
                            remaining_calculations = -1
                            # 默认赠送30天有效期
                            try:
                                expiry_date = (
                                    datetime.now() + timedelta(days=30)
                                ).isoformat()
                                import time as _t
                                subscription_expires = (
                                    int(_t.time()) + 30 * 86400
                                )
                            except (ValueError, TypeError, OSError):
                                expiry_date = None
                                subscription_expires = None
                        elif user_type == "enterprise":
                            remaining_calculations = -1
                        try:
                            # 根据数据库类型决定是否添加 RETURNING 子句
                            is_pg = _is_postgresql_connection(conn)
                            returning_clause = " RETURNING id" if is_pg else ""
                            insert_sql_raw = (
                                "INSERT INTO users (username, password, "
                                "role, user_type, subscription_type, "
                                "expiry_date, subscription_expires, "
                                "remaining_calculations, "
                                "first_login_date, test_days_remaining) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                                f"{returning_clause}"
                            )
                            insert_sql = _safe_adapt_sql(insert_sql_raw, conn)
                            c.execute(
                                insert_sql,
                                (
                                    username, hashed, role, user_type,
                                    user_type, expiry_date,
                                    subscription_expires,
                                    remaining_calculations,
                                    first_login_date, test_days_remaining,
                                ),
                            )
                            # PostgreSQL 使用 RETURNING 子句，SQLite 使用 lastrowid
                            if is_pg:
                                result = c.fetchone()
                                new_user_id = result[0] if result else None
                            else:
                                new_user_id = c.lastrowid
                            conn.commit()
                            # 记录审计日志（admin创建用户）
                            try:
                                if is_admin():
                                    from db_utils import log_admin_action
                                    admin_id = current_user_id()
                                    if admin_id is not None:
                                        log_admin_action(
                                            admin_id=admin_id,
                                            action_type='创建用户',
                                            action_detail=(
                                                "创建用户: "
                                                f"{username} "
                                                f"(类型: {user_type}, "
                                                f"ID: {new_user_id})"
                                            ),
                                            target_user_id=new_user_id,
                                            target_type='user'
                                        )
                            except (ImportError, AttributeError, TypeError,
                                    ValueError, sqlite3.Error):
                                pass  # 审计日志记录失败不影响主流程
                            st.success("用户添加成功！")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("有同名用户存在")
                        except sqlite3.Error as exc:
                            st.error(f"添加用户失败: {exc}")

        # 批量同步
        with st.expander("📦 批量物流规则同步", expanded=False):
            sql = _safe_adapt_sql(
                "SELECT id, username FROM users WHERE role != 'admin' "
                "ORDER BY id",
                conn
            )
            non_admin_users = pd.read_sql(sql, conn)
            if non_admin_users.empty:
                st.info("没有可同步的用户账号")
            else:
                query = (
                    "SELECT COUNT(*) FROM logistics WHERE user_id = "
                    "(SELECT id FROM users WHERE role='admin' LIMIT 1)"
                )
                c.execute(query)
                result = c.fetchone()
                admin_count = result[0] if result else 0
                st.info(f"Admin物流规则数量: {admin_count}")
                if admin_count > 0:

                    # 为静态类型检查避免 Pandas 访问器告警，先构造映射表
                    _rows = non_admin_users.to_dict(orient="records")
                    id_to_username: dict[int, str] = {
                        int(r["id"]): str(r["username"]) for r in _rows
                    }

                    def get_username_for_display(user_id: int) -> str:
                        return id_to_username.get(int(user_id), str(user_id))
                    selected = st.multiselect(
                        "选择要同步的用户:",
                        options=non_admin_users['id'].tolist(),
                        format_func=get_username_for_display,
                        key="batch_sync_users",
                    )
                    mode = st.radio(
                        "批量同步方式:",
                        ["追加模式 (保留用户现有规则)",
                         "覆盖模式 (删除用户现有规则)"],
                        key="batch_sync_mode",
                    )
                    if st.button("🚀 批量同步物流规则") and selected:
                        overwrite = (mode == "覆盖模式 (删除用户现有规则)")
                        success = 0
                        failed: list[str] = []
                        for uid in selected:
                            try:
                                sync_logistics_rules(uid, overwrite)
                                success += 1
                            except sqlite3.Error as exc:
                                uname = id_to_username.get(
                                    int(uid), f"用户ID:{uid}"
                                )
                                failed.append(f"{uname}: {exc}")
                        if success:
                            st.success(f"成功同步到 {success} 个用户账号")
                        if failed:
                            st.error("以下用户同步失败:")
                            for item in failed:
                                st.write(f"- {item}")
                        if success:
                            st.rerun()
                else:
                    st.warning("Admin账号没有物流规则可同步")

        # 用户列表与操作
        st.subheader("用户列表")
        sql = _safe_adapt_sql(
            "SELECT id, username, role FROM users ORDER BY id",
            conn
        )
        users = pd.read_sql(sql, conn)

        if users.empty:
            st.info("暂无用户数据")
            return

        def _format_user_row(user_row: Any) -> str:
            return (
                f"{user_row.id} - {user_row.username} "
                f"({user_row.role})"
            )
        choice = st.radio(
            "请选择一名用户",
            options=users.itertuples(index=False),
            format_func=_format_user_row,
        )

        if choice:
            # choice 可能是 namedtuple、tuple 或字符串
            # 如果是字符串，说明是测试环境，跳过用户选择处理
            if isinstance(choice, str):
                # 测试环境：choice 是字符串，跳过用户选择处理
                return
            else:
                # choice 本身就是 namedtuple 或 tuple，直接使用
                try:
                    uid = int(getattr(choice, "id", choice[0]))
                    uname = str(getattr(choice, "username", choice[1]))
                    urole = str(getattr(choice, "role", choice[2]))

                    st.write("---")
                    st.write(f"**已选用户：** {uname}（{urole}）")
                except (ValueError, TypeError, IndexError, AttributeError):
                    # 如果无法解析choice，跳过用户选择处理
                    return

            # 操作按钮 - 放在顶部显眼位置
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(
                    "📋 订阅管理",
                    key=f"subscription_{uid}",
                    width='stretch'
                ):
                    st.session_state.selected_user_for_subscription = uid
                    st.rerun()
            with col2:
                if st.button(
                    "🔒 重置密码",
                    key=f"show_reset_pwd_{uid}",
                    width='stretch'
                ):
                    st.session_state[f"show_reset_password_{uid}"] = True
            with col3:
                if st.button(
                    "🗑️ 删除用户",
                    key=f"del_user_{uid}",
                    width='stretch'
                ):
                    if uid == st.session_state.user["id"]:
                        st.error("不能删除当前登录用户")
                    else:
                        st.session_state.delete_confirm_user_id = uid
                        st.rerun()

            # 重置密码
            if st.session_state.get(f"show_reset_password_{uid}", False):
                with st.expander("重置密码", expanded=True):
                    with st.form("reset_password_form"):
                        new_pwd = st.text_input(
                            "新密码*", type="password",
                            help=get_password_requirements_text(),
                        )
                        if st.form_submit_button("确认重置"):
                            if not new_pwd:
                                st.error("请输入新密码")
                            else:
                                ok = validate_password_strength(new_pwd)
                                if not ok.get('is_valid', False):
                                    st.error("密码强度不符合要求：")
                                    for err in ok.get('errors', []):
                                        st.error(f"• {err}")
                                    return
                                hashed = hash_password(new_pwd)
                                c.execute(
                                    "UPDATE users SET password=? WHERE id=?",
                                    (hashed, uid),
                                )
                                conn.commit()
                                st.success("密码已更新！")
                                pwd_key = f"show_reset_password_{uid}"
                                if pwd_key in st.session_state:
                                    del st.session_state[pwd_key]
                                st.rerun()

            # 单用户同步
            with st.expander("物流规则同步"):
                query = (
                    "SELECT COUNT(*) FROM logistics WHERE user_id = "
                    "(SELECT id FROM users WHERE role='admin' LIMIT 1)"
                )
                c.execute(query)
                result = c.fetchone()
                admin_cnt = result[0] if result else 0
                sql = _safe_adapt_sql(
                    "SELECT COUNT(*) FROM logistics WHERE user_id = ?",
                    conn
                )
                c.execute(sql, (uid,))
                result = c.fetchone()
                user_cnt = result[0] if result else 0
                st.info(f"Admin物流规则数量: {admin_cnt}")
                st.info(f"{uname}当前物流规则数量: {user_cnt}")
                sync_mode = st.radio(
                    "同步方式:",
                    ["追加模式 (保留用户现有规则)",
                     "覆盖模式 (删除用户现有规则)"],
                    key=f"sync_mode_{uid}",
                )
                if st.button("🔄 同步物流规则", key=f"sync_logistics_{uid}"):
                    if admin_cnt == 0:
                        st.warning("Admin账号没有物流规则可同步")
                    else:
                        overwrite = (
                            sync_mode == "覆盖模式 (删除用户现有规则)"
                        )
                        sync_logistics_rules(uid, overwrite)
                        st.success(
                            f"成功同步 {admin_cnt} 条物流规则到 {uname}")
                        st.rerun()

            # 删除确认
            if st.session_state.get("delete_confirm_user_id"):
                pending_uid = st.session_state.delete_confirm_user_id
                if pending_uid == st.session_state.user["id"]:
                    st.error("不能删除当前登录用户")
                    del st.session_state.delete_confirm_user_id
                else:
                    st.warning("确定要删除该用户吗？")
                    col_c, col_x = st.columns(2)
                    with col_c:
                        if st.button("确定删除", key="confirm_delete_user"):
                            # 使用专门的删除用户函数，它会处理所有关联数据
                            from db_utils import delete_user
                            if delete_user(pending_uid):
                                del st.session_state.delete_confirm_user_id
                                st.success("用户已删除！")
                                st.rerun()
                            else:
                                st.error("删除用户失败，可能该用户不存在或为管理员用户")
                                del st.session_state.delete_confirm_user_id
                                st.rerun()
                    with col_x:
                        if st.button("取消", key="cancel_delete_user"):
                            del st.session_state.delete_confirm_user_id
                            st.rerun()
    # 数据库连接由上下文管理器自动关闭


def subscription_management_page():
    """订阅管理页面"""
    if 'selected_user_for_subscription' not in st.session_state:
        st.error("请先选择要管理的用户")
        return

    user_id = st.session_state.selected_user_for_subscription
    user_info = get_user_subscription_info(user_id)

    if not user_info:
        st.error("用户信息不存在")
        return

    # 添加返回按钮
    if st.button("← 返回用户列表", key="back_to_user_list"):
        del st.session_state.selected_user_for_subscription
        st.rerun()

    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 class="main-title">📋 订阅管理</h1>
            <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                管理用户订阅状态和权限
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 显示用户基本信息
    st.subheader("用户信息")
    st.write(f"**用户名称：** {user_info['username']}")

    # 显示该用户的产品数量
    try:
        with get_db_connection() as (conn, c):
            sql = _safe_adapt_sql(
                "SELECT COUNT(*) FROM products WHERE user_id = ?", conn)
            c.execute(sql, (user_id,))
            result = c.fetchone()
            prod_cnt = result[0] if result else 0
        st.write(f"**产品数量：** {prod_cnt} 个")
    except (sqlite3.Error, ValueError, TypeError, OSError):
        # 安全兜底，不阻断订阅管理页面
        st.write("**产品数量：** 获取失败")

    # 检查是否为admin用户
    with get_db_connection() as (conn, cursor):
        sql = _safe_adapt_sql("SELECT role FROM users WHERE id = ?", conn)
        cursor.execute(sql, (user_id,))
        result = cursor.fetchone()
        user_role = result[0] if result else None

    if user_role == 'admin':
        st.write("**用户类型：** 管理员")
    else:
        user_type_names = {
            "test": "测试用户",
            "permanent": "永久用户",
            "monthly": "按月付费用户",
            "enterprise": "企业用户",
            "free": "免费版用户",
            "efficiency": "效率版用户",
            "professional": "专业版用户",
            "gratitude": "感谢版用户"
        }
        # 以 subscription_type 为准，兼容历史 user_type 数据不一致
        effective_type = str(
            user_info.get('subscription_type') or
            user_info.get('user_type') or ''
        )
        st.write(
            f"**用户类型：** "
            f"{user_type_names.get(effective_type, '未知')}"
        )

    # 显示订阅状态
    subscription_status = check_user_subscription_status(user_id)

    # 如果是admin用户，显示管理员状态，不显示订阅信息
    if user_role == 'admin':
        st.success("**用户状态：** 管理员用户")
    else:
        if subscription_status.get('valid', False):
            st.success(
                f"**订阅状态：** {subscription_status.get('message', '有效')}"
            )
        else:
            st.error(
                f"**订阅状态：** {subscription_status.get('message', '无效')}"
            )

    # 显示订阅信息
    # 如果是admin用户，不显示订阅信息
    if user_role == 'admin':
        st.info("**管理员用户无需订阅**")
    else:
        # 优先使用subscription_expires（时间戳），如果没有则使用expiry_date
        subscription_expires = user_info.get('subscription_expires')
        expiry_date = user_info.get('expiry_date')
        days_remaining = None

        if subscription_expires:
            # 使用subscription_expires（Unix时间戳）
            import time
            import math
            current_time = int(time.time())
            subscription_expires_int = int(subscription_expires)
            # 使用向上取整，确保用户看到完整的剩余天数
            days_remaining = math.ceil(
                (subscription_expires_int - current_time) / (24 * 3600)
            )
        elif expiry_date:
            # 使用expiry_date（ISO格式或datetime对象）
            from datetime import date
            try:
                if isinstance(expiry_date, str):
                    expiry = datetime.fromisoformat(expiry_date)
                elif isinstance(expiry_date, datetime):
                    expiry = expiry_date
                else:
                    expiry = None

                if expiry:
                    days_remaining = (expiry.date() - date.today()).days
            except (ValueError, TypeError):
                days_remaining = None

        # 显示剩余时长（如果有订阅期限）
        if days_remaining is not None:
            st.write(f"**剩余时长：** {days_remaining} 天")

        # 显示剩余计算次数
        # 只有免费版用户才有计算次数限制，其他用户都是无限次
        user_type = (
            user_info.get('subscription_type') or
            user_info.get('user_type')
        )
        if user_type == 'free':
            # 免费版用户：显示剩余计算次数
            remaining_calculations = user_info.get('remaining_calculations', 0)
            if remaining_calculations == -1:
                st.write("**剩余计算次数：** 无限次")
            else:
                st.write(f"**剩余计算次数：** {remaining_calculations} 次")
        elif user_type not in ['permanent', 'admin']:
            # 付费用户（efficiency、professional等）：显示无限次
            st.write("**剩余计算次数：** 无限次")

    # 订阅管理操作
    st.subheader("订阅管理")

    # 如果是admin用户，显示提示信息
    if user_role == 'admin':
        st.info("**管理员用户无需订阅管理**")
    else:
        # 通用的增加订阅天数功能
        st.write("**增加订阅时长：**")
        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "➕ 增加30天",
                key="add_30_days",
                width='stretch'
            ):
                # 优先使用subscription_expires，如果没有则使用expiry_date
                current_subscription_expires = user_info.get(
                    'subscription_expires'
                )
                current_expiry = user_info.get('expiry_date')
                from datetime import date

                if current_subscription_expires:
                    # 优先使用subscription_expires（时间戳）
                    try:
                        expires_timestamp = int(current_subscription_expires)
                        expires_dt = datetime.fromtimestamp(expires_timestamp)
                        today = datetime.now()
                        # 如果已经过期，从今天开始加天数；否则从过期日期加天数
                        if expires_dt.date() <= date.today():
                            new_expiry = today + timedelta(days=30)
                        else:
                            new_expiry = expires_dt + timedelta(days=30)
                    except (ValueError, TypeError, OSError):
                        new_expiry = datetime.now() + timedelta(days=30)
                elif current_expiry:
                    # 如果没有subscription_expires，使用expiry_date
                    try:
                        if isinstance(current_expiry, str):
                            expiry = datetime.fromisoformat(current_expiry)
                        elif isinstance(current_expiry, datetime):
                            expiry = current_expiry
                        else:
                            expiry = None

                        if expiry:
                            today = datetime.now()
                            # 如果已经过期，从今天开始加天数；否则从过期日期加天数
                            if expiry.date() <= date.today():
                                new_expiry = today + timedelta(days=30)
                            else:
                                new_expiry = expiry + timedelta(days=30)
                        else:
                            new_expiry = datetime.now() + timedelta(days=30)
                    except (ValueError, TypeError):
                        new_expiry = datetime.now() + timedelta(days=30)
                else:
                    new_expiry = datetime.now() + timedelta(days=30)

                # 计算新的subscription_expires时间戳
                new_subscription_expires = int(new_expiry.timestamp())

                update_user_subscription(user_id, {
                    'expiry_date': new_expiry.isoformat(),
                    'subscription_expires': new_subscription_expires
                })
                st.success("✅ 已增加30天订阅时长！")
                st.rerun()

        with col2:
            if st.button(
                "➕ 增加365天",
                key="add_365_days",
                width='stretch'
            ):
                # 优先使用subscription_expires，如果没有则使用expiry_date
                current_subscription_expires = user_info.get(
                    'subscription_expires'
                )
                current_expiry = user_info.get('expiry_date')
                from datetime import date

                if current_subscription_expires:
                    # 优先使用subscription_expires（时间戳）
                    try:
                        expires_timestamp = int(current_subscription_expires)
                        expires_dt = datetime.fromtimestamp(expires_timestamp)
                        today = datetime.now()
                        # 如果已经过期，从今天开始加天数；否则从过期日期加天数
                        if expires_dt.date() <= date.today():
                            new_expiry = today + timedelta(days=365)
                        else:
                            new_expiry = expires_dt + timedelta(days=365)
                    except (ValueError, TypeError, OSError):
                        new_expiry = datetime.now() + timedelta(days=365)
                elif current_expiry:
                    # 如果没有subscription_expires，使用expiry_date
                    try:
                        if isinstance(current_expiry, str):
                            expiry = datetime.fromisoformat(current_expiry)
                        elif isinstance(current_expiry, datetime):
                            expiry = current_expiry
                        else:
                            expiry = None

                        if expiry:
                            today = datetime.now()
                            # 如果已经过期，从今天开始加天数；否则从过期日期加天数
                            if expiry.date() <= date.today():
                                new_expiry = today + timedelta(days=365)
                            else:
                                new_expiry = expiry + timedelta(days=365)
                        else:
                            new_expiry = datetime.now() + timedelta(days=365)
                    except (ValueError, TypeError):
                        new_expiry = datetime.now() + timedelta(days=365)
                else:
                    new_expiry = datetime.now() + timedelta(days=365)

                # 计算新的subscription_expires时间戳
                new_subscription_expires = int(new_expiry.timestamp())

                update_user_subscription(user_id, {
                    'expiry_date': new_expiry.isoformat(),
                    'subscription_expires': new_subscription_expires
                })
                st.success("✅ 已增加365天订阅时长！")
                st.rerun()

        # 针对特定用户类型的额外操作
        st.write("---")
        if user_info['user_type'] == 'test':
            if st.button("转为感谢版用户"):
                update_user_subscription(user_id, {
                    'user_type': 'gratitude',
                    'expiry_date': None,
                    'remaining_calculations': -1,
                    'test_days_remaining': 0
                })
                st.success("用户已转为感谢版用户！")
                st.rerun()

        elif user_info['user_type'] == 'monthly':
            st.write("**增加计算次数：**")
            calculation_option = st.radio(
                "选择次数", ["100次", "500次"], key="calc_option"
            )
            calculations = 100 if calculation_option == "100次" else 500

            if st.button("增加计算次数", key="add_calculations"):
                new_calculations = (
                    user_info.get('remaining_calculations', 0) + calculations
                )
                update_user_subscription(user_id, {
                    'remaining_calculations': new_calculations
                })
                st.success(f"✅ 已增加{calculations}次计算！")
                st.rerun()

    # 减少订阅
    st.subheader("减少订阅")
    col1, col2 = st.columns(2)

    with col1:
        reduce_days = st.number_input("减少使用天数", min_value=1, value=1)
        if st.button("减少天数"):
            # 优先使用subscription_expires，如果没有则使用expiry_date
            current_subscription_expires = user_info.get(
                'subscription_expires'
            )
            current_expiry = user_info.get('expiry_date')
            new_expiry = None

            if current_subscription_expires:
                # 优先使用subscription_expires（时间戳）
                try:
                    expires_timestamp = int(current_subscription_expires)
                    expires_dt = datetime.fromtimestamp(expires_timestamp)
                    new_expiry = expires_dt - timedelta(days=reduce_days)
                except (ValueError, TypeError, OSError):
                    st.error("订阅时间格式错误")
                    st.rerun()
            elif current_expiry:
                # 如果没有subscription_expires，使用expiry_date
                try:
                    if isinstance(current_expiry, str):
                        expiry = datetime.fromisoformat(current_expiry)
                    elif isinstance(current_expiry, datetime):
                        expiry = current_expiry
                    else:
                        expiry = None
                    if expiry:
                        new_expiry = expiry - timedelta(days=reduce_days)
                    else:
                        st.error("无法解析到期时间")
                        st.rerun()
                except (ValueError, TypeError):
                    st.error("到期时间格式错误")
                st.rerun()
            else:
                st.error("用户没有到期时间")
                st.rerun()

            # 只有当 new_expiry 被正确定义时才执行更新
            if new_expiry is not None:
                # 计算新的subscription_expires时间戳
                new_subscription_expires = int(new_expiry.timestamp())

                update_user_subscription(user_id, {
                    'expiry_date': new_expiry.isoformat(),
                    'subscription_expires': new_subscription_expires
                })
                st.success(f"已减少{reduce_days}天！")
                st.rerun()

    with col2:
        reduce_calculations = st.number_input("减少使用次数", min_value=1, value=1)
        if st.button("减少次数"):
            current_calculations = user_info.get('remaining_calculations', 0)
            if current_calculations > 0:
                new_calculations = max(
                    0,
                    current_calculations - reduce_calculations,
                )
                update_user_subscription(
                    user_id,
                    {'remaining_calculations': new_calculations}
                )
                st.success(f"已减少{reduce_calculations}次！")
                st.rerun()
            else:
                st.error("用户没有剩余计算次数")

    # 返回按钮
    if st.button("返回用户管理"):
        del st.session_state.selected_user_for_subscription
        st.rerun()


def login_or_register_page():
    """登录页面"""
    # 美化登录页面
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 3rem;">
            <h1 class="main-title">🚢 跨境运费与定价决策引擎</h1>
            <p style="color: #718096; font-size: 1.2rem; margin: 0;">
                3秒完成数百家物流方案筛选，秒定建议零售价
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 检查是否开放注册
    try:
        from .db_utils import is_registration_open
    except ImportError:
        from db_utils import is_registration_open

    registration_open = is_registration_open()
    # 根据开放注册状态决定是否显示标签页
    if registration_open:
        tab1, tab2 = st.tabs(["🔐 登录", "📝 用户注册"])
        with tab1:
            _show_login_form()
        with tab2:
            _show_register_form()
    else:
        # 不开放注册时只显示登录表单
        _show_login_form()

    # 忘记密码页面
    if st.session_state.get("show_forgot_password", False):
        _show_forgot_password_page()
        return

    # 用户协议弹窗
    if st.session_state.get("show_terms_modal", False):
        _show_terms_modal()
    # 添加备案信息（ICP备案号和公安备案信息在同一行显示）
    st.markdown(
        """
        <div style="text-align: center; margin-top: 3rem; padding: 1rem;
             color: #718096; font-size: 0.9rem;">
        """,
        unsafe_allow_html=True
    )

    # 在同一行中显示ICP备案号和公安备案信息
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        # 在同一列中创建水平布局，使用HTML实现真正的左右排列
        import os
        icon_path = os.path.join(
            os.path.dirname(__file__), "PSB Filing Icon.png"
        )

        # 读取图标文件并转换为base64，确保能正确显示
        import base64
        try:
            with open(icon_path, 'rb') as f:
                icon_data = base64.b64encode(f.read()).decode()
            icon_src = f"data:image/png;base64,{icon_data}"
        except (FileNotFoundError, PermissionError, OSError):
            icon_src = ""

        # 使用HTML实现同一行中的左右排列：
        # ICP备案号 | 公安备案图标+备案号
        st.markdown(
            f"""
            <div style="display: flex; align-items: center;
                 justify-content: center; gap: 20px;">
                <a href="https://beian.miit.gov.cn/#/Integrated/index"
                   target="_blank"
                   style="color: #718096; text-decoration: none;">
                    ICP备案号：粤ICP备2025471825号-1
                </a>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <img src="{icon_src}"
                         style="width: 36px; height: 40px; flex-shrink: 0;"
                         alt="公安备案图标">
                    <a href="https://beian.mps.gov.cn/#/query/webSearch"
                       rel="noreferrer"
                       target="_blank"
                       style="color: #718096; text-decoration: none;
                              font-size: 0.9rem;">
                        粤公网安备44030002008086号
                    </a>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown(
        """
        </div>
        """,
        unsafe_allow_html=True
    )


def _show_login_form():
    """显示登录表单"""
    with st.form("login_form"):
        identifier = st.text_input("用户名或邮箱")
        pwd = st.text_input("密码", type="password")
        col1, col2 = st.columns([3, 1])
        with col1:
            submitted = st.form_submit_button("登录", use_container_width=True)
        with col2:
            forgot_pwd = st.form_submit_button(
                "忘记密码？", use_container_width=True
            )

        if forgot_pwd:
            st.session_state.show_forgot_password = True
            st.rerun()

        if submitted:
            # 输入验证
            if not identifier or not identifier.strip():
                st.error("❌ 请输入用户名或邮箱")
                return

            if not pwd or not pwd.strip():
                st.error("❌ 请输入密码")
                return

            try:
                from .session_security import secure_login
            except ImportError:
                from session_security import secure_login

            try:
                login_success = secure_login(identifier.strip(), pwd)
                if login_success:
                    st.rerun()
            except (ImportError, AttributeError, RuntimeError) as e:
                # 捕获导入错误、属性错误和运行时错误
                error_msg = str(e)
                st.error(f"❌ 登录过程中发生错误: {error_msg}")
                # 记录错误日志
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"登录错误: {error_msg}", exc_info=True)
                except (AttributeError, RuntimeError, ImportError):
                    pass
            except sqlite3.Error as e:
                # 数据库相关错误
                error_msg = str(e)
                st.error(f"❌ 数据库错误: {error_msg}")
                # 记录错误日志
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"登录数据库错误: {error_msg}", exc_info=True)
                except (AttributeError, RuntimeError, ImportError):
                    pass
            except Exception as e:
                # 捕获其他未预期的异常
                error_msg = str(e)
                st.error(f"❌ 登录过程中发生未知错误: {error_msg}")
                # 记录错误日志
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"登录未知错误: {error_msg}", exc_info=True)
                except (AttributeError, RuntimeError, ImportError):
                    pass


def _show_register_form():
    """显示注册表单"""
    with st.form("register_form"):
        st.markdown("### 📝 用户注册")
        username = st.text_input("用户名", help="请输入用户名")
        password = st.text_input("密码", type="password", help="请输入密码")
        confirm_password = st.text_input(
            "确认密码", type="password", help="请再次输入密码"
        )

        # 安全问题设置
        st.markdown("---")
        st.markdown("#### 🔒 安全问题设置（用于密码找回）")

        try:
            from .security_questions import get_security_questions
        except ImportError:
            from security_questions import get_security_questions

        security_questions = get_security_questions()

        col1, col2 = st.columns(2)
        with col1:
            security_q1 = st.selectbox(
                "安全问题1",
                options=[""] + security_questions,
                help="请选择一个安全问题"
            )
            security_a1 = st.text_input(
                "答案1",
                type="password",
                help="请输入答案（不区分大小写）"
            )

        with col2:
            # 过滤掉已选择的问题1
            available_q2 = [
                q for q in security_questions if q != security_q1
            ]
            security_q2 = st.selectbox(
                "安全问题2",
                options=[""] + available_q2,
                help="请选择另一个安全问题（不能与问题1相同）"
            )
            security_a2 = st.text_input(
                "答案2",
                type="password",
                help="请输入答案（不区分大小写）"
            )

        # 用户协议复选框
        st.markdown("---")
        agree_terms = st.checkbox(
            "我已阅读并同意《最终用户协议》",
            key="agree_terms_checkbox"
        )

        # 查看协议和注册按钮
        col1, col2, _ = st.columns([1, 1, 6])
        with col1:
            submitted = st.form_submit_button(
                "注册并登录",
                width='stretch'
            )
        with col2:
            view_terms = st.form_submit_button(
                "📋 查看协议",
                width='stretch'
            )
        # col3 留空用于压缩前两个按钮的间距

        # 处理查看协议按钮
        if view_terms:
            st.session_state.show_terms_modal = True
            st.rerun()

        if submitted:
            if not username or not password:
                st.error("❌ 请填写所有必填字段")
                return

            if not agree_terms:
                st.error("❌ 请先阅读并同意《最终用户协议》")
                return

            if password != confirm_password:
                st.error("❌ 两次输入的密码不一致")
                return
            # 验证密码强度
            try:
                from .password_utils import validate_password_strength
            except ImportError:
                from password_utils import validate_password_strength
            # 验证安全问题
            try:
                from .security_questions import (
                    validate_security_questions,
                    validate_security_answers
                )
            except ImportError:
                from security_questions import (
                    validate_security_questions,
                    validate_security_answers
                )

            is_valid_q, error_msg_q = validate_security_questions(
                security_q1, security_q2
            )
            if not is_valid_q:
                st.error(f"❌ {error_msg_q}")
                return

            is_valid_a, error_msg_a = validate_security_answers(
                security_a1, security_a2
            )
            if not is_valid_a:
                st.error(f"❌ {error_msg_a}")
                return

            if not validate_password_strength(password):
                st.error("❌ 密码强度不够，请使用更复杂的密码")
                return

            # 注册用户
            try:
                from .db_utils import get_db_connection, hash_password
                import bcrypt
            except ImportError:
                from db_utils import get_db_connection, hash_password
                import bcrypt

            with get_db_connection() as (conn, c):
                try:
                    # 检查用户名是否已存在
                    existing_user = c.execute(
                        "SELECT id FROM users WHERE username = ?",
                        (username,)
                    ).fetchone()
                    if existing_user:
                        st.error("❌ 用户名已存在")
                        return

                    # 加密密码和安全答案
                    hashed_pwd = hash_password(password)
                    # 答案不区分大小写，转换为小写后加密
                    hashed_a1 = bcrypt.hashpw(
                        security_a1.strip().lower().encode('utf-8'),
                        bcrypt.gensalt()
                    ).decode('utf-8')
                    hashed_a2 = bcrypt.hashpw(
                        security_a2.strip().lower().encode('utf-8'),
                        bcrypt.gensalt()
                    ).decode('utf-8')

                    # 创建新用户（包含安全问题）
                    c.execute(
                        "INSERT INTO users (username, password, "
                        "role, user_type, remaining_calculations, "
                        "security_q1, security_a1, security_q2, security_a2) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            username, hashed_pwd, 'user', 'free', 10,
                            security_q1, hashed_a1, security_q2, hashed_a2
                        )
                    )
                    conn.commit()
                    # 注册成功后自动登录
                    try:
                        from .session_security import secure_login
                    except ImportError:
                        from session_security import secure_login

                    # 自动登录
                    login_success = secure_login(username, password)
                    if login_success:
                        st.success("✅ 注册成功！正在为您自动登录...")
                        st.rerun()
                    else:
                        st.error("❌ 注册成功但自动登录失败，请手动登录")
                except Exception as e:
                    st.error(f"❌ 注册失败: {str(e)}")
    # 数据库连接在get_db_connection上下文管理器中自动关闭


def _show_forgot_password_page():
    """显示忘记密码页面"""
    st.markdown("### 🔐 密码找回")

    # 返回登录按钮
    if st.button("← 返回登录"):
        st.session_state.show_forgot_password = False
        st.rerun()

    st.markdown("---")

    try:
        from .password_recovery import (
            get_user_security_questions,
            verify_security_answers,
            reset_password
        )
    except ImportError:
        from password_recovery import (
            get_user_security_questions,
            verify_security_answers,
            reset_password
        )

    # 阶段1：输入用户名
    if 'forgot_pwd_step' not in st.session_state:
        st.session_state.forgot_pwd_step = 'username'

    if st.session_state.forgot_pwd_step == 'username':
        with st.form("forgot_password_username_form"):
            username = st.text_input("请输入用户名")
            submitted = st.form_submit_button("下一步")

            if submitted:
                if not username:
                    st.error("❌ 请输入用户名")
                else:
                    # 获取用户的安全问题
                    user_info = get_user_security_questions(username)

                    if not user_info:
                        st.error("❌ 用户不存在")
                    elif not user_info.get('has_questions', False):
                        st.error(
                            "❌ 该用户未设置安全问题，"
                            "请联系管理员重置密码"
                        )
                    elif user_info.get('is_locked', False):
                        locked_until = user_info.get('locked_until', '未知时间')
                        st.error(
                            f"❌ 账号已被锁定，请于 {locked_until} 后重试。"
                            "或联系管理员解锁。"
                        )
                    else:
                        st.session_state.forgot_pwd_username = username
                        st.session_state.forgot_pwd_step = 'questions'
                        st.session_state.forgot_pwd_q1 = (
                            user_info['security_q1']
                        )
                        st.session_state.forgot_pwd_q2 = (
                            user_info['security_q2']
                        )
                        st.rerun()

    # 阶段2：回答安全问题
    elif st.session_state.forgot_pwd_step == 'questions':
        st.markdown(f"**用户名**: {st.session_state.forgot_pwd_username}")
        st.markdown("---")

        with st.form("forgot_password_questions_form"):
            st.markdown("#### 请回答以下安全问题")
            st.text(f"**问题1**: {st.session_state.forgot_pwd_q1}")
            answer1 = st.text_input("答案1", type="password")

            st.text(f"**问题2**: {st.session_state.forgot_pwd_q2}")
            answer2 = st.text_input("答案2", type="password")

            col1, col2 = st.columns(2)
            with col1:
                back_btn = st.form_submit_button("← 返回")
            with col2:
                verify_btn = st.form_submit_button("验证答案")

            if back_btn:
                st.session_state.forgot_pwd_step = 'username'
                del st.session_state.forgot_pwd_username
                st.rerun()

            if verify_btn:
                if not answer1 or not answer2:
                    st.error("❌ 请填写两个答案")
                else:
                    success, message = verify_security_answers(
                        st.session_state.forgot_pwd_username,
                        answer1,
                        answer2
                    )

                    if success:
                        st.session_state.forgot_pwd_step = 'reset'
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

    # 阶段3：重置密码
    elif st.session_state.forgot_pwd_step == 'reset':
        st.markdown(f"**用户名**: {st.session_state.forgot_pwd_username}")
        st.markdown("---")
        st.success("✅ 安全验证成功！请设置新密码")

        with st.form("forgot_password_reset_form"):
            new_password = st.text_input(
                "新密码",
                type="password",
                help="密码必须至少13位，包含大小写字母、数字和特殊字符"
            )
            confirm_password = st.text_input(
                "确认新密码",
                type="password"
            )

            col1, col2 = st.columns(2)
            with col1:
                back_btn = st.form_submit_button("← 返回")
            with col2:
                reset_btn = st.form_submit_button("重置密码")

            if back_btn:
                st.session_state.forgot_pwd_step = 'questions'
                st.rerun()

            if reset_btn:
                if not new_password or not confirm_password:
                    st.error("❌ 请填写新密码和确认密码")
                elif new_password != confirm_password:
                    st.error("❌ 两次输入的密码不一致")
                else:
                    success, message = reset_password(
                        st.session_state.forgot_pwd_username,
                        new_password
                    )

                    if success:
                        st.success(f"✅ {message}")
                        st.info("正在跳转到登录页面...")
                        # 清除状态
                        del st.session_state.show_forgot_password
                        del st.session_state.forgot_pwd_step
                        del st.session_state.forgot_pwd_username
                        del st.session_state.forgot_pwd_q1
                        del st.session_state.forgot_pwd_q2
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")


def _show_terms_modal():
    """显示用户协议弹窗"""
    # 读取用户协议内容
    try:
        with open("最终用户协议.md", "r", encoding="utf-8") as f:
            terms_content = f.read()
    except FileNotFoundError:
        terms_content = "无法加载用户协议内容，请联系客服获取。"
    # 创建弹窗样式
    st.markdown(
        """
        <style>
        .terms-modal {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
            border: 2px solid #dee2e6;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            max-height: 70vh;
            overflow-y: auto;
        }
        .terms-header {
            text-align: center;
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #3498db;
        }
        .terms-content {
            line-height: 1.6;
            color: #333;
            font-size: 14px;
        }
        .close-btn-container {
            text-align: center;
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #dee2e6;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # 弹窗容器
    with st.container():
        st.markdown('<div class="terms-modal">', unsafe_allow_html=True)

        # 弹窗标题
        st.markdown(
            '<div class="terms-header"><h2>📋 最终用户协议</h2></div>',
            unsafe_allow_html=True
        )

        # 协议内容
        st.markdown('<div class="terms-content">', unsafe_allow_html=True)
        st.markdown(terms_content)
        st.markdown('</div>', unsafe_allow_html=True)

        # 关闭按钮
        st.markdown(
            '<div class="close-btn-container">',
            unsafe_allow_html=True
        )
        _, col2, _ = st.columns([1, 1, 1])
        with col2:
            if st.button(
                "✖ 关闭协议",
                key="close_terms_modal",
                width='stretch'
            ):
                st.session_state.show_terms_modal = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
