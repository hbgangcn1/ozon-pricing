import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# 兼容包内导入与脚本直跑两种方式
try:
    from .db_utils import (
        get_db_connection,
        require_admin,
        get_user_subscription_info,
        update_user_subscription,
        hash_password,
        check_user_subscription_status,
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
    )
    from password_utils import (
        validate_password_strength,
        get_password_requirements_text,
    )
from typing import Any


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
            admin_user = c.execute(
                "SELECT id FROM users WHERE role='admin' LIMIT 1"
            ).fetchone()

            if not admin_user:
                st.error("找不到admin用户")
                return

            admin_id = admin_user[0]

            # 如果是覆盖模式，先删除目标用户的现有物流规则
            if overwrite:
                c.execute(
                    "DELETE FROM logistics WHERE user_id = ?",
                    (target_user_id,)
                )

            # 获取admin的所有物流规则
            admin_logistics = c.execute(
                "SELECT * FROM logistics WHERE user_id = ?", (admin_id,)
            ).fetchall()

            # 获取logistics表的所有列名（除了id和user_id）
            columns_info = c.execute("PRAGMA table_info(logistics)").fetchall()
            columns = [col[1] for col in columns_info
                       if col[1] not in ['id', 'user_id']]

            # 复制每条物流规则到目标用户
            for logistics_rule in admin_logistics:
                # 构建INSERT语句
                placeholders = ','.join(['?' for _ in columns])
                columns_str = ','.join(columns)

                # 准备数据（排除id和user_id列）
                values = []
                for col in columns:
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

                # 插入新记录
                c.execute(
                    f"INSERT INTO logistics (user_id, {columns_str}) "
                    f"VALUES (?, {placeholders})",
                    [target_user_id] + values
                )

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

    # 订阅管理子页面切换
    if 'selected_user_for_subscription' in st.session_state:
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
                "permanent": "永久用户",
                "test": "测试用户",
                "monthly": "按月付费用户",
                "enterprise": "企业用户",
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
                    ["permanent", "test", "monthly", "enterprise"],
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
                            exists = c.execute(
                                (
                                    "SELECT 1 FROM users WHERE "
                                    "LOWER(username) = LOWER(?) LIMIT 1"
                                ),
                                (username.strip(),),
                            ).fetchone()
                            if exists:
                                st.error("有同名用户存在")
                                return
                        except sqlite3.Error:
                            pass
                        hashed = hash_password(password)
                        expiry_date = None
                        remaining_calculations = 0
                        first_login_date = None
                        test_days_remaining = 0
                        if user_type == "test":
                            remaining_calculations = -1
                            test_days_remaining = 7
                        elif user_type == "permanent":
                            remaining_calculations = -1
                        elif user_type == "monthly":
                            remaining_calculations = 100
                        elif user_type == "enterprise":
                            remaining_calculations = -1
                        try:
                            c.execute(
                                (
                                    "INSERT INTO users (username, password, "
                                    "role, user_type, expiry_date, "
                                    "remaining_calculations, "
                                    "first_login_date, "
                                    "test_days_remaining) VALUES ("
                                    "?, ?, ?, ?, ?, ?, ?, ?)"
                                ),
                                (
                                    username, hashed, role, user_type,
                                    expiry_date, remaining_calculations,
                                    first_login_date, test_days_remaining,
                                ),
                            )
                            conn.commit()
                            st.success("用户添加成功！")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("有同名用户存在")
                        except sqlite3.Error as exc:
                            st.error(f"添加用户失败: {exc}")

        # 批量同步
        with st.expander("📦 批量物流规则同步", expanded=False):
            non_admin_users = pd.read_sql(
                "SELECT id, username FROM users WHERE role != 'admin'",
                conn,
            )
            if non_admin_users.empty:
                st.info("没有可同步的用户账号")
            else:
                query = (
                    "SELECT COUNT(*) FROM logistics WHERE user_id = "
                    "(SELECT id FROM users WHERE role='admin' LIMIT 1)"
                )
                admin_count = c.execute(query).fetchone()[0]
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
        users = pd.read_sql(
            "SELECT id, username, role FROM users", conn
        )
        if users.empty:
            st.info("暂无用户数据")
            return

        def _format_user_row(row: Any) -> str:
            return (
                f"{row.id} - {row.username} "
                f"({row.role})"
            )
        choice = st.radio(
            "请选择一名用户",
            options=users.itertuples(index=False),
            format_func=_format_user_row,
        )
        if choice:
            # itertuples 默认 namedtuple，但静态检查可能视为 tuple
            uid = int(getattr(choice, "id", choice[0]))
            uname = str(getattr(choice, "username", choice[1]))
            urole = str(getattr(choice, "role", choice[2]))
            st.write("---")
            st.write(f"**已选用户：** {uname}（{urole}）")

            # 重置密码
            with st.expander("重置密码"):
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
                            st.rerun()
            # 单用户同步
            with st.expander("物流规则同步"):
                query = (
                    "SELECT COUNT(*) FROM logistics WHERE user_id = "
                    "(SELECT id FROM users WHERE role='admin' LIMIT 1)"
                )
                admin_cnt = c.execute(query).fetchone()[0]
                user_cnt = c.execute(
                    "SELECT COUNT(*) FROM logistics WHERE user_id = ?",
                    (uid,),
                ).fetchone()[0]
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

            # 顶部操作
            col1, col2 = st.columns(2)
            with col1:
                if st.button("订阅管理", key=f"subscription_{uid}"):
                    st.session_state.selected_user_for_subscription = uid
                    st.rerun()
            with col2:
                if st.button("删除用户", key=f"del_user_{uid}"):
                    if uid == st.session_state.user["id"]:
                        st.error("不能删除当前登录用户")
                    else:
                        st.session_state.delete_confirm_user_id = uid
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
                            c.execute(
                                "DELETE FROM users WHERE id = ?",
                                (pending_uid,),
                            )
                            conn.commit()
                            del st.session_state.delete_confirm_user_id
                            st.success("用户已删除！")
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

    user_type_names = {
        "test": "测试用户",
        "permanent": "永久用户",
        "monthly": "按月付费用户",
        "enterprise": "企业用户"
    }
    st.write(f"**用户类型：** {user_type_names.get(user_info['user_type'], '未知')}")

    # 显示订阅状态
    subscription_status = check_user_subscription_status(user_id)
    if subscription_status.get('valid', False):
        st.success(f"**订阅状态：** {subscription_status.get('message', '有效')}")
    else:
        st.error(f"**订阅状态：** {subscription_status.get('message', '无效')}")

    # 显示订阅信息
    if user_info['user_type'] == 'monthly':
        if user_info['expiry_date']:
            expiry = datetime.fromisoformat(user_info['expiry_date'])
            from datetime import date
            days_remaining = (expiry.date() - date.today()).days
            st.write(f"**剩余时长：** {days_remaining} 天")
        st.write(f"**剩余计算次数：** {user_info['remaining_calculations']} 次")

    elif user_info['user_type'] == 'enterprise':
        if user_info['expiry_date']:
            expiry = datetime.fromisoformat(user_info['expiry_date'])
            from datetime import date
            days_remaining = (expiry.date() - date.today()).days
            st.write(f"**剩余时长：** {days_remaining} 天")

    # 订阅管理操作
    st.subheader("订阅管理")

    if user_info['user_type'] == 'test':
        if st.button("转为永久用户"):
            update_user_subscription(user_id, {
                'user_type': 'permanent',
                'expiry_date': None,
                'remaining_calculations': -1,
                'test_days_remaining': 0
            })
            st.success("用户已转为永久用户！")
            st.rerun()

    elif user_info['user_type'] == 'monthly':
        st.write("**增加订阅：**")
        calculation_option = st.radio("选择次数", ["100次", "500次"])
        calculations = 100 if calculation_option == "100次" else 500

        if st.button("增加30天"):
            current_expiry = user_info.get('expiry_date')
            if current_expiry:
                new_expiry = (
                    datetime.fromisoformat(current_expiry) +
                    timedelta(days=30)
                )
            else:
                new_expiry = datetime.now() + timedelta(days=30)

            new_calculations = (
                user_info.get(
                    'remaining_calculations',
                    0,
                ) + calculations
            )

            update_user_subscription(user_id, {
                'expiry_date': new_expiry.isoformat(),
                'remaining_calculations': new_calculations
            })
            st.success(f"已增加30天时长和{calculations}次计算！")
            st.rerun()

    elif user_info['user_type'] == 'enterprise':
        if st.button("增加30天"):
            current_expiry = user_info.get('expiry_date')
            if current_expiry:
                new_expiry = (
                    datetime.fromisoformat(current_expiry) +
                    timedelta(days=30)
                )
            else:
                new_expiry = datetime.now() + timedelta(days=30)

            update_user_subscription(user_id, {
                'expiry_date': new_expiry.isoformat()
            })
            st.success("已增加30天时长！")
            st.rerun()

    # 减少订阅
    st.subheader("减少订阅")
    col1, col2 = st.columns(2)

    with col1:
        reduce_days = st.number_input("减少使用天数", min_value=1, value=1)
        if st.button("减少天数"):
            current_expiry = user_info.get('expiry_date')
            if current_expiry:
                new_expiry = (
                    datetime.fromisoformat(current_expiry) -
                    timedelta(days=reduce_days)
                )
                update_user_subscription(
                    user_id,
                    {'expiry_date': new_expiry.isoformat()}
                )
                st.success(f"已减少{reduce_days}天！")
                st.rerun()
            else:
                st.error("用户没有到期时间")

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
    with st.form("login_form"):
        identifier = st.text_input("用户名或邮箱")
        pwd = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
        if submitted:
            try:
                from .session_security import secure_login
            except ImportError:
                from session_security import secure_login
            login_success = secure_login(identifier, pwd)
            if login_success:
                st.rerun()
            # secure_login函数内部已经处理了错误信息显示

    # 数据库连接在get_db_connection上下文管理器中自动关闭
