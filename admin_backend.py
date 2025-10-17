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
        get_dashboard_stats,
    )
    from statistics_service import (
        get_retention_analysis,
        get_user_activity_stats,
        get_revenue_stats,
        get_user_retention_details,
        get_plan_stats,
        get_admin_action_logs,
        get_alert_records,
        handle_alert,
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
        get_dashboard_stats,
    )
    from .statistics_service import (
        get_retention_analysis,
        get_user_activity_stats,
        get_revenue_stats,
        get_user_retention_details,
        get_plan_stats,
        get_admin_action_logs,
        get_alert_records,
        handle_alert,
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
    if 'stats_date_range' not in st.session_state:
        from datetime import date, timedelta
        st.session_state.stats_date_range = {
            'start': (date.today() - timedelta(days=30)).isoformat(),
            'end': date.today().isoformat()
        }


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
        menu_options = [
            "用户管理", "订阅管理", "操作日志",
            "📈 数据统计"
        ]

        # 如果当前页面是统计的子页面，需要特殊处理
        current_idx = 0
        if st.session_state.current_page in menu_options:
            current_idx = menu_options.index(st.session_state.current_page)
        elif st.session_state.current_page.startswith("统计-"):
            current_idx = menu_options.index("📈 数据统计")

        page = st.selectbox(
            "选择功能",
            menu_options,
            index=current_idx
        )

        # 如果选择了数据统计，显示子菜单
        if page == "📈 数据统计":
            st.markdown("---")
            stats_submenu = st.radio(
                "统计模块",
                [
                    "总览", "留存分析", "用户活跃",
                    "充值与收入", "留存明细", "套餐分析",
                    "操作日志", "异常监控"
                ],
                key="stats_submenu"
            )
            page = f"统计-{stats_submenu}"

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
        st.dataframe(df, width='stretch', hide_index=True)

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


def statistics_dashboard_page():
    """统计总览页面"""
    st.markdown("""
    <div class="main-header">
        <h1>📊 数据总览</h1>
        <p>系统运营核心指标一览</p>
    </div>
    """, unsafe_allow_html=True)

    # 刷新按钮
    col1, col2, col3 = st.columns([5, 1, 1])
    with col3:
        if st.button("🔄 刷新", key="refresh_dashboard"):
            st.cache_data.clear()
            st.rerun()

    # 获取统计数据
    stats = get_dashboard_stats()

    if not stats:
        st.error("无法获取统计数据")
        return

    # 核心指标卡片
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="今日活跃用户",
            value=stats.get('active_users_today', 0),
            delta=f"+{stats.get('new_users_today', 0)} 新增"
        )

    with col2:
        st.metric(
            label="累计注册用户",
            value=stats.get('total_users', 0)
        )

    with col3:
        revenue_delta = (stats.get('revenue_today', 0) -
                         stats.get('revenue_yesterday', 0))
        st.metric(
            label="今日收入（元）",
            value=f"¥{stats.get('revenue_today', 0):.2f}",
            delta=f"¥{revenue_delta:.2f}" if revenue_delta != 0 else None
        )

    with col4:
        st.metric(
            label="实时在线",
            value=stats.get('online_users', 0),
            help="过去5分钟有登录记录的用户"
        )

    st.divider()

    # 收入统计
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💰 收入概况")
        st.write(f"**昨日收入:** ¥{stats.get('revenue_yesterday', 0):.2f}")
        st.write(f"**本月收入:** ¥{stats.get('revenue_month', 0):.2f}")
        st.write(f"**历史总收入:** ¥{stats.get('total_revenue', 0):.2f}")

    with col2:
        st.subheader("📈 用户增长")
        st.write(f"**今日新增:** {stats.get('new_users_today', 0)} 人")
        st.write(f"**今日活跃:** {stats.get('active_users_today', 0)} 人")
        st.write(f"**累计用户:** {stats.get('total_users', 0)} 人")


def statistics_retention_page():
    """留存分析页面"""
    st.markdown("""
    <div class="main-header">
        <h1>📈 留存分析</h1>
        <p>用户留存率趋势分析</p>
    </div>
    """, unsafe_allow_html=True)

    # 日期选择
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=30),
            key="retention_start_date"
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=datetime.now(),
            key="retention_end_date"
        )
    with col3:
        if st.button("🔄 刷新", key="refresh_retention"):
            st.cache_data.clear()
            st.rerun()

    # 获取留存数据
    retention_data = get_retention_analysis(
        start_date.isoformat(),
        end_date.isoformat()
    )

    if not retention_data:
        st.warning("暂无留存数据")
        return

    # 平均留存率
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("D1 留存率", f"{retention_data.get('d1_retention', 0):.2f}%")
    with col2:
        st.metric("D3 留存率", f"{retention_data.get('d3_retention', 0):.2f}%")
    with col3:
        st.metric("D7 留存率", f"{retention_data.get('d7_retention', 0):.2f}%")
    with col4:
        st.metric("D30 留存率", f"{retention_data.get('d30_retention', 0):.2f}%")

    # 留存趋势图
    daily_trend = retention_data.get('daily_trend', [])
    if daily_trend:
        st.subheader("📊 留存趋势图")
        df = pd.DataFrame(daily_trend)
        st.line_chart(df.set_index('date')[['d1', 'd3', 'd7', 'd30']])

        # 详细数据表格
        with st.expander("查看详细数据"):
            st.dataframe(df, width='stretch', hide_index=True)


def statistics_activity_page():
    """用户活跃页面"""
    st.markdown("""
    <div class="main-header">
        <h1>👥 用户活跃</h1>
        <p>用户登录与活跃行为分析</p>
    </div>
    """, unsafe_allow_html=True)

    # 刷新按钮
    col1, col2 = st.columns([10, 1])
    with col2:
        if st.button("🔄 刷新", key="refresh_activity"):
            st.cache_data.clear()
            st.rerun()

    # 获取活跃数据
    activity_data = get_user_activity_stats()

    if not activity_data:
        st.warning("暂无活跃数据")
        return

    # 核心指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("DAU（日活）", activity_data.get('dau', 0))
    with col2:
        st.metric("WAU（周活）", activity_data.get('wau', 0))
    with col3:
        st.metric("MAU（月活）", activity_data.get('mau', 0))

    st.divider()

    # Top 10 活跃用户
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⭐ Top 10 活跃用户")
        top_users = activity_data.get('top_active_users', [])
        if top_users:
            for idx, user in enumerate(top_users, 1):
                st.write(
                    f"{idx}. **{user['username']}** "
                    f"({user['user_type']}) - {user['login_count']} 次登录"
                )
        else:
            st.info("暂无数据")

    with col2:
        st.subheader("📈 30天活跃趋势")
        trend = activity_data.get('trend', [])
        if trend:
            df = pd.DataFrame(trend)
            st.line_chart(df.set_index('date')['active_users'])
        else:
            st.info("暂无数据")


def statistics_revenue_page():
    """充值与收入页面"""
    st.markdown("""
    <div class="main-header">
        <h1>💰 充值与收入</h1>
        <p>订单与收入统计分析</p>
    </div>
    """, unsafe_allow_html=True)

    # 日期选择
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=30),
            key="revenue_start_date"
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=datetime.now(),
            key="revenue_end_date"
        )
    with col3:
        if st.button("🔄 刷新", key="refresh_revenue"):
            st.cache_data.clear()
            st.rerun()
    with col4:
        if st.button("📥 导出", key="export_revenue"):
            st.info("导出功能开发中")

    # 获取收入数据
    revenue_data = get_revenue_stats(
        start_date.isoformat(),
        end_date.isoformat()
    )

    if not revenue_data:
        st.warning("暂无收入数据")
        return

    # 核心指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("订单总数", revenue_data.get('total_orders', 0))
    with col2:
        st.metric("总金额", f"¥{revenue_data.get('total_amount', 0):.2f}")
    with col3:
        st.metric("平均客单价", f"¥{revenue_data.get('avg_order_value', 0):.2f}")

    st.divider()

    # 收入趋势图和套餐分布
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("📊 收入趋势")
        trend = revenue_data.get('revenue_trend', [])
        if trend:
            df = pd.DataFrame(trend)
            st.line_chart(df.set_index('date')['revenue'])
        else:
            st.info("暂无数据")

    with col2:
        st.subheader("🥧 套餐分布")
        plan_dist = revenue_data.get('plan_distribution', [])
        if plan_dist:
            for plan in plan_dist:
                st.write(
                    f"**{plan['plan_type']}**: {plan['count']} 单 "
                    f"(¥{plan['total_amount']:.2f})"
                )
        else:
            st.info("暂无数据")

    # 订单列表
    st.subheader("📋 订单列表")
    orders = revenue_data.get('order_list', [])
    if orders:
        df = pd.DataFrame(orders)
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("暂无订单数据")


def statistics_user_retention_details_page():
    """用户留存明细页面"""
    st.markdown("""
    <div class="main-header">
        <h1>📋 用户留存明细</h1>
        <p>详细用户留存与行为记录</p>
    </div>
    """, unsafe_allow_html=True)

    # 筛选和排序
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sort_by = st.selectbox(
            "排序方式",
            [
                ("login_count_desc", "登录次数（降序）"),
                ("login_count_asc", "登录次数（升序）"),
                ("created_at_desc", "注册时间（最新）"),
                ("created_at_asc", "注册时间（最早）"),
                ("last_login_desc", "最近登录（最新）"),
                ("last_login_asc", "最近登录（最早）"),
            ],
            format_func=lambda x: x[1]
        )[0]

    with col2:
        per_page = st.selectbox("每页显示", [10, 20, 50], index=1)

    with col3:
        if st.button("🔄 刷新", key="refresh_user_retention"):
            st.rerun()

    # 获取数据
    page = st.session_state.get('user_retention_page', 1)
    data = get_user_retention_details(page, per_page, sort_by)

    if not data or not data.get('users'):
        st.info("暂无用户数据")
        return

    # 显示用户列表
    st.subheader(f"用户列表（共 {data['total']} 人）")

    users_data = []
    for user in data['users']:
        users_data.append({
            'ID': user['user_id'],
            '用户名': user['username'],
            '邮箱': user['email'] or '无',
            '套餐': user['user_type'],
            '注册日期': user['created_at'][:10] if user['created_at'] else '未知',
            '最近登录': user['last_login'][:10] if user['last_login'] else '从未',
            '登录次数': user['login_count'],
            '留存天数': user['retention_days'],
            '是否续费': '是' if user['is_renewed'] else '否'
        })

    df = pd.DataFrame(users_data)
    st.dataframe(df, width='stretch', hide_index=True)

    # 分页控制
    if data['total_pages'] > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            page_numbers = list(range(1, data['total_pages'] + 1))
            current_page = st.selectbox(
                "页码",
                page_numbers,
                index=page_numbers.index(page) if page in page_numbers else 0,
                key="user_retention_page_selector"
            )
            if current_page != page:
                st.session_state.user_retention_page = current_page
                st.rerun()


def statistics_plan_page():
    """套餐分析页面"""
    st.markdown("""
    <div class="main-header">
        <h1>📦 套餐分析</h1>
        <p>套餐使用与升级情况分析</p>
    </div>
    """, unsafe_allow_html=True)

    # 刷新按钮
    col1, col2 = st.columns([10, 1])
    with col2:
        if st.button("🔄 刷新", key="refresh_plan"):
            st.cache_data.clear()
            st.rerun()

    # 获取套餐数据
    plan_data = get_plan_stats()

    if not plan_data:
        st.warning("暂无套餐数据")
        return

    # 套餐用户数量
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📊 各套餐用户数量")
        plan_count = plan_data.get('plan_count', [])
        if plan_count:
            for plan in plan_count:
                st.write(f"**{plan['plan_type']}**: {plan['user_count']} 人")
        else:
            st.info("暂无数据")

    with col2:
        st.subheader("🔄 套餐升级路径（Top 10）")
        upgrade_paths = plan_data.get('upgrade_paths', [])
        if upgrade_paths:
            for path in upgrade_paths:
                st.write(
                    f"{path['from_plan']} → {path['to_plan']}: "
                    f"{path['count']} 次"
                )
        else:
            st.info("暂无升级数据")

    st.divider()

    # 套餐收入贡献
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("💰 套餐收入贡献")
        plan_revenue = plan_data.get('plan_revenue', [])
        if plan_revenue:
            for plan in plan_revenue:
                st.write(
                    f"**{plan['plan_type']}**: ¥{plan['total_revenue']:.2f}"
                )
        else:
            st.info("暂无数据")

    with col2:
        st.subheader("📈 用户生命周期价值（LTV）")
        ltv_stats = plan_data.get('ltv_stats', [])
        if ltv_stats:
            for ltv in ltv_stats:
                st.write(
                    f"**{ltv['user_type']}**: ¥{ltv['ltv']:.2f} "
                    f"({ltv['user_count']} 人)"
                )
        else:
            st.info("暂无数据")


def statistics_admin_logs_page():
    """管理员操作日志页面"""
    st.markdown("""
    <div class="main-header">
        <h1>📜 管理员操作日志</h1>
        <p>记录所有管理员操作行为</p>
    </div>
    """, unsafe_allow_html=True)

    # 刷新和导出
    col1, col2, col3 = st.columns([9, 1, 1])
    with col2:
        if st.button("🔄 刷新", key="refresh_admin_logs"):
            st.rerun()
    with col3:
        if st.button("📥 导出", key="export_admin_logs"):
            st.info("导出功能开发中")

    # 获取日志数据
    page = st.session_state.get('admin_logs_page', 1)
    per_page = st.selectbox("每页显示", [20, 50, 100], key="admin_logs_per_page")

    logs_data = get_admin_action_logs(page, per_page)

    if not logs_data or not logs_data.get('logs'):
        st.info("暂无日志数据")
        return

    # 显示日志
    st.subheader(f"操作日志（共 {logs_data['total']} 条）")

    log_list = []
    for log in logs_data['logs']:
        log_list.append({
            '时间': log['created_at'],
            '管理员': log['admin_username'] or '未知',
            '操作类型': log['action_type'],
            '操作详情': log['action_detail'],
            '目标用户': log['target_username'] or '-'
        })

    df = pd.DataFrame(log_list)
    st.dataframe(df, width='stretch', hide_index=True)

    # 分页控制
    if logs_data['total_pages'] > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            page_numbers = list(range(1, logs_data['total_pages'] + 1))
            current_page = st.selectbox(
                "页码",
                page_numbers,
                index=page_numbers.index(page) if page in page_numbers else 0,
                key="admin_logs_page_selector"
            )
            if current_page != page:
                st.session_state.admin_logs_page = current_page
                st.rerun()


def statistics_alerts_page():
    """异常监控与告警页面"""
    st.markdown("""
    <div class="main-header">
        <h1>🚨 异常监控与告警</h1>
        <p>系统异常数据监控与预警</p>
    </div>
    """, unsafe_allow_html=True)

    # 筛选条件
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        status_filter = st.selectbox(
            "状态筛选",
            [("all", "全部"), ("unhandled", "未处理"), ("handled", "已处理")],
            format_func=lambda x: x[1]
        )[0]

    with col2:
        if st.button("🔄 刷新", key="refresh_alerts"):
            st.rerun()

    # 获取告警数据
    alert_data = get_alert_records(
        status=None if status_filter == "all" else status_filter
    )

    if not alert_data:
        st.warning("暂无告警数据")
        return

    # 告警统计
    col1, col2 = st.columns([1, 3])

    with col1:
        st.metric("告警总数", alert_data.get('total_alerts', 0))

    with col2:
        st.subheader("📈 近7天告警趋势")
        trend = alert_data.get('alert_trend', [])
        if trend:
            df = pd.DataFrame(trend)
            st.line_chart(df.set_index('date')['count'])
        else:
            st.info("暂无数据")

    st.divider()

    # 告警列表
    st.subheader("📋 告警记录")
    alerts = alert_data.get('alerts', [])

    if alerts:
        for alert in alerts:
            # 根据级别设置颜色
            level_color = {
                'high': '🔴',
                'medium': '🟠',
                'low': '🟡'
            }.get(alert['alert_level'], '⚪')

            with st.expander(
                f"{level_color} {alert['description']} - {alert['created_at']}"
            ):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**类型:** {alert['alert_type']}")
                    st.write(f"**级别:** {alert['alert_level']}")
                    if alert['threshold']:
                        st.write(f"**阈值:** {alert['threshold']}")
                    if alert['actual']:
                        st.write(f"**实际值:** {alert['actual']}")
                    st.write(f"**状态:** {alert['status']}")
                    if alert['handled_at']:
                        st.write(f"**处理时间:** {alert['handled_at']}")
                    if alert['handle_note']:
                        st.write(f"**处理备注:** {alert['handle_note']}")

                with col2:
                    if alert['status'] == '未处理':
                        if st.button("✅ 标记已处理", key=f"handle_{alert['id']}"):
                            st.session_state[f'handle_note_{alert["id"]}'] = ""
                            st.rerun()

                        # 处理备注输入
                        if f'handle_note_{alert["id"]}' in st.session_state:
                            note = st.text_area(
                                "处理备注",
                                key=f"note_input_{alert['id']}"
                            )
                            if st.button("确认处理", key=f"confirm_{alert['id']}"):
                                admin_id = st.session_state.admin_user['id']
                                handle_alert(alert['id'], admin_id, note)
                                st.success("已处理")
                                st.rerun()
    else:
        st.info("暂无告警记录")


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
    page = st.session_state.current_page

    if page == "用户管理":
        if st.session_state.selected_user_id:
            user_detail_page()
        else:
            user_management_page()
    elif page == "订阅管理":
        st.info("订阅管理功能正在开发中...")
    elif page == "操作日志":
        audit_logs_page()
    elif page == "统计-总览":
        statistics_dashboard_page()
    elif page == "统计-留存分析":
        statistics_retention_page()
    elif page == "统计-用户活跃":
        statistics_activity_page()
    elif page == "统计-充值与收入":
        statistics_revenue_page()
    elif page == "统计-留存明细":
        statistics_user_retention_details_page()
    elif page == "统计-套餐分析":
        statistics_plan_page()
    elif page == "统计-操作日志":
        statistics_admin_logs_page()
    elif page == "统计-异常监控":
        statistics_alerts_page()


if __name__ == "__main__":
    main()
