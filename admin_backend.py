import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 导入数据库函数
try:
    from db_utils import (
        authenticate_admin,
        get_all_users,
        get_user_detail,
        update_user_subscription_admin,
        freeze_user,
        unfreeze_user,
        delete_user_admin,
        get_audit_logs,
        reset_user_password,
    )
except ImportError:
    from .db_utils import (
        authenticate_admin,
        get_all_users,
        get_user_detail,
        update_user_subscription_admin,
        freeze_user,
        unfreeze_user,
        delete_user_admin,
        get_audit_logs,
        reset_user_password,
    )

# 页面配置
st.set_page_config(
    page_title="管理员后台",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .user-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
    }
    .status-active { color: #28a745; }
    .status-expired { color: #dc3545; }
    .status-frozen { color: #6c757d; }
    .admin-sidebar {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """初始化会话状态"""
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False
    if 'admin_user' not in st.session_state:
        st.session_state.admin_user = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = '用户管理'
    if 'selected_user_id' not in st.session_state:
        st.session_state.selected_user_id = None


def admin_login():
    """管理员登录页面"""
    st.markdown("""
    <div class="main-header">
        <h1>🔧 管理员后台系统</h1>
        <p>用户管理与订阅控制中心</p>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 管理员登录")

            with st.form("admin_login_form"):
                username = st.text_input("用户名", key="admin_username")
                password = st.text_input(
                    "密码",
                    type="password",
                    key="admin_password",
                )
                submit = st.form_submit_button("登录")

                if submit:
                    if username and password:
                        admin_user = authenticate_admin(username, password)
                        if admin_user:
                            st.session_state.admin_logged_in = True
                            st.session_state.admin_user = admin_user
                            st.success("登录成功！")
                            st.rerun()
                        else:
                            st.error("用户名或密码错误")
                    else:
                        st.error("请输入用户名和密码")


def admin_sidebar():
    """管理员侧边栏"""
    with st.sidebar:
        st.markdown("""
        <div class="admin-sidebar">
            <h3>🔧 管理员后台</h3>
        </div>
        """, unsafe_allow_html=True)

        st.write(f"**管理员:** {st.session_state.admin_user['username']}")
        st.write(f"**角色:** {st.session_state.admin_user['role']}")

        st.divider()

        # 导航菜单
        page = st.selectbox(
            "选择功能",
            ["用户管理", "订阅管理", "操作日志"],
            index=["用户管理", "订阅管理", "操作日志"].index(st.session_state.current_page)
        )

        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.session_state.selected_user_id = None
            st.rerun()

        st.divider()

        if st.button("退出登录"):
            st.session_state.admin_logged_in = False
            st.session_state.admin_user = None
            st.rerun()


def user_management_page():
    """用户管理页面"""
    st.markdown("""
    <div class="main-header">
        <h1>👥 用户管理</h1>
        <p>浏览、搜索和管理所有用户</p>
    </div>
    """, unsafe_allow_html=True)

    # 搜索和筛选
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        search = st.text_input("搜索用户名/邮箱", key="user_search")

    with col2:
        user_type_filter = st.selectbox(
            "用户类型",
            [
                "all",
                "free",
                "efficiency",
                "professional",
                "enterprise",
                "gratitude",
            ],
            format_func=lambda x: {
                "all": "全部",
                "free": "免费版",
                "efficiency": "效率版",
                "professional": "专业版",
                "enterprise": "企业版",
                "gratitude": "感谢版"
            }.get(str(x), str(x)) or str(x),
            key="user_type_filter"
        )

    with col3:
        status_filter = st.selectbox(
            "订阅状态",
            ["all", "active", "expired", "expiring_soon"],
            format_func=lambda x: {
                "all": "全部",
                "active": "有效",
                "expired": "已过期",
                "expiring_soon": "即将到期"
            }.get(str(x), str(x)) or str(x),
            key="status_filter"
        )

    with col4:
        per_page = st.selectbox("每页显示", [10, 20, 50, 100], key="per_page")

    # 获取用户数据
    page = st.session_state.get('user_page', 1)
    users_data = get_all_users(
        page=page,
        per_page=per_page,
        search=search if search else None,
        user_type_filter=(
            user_type_filter if user_type_filter != 'all' else None
        ),
        status_filter=(
            status_filter if status_filter != 'all' else None
        ),
    )

    # 显示用户列表
    if users_data['users']:
        st.subheader(f"用户列表 (共 {users_data['total_count']} 个用户)")

        # 创建用户数据表格
        user_data = []
        for user in users_data['users']:
            templates_limit_display = (
                user['logistics_templates_limit']
                if user['logistics_templates_limit'] != -1
                else '无限'
            )
            # 格式化状态
            if user['is_frozen']:
                status = "❄️ 已冻结"
            elif user['remaining_days'] is not None:
                if user['remaining_days'] <= 0:
                    status = "❌ 已过期"
                elif user['remaining_days'] <= 7:
                    status = f"⚠️ {user['remaining_days']}天后到期"
                else:
                    status = f"✅ {user['remaining_days']}天"
            else:
                status = "✅ 永久有效"

            user_data.append({
                "ID": user['id'],
                "用户名": user['username'],
                "邮箱": user['email'],
                "用户类型": {
                    "free": "免费版",
                    "efficiency": "效率版",
                    "professional": "专业版",
                    "enterprise": "企业版",
                    "gratitude": "感谢版"
                }.get(user['user_type'], user['user_type']),
                "状态": status,
                "剩余次数": (
                    user['remaining_calculations']
                    if user['remaining_calculations'] != -1 else "无限"
                ),
                "物流模板": (
                    f"{user['current_logistics_count']}/"
                    f"{templates_limit_display}"
                ),
                "注册时间": (
                    user['created_at'][:10] if user['created_at'] else "未知"
                ),
                "最后登录": (
                    user['last_login'][:10] if user['last_login'] else "从未登录"
                )
            })

        # 显示用户列表（每个用户一行，带操作按钮）
        for i, user in enumerate(users_data['users']):
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])

                with col1:
                    st.write(f"**{user['username']}**")
                    st.write(f"ID: {user['id']}")
                    st.write(f"邮箱: {user['email'] or '无'}")

                with col2:
                    user_type_name = {
                        "free": "免费版",
                        "efficiency": "效率版",
                        "professional": "专业版",
                        "enterprise": "企业版",
                        "gratitude": "感谢版"
                    }.get(user['user_type'], user['user_type'])
                    st.write(f"**{user_type_name}**")

                    # 状态显示
                    if user['is_frozen']:
                        st.write("❄️ 已冻结")
                    elif user['remaining_days'] is not None:
                        if user['remaining_days'] <= 0:
                            st.write("❌ 已过期")
                        elif user['remaining_days'] <= 7:
                            st.write(f"⚠️ {user['remaining_days']}天后到期")
                        else:
                            st.write(f"✅ {user['remaining_days']}天")
                    else:
                        st.write("✅ 永久有效")

                with col3:
                    calc_display = (
                        user['remaining_calculations']
                        if user['remaining_calculations'] != -1 else '无限'
                    )
                    tmpl_limit_display = (
                        user['logistics_templates_limit']
                        if user['logistics_templates_limit'] != -1 else '无限'
                    )
                    st.write(f"计算次数: {calc_display}")
                    st.write(
                        f"物流模板: {user['current_logistics_count']}/"
                        f"{tmpl_limit_display}"
                    )

                with col4:
                    created_display = (
                        user['created_at'][:10] if user['created_at'] else '未知'
                    )
                    login_display = (
                        user['last_login'][:10]
                        if user['last_login'] else '从未登录'
                    )
                    st.write(f"注册: {created_display}")
                    st.write(f"登录: {login_display}")

                with col5:
                    if st.button("查看详情", key=f"view_user_{user['id']}"):
                        st.session_state.selected_user_id = user['id']
                        st.rerun()

                st.divider()

        # 分页控制
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if users_data['total_pages'] > 1:
                page_numbers = list(range(1, users_data['total_pages'] + 1))
                current_page = st.selectbox(
                    "页码",
                    page_numbers,
                    index=page_numbers.index(page),
                    key="page_selector"
                )
                if current_page != page:
                    st.session_state.user_page = current_page
                    st.rerun()

        # 创建DataFrame用于导出
        df = pd.DataFrame(user_data)

        # 批量操作
        st.subheader("批量操作")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("批量延长30天"):
                # 这里可以实现批量延长功能
                st.info("批量延长功能待实现")

        with col2:
            if st.button("批量增加100次计算"):
                # 这里可以实现批量增加计算次数功能
                st.info("批量增加计算次数功能待实现")

        with col3:
            if st.button("导出用户数据"):
                # 导出CSV
                csv = df.to_csv(index=False, encoding='utf-8-sig')
                export_name = (
                    f"用户数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )
                st.download_button(
                    label="下载CSV文件",
                    data=csv,
                    file_name=export_name,
                    mime="text/csv",
                )

    else:
        st.info("没有找到符合条件的用户")


def user_detail_page():
    """用户详情页面"""
    if not st.session_state.selected_user_id:
        st.error("请先选择一个用户")
        return

    user_detail = get_user_detail(st.session_state.selected_user_id)
    if not user_detail:
        st.error("用户不存在")
        return

    st.markdown(f"""
    <div class="main-header">
        <h1>👤 用户详情 - {user_detail['username']}</h1>
        <p>管理用户订阅和权限</p>
    </div>
    """, unsafe_allow_html=True)

    # 基本信息
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📋 基本信息")
        st.write(f"**用户ID:** {user_detail['id']}")
        st.write(f"**用户名:** {user_detail['username']}")
        st.write(f"**邮箱:** {user_detail['email']}")
        st.write(f"**角色:** {user_detail['role']}")
        st.write(f"**注册时间:** {user_detail['created_at']}")
        st.write(f"**最后登录:** {user_detail['last_login'] or '从未登录'}")
        st.write(f"**产品数量:** {user_detail['products_count']}")

    with col2:
        st.subheader("💎 订阅信息")

        # 用户类型
        user_type_names = {
            "free": "免费版",
            "efficiency": "效率版",
            "professional": "专业版",
            "enterprise": "企业版",
            "gratitude": "感谢版"
        }

        current_type = user_type_names.get(
            user_detail['user_type'],
            user_detail['user_type'],
        )
        st.write(f"**当前套餐:** {current_type}")

        # 订阅时间
        if user_detail['subscription_start']:
            st.write(f"**订阅开始:** {user_detail['subscription_start']}")
        if user_detail['subscription_end']:
            st.write(f"**订阅到期:** {user_detail['subscription_end']}")

        # 剩余天数
        if user_detail['remaining_days'] is not None:
            if user_detail['remaining_days'] <= 0:
                st.error(f"**剩余天数:** {user_detail['remaining_days']}天 (已过期)")
            elif user_detail['remaining_days'] <= 7:
                remaining_display = user_detail['remaining_days']
                st.warning(
                    f"**剩余天数:** {remaining_display}天 (即将到期)"
                )
            else:
                st.success(f"**剩余天数:** {user_detail['remaining_days']}天")
        else:
            st.success("**剩余天数:** 永久有效")

        # 计算次数
        if user_detail['remaining_calculations'] == -1:
            st.write("**剩余计算次数:** 无限")
        else:
            st.write(f"**剩余计算次数:** {user_detail['remaining_calculations']}次")

        # 物流模板
        if user_detail['logistics_templates_limit'] == -1:
            st.write(f"**物流模板:** {user_detail['current_logistics_count']}/无限")
        else:
            st.write(
                f"**物流模板:** "
                f"{user_detail['current_logistics_count']}/"
                f"{user_detail['logistics_templates_limit']}"
            )

        # 状态
        if user_detail['is_frozen']:
            st.error("**状态:** 已冻结")
        else:
            st.success("**状态:** 正常")

    st.divider()

    # 操作按钮
    st.subheader("🔧 管理操作")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("修改套餐", key="change_plan"):
            st.session_state.show_plan_modal = True

    with col2:
        if user_detail['is_frozen']:
            if st.button("解冻用户", key="unfreeze"):
                if unfreeze_user(
                    user_detail['id'],
                    st.session_state.admin_user['id'],
                ):
                    st.success("用户已解冻")
                    st.rerun()
                else:
                    st.error("解冻失败")
        else:
            if st.button("冻结用户", key="freeze"):
                if freeze_user(
                    user_detail['id'],
                    st.session_state.admin_user['id'],
                ):
                    st.success("用户已冻结")
                    st.rerun()
                else:
                    st.error("冻结失败")

    with col3:
        if st.button("重置密码", key="reset_pwd"):
            new_password = reset_user_password(
                user_detail['id'],
                st.session_state.admin_user['id'],
            )
            if new_password:
                st.success(f"密码已重置为: {new_password}")
            else:
                st.error("密码重置失败")

    with col4:
        if st.button("删除用户", key="delete_user", type="secondary"):
            st.error("⚠️ 删除操作不可恢复！")
            if st.button("确认删除", key="confirm_delete"):
                if delete_user_admin(
                    user_detail['id'],
                    st.session_state.admin_user['id'],
                ):
                    st.success("用户已删除")
                    st.session_state.selected_user_id = None
                    st.rerun()
                else:
                    st.error("删除失败")

    # 套餐修改模态框
    if st.session_state.get('show_plan_modal', False):
        st.subheader("📝 修改套餐")

        with st.form("change_plan_form"):
            new_plan = st.selectbox(
                "新套餐",
                [
                    "free",
                    "efficiency",
                    "professional",
                    "enterprise",
                    "gratitude",
                ],
                format_func=lambda x: {
                    "free": "免费版",
                    "efficiency": "效率版",
                    "professional": "专业版",
                    "enterprise": "企业版",
                    "gratitude": "感谢版"
                }.get(str(x), str(x)) or str(x)
            )

            extend_days = st.number_input("延长天数", min_value=0, value=30)

            if new_plan == "efficiency":
                add_calculations = st.number_input(
                    "增加计算次数",
                    min_value=0,
                    value=100,
                )
            else:
                add_calculations = 0

            submitted = st.form_submit_button("确认修改")

            if submitted:
                # 计算新的到期时间
                if user_detail['subscription_end']:
                    try:
                        current_end = datetime.fromisoformat(
                            user_detail['subscription_end']
                        )
                        new_end_date = (
                            current_end + timedelta(days=extend_days)
                        ).isoformat()
                    except (ValueError, TypeError):
                        new_end_date = (
                            datetime.now() + timedelta(days=extend_days)
                        ).isoformat()
                else:
                    new_end_date = (
                        datetime.now() + timedelta(days=extend_days)
                    ).isoformat()

                # 计算新的计算次数
                new_calculations = user_detail['remaining_calculations']
                if new_calculations != -1:
                    new_calculations += add_calculations

                # 更新用户信息
                updates = {
                    'user_type': new_plan,
                    'subscription_end': new_end_date,
                    'remaining_calculations': new_calculations
                }

                if update_user_subscription_admin(
                    user_detail['id'],
                    updates,
                    st.session_state.admin_user['id'],
                ):
                    st.success("套餐修改成功")
                    st.session_state.show_plan_modal = False
                    st.rerun()
                else:
                    st.error("套餐修改失败")

    # 返回按钮
    if st.button("← 返回用户列表"):
        st.session_state.selected_user_id = None
        st.rerun()


def audit_logs_page():
    """操作日志页面"""
    st.markdown("""
    <div class="main-header">
        <h1>📋 操作日志</h1>
        <p>查看所有管理员操作记录</p>
    </div>
    """, unsafe_allow_html=True)

    # 筛选条件
    col1, col2, col3 = st.columns(3)

    with col1:
        action_filter = st.selectbox(
            "操作类型",
            [
                "all",
                "update_subscription",
                "freeze_user",
                "unfreeze_user",
                "delete_user",
                "reset_password",
            ],
            format_func=lambda x: {
                "all": "全部",
                "update_subscription": "修改订阅",
                "freeze_user": "冻结用户",
                "unfreeze_user": "解冻用户",
                "delete_user": "删除用户",
                "reset_password": "重置密码"
            }.get(str(x), str(x)) or str(x)
        )

    with col2:
        per_page = st.selectbox("每页显示", [20, 50, 100], key="audit_per_page")

    with col3:
        if st.button("导出日志"):
            st.info("导出功能待实现")

    # 获取日志数据
    page = st.session_state.get('audit_page', 1)
    logs_data = get_audit_logs(
        page=page,
        per_page=per_page,
        action=action_filter if action_filter != 'all' else None
    )

    # 显示日志
    if logs_data['logs']:
        st.subheader(f"操作日志 (共 {logs_data['total_count']} 条记录)")

        log_data = []
        for log in logs_data['logs']:
            log_data.append({
                "时间": log['timestamp'],
                "管理员": log['admin_username'] or "未知",
                "用户": log['user_username'] or "未知",
                "操作": {
                    "update_subscription": "修改订阅",
                    "freeze_user": "冻结用户",
                    "unfreeze_user": "解冻用户",
                    "delete_user": "删除用户",
                    "reset_password": "重置密码"
                }.get(log['action'], log['action']),
                "详情": log['details']
            })

        df = pd.DataFrame(log_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 分页控制
        if logs_data['total_pages'] > 1:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                page_numbers = list(range(1, logs_data['total_pages'] + 1))
                current_page = st.selectbox(
                    "页码",
                    page_numbers,
                    index=page_numbers.index(page),
                    key="audit_page_selector"
                )
                if current_page != page:
                    st.session_state.audit_page = current_page
                    st.rerun()
    else:
        st.info("没有找到操作日志")


def main():
    """主函数"""
    init_session_state()

    # 检查登录状态
    if not st.session_state.admin_logged_in:
        admin_login()
        return

    # 显示侧边栏
    admin_sidebar()

    # 根据当前页面显示内容
    if st.session_state.current_page == "用户管理":
        if st.session_state.selected_user_id:
            user_detail_page()
        else:
            user_management_page()
    elif st.session_state.current_page == "订阅管理":
        st.info("订阅管理功能正在开发中...")
    elif st.session_state.current_page == "操作日志":
        audit_logs_page()


if __name__ == "__main__":
    main()
