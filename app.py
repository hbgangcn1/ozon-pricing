# type: ignore
import streamlit as st
import pandas as pd
import sqlite3
import threading
import os
from typing import Optional, Dict, List, Any

# 配置 Streamlit 服务器设置
st.set_page_config(
    page_title="物流系统",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== 公安备案临时配置已移除 =====
# 备案已完成，恢复正常登录流程
POLICE_FILING_MODE = False  # 恢复为False，启用正常登录流程

# ===== 公安备案临时配置结束 =====
try:
    from .db_utils import (
        init_db,
        check_user_subscription_status,
        update_user_password,
        is_admin,
        current_user_id,
        get_db_connection,
        hash_password,
        require_admin,
        get_user_preferred_mode,
        update_user_preferred_mode,
        migrate_user_preferences,
        decrement_user_calculations,
    )

    from .ui_user import (
        user_management_page,
        login_or_register_page,
        subscription_management_page as admin_subscription_management_page
    )
    from .ui_products import (
        edit_product_form,
        batch_edit_pricing_form,
    )
    from .ui_logistics import logistics_page
    # pricing_calculator_page is not used in this module

    from .password_utils import (
        validate_password_strength, get_password_requirements_text,
    )
    from .auto_backup import (
        create_manual_backup, get_backup_info, start_backup_service,
    )
    from .session_security import (
        check_session_security, SessionSecurity, secure_logout,
    )
    from .exchange_service import ExchangeRateService, get_usd_rate
except ImportError:  # Fallback when run as a top-level module
    from db_utils import (
        init_db,
        check_user_subscription_status,
        update_user_password,
        is_admin,
        current_user_id,
        get_db_connection,
        hash_password,
        require_admin,
        get_user_preferred_mode,
        update_user_preferred_mode,
        migrate_user_preferences,
        decrement_user_calculations,
    )

    from ui_user import (
        user_management_page,
        login_or_register_page,
        subscription_management_page as admin_subscription_management_page
    )
    from ui_products import edit_product_form, batch_edit_pricing_form
    from ui_logistics import logistics_page
    # pricing_calculator_page is imported at module level

    from password_utils import (
        validate_password_strength, get_password_requirements_text,
    )
    from auto_backup import (
        create_manual_backup, get_backup_info, start_backup_service,
    )
    from session_security import (
        check_session_security, SessionSecurity, secure_logout,
    )
    from exchange_service import ExchangeRateService, get_usd_rate

# 设置页面配置
st.set_page_config(
    page_title="物流定价系统",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# 隐藏侧边栏
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    /* 注释掉可能影响登录界面显示的CSS规则 */
    /* .stApp > div:first-child {display: none;} */
</style>
""", unsafe_allow_html=True)

# 设置默认主题为Light
st.markdown("""
<script>
// 设置默认主题为Light
if (window.localStorage.getItem('theme') === null) {
    window.localStorage.setItem('theme', 'light');
}
</script>
""", unsafe_allow_html=True)

# 自定义CSS样式
st.markdown("""
<style>
/* 全局背景 - 经典白色主题 */
.stApp {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    min-height: 100vh;
}

/* 侧边栏样式 */
.sidebar .sidebar-content {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(0, 0, 0, 0.1);
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

/* 按钮样式 - 现代蓝色主题 */
.stButton > button {
    background: linear-gradient(45deg, #2196F3, #1976D2);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(33, 150, 243, 0.3);
}

.stButton > button:hover {
    background: linear-gradient(45deg, #1976D2, #1565C0);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(33, 150, 243, 0.4);
}

/* 输入框样式 */
.stTextInput > div > div > input {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 10px 12px;
    transition: border-color 0.3s ease;
}

.stTextInput > div > div > input:focus {
    border-color: #2196F3;
    box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
}

/* 选择框样式 */
.stSelectbox > div > div > select {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 8px 12px;
    transition: border-color 0.3s ease;
}

.stSelectbox > div > div > select:focus {
    border-color: #2196F3;
    box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
}

/* 卡片容器 - 现代卡片设计 */
.card-container {
    background: white;
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.05);
    transition: box-shadow 0.3s ease;
}

.card-container:hover {
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

/* 标题样式 - 深色文字 */
.custom-title {
    color: #2c3e50;
    text-align: center;
    font-size: 2.2em;
    font-weight: 700;
    margin-bottom: 30px;
    letter-spacing: -0.5px;
}

/* 消息样式 */
.custom-message {
    background: white;
    border-radius: 8px;
    padding: 16px;
    margin: 12px 0;
    border-left: 4px solid #2196F3;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 数据框样式 */
.dataframe {
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 表单样式 */
.stForm {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.05);
}

/* 扩展器样式 */
.streamlit-expanderHeader {
    background: white !important;
    border-radius: 8px !important;
    border: 1px solid #e0e0e0 !important;
    font-weight: 600 !important;
}

/* 侧边栏标题样式 */
.sidebar .sidebar-content h1,
.sidebar .sidebar-content h2,
.sidebar .sidebar-content h3 {
    color: #2c3e50 !important;
}

/* 主标题样式 */
.main-title {
    color: #2c3e50;
    font-size: 2.2em;
    font-weight: 700;
    text-align: center;
    margin-bottom: 1rem;
    letter-spacing: -0.5px;
}

/* 副标题样式 */
.sub-title {
    color: #34495e;
    font-size: 1.4em;
    font-weight: 600;
    margin-bottom: 1rem;
}

/* 成功消息样式 */
.stSuccess {
    background: #e8f5e8 !important;
    border-left: 4px solid #4caf50 !important;
    color: #2e7d32 !important;
}

/* 错误消息样式 */
.stError {
    background: #ffebee !important;
    border-left: 4px solid #f44336 !important;
    color: #c62828 !important;
}

/* 警告消息样式 */
.stWarning {
    background: #fff3e0 !important;
    border-left: 4px solid #ff9800 !important;
    color: #ef6c00 !important;
}

/* 信息消息样式 */
.stInfo {
    background: #e3f2fd !important;
    border-left: 4px solid #2196f3 !important;
    color: #1565c0 !important;
}

/* 统一按钮样式 - 所有按钮都使用蓝色主题 */
.stButton > button {
    background: linear-gradient(45deg, #2196F3, #1976D2) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 8px rgba(33, 150, 243, 0.3) !important;
}

.stButton > button:hover {
    background: linear-gradient(45deg, #1976D2, #1565C0) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(33, 150, 243, 0.4) !important;
}

/* 模式切换按钮特殊样式 */
[data-testid="stButton"] button {
    background: linear-gradient(45deg, #2196F3, #1976D2) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 8px rgba(33, 150, 243, 0.3) !important;
}

[data-testid="stButton"] button:hover {
    background: linear-gradient(45deg, #1976D2, #1565C0) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(33, 150, 243, 0.4) !important;
}

/* 强制列布局样式 - 解决列显示问题 */
.main .block-container {
    max-width: 100% !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

[data-testid="column"] {
    width: 100% !important;
    min-width: 0 !important;
}

.stColumns {
    display: flex !important;
    gap: 1rem !important;
    width: 100% !important;
}

.element-container {
    width: 100% !important;
}

/* 强制容器宽度 */
.main .block-container > div {
    max-width: none !important;
    width: 100% !important;
}

/* 确保flex布局正常工作 */
[data-testid="column"] > div {
    width: 100% !important;
}

/* 登录按钮特殊样式 - 适应内容宽度 */
.stFormSubmitButton > button {
    width: auto !important;
    min-width: fit-content !important;
}
</style>
""", unsafe_allow_html=True)


def show_system_settings():
    """显示系统设置内容（备份管理、系统信息等）"""
    # 系统配置 - 仅admin用户可见
    if is_admin():
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.markdown(
            '<h2 style="color: #667eea; margin-bottom: 20px;">'
            '⚙️ 系统配置</h2>',
            unsafe_allow_html=True
        )

    # 开放注册开关
        from db_utils import get_system_config, set_system_config
        current_registration_status = get_system_config(
            'open_registration', 'false'
        )
        is_open = current_registration_status.lower() == 'true'

        new_status = st.toggle(
            "开放注册",
            value=is_open,
            help="开启后，用户可以在登录页面自行注册账号，"
                 "所有用户都能看到订阅管理页面",
            key="open_registration_toggle"
        )
        if new_status != is_open:
            if set_system_config(
                'open_registration',
                str(new_status).lower(),
                '是否开放用户注册'
            ):
                st.success("✅ 系统配置已更新")
                st.rerun()
            else:
                st.error("❌ 系统配置更新失败")
        st.markdown('</div>', unsafe_allow_html=True)

    # 备份管理 - 仅admin用户可见
    if is_admin():
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.markdown(
            '<h2 style="color: #667eea; margin-bottom: 20px;">'
            '💾 备份管理</h2>',
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📦 立即备份", help="手动创建数据库备份", key="backup_now"):
                if create_manual_backup():
                    st.success("✅ 备份创建成功！")
                else:
                    st.error("❌ 备份创建失败！")

        with col2:
            if st.button("🔄 刷新状态", help="刷新备份状态信息", key="refresh_backup"):
                st.rerun()

    # 显示备份统计信息
        backup_stats = get_backup_info()
        if backup_stats:
            st.write(f"**备份文件数量：** {backup_stats['count']} 个")
            st.write(f"**总备份大小：** {backup_stats['total_size_mb']} MB")

            if backup_stats['files']:
                st.write("**最新备份文件：**")
                for i, file in enumerate(backup_stats['files'][:3]):
                    st.write(
                        f"  {i+1}. {file['name']} "
                        f"({file['mtime'].strftime('%Y-%m-%d %H:%M:%S')})"
                    )
        else:
            st.warning("⚠️ 无法获取备份信息")

        st.markdown('</div>', unsafe_allow_html=True)

    # 系统信息
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.markdown(
        '<h2 style="color: #667eea; margin-bottom: 20px;">'
        'ℹ️ 系统信息</h2>',
        unsafe_allow_html=True
    )

    st.write(f"**当前用户：** {st.session_state.user['username']}")
    st.write(f"**用户角色：** {st.session_state.user['role']}")

    # 显示会话安全信息
    session_info = SessionSecurity.get_session_info(
        (st.session_state.get('session_id', '')
         if hasattr(st.session_state, 'get')
         else getattr(st.session_state, 'session_id', ''))
    )
    if session_info:
        import time
        last_activity_str = time.strftime(
            '%H:%M:%S', time.localtime(session_info['last_activity']))
        st.write(f"**最后活动：** {last_activity_str}")

    # 简化的会话信息显示
        st.write(f"**会话ID：** {session_info['session_id'][:8]}...")

    st.markdown('</div>', unsafe_allow_html=True)


def settings_page():
    """设置页面 - 账户管理（保留原函数以兼容性）"""
    st.markdown('<h1 class="custom-title">⚙️ 系统设置</h1>',
                unsafe_allow_html=True)

    # 检查是否开放注册
    from db_utils import is_registration_open
    registration_open = is_registration_open()

    # 根据开放注册状态决定标签页
    if registration_open:
        tab1, tab2 = st.tabs(["🔐 账户管理", "💎 订阅管理"])

        with tab1:
            st.markdown('<div class="card-container">', unsafe_allow_html=True)
            st.markdown(
                '<h2 style="color: #667eea; margin-bottom: 20px;">'
                '🔐 账户管理</h2>',
                unsafe_allow_html=True
            )

        # 修改密码 - 使用show_password_change_form函数
            show_password_change_form()

            st.markdown('</div>', unsafe_allow_html=True)

        with tab2:
            subscription_management_page()
    else:
        # 不开放注册时只显示账户管理
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.markdown(
            '<h2 style="color: #667eea; margin-bottom: 20px;">'
            '🔐 账户管理</h2>',
            unsafe_allow_html=True
        )

    # 修改密码 - 使用show_password_change_form函数
        show_password_change_form()

        st.markdown('</div>', unsafe_allow_html=True)

    # 备份管理 - 仅admin用户可见
    if is_admin():
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.markdown(
            '<h2 style="color: #667eea; margin-bottom: 20px;">'
            '💾 备份管理</h2>',
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📦 立即备份", help="手动创建数据库备份", key="backup_now"):
                if create_manual_backup():
                    st.success("✅ 备份创建成功！")
                else:
                    st.error("❌ 备份创建失败！")

        with col2:
            if st.button("🔄 刷新状态", help="刷新备份状态信息", key="refresh_backup"):
                st.rerun()

    # 显示备份统计信息
        backup_stats = get_backup_info()
        if backup_stats:
            st.write(f"**备份文件数量：** {backup_stats['count']} 个")
            st.write(f"**总备份大小：** {backup_stats['total_size_mb']} MB")

            if backup_stats['files']:
                st.write("**最新备份文件：**")
                for i, file in enumerate(backup_stats['files'][:3]):
                    st.write(
                        f"  {i+1}. {file['name']} "
                        f"({file['mtime'].strftime('%Y-%m-%d %H:%M:%S')})"
                    )
        else:
            st.warning("⚠️ 无法获取备份信息")

        st.markdown('</div>', unsafe_allow_html=True)

    # 系统信息
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.markdown(
        '<h2 style="color: #667eea; margin-bottom: 20px;">'
        'ℹ️ 系统信息</h2>',
        unsafe_allow_html=True
    )

    st.write(f"**当前用户：** {st.session_state.user['username']}")
    st.write(f"**用户角色：** {st.session_state.user['role']}")

    # 显示会话安全信息
    session_info = SessionSecurity.get_session_info(
        (st.session_state.get('session_id', '')
         if hasattr(st.session_state, 'get')
         else getattr(st.session_state, 'session_id', ''))
    )
    if session_info:
        import time
        last_activity_str = time.strftime(
            '%H:%M:%S', time.localtime(session_info['last_activity']))
        st.write(f"**最后活动：** {last_activity_str}")

    # 简化的会话信息显示
        st.write(f"**会话ID：** {session_info['session_id'][:8]}...")

    st.markdown('</div>', unsafe_allow_html=True)


# noinspection PyUnboundLocalVariable
def should_show_subscription_management():
    """检查是否应该显示订阅管理页面"""

    # 检查当前用户类型，测试用户和感谢版用户不显示订阅管理
    # 测试环境兼容性处理
    if hasattr(st.session_state, 'get'):
        current_user = st.session_state.get('user', {})
    else:
        current_user = getattr(st.session_state, 'user', {})
    if not current_user or 'id' not in current_user:
        return True  # 如果没有用户信息，默认显示

    # 获取用户订阅状态以确定用户类型
    try:
        subscription_status = check_user_subscription_status(
            current_user['id']
        )
        if subscription_status:
            user_type = subscription_status.get('user_type', 'free')
        # 测试用户和感谢版用户不显示订阅管理标签页
            if user_type in ['test', 'gratitude']:
                return False
    except (KeyError, TypeError, AttributeError):
        pass  # 如果获取失败，默认显示

    # 修改：无论开放注册状态如何，都显示订阅管理页面
    # 这样可以确保所有用户都能访问订阅管理功能
    return True


def _create_main_layout():
    """创建主界面布局"""
    return st.columns([2, 2, 2])


def _validate_user_and_get_mode():
    """验证用户并获取模式，返回 (current_user, current_mode, subscription_status) 或 None"""
    # ✅ 直接取 session_state，不用前置初始化
    # 测试环境兼容性处理
    if hasattr(st.session_state, 'get'):
        current_user = st.session_state.get('user', {}) or {}
        current_mode = st.session_state.get('current_mode')  # 不设置默认值
    else:
        # 测试环境中的 SimpleNamespace 对象
        current_user = getattr(st.session_state, 'user', {}) or {}
        current_mode = getattr(st.session_state, 'current_mode', None)

    # 明确告知静态分析器：类型已确定
    assert isinstance(current_user, dict)

    # 验证用户信息
    if not current_user or 'id' not in current_user:
        st.error("用户未登录或用户信息不完整")
        return None

    # 检查用户订阅状态
    subscription_status = check_user_subscription_status(current_user['id'])
    if not subscription_status:
        st.error("无法获取用户订阅状态")
        return None

    # 检查订阅是否有效
    if not subscription_status.get('valid', True):
        st.error("账号已到期")
        return None

    # 获取用户类型并对免费版/效率版强制设为极速模式
    user_type = subscription_status.get('user_type', 'free')
    if user_type in ['free', 'efficiency']:
        st.session_state.current_mode = 'fast'
        current_mode = 'fast'

    # 如果session_state中没有current_mode，从数据库获取用户偏好
    if current_mode is None:
        current_mode = get_user_preferred_mode(current_user['id'])
        if current_mode is None:
            # 首次登录用户，设置默认为极速模式
            current_mode = 'fast'
            update_user_preferred_mode(current_user['id'], 'fast')
        st.session_state.current_mode = current_mode

    # 验证current_mode的有效性
    assert isinstance(current_mode, str)  # 确保类型正确
    if current_mode not in ['fast', 'precise']:
        st.error("无效的模式设置")
        return None

    return current_user, current_mode, subscription_status


def show_main_interface():
    """显示主界面"""
    # noinspection PyUnboundLocalVariable

    # 由于服务会频繁重启导致session_state丢失，不再显示支付成功通知
    # 用户可以直接在侧边栏查看订阅状态
    # 清除可能残留的支付成功标记
    if 'last_successful_payment' in st.session_state:
        # 清除订阅状态缓存，强制从数据库重新读取
        if 'subscription_status' in st.session_state:
            del st.session_state['subscription_status']
            print("🗑️ 已清除订阅状态缓存（支付成功后）")
        # 清除支付成功标记
        del st.session_state['last_successful_payment']
        print("🗑️ 已清除支付成功标记")

    # 移除未使用的导入

    # 验证用户并获取信息
    validation_result = _validate_user_and_get_mode()
    if validation_result is None:
        return

    current_user, current_mode, subscription_status = (
        validation_result
    )

    # 在所有验证通过后创建列，避免静态分析器误报
    left_col, middle_col, right_col = _create_main_layout()
    # 明确检查变量已被创建
    assert (left_col is not None and middle_col is not None and
            right_col is not None)

    # 顶部信息栏 - 左列：模式文字和切换按钮
    # noinspection PyUnboundLocalVariable
    with left_col:
        mode_cols = st.columns([5, 6, 5], vertical_alignment="center")

        with mode_cols[0]:
            if current_mode == 'fast':
                st.markdown(
                    (
                        '<div style="font-size: 18px; font-weight: 600; '
                        'color: #2c3e50;">'
                        '⚡ 极速模式'
                        '</div>'
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    (
                        '<div style="font-size: 18px; font-weight: 600; '
                        'color: #2c3e50;">'
                        '🎯 精准模式'
                        '</div>'
                    ),
                    unsafe_allow_html=True,
                )
        with mode_cols[1]:
            if current_mode == 'fast':
                # 免费版与效率版不显示"切换精准模式"按钮
                user_type = subscription_status.get('user_type', 'free')
                if user_type not in ['free', 'efficiency']:
                    if st.button(
                        "切换精准模式",
                        key="switch_to_precise",
                        help="切换到精准模式",
                    ):
                        st.session_state.current_mode = 'precise'
                    # noinspection PyUnboundLocalVariable
                        update_user_preferred_mode(
                            current_user['id'], 'precise'
                        )
                        st.rerun()
            else:
                # 免费版与效率版不应出现在精准模式，亦不显示切换按钮
                user_type = subscription_status.get('user_type', 'free')
                if user_type not in ['free', 'efficiency']:
                    if st.button(
                        "切换极速模式",
                        key="switch_to_fast",
                        help="切换到极速模式",
                    ):
                        st.session_state.current_mode = 'fast'
                    # noinspection PyUnboundLocalVariable
                        update_user_preferred_mode(current_user['id'], 'fast')
                        st.rerun()

        with mode_cols[2]:
            pass

    # 中间列与右列（占位或放内容）

    # pylint: disable=possibly-used-before-assignment
    # noinspection PyUnboundLocalVariable
    with middle_col:
        pass

    # noinspection PyUnboundLocalVariable
    with right_col:
        # 右侧列: 欢迎信息和退出按钮
        welcome_cols = st.columns([2, 1], vertical_alignment="center")

        with welcome_cols[0]:
            # 欢迎信息
            # noinspection PyUnboundLocalVariable
            _username = current_user.get("username", "")
            content = (
                '<div style="text-align: right;"><div style="font-size: 18px; '
                'font-weight: 600; color: #2c3e50;">'
                f'欢迎回来，{_username}！'
                '</div></div>'
            )
            st.markdown(content, unsafe_allow_html=True)

        with welcome_cols[1]:
            # 退出按钮
            if st.button("🚪 退出", key="logout", use_container_width=False):
                secure_logout()

    # 根据模式显示不同的界面
    # noinspection PyUnboundLocalVariable
    if current_mode == 'fast':
        # noinspection PyUnboundLocalVariable
        show_fast_mode_interface(current_user)
    else:
        # noinspection PyUnboundLocalVariable
        show_precise_mode_interface(current_user)


def show_fast_mode_interface(current_user):
    """显示极速模式界面"""
    # 根据用户角色创建标签页
    if current_user["role"] == "admin":
        # 根据开放注册状态决定标签页
        if should_show_subscription_management():
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "💎 订阅管理",
                    "💳 支付中心",
                    "⚙️ 系统设置",
                    "👥 用户管理",
                    "ℹ️ 关于我们",
                ]
            )
            user_management_tab = tab7
            about_us_tab = tab8
        else:
            tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "💳 支付中心",
                    "⚙️ 系统设置",
                    "👥 用户管理",
                    "ℹ️ 关于我们",
                ]
            )
            user_management_tab = tab6
            about_us_tab = tab7
        with tab1:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">⚡ 极速定价系统</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        快速定价，无需记录产品信息
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fast_pricing_calculator()
        with tab2:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🚚 物流管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理物流规则和模板
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fast_logistics_management()
        with tab3:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🔐 账户管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理账户信息和密码
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_password_change_form()
    # 订阅管理标签页 - 根据开放注册状态决定是否显示
        if should_show_subscription_management():
            with tab4:
                st.markdown(
                    """
                    <div style="text-align: center; margin-bottom: 2rem;">
                        <h1 class="main-title">💎 订阅管理</h1>
                        <p style="color: #718096; font-size: 1.1rem; "
                           "margin: 0;">
                            管理订阅和套餐信息
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                subscription_management_page()

    # 支付中心标签页
        payment_tab = tab5 if should_show_subscription_management() else tab4
        with payment_tab:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">💳 支付中心</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理支付和订单信息
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            payment_center_page()

    # 系统设置标签页 - 根据开放注册状态调整索引
        system_tab = tab6 if should_show_subscription_management() else tab5
        with system_tab:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">⚙️ 系统设置</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        系统配置和偏好设置
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_system_settings()

    # 用户管理标签页
        with user_management_tab:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">👥 用户管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理系统用户和权限
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        # 检查是否需要显示订阅管理页面
            if 'selected_user_for_subscription' in st.session_state:
                admin_subscription_management_page()
            else:
                user_management_page()
    else:
        # 根据开放注册状态决定标签页
        if should_show_subscription_management():
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "💎 订阅管理",
                    "⚙️ 系统设置",
                    "ℹ️ 关于我们",
                ]
            )
            settings_tab = tab5
            about_us_tab = tab6
        else:
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "⚙️ 系统设置",
                    "ℹ️ 关于我们",
                ]
            )
            settings_tab = tab4
            about_us_tab = tab5

        with tab1:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">⚡ 极速定价系统</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        快速定价，无需记录产品信息
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fast_pricing_calculator()
        with tab2:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🚚 物流管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理物流规则和模板
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fast_logistics_management()
        with tab3:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🔐 账户管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理账户信息和密码
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_password_change_form()
    # 订阅管理标签页 - 根据开放注册状态决定是否显示
        if should_show_subscription_management():
            with tab4:
                st.markdown(
                    """
                    <div style="text-align: center; margin-bottom: 2rem;">
                        <h1 class="main-title">💎 订阅管理</h1>
                        <p style="color: #718096; font-size: 1.1rem; "
                           "margin: 0;">
                            管理订阅和套餐信息
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                subscription_management_page()

    # 系统设置标签页
        with settings_tab:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">⚙️ 系统设置</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        系统配置和偏好设置
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_system_settings()

    # 添加"关于我们"标签页
    with about_us_tab:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 2rem;">
                <h1 class="main-title">ℹ️ 关于我们</h1>
                <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                    公司信息与业务介绍
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 公司信息卡片
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #667eea 0%,
                 #764ba2 100%);
                 border-radius: 15px; padding: 2rem;
                 margin-bottom: 2rem;
                 color: white;
                 box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);">
                <h2 style="color: white; margin-bottom: 1.5rem;
                    text-align: center;">
                    🏢 公司信息
                </h2>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;
                     margin-bottom: 1rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        📋 公司名称</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        深圳超凡酷玩电子商务有限公司
                    </p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;
                     margin-bottom: 1rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        🌍 主营业务</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        中俄、中美跨境电商（Ozon、亚马逊、eBay、沃尔玛），
                        同时为跨境卖家提供专业的物流定价解决方案。
                    </p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;
                     margin-bottom: 1rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        📍 办公地址</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        广东省深圳市龙岗区平湖街道平湖社区<br>
                        平安大道一号<br>
                        华南城铁东物流区14栋219
                    </p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        📞 联系电话</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        19328702460
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 业务介绍
        st.markdown(
            """
            <div style="background: #f8fafc; border-radius: 15px;
                 padding: 2rem;
                 margin-bottom: 2rem; border-left: 5px solid #667eea;">
                <h2 style="color: #2c3e50;
                    margin-bottom: 1.5rem;">
                    🚀 业务简介
                </h2>
                <p style="color: #4a5568; font-size: 1.1rem;
                    line-height: 1.8; margin: 0;">
                    我们专注于跨境电商领域，主要服务于中俄和中美两个重要市场。
                    通过Ozon、亚马逊、eBay、沃尔玛等
                    国际知名电商平台，
                    为全球消费者提供优质的商品和服务。
                </p>
                <br>
                <p style="color: #4a5568; font-size: 1.1rem;
                    line-height: 1.8; margin: 0;">
                    同时，公司致力于为跨境电商卖家提供
                    专业的物流定价解决方案，
                    帮助客户优化成本结构，提升运营效率，实现业务增长。
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def show_precise_mode_interface(current_user):
    """显示精准模式界面"""
    # 根据用户角色创建标签页
    if current_user["role"] == "admin":
        # 根据开放注册状态决定标签页
        if should_show_subscription_management():
            tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "💎 订阅管理",
                    "⚙️ 系统设置",
                    "👥 用户管理",
                    "ℹ️ 关于我们",
                ]
            )
            user_management_tab = tab6
            about_us_tab = tab7
        else:
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "⚙️ 系统设置",
                    "👥 用户管理",
                    "ℹ️ 关于我们",
                ]
            )
            user_management_tab = tab5
            about_us_tab = tab6
        with tab1:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🎯 精准定价系统</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        完整功能，详细配置
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            precise_products_page()

        with tab2:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🚚 物流管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理物流规则和模板
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            logistics_page()

        with tab3:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🔐 账户管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理账户信息和密码
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_password_change_form()

    # 订阅管理标签页 - 根据开放注册状态决定是否显示
        if should_show_subscription_management():
            with tab4:
                st.markdown(
                    """
                    <div style="text-align: center; margin-bottom: 2rem;">
                        <h1 class="main-title">💎 订阅管理</h1>
                        <p style="color: #718096; font-size: 1.1rem; "
                           "margin: 0;">
                            管理订阅和套餐信息
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                subscription_management_page()

    # 系统设置标签页 - 根据开放注册状态调整索引
        system_tab = tab5 if should_show_subscription_management() else tab4
        with system_tab:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">⚙️ 系统设置</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        系统配置和偏好设置
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_system_settings()

    # 用户管理标签页
        with user_management_tab:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">👥 用户管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理系统用户和权限
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        # 检查是否需要显示订阅管理页面
            if 'selected_user_for_subscription' in st.session_state:
                admin_subscription_management_page()
            else:
                user_management_page()
    else:
        # 根据开放注册状态决定标签页
        if should_show_subscription_management():
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "💎 订阅管理",
                    "⚙️ 系统设置",
                    "ℹ️ 关于我们",
                ]
            )
            settings_tab = tab5
            about_us_tab = tab6
        else:
            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                [
                    "💰 定价计算",
                    "🚚 物流管理",
                    "🔐 账户管理",
                    "⚙️ 系统设置",
                    "ℹ️ 关于我们",
                ]
            )
            settings_tab = tab4
            about_us_tab = tab5
        with tab1:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🎯 精准定价系统</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        完整功能，详细配置
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            precise_products_page()
        with tab2:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🚚 物流管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理物流规则和模板
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            logistics_page()
        with tab3:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">🔐 账户管理</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理账户信息和密码
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_password_change_form()
    # 订阅管理标签页 - 根据开放注册状态决定是否显示
        if should_show_subscription_management():
            with tab4:
                st.markdown(
                    """
                    <div style="text-align: center; margin-bottom: 2rem;">
                        <h1 class="main-title">💎 订阅管理</h1>
                        <p style="color: #718096; font-size: 1.1rem; "
                           "margin: 0;">
                            管理订阅和套餐信息
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                subscription_management_page()

    # 系统设置标签页
        with settings_tab:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <h1 class="main-title">⚙️ 系统设置</h1>
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        系统配置和偏好设置
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            show_system_settings()

    # 添加"关于我们"标签页
    with about_us_tab:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 2rem;">
                <h1 class="main-title">ℹ️ 关于我们</h1>
                <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                    公司信息与业务介绍
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 公司信息卡片
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #667eea 0%,
                 #764ba2 100%);
                 border-radius: 15px; padding: 2rem;
                 margin-bottom: 2rem;
                 color: white;
                 box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);">
                <h2 style="color: white; margin-bottom: 1.5rem;
                    text-align: center;">
                    🏢 公司信息
                </h2>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;
                     margin-bottom: 1rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        📋 公司名称</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        深圳超凡酷玩电子商务有限公司
                    </p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;
                     margin-bottom: 1rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        🌍 主营业务</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        中俄、中美跨境电商（Ozon、亚马逊、eBay、沃尔玛），
                        同时为跨境卖家提供专业的物流定价解决方案。
                    </p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;
                     margin-bottom: 1rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        📍 办公地址</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        广东省深圳市龙岗区平湖街道平湖社区<br>
                        平安大道一号<br>
                        华南城铁东物流区14栋219
                    </p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1);
                     border-radius: 10px;
                     padding: 1.5rem;">
                    <h3 style="color: white; margin-bottom: 0.5rem;">
                        📞 联系电话</h3>
                    <p style="color: white; font-size: 1.1rem;
                        margin: 0;">
                        19328702460
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 业务介绍
        st.markdown(
            """
            <div style="background: #f8fafc; border-radius: 15px;
                 padding: 2rem;
                 margin-bottom: 2rem; border-left: 5px solid #667eea;">
                <h2 style="color: #2c3e50;
                    margin-bottom: 1.5rem;">
                    🚀 业务简介
                </h2>
                <p style="color: #4a5568; font-size: 1.1rem;
                    line-height: 1.8; margin: 0;">
                    我们专注于跨境电商领域，主要服务于中俄和中美两个重要市场。
                    通过Ozon、亚马逊、eBay、沃尔玛等
                    国际知名电商平台，
                    为全球消费者提供优质的商品和服务。
                </p>
                <br>
                <p style="color: #4a5568; font-size: 1.1rem;
                    line-height: 1.8; margin: 0;">
                    同时，公司致力于为跨境电商卖家提供
                    专业的物流定价解决方案，
                    帮助客户优化成本结构，提升运营效率，实现业务增长。
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def fast_pricing_calculator():
    """极速模式定价计算器"""
    # 免费版：显示今日剩余计算次数占位（可即时刷新）
    user_id_for_free = current_user_id()
    free_count_placeholder = st.empty()
    try:
        _status = check_user_subscription_status(user_id_for_free)
        if _status.get('user_type') == 'free':
            _rem = _status.get('remaining_calculations', 0)
            free_count_placeholder.markdown(
                (
                    '<div style="text-align: center; margin-bottom: 1rem;">'
                    '<p style="color: #2c3e50; font-size: 1.1rem; '
                    'margin: 0;">'
                    f'今日剩余计算次数：{_rem}'
                    '</p>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )
    except (KeyError, TypeError, ValueError):
        pass
    # 基本信息输入
    # 第一行：进货单价（元）*、重量（克）*
    col1, col2 = st.columns(2)
    with col1:
        unit_price = st.number_input(
            "进货单价（元）*",
            min_value=0.0,
            value=0.0,
            step=0.01,
        )
    with col2:
        weight_g = st.number_input(
            "重量（克）*",
            min_value=0.0,
            value=0.0,
            step=0.1,
        )

    # 第二行：佣金率（%）、运营利润率（%）
    col1, col2 = st.columns(2)
    with col1:
        commission_rate = (
            st.number_input(
                "佣金率（%）",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
            )
            / 100.0
        )
    with col2:
        target_profit_margin = (
            st.number_input(
                "运营利润率（%）",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
            )
            / 100.0
        )

    # 第三行：活动折扣率(%)、推广费率（%）
    col1, col2 = st.columns(2)
    with col1:
        promotion_rate = (
            st.number_input(
                "活动折扣率（%）",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
            )
            / 100.0
        )
    with col2:
        promotion_rate_extra = (
            st.number_input(
                "推广费率（%）",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
            )
            / 100.0
        )

    # 第四行：打款提现费率(%)、收单手续费率(%)
    col1, col2 = st.columns(2)
    with col1:
        withdrawal_fee_rate = (
            st.number_input(
                "打款提现费率（%）",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
            )
            / 100.0
        )
    with col2:
        payment_processing_fee = (
            st.number_input(
                "收单手续费率（%）",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
            )
            / 100.0
        )

    # 第五行：历史退货率(%)
    col1, col2 = st.columns(2)
    with col1:
        return_rate = (
            st.number_input(
                "历史退货率（%）",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
            )
            / 100.0
        )
    with col2:
        pass

    # 开始计算按钮
    if st.button(
        "🚀 开始计算",
        type="primary",
        use_container_width=True,
        key="fast_calc_button",
    ):
        if unit_price <= 0 or weight_g <= 0:
            st.error("请填写进货单价和重量")
            return
    # 获取物流规则 - 使用精准模式的物流规则表
        logistics_rules = get_precise_logistics_rules()
        if not logistics_rules:
            st.warning("请先在物流管理中添加物流规则")
            return
    # 为 UI 构建字符串化选项（避免 (str, float) 触发的类型告警）
        ui_rule_options = []
        for r in logistics_rules:
            name = str(r.get('name', ''))
            wf = r.get('weight_factor', 0.0)
            wf_str = f"{wf:.3f}"
            display = f"{name} | 因子:{wf_str}"
            ui_rule_options.append(display)

    # 可选：如需让用户筛选某条规则，可启用下列示例
    # idx = st.selectbox(
    #     "筛选物流规则(可选)",
    #     [-1] + list(range(len(ui_rule_options))),
    #     format_func=lambda i: (
    #         "全部" if i == -1 else ui_rule_options[i]
    #     ),
    # )
    # if idx != -1:
    #     logistics_rules = [logistics_rules[idx]]

    # 执行计算并显示结果（保持数据层使用原始 logistics_rules 和 float 类型）
        calculate_fast_pricing_with_params(
            unit_price,
            weight_g,
            commission_rate,
            promotion_rate,
            promotion_rate_extra,
            target_profit_margin,
            withdrawal_fee_rate,
            payment_processing_fee,
            return_rate,
            logistics_rules,
        )

    # 计算完成后，重新查询并即时刷新免费版剩余次数显示
        try:
            _status_after = check_user_subscription_status(
                user_id_for_free
            )
            if _status_after.get('user_type') == 'free':
                _rem_after = _status_after.get('remaining_calculations', 0)
                free_count_placeholder.markdown(
                    (
                        '<div style="text-align: center; '
                        'margin-bottom: 1rem;">'
                        '<p style="color: #2c3e50; font-size: 1.1rem; '
                        'margin: 0;">'
                        f'今日剩余计算次数：{_rem_after}'
                        '</p>'
                        '</div>'
                    ),
                    unsafe_allow_html=True,
                )
        except (KeyError, TypeError, ValueError):
            pass


def fast_logistics_management():
    """极速模式物流管理 - 使用精准模式的物流页面"""
    # 直接调用精准模式的物流页面，实现统一的物流管理
    logistics_page()


def precise_products_page():
    """精准模式产品管理页面"""
    uid = current_user_id()

    with get_db_connection() as (conn, c):
        subscription_status = check_user_subscription_status(uid)

        if st.session_state.get("edit_product_id"):
            edit_product_form()
            return

        if st.session_state.get("batch_edit_products"):
            batch_edit_pricing_form()
            return
    # 检查是否从编辑页面返回，如果是则显示产品列表
        if st.session_state.get("return_to_product_list", False):
            st.session_state.show_product_list = True
            del st.session_state.return_to_product_list

    # 产品数据在下方 user_products 查询中使用，这里移除未使用的缓存查询

    # 检查是否显示产品列表页面
        show_list = st.session_state.get("show_product_list", False)
    # 产品基本信息标题与产品选择控件在同一行
        col1, col2, col3, col4 = st.columns(
            [2, 3, 1, 1],
            vertical_alignment="bottom",
        )
        with col1:
            st.markdown(
                '<h3 class="sub-title">产品基本信息</h3>', unsafe_allow_html=True
            )
        with col2:
            st.write("")  # 空列，保持布局平衡
        with col3:
            # 获取用户产品列表
            user_products = pd.read_sql(
                (
                    "SELECT id, name FROM products "
                    "WHERE user_id = ? ORDER BY name"
                ),
                conn,
                params=(uid,),
            )
            if not show_list:
                if user_products.empty:
                    # 即使没有产品也显示选择框，只有默认选项
                    product_options = ["选择产品"]
                else:
                    names = [
                        str(row['name'])
                        for _, row in user_products.iterrows()
                    ]
                    product_options = ["选择产品"] + names

                selected_product = st.selectbox(
                    "选择产品",
                    product_options,
                    key="product_selector",
                    label_visibility="collapsed",
                )
            # 当选择产品时，获取产品数据并填充表单
                if selected_product != "选择产品" and not user_products.empty:
                    # 检查是否需要更新产品数据（避免重复查询）
                    current_product = st.session_state.get(
                        "selected_product_data", {}
                    ).get("name", "")
                    if current_product != selected_product:
                        # 获取选中产品的完整数据
                        product_data = pd.read_sql(
                            (
                                "SELECT * FROM products "
                                "WHERE name = ? AND user_id = ?"
                            ),
                            conn,
                            params=(selected_product, uid),
                        )
                        if not product_data.empty:
                            # 将产品数据存储到session state中，供表单使用
                            st.session_state.selected_product_data = (
                                product_data.iloc[0].to_dict()
                            )
                else:
                    # 清除之前选择的产品数据
                    if "selected_product_data" in st.session_state:
                        del st.session_state.selected_product_data
        with col4:
            if not show_list:
                if st.button("📋 打开产品列表", key="open_product_list"):
                    st.session_state.show_product_list = True
                    st.rerun()
    # 显示产品列表页面
        if st.session_state.get("show_product_list", False):
            show_product_list_page(uid)
            return

    # 添加/编辑产品
        st.markdown("### ➕ 添加新产品")
        with st.container():
            # 获取选中的产品数据
            selected_data = st.session_state.get("selected_product_data", {})

            # 如果选择了产品，更新表单控件的默认值
            if selected_data:
                # 确保表单控件使用选中的产品数据
                default_name = selected_data.get("name", "")
                default_price = float(selected_data.get("unit_price", 0.0))
            else:
                default_name = ""
                default_price = 0.0

        # 产品名称和进货单价在一行中分两个列显示
            col1, col2 = st.columns(2)
            with col1:
                # 如果session state中没有该key，使用默认值；否则保持用户输入的值
                if "precise_product_name" not in st.session_state:
                    st.session_state.precise_product_name = default_name
                elif (selected_data and
                      st.session_state.precise_product_name != default_name):
                    # 如果选择了新产品，更新表单值
                    st.session_state.precise_product_name = default_name

                name = st.text_input(
                    "产品名称*",
                    key="precise_product_name",
                )
            with col2:
                # 如果session state中没有该key，使用默认值；否则保持用户输入的值
                if "precise_unit_price" not in st.session_state:
                    st.session_state.precise_unit_price = default_price
                elif (selected_data and
                      st.session_state.precise_unit_price != default_price):
                    # 如果选择了新产品，更新表单值
                    st.session_state.precise_unit_price = default_price

                unit_price = st.number_input(
                    "进货单价（元）*",
                    min_value=0.0,
                    step=0.01,
                    key="precise_unit_price",
                )

        # 初始化已删除的字段变量
            russian_name = ""
            category = ""
            model = ""

            st.subheader("物流规格")
        # 使用st.radio显示包装类型选择
            package_type = st.radio(
                "包装类型",
                ["常规包装", "圆柱包装"],
                index=1 if selected_data.get("is_cylinder", False) else 0,
                horizontal=True
            )

        # 根据包装类型显示不同的输入字段
            if package_type == "常规包装":
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    weight_g = st.number_input(
                        "重量（克）*",
                        min_value=0.0,
                        value=float(selected_data.get("weight_g", 0.0)),
                        step=0.1,
                    )
                with col2:
                    length_cm = st.number_input(
                        "长度（厘米）*",
                        min_value=0.0,
                        value=float(selected_data.get("length_cm", 0.0)),
                        step=0.1,
                    )
                with col3:
                    width_cm = st.number_input(
                        "宽度（厘米）*",
                        min_value=0.0,
                        value=float(selected_data.get("width_cm", 0.0)),
                        step=0.1,
                    )
                with col4:
                    height_cm = st.number_input(
                        "高度（厘米）*",
                        min_value=0.0,
                        value=float(selected_data.get("height_cm", 0.0)),
                        step=0.1,
                    )
            # 初始化圆柱包装的变量
                cylinder_diameter = 0
                cylinder_length = 0
                is_cylinder = False
            else:  # 圆柱包装
                col1, col2, col3 = st.columns(3)
                with col1:
                    weight_g = st.number_input(
                        "重量（克）*",
                        min_value=0.0,
                        value=float(selected_data.get("weight_g", 0.0)),
                        step=0.1,
                    )
                with col2:
                    cylinder_diameter = st.number_input(
                        "圆柱直径（厘米）*",
                        min_value=0.0,
                        value=float(
                            selected_data.get("cylinder_diameter", 0.0)
                        ),
                        step=0.1,
                    )
                with col3:
                    cylinder_length = st.number_input(
                        "圆柱长度（厘米）*",
                        min_value=0.0,
                        value=float(
                            selected_data.get("cylinder_length", 0.0)
                        ),
                        step=0.1,
                    )
            # 初始化圆柱包装的变量
                length_cm = 0
                width_cm = 0
                height_cm = 0
                is_cylinder = True

    # 电池和液体标题
        st.subheader("电池和液体")
    # 包含电池和包含易燃液体复选框放在同一行
        col1, col2 = st.columns(2)
        with col1:
            has_battery = st.checkbox(
                "包含电池",
                value=bool(selected_data.get("has_battery", False)),
            )
        with col2:
            has_flammable = st.checkbox(
                "包含易燃液体",
                value=bool(selected_data.get("has_flammable", False)),
            )
    # 初始化电池相关变量
        choice = None
        battery_capacity_mah = 0
        battery_voltage = 0.0
        has_msds = False
        if has_battery:
            # 电池容量填写方式和MSDS证书在同一行
            col1, col2 = st.columns(2, vertical_alignment="bottom")
            with col1:
                choice = st.radio(
                    "电池容量填写方式",
                    ["填写 Wh（瓦时）", "填写 mAh + V"],
                    index=(
                        0
                        if selected_data.get("battery_capacity_wh", 0) > 0
                        else 1
                    ),
                    horizontal=True,
                )
            with col2:
                has_msds = st.checkbox(
                    "有 MSDS 证书",
                    value=bool(selected_data.get("has_msds", False)),
                )
        if choice == "填写 Wh（瓦时）":
            battery_capacity_wh = st.number_input(
                "电池容量（Wh）",
                min_value=0.0,
                value=float(
                    selected_data.get("battery_capacity_wh", 0.0)
                ),
                step=0.1,
            )
            battery_capacity_mah = 0
            battery_voltage = 0.0
        else:
            # 电池容量（mAh）和电池电压（V）在一行中分两个列显示
            col1, col2 = st.columns(2)
            with col1:
                battery_capacity_mah = st.number_input(
                    "电池容量（mAh）",
                    min_value=0,
                    value=int(
                        selected_data.get("battery_capacity_mah", 0)
                    ),
                    step=1,
                )
            with col2:
                battery_voltage = st.number_input(
                    "电池电压（V）",
                    min_value=0.0,
                    value=float(
                        selected_data.get("battery_voltage", 0.0)
                    ),
                    step=0.1,
                )
            battery_capacity_wh = 0.0
    # 注意：电池相关变量已经在上面初始化过了
        st.subheader("定价参数")
    # 第一行：贴标费用（元）、供货方不包邮运（元）
        col1, col2 = st.columns(2)
        with col1:
            labeling_fee = st.number_input(
                "贴标费用（元）",
                min_value=0.0,
                value=float(
                    selected_data.get("labeling_fee", 0.0)
                ),
                step=0.01,
            )
        with col2:
            shipping_fee = st.number_input(
                "供货方不包邮运（元）",
                min_value=0.0,
                value=float(
                    selected_data.get("shipping_fee", 0.0)
                ),
                step=0.01,
            )
    # 第二行：佣金率（%）、运营利润率（%）
        col1, col2 = st.columns(2)
        with col1:
            commission_rate = (
                st.number_input(
                    "佣金率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        selected_data.get("commission_rate", 0.0)
                    )
                    * 100.0,
                    step=0.1,
                    format="%.1f",
                )
                / 100.0
            )
        with col2:
            target_profit_margin = (
                st.number_input(
                    "运营利润率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        selected_data.get("target_profit_margin", 0.0)
                    ) * 100.0,
                    step=0.1,
                    format="%.1f",
                )
                / 100.0
            )
    # 第三行：活动折扣率(%)、推广费率（%）
        col1, col2 = st.columns(2)
        with col1:
            promotion_discount = (
                st.number_input(
                    "活动折扣率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        selected_data.get("promotion_discount", 0.0)
                    )
                    * 100.0,
                    step=0.1,
                    format="%.1f",
                )
                / 100.0
            )
        with col2:
            promotion_cost_rate = (
                st.number_input(
                    "推广费率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        selected_data.get("promotion_cost_rate", 0.0)
                    )
                    * 100.0,
                    step=0.1,
                    format="%.1f",
                )
                / 100.0
            )
    # 第四行：打款提现费率(%)、收单手续费率(%)
        col1, col2 = st.columns(2)
        with col1:
            withdrawal_fee_rate = (
                st.number_input(
                    "打款提现费率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        selected_data.get("withdrawal_fee_rate", 0.0)
                    )
                    * 100.0,
                    step=0.1,
                    format="%.1f",
                )
                / 100.0
            )
        with col2:
            payment_processing_fee = (
                st.number_input(
                    "收单手续费率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        selected_data.get("payment_processing_fee", 0.0)
                    )
                    * 100.0,
                    step=0.1,
                    format="%.1f",
                )
                / 100.0
            )
    # 第五行：历史退货率(%)和保存产品按钮
        col1, col2 = st.columns(2, vertical_alignment="bottom")
        with col1:
            return_rate = (
                st.number_input(
                    "历史退货率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        selected_data.get("return_rate", 0.0)
                    )
                    * 100.0,
                    step=0.1,
                    format="%.1f",
                )
                / 100.0
            )
        with col2:
            if st.button(
                "💾 保存产品",
                use_container_width=True,
                key="save_product_inside",
            ):
                if not subscription_status.get("valid", True):
                    st.error("账号到期，请联系客服续费")
                    return
            # 确保is_cylinder变量被正确定义
                is_cylinder = package_type == "圆柱包装"
            # 检查必填字段
                missing_fields = []
                if not name or name.strip() == "":
                    missing_fields.append("产品名称")
                if weight_g <= 0:
                    missing_fields.append("重量")
                if unit_price <= 0:
                    missing_fields.append("进货单价")
                if not is_cylinder:
                    if length_cm <= 0:
                        missing_fields.append("长度")
                    if width_cm <= 0:
                        missing_fields.append("宽度")
                    if height_cm <= 0:
                        missing_fields.append("高度")
                else:
                    if cylinder_diameter <= 0:
                        missing_fields.append("圆柱直径")
                    if cylinder_length <= 0:
                        missing_fields.append("圆柱长度")

                if missing_fields:
                    st.error(
                        f"请填写以下必填字段：{', '.join(missing_fields)}"
                    )
                else:
                    # 确保name不为None
                    product_name = name.strip() if name else ""
                    if not product_name:
                        st.error("产品名称不能为空")
                        return

                # 保存产品逻辑
                    if save_product_to_db(
                        product_name,
                        russian_name,
                        category,
                        model,
                        unit_price,
                        weight_g,
                        is_cylinder,
                        length_cm,
                        width_cm,
                        height_cm,
                        cylinder_diameter,
                        cylinder_length,
                        has_battery,
                        battery_capacity_wh,
                        battery_capacity_mah,
                        battery_voltage,
                        has_msds,
                        has_flammable,
                        labeling_fee,
                        shipping_fee,
                        promotion_discount,
                        promotion_cost_rate,
                        target_profit_margin,
                        commission_rate,
                        withdrawal_fee_rate,
                        payment_processing_fee,
                        return_rate,
                    ):
                        st.success("产品保存成功！")
                        st.rerun()
    # 开始计算按钮
        st.markdown("---")
        st.markdown("### 🚀 开始计算")
        if st.button(
            "🚀 开始计算",
            type="primary",
            use_container_width=True,
            key="start_calc_inside",
        ):
            # 调用计算函数
            calculate_precise_pricing_from_form(
                name,
                unit_price,
                weight_g,
                "长方体包装" if not is_cylinder else "圆柱包装",
                length_cm,
                width_cm,
                height_cm,
                cylinder_diameter,
                cylinder_length,
                has_battery,
                has_flammable,
                battery_capacity_wh,
                battery_capacity_mah,
                battery_voltage,
                has_msds,
                labeling_fee,
                shipping_fee,
                promotion_discount,
                promotion_cost_rate=promotion_cost_rate,
                target_profit_margin=target_profit_margin,
                commission_rate=commission_rate,
                withdrawal_fee_rate=withdrawal_fee_rate,
                payment_processing_fee=payment_processing_fee,
                return_rate=return_rate,
            )


def precise_pricing_calculator():
    """精准模式定价计算器"""
    st.subheader("💰 精准定价计算")

    # 选择产品
    products = get_user_products(current_user_id())

    # 创建选项列表，如果没有产品就只有默认选项
    if products:
        options = products

        def format_func(x):
            return f"{x['name']} - {x['weight_g']}g"
    else:
        options = [None]

        def format_func(_):
            return "选择产品"

    selected_product = st.selectbox(
        "选择产品",
        options=options,
        format_func=format_func,
        key="precise_product_select"
    )

    if products and selected_product:
        if st.button(
            "🚀 开始计算",
            type="primary",
            use_container_width=True,
            key="precise_calc_from_select",
        ):
            # 调用现有的定价计算逻辑
            calculate_precise_pricing_with_product(selected_product)
    elif not products:
        st.warning("请先添加产品后再进行计算")


# 极速模式相关函数
def get_precise_logistics_rules() -> List[Dict[str, Any]]:
    """获取精准模式的物流规则 - 用于极速模式"""
    try:
        with get_db_connection() as (conn, c):
            # 首先检查表结构，确保字段存在
            c.execute("PRAGMA table_info(logistics)")
            columns = [col[1] for col in c.fetchall()]
        # 根据实际存在的字段构建查询
            if 'weight_factor' in columns:
                # 新版本表结构
                c.execute(
                    """
                    SELECT
                        id, name, type,
                        base_fee, continue_fee, fee_mode,
                        continue_unit, first_fee, first_weight_g,
                        weight_factor, min_weight, max_weight,
                        min_days, max_days, max_sum_of_sides,
                        max_longest_side, volume_mode, longest_side_threshold,
                        volume_coefficient, allow_battery, allow_flammable,
                        delivery_method, priority_group
                    FROM logistics
                    WHERE user_id = ?
                    ORDER BY name ASC
                    """,
                    (current_user_id(),),
                )
            else:
                # 旧版本表结构，使用兼容字段
                c.execute(
                    """
                    SELECT
                        id, name, type,
                        base_fee, continue_fee, fee_mode,
                        continue_unit, first_fee, first_weight_g,
                        min_weight, max_weight, min_days,
                        max_days, max_sum_of_sides, max_longest_side,
                        volume_mode, longest_side_threshold,
                        volume_coefficient, allow_battery, allow_flammable,
                        delivery_method, priority_group
                    FROM logistics
                    WHERE user_id = ?
                    ORDER BY name ASC
                    """,
                    (current_user_id(),),
                )
    # 明确类型为 Dict[str, Any]，避免被推断为 Dict[str, str]
            from typing import List, Dict, Any
            results: List[Dict[str, Any]] = [dict(row) for row in c.fetchall()]
        # 为旧版本表结构添加默认字段
            for rule in results:
                if 'weight_factor' not in rule:
                    rule['weight_factor'] = 0.0  # 默认值
                if 'delivery_method' not in rule:
                    rule['delivery_method'] = 'pickup_point'  # 默认取货点
                if 'priority_group' not in rule:
                    rule['priority_group'] = 'D'  # 默认优先级组
            return results
    except (sqlite3.Error, ValueError, TypeError) as e:
        st.error(f"获取物流规则失败: {e}")
        return []


def get_fast_logistics_rules() -> List[Dict[str, Any]]:
    """获取极速模式的物流规则 - 已废弃，使用get_precise_logistics_rules"""
    return get_precise_logistics_rules()


def add_fast_logistics_rule(
    _name: str,
    _logistic_type: str,
    _base_fee: float,
    _continue_fee: float,
    _delivery_method: str,
    _priority: int,
    _is_active: bool,
):
    """添加极速模式物流规则 - 已废弃，使用精准模式物流规则"""
    st.warning("极速模式物流规则已废弃，请使用精准模式物流规则")


def delete_fast_logistics_rule(_rule_id: int):
    """删除极速模式物流规则 - 已废弃，使用精准模式物流规则"""
    st.warning("极速模式物流规则已废弃，请使用精准模式物流规则")


def calculate_fast_pricing(
    unit_price: float,
    weight_g: float,
    volume_weight_g: float,
    commission_rate: float,
    promotion_rate: float,
    target_profit_margin: float,
    logistics_rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """极速模式定价计算 - 使用精准模式物流规则"""
    results = []

    # 使用实际重量或体积重量的较大值
    effective_weight = (
        max(weight_g, volume_weight_g) if volume_weight_g > 0 else weight_g
    )
    for rule in logistics_rules:
        try:
            # 检查重量限制
            min_weight = rule.get('min_weight', 0)
            max_weight = rule.get('max_weight', 10**9)
            if effective_weight < min_weight or effective_weight > max_weight:
                continue

        # 计算运费 - 使用精准模式的运费计算逻辑
            base_fee = rule.get('base_fee', 0)
            weight_factor = rule.get('weight_factor', 0)

        # 运费计算：基础费用 + 重量因子 * 重量（千克）
            shipping_cost = (
                base_fee + (weight_factor * effective_weight / 1000)
            )

        # 如果运费为0或负数，跳过这个物流规则
            if shipping_cost <= 0:
                continue
        # 计算总成本
            total_cost = unit_price + shipping_cost

        # 计算售价
            denominator = (1 - commission_rate) * (1 - promotion_rate)
            if denominator <= 0:
                continue

            selling_price = (
                total_cost / (1 - target_profit_margin) / denominator
            )

        # 计算利润
            profit = selling_price - total_cost
            profit_margin = (
                (profit / selling_price) * 100 if selling_price > 0 else 0
            )

            results.append({
                'logistic_name': rule['name'],
                'logistic_type': rule.get('type', 'unknown'),
                'shipping_cost': shipping_cost,
                'total_cost': total_cost,
                'selling_price': selling_price,
                'profit': profit,
                'profit_margin': profit_margin,
                'effective_weight': effective_weight
            })
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as e:
            st.error(f"计算 {rule.get('name', '未知物流')} 失败: {e}")

    # 按利润排序
    results.sort(key=lambda x: x['profit'], reverse=True)
    return results


def calculate_fast_pricing_with_params(
    unit_price: float,
    weight_g: float,
    commission_rate: float,
    promotion_rate: float,
    promotion_rate_extra: float,
    target_profit_margin: float,
    withdrawal_fee_rate: float,
    payment_processing_fee: float,
    return_rate: float,
    logistics_rules: List[Dict[str, Any]],
):
    """极速模式定价计算 - 使用参数直接计算，显示精准模式样式的结果"""

    # 检查用户订阅状态和计算权限
    user_id = current_user_id()
    subscription_status = check_user_subscription_status(user_id)
    if not subscription_status.get('valid', False):
        st.error(f"❌ {subscription_status.get('message', '订阅已过期，请续费')}")
        return

    # 检查免费用户的每日计算次数（admin用户不受限制）
    if subscription_status.get('user_type') == 'free':
        remaining_calculations = subscription_status.get(
            'remaining_calculations', 0
        )
        if remaining_calculations <= 0:
            st.error("❌ 今日计算次数已用完，请升级到效率版享受无限次计算")
            st.info("💡 效率版首月仅需¥1，次月¥9.9/月")
            return

    # 减少计算次数
        if not decrement_user_calculations(user_id):
            st.error("❌ 计算次数扣除失败")
            return

    # 创建虚拟产品数据，用于调用精准模式的计算逻辑
    # 极速模式不设置尺寸，让所有物流规则都能通过尺寸检查
    virtual_product = {
        'name': '极速模式产品',
        'category': '快速计算',
        'weight_g': weight_g,
        'unit_price': unit_price,
        'labeling_fee': 0.0,
        'shipping_fee': 0.0,
        'target_profit_margin': target_profit_margin,
        'commission_rate': commission_rate,
        'withdrawal_fee_rate': withdrawal_fee_rate,
        'payment_processing_fee': payment_processing_fee,
        'return_rate': return_rate,
        'promotion_cost_rate': promotion_rate + promotion_rate_extra,
        'length_cm': 0.0,  # 极速模式不设置尺寸
        'width_cm': 0.0,   # 极速模式不设置尺寸
        'height_cm': 0.0,  # 极速模式不设置尺寸
        'is_cylinder': False,
        'cylinder_diameter': 0.0,
        'cylinder_length': 0.0,
        'has_battery': False,
        'battery_capacity_wh': 0.0,
        'battery_capacity_mah': 0,
        'battery_voltage': 0.0,
        'has_msds': False,
        'has_flammable': False
    }

    # 极速模式直接使用输入的重量，不进行体积重量计算
    effective_weight = weight_g

    # 分离陆运和空运物流
    land_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'land'
    ]
    air_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'air'
    ]

    # 转换为DataFrame格式以兼容精准模式的计算逻辑（使用顶层已导入的 pd）
    land_logistics_df = (
        pd.DataFrame(land_logistics) if land_logistics else pd.DataFrame()
    )
    air_logistics_df = (
        pd.DataFrame(air_logistics) if air_logistics else pd.DataFrame()
    )
    # 调用精准模式的计算逻辑
    try:
        from .logic import calculate_pricing
    except ImportError:
        from logic import calculate_pricing

    # 显示进度提示
    with st.spinner("正在计算定价，请稍候..."):
        # 根据delivery_method分离物流
        land_pickup = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        land_home = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        air_pickup = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )
        air_home = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )

    # 计算定价 - 低价优先和速度优先
    # 对于送到取货点，使用pickup_point的物流
        pricing_result_low = calculate_pricing(
            virtual_product, land_pickup, air_pickup, "低价优先"
        )
        pricing_result_fast = calculate_pricing(
            virtual_product, land_pickup, air_pickup, "速度优先"
        )

    # 计算送货上门的定价结果
        pricing_result_low_home = calculate_pricing(
            virtual_product, land_home, air_home, "低价优先"
        )
        pricing_result_fast_home = calculate_pricing(
            virtual_product, land_home, air_home, "速度优先"
        )

    # 显示计算结果
    display_fast_pricing_results_precise_style(
        pricing_result_low, pricing_result_fast,
        pricing_result_low_home, pricing_result_fast_home,
        virtual_product, effective_weight
    )


def display_fast_pricing_results(results: List[Dict[str, Any]]):
    """显示极速模式定价结果"""
    if not results:
        st.warning("没有可用的物流规则或计算失败")
        return

    st.subheader("💰 定价结果")

    # 显示最佳方案
    best_result = results[0]
    st.success(f"""
    **最佳方案：{best_result['logistic_name']}**
    - 售价：¥{best_result['selling_price']:.2f}
    - 运费：¥{best_result['shipping_cost']:.2f}
    - 利润：¥{best_result['profit']:.2f} ({best_result['profit_margin']:.1f}%)
    - 有效重量：{best_result['effective_weight']:.1f}g
    """)

    # 显示所有方案
    st.subheader("📊 所有方案对比")
    for i, result in enumerate(results[:5]):  # 只显示前5个
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.write(
                    f"**{i+1}. {result['logistic_name']}** "
                    f"({result['logistic_type']})"
                )
            with col2:
                st.write(f"¥{result['selling_price']:.2f}")
            with col3:
                st.write(f"¥{result['profit']:.2f}")
            with col4:
                st.write(f"{result['profit_margin']:.1f}%")


def _render_pricing_card(
    grad_start: str,
    grad_end: str,
    border_color: str,
    shadow_rgba: str,
    best_name: str,
    cost_display: str,
    time_display: str,
    price: float,
    expected_profit: float,
    profit_margin: float,
    avg_cost: float,
    cost_saving: float,
    avg_time: float,
    time_saving_display: str,
) -> str:
    """渲染定价卡片"""
    parts: list[str] = [
        "<div style='background: linear-gradient(135deg,",
        f"{grad_start} 0%, ",
        f"{grad_end} 100%); ",
        "border-radius:12px; padding:16px; margin:8px 0; ",
        f"border-left:4px solid {border_color}; ",
        f"box-shadow:0 4px 12px {shadow_rgba};'>",
        "<div style='font-size:1.6em; color:#2c3e50; ",
        "font-weight:800; margin-bottom:8px;'>最佳物流：",
        f"{best_name}</div>",
        "<div>运费：<span style='color:#e74c3c; font-weight:600;'>",
        f"{cost_display}</span></div>",
        "<div>时效：<span style='font-weight:600;'>",
        f"{time_display}</span></div>",
        "<hr style='margin:10px 0; border:none; ",
        "border-top:2px solid rgba(52,73,94,0.2);'>",
        "<div style='font-size:1.6em; font-weight:800;'>建议售价：",
        "<span style='color:#e74c3c; font-weight:800; ",
        "font-size:1.6em;'>",
        f"¥{price:.2f}</span></div>",
        "<div>预期运营利润：<span style='color:#27ae60; font-weight:600;'>",
        f"¥{expected_profit:.2f}</span></div>",
        "<div>运营利润率：<span style='color:#27ae60; font-weight:600;'>",
        f"{profit_margin:.1f}%</span></div>",
        "<hr style='margin:10px 0; border:none; ",
        "border-top:2px solid rgba(52,73,94,0.2);'>",
        "<div>平均运费：<span style='font-weight:600;'>",
        f"¥{avg_cost:.2f}</span></div>",
        "<div>节省运费：<span style='color:#27ae60; font-weight:600;'>",
        f"{cost_saving:+.1f}%</span></div>",
        "<div>平均时效：<span style='font-weight:600;'>",
        f"{avg_time:.1f}天</span></div>",
        "<div>节省时效：<span style='color:#27ae60; font-weight:600;'>",
        f"{time_saving_display}</span></div>",
        "</div>",
    ]
    return "".join(parts)


def display_fast_pricing_results_precise_style(
    pricing_result_low: Dict[str, Any],
    pricing_result_fast: Dict[str, Any],
    pricing_result_low_home: Dict[str, Any],
    pricing_result_fast_home: Dict[str, Any],
    virtual_product: Dict[str, Any],
    effective_weight: float,
):
    """显示极速模式定价结果 - 使用精准模式样式"""

    # 显示结果
    st.markdown(
        (
            '<h3 style="color: #2c3e50; margin-bottom: 20px; '
            "font-size: 1.5em; font-weight: 600; "
            "border-bottom: 2px solid #3498db; "
            'padding-bottom: 8px;">📊 计算结果</h3>'
        ),
        unsafe_allow_html=True,
    )

    # 产品信息
    st.markdown(
        (
            '<h4 style="color: #34495e; margin-bottom: 15px; '
            'font-size: 1.2em; font-weight: 600;">📦 产品信息</h4>'
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        (
            '<div style="background: linear-gradient(135deg, '
            "#f8f9fa 0%, #e9ecef 100%); border-radius: 12px; "
            "padding: 20px; margin: 15px 0; "
            'border-left: 4px solid #28a745;">'
            '<div style="font-size: 1.1em; color: #2c3e50; '
            'margin-bottom: 8px;"><strong>产品名称：</strong>'
            f"{virtual_product['name']}</div>"
            '<div style="font-size: 1.1em; color: #2c3e50; '
            'margin-bottom: 8px;"><strong>产品类别：</strong>'
            f"{virtual_product['category']}</div>"
            '<div style="font-size: 1.1em; color: #2c3e50; '
            'margin-bottom: 8px;"><strong>进货单价：</strong>'
            f"¥{virtual_product['unit_price']:.2f}</div>"
            '<div style="font-size: 1.1em; color: #2c3e50;">'
            f"<strong>有效重量：</strong>{effective_weight:.1f}g</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    # # 显示调试信息
    # with st.expander("🔍 物流筛选详情", expanded=False):
    #     st.markdown("### 物流筛选过程")
    #
    #     # 获取物流规则
    #     logistics_rules = get_precise_logistics_rules()
    #     land_logistics = [
    #         rule for rule in logistics_rules
    #         if rule.get('type') == 'land'
    #     ]
    #     air_logistics = [
    #         rule for rule in logistics_rules
    #         if rule.get('type') == 'air'
    #     ]
    #
    #     st.write(
    #         f"**总物流规则数量：** {len(logistics_rules)}"
    #     )
    #     st.write(
    #         f"**陆运规则数量：** {len(land_logistics)}"
    #     )
    #     st.write(
    #         f"**空运规则数量：** {len(air_logistics)}"
    #     )
    #     # 显示每个物流规则的筛选结果
    #     # 显示每个物流规则的筛选结果
    #     st.markdown("#### 陆运物流筛选结果")
    #     for i, rule in enumerate(land_logistics):
    #         with st.container():
    #             col1, col2 = st.columns([3, 1])
    #             with col1:
    #                 st.write(f"**{i+1}. {rule.get('name', '未知物流')}**")
    #                 st.write(
    #                     f"   重量限制: {rule.get('min_weight', 0)}g - "
    #                     f"{rule.get('max_weight', '无限制')}g"
    #                 )
    #             with col2:
    #             # 检查重量限制
    #                 if effective_weight < rule.get('min_weight', 0):
    #                     st.error("❌ 重量过低")
    #                 elif effective_weight > rule.get('max_weight', 10**9):
    #                     st.error("❌ 重量过高")
    #                 else:
    #                     st.success("✅ 通过")
    #
    #     st.markdown("#### 空运物流筛选结果")
    #     for i, rule in enumerate(air_logistics):
    #         with st.container():
    #             col1, col2 = st.columns([3, 1])
    #             with col1:
    #                 st.write(f"**{i+1}. {rule.get('name', '未知物流')}**")
    #                 st.write(
    #                     f"   重量限制: {rule.get('min_weight', 0)}g - "
    #                     f"{rule.get('max_weight', '无限制')}g"
    #                 )
    #             with col2:
    #             # 检查重量限制
    #                 if effective_weight < rule.get('min_weight', 0):
    #                     st.error("❌ 重量过低")
    #                 elif effective_weight > rule.get('max_weight', 10**9):
    #                     st.error("❌ 重量过高")
    #                 else:
    #                     st.success("✅ 通过")

    # 定价结果 - 低价优先显示
    st.markdown(
        (
            '<h3 style="color: #2c3e50; margin-bottom: 20px; '
            "font-size: 1.5em; font-weight: 600; "
            "border-bottom: 2px solid #3498db; "
            'padding-bottom: 8px;">💰 低价优先</h3>'
        ),
        unsafe_allow_html=True,
    )

    # 添加调试信息
    # with st.expander("🔧 计算调试信息", expanded=True):
    #     st.markdown("### 计算结果调试")
    #     st.write(
    #         f"**pricing_result_low keys:** "
    #         f"{list(pricing_result_low.keys())}"
    #     )
    #     st.write(
    #         f"**land_cost:** {pricing_result_low.get('land_cost')}"
    #     )
    #     st.write(
    #         f"**air_cost:** {pricing_result_low.get('air_cost')}"
    #     )
    #     st.write(
    #         f"**best_land:** {pricing_result_low.get('best_land')}"
    #     )
    #     st.write(
    #         f"**best_air:** {pricing_result_low.get('best_air')}"
    #     )
    #
    #     # 显示预期利润计算调试信息
    #     st.markdown("### 预期利润计算调试")
    #     land_debug = pricing_result_low.get('land_debug', [])
    #     air_debug = pricing_result_low.get('air_debug', [])
    #
    #     if land_debug:
    #         st.markdown("#### 陆运预期利润计算")
    #         for debug_line in land_debug:
    #             st.write(debug_line)
    #
    #     if air_debug:
    #         st.markdown("#### 空运预期利润计算")
    #         for debug_line in air_debug:
    #             st.write(debug_line)
    #
    #     # 检查all_costs_debug中的详细信息
    #     all_costs_debug = pricing_result_low.get('all_costs_debug', [])
    #     st.write(f"**all_costs_debug 数量:** {len(all_costs_debug)}")

    #     # 查找运费为0的物流规则
    #     zero_cost_rules = []
    #     for debug_info in all_costs_debug:
    #         if isinstance(debug_info, dict) and debug_info.get('cost') == 0:
    #             zero_cost_rules.append(debug_info)
    #
    #     st.write(f"**运费为0的物流规则数量:** {len(zero_cost_rules)}")
    #     if zero_cost_rules:
    #         st.write("**运费为0的物流规则:**")
    #         for rule in zero_cost_rules[:5]:  # 只显示前5个
    #             st.write(
    #                 f"  - {rule.get('name', 'Unknown')}: "
    #                 f"cost={rule.get('cost')}"
    #         )
    #
    #     # 查找特定物流规则的运费
    #     target_rules = ['GUOO Economy Extra Small', 'China Post e特快']
    #     for debug_info in all_costs_debug:
    #         if isinstance(debug_info, dict):
    #             logistic = debug_info.get('logistic', {})
    #             name = logistic.get('name', 'Unknown')
    #             if name in target_rules:
    #                 st.write(
    #                     f"**{name}:** cost={debug_info.get('cost')}, "
    #                     f"type={logistic.get('type')}"
    #                 )
    pass

    # =============================
    # 低价优先
    # =============================
    col_land_l, col_air_l = st.columns(2)

    # ------- 陆运（低价优先）：送到取货点 + 送货上门 -------
    with col_land_l:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">🚛 陆运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_low = pricing_result_low.get("best_land")
        if best_land_low:
            # 计算时效（取平均值）
            min_days = best_land_low.get("min_days", 0)
            max_days = best_land_low.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            land_stats = pricing_result_low.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_low.get(
                "land_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#e3f2fd",
                "#bbdefb",
                "#2196f3",
                "rgba(33,150,243,0.15)",
                best_land_low["name"],
                f"¥{pricing_result_low.get('land_cost', 0):.2f}",
                time_display,
                pricing_result_low.get("land_price", 0),
                land_expected_profit,
                pricing_result_low.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_low_home = pricing_result_low_home.get("best_land")
        if best_land_low_home:
            # 使用送货上门的物流数据
            min_days = best_land_low_home.get("min_days", 0)
            max_days = best_land_low_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            land_stats = pricing_result_low_home.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_low_home.get(
                "land_expected_profit", 0
            )

            land_cost_display = (
                f"¥{pricing_result_low_home.get('land_cost', 0):.2f}"
            )

            card_html = _render_pricing_card(
                "#e8f5e8",
                "#c8e6c9",
                "#4caf50",
                "rgba(76,175,80,0.15)",
                best_land_low_home["name"],
                land_cost_display,
                time_display,
                pricing_result_low_home.get("land_price", 0),
                land_expected_profit,
                pricing_result_low_home.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

    # ------- 空运（低价优先）：送到取货点 + 送货上门 -------
    with col_air_l:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">✈️ 空运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_low = pricing_result_low.get("best_air")
        if best_air_low:
            # 计算时效（取平均值）
            min_days = best_air_low.get("min_days", 0)
            max_days = best_air_low.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            air_stats = pricing_result_low.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_low.get(
                "air_expected_profit", 0
            )

            air_cost_display = (
                f"¥{pricing_result_low.get('air_cost', 0):.2f}"
            )

            card_html = _render_pricing_card(
                "#f3e5f5",
                "#e1bee7",
                "#9c27b0",
                "rgba(156,39,176,0.15)",
                best_air_low["name"],
                air_cost_display,
                time_display,
                pricing_result_low.get("air_price", 0),
                air_expected_profit,
                pricing_result_low.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_low_home = pricing_result_low_home.get("best_air")
        if best_air_low_home:
            # 使用送货上门的物流数据
            min_days = best_air_low_home.get("min_days", 0)
            max_days = best_air_low_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            air_stats = pricing_result_low_home.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_low_home.get(
                "air_expected_profit", 0
            )

            air_cost_display_home = (
                f"¥{pricing_result_low_home.get('air_cost', 0):.2f}"
            )

            card_html = _render_pricing_card(
                "#fce4ec",
                "#f8bbd9",
                "#e91e63",
                "rgba(233,30,99,0.15)",
                best_air_low_home["name"],
                air_cost_display_home,
                time_display,
                pricing_result_low_home.get("air_price", 0),
                air_expected_profit,
                pricing_result_low_home.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

    # =============================
    # 速度优先
    # =============================
    st.markdown(
        (
            '<h3 style="color: #2c3e50; margin: 24px 0 12px 0; '
            "font-size: 1.5em; font-weight: 600; "
            "border-bottom: 2px solid #3498db; "
            'padding-bottom: 8px;">⚡ 速度优先</h3>'
        ),
        unsafe_allow_html=True,
    )

    col_land_s, col_air_s = st.columns(2)

    # ------- 陆运（速度优先）：送到取货点 + 送货上门 -------
    with col_land_s:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">🚛 陆运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_fast = pricing_result_fast.get("best_land")
        if best_land_fast:
            # 计算时效（取平均值）
            min_days = best_land_fast.get("min_days", 0)
            max_days = best_land_fast.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            land_stats = pricing_result_fast.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_fast.get(
                "land_expected_profit", 0
            )

            land_cost_display_fast = (
                f"¥{pricing_result_fast.get('land_cost', 0):.2f}"
            )
            card_html = _render_pricing_card(
                "#e3f2fd",
                "#bbdefb",
                "#2196f3",
                "rgba(33,150,243,0.15)",
                best_land_fast["name"],
                land_cost_display_fast,
                time_display,
                pricing_result_fast.get("land_price", 0),
                land_expected_profit,
                pricing_result_fast.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_fast_home = pricing_result_fast_home.get("best_land")
        if best_land_fast_home:
            # 使用送货上门的物流数据
            min_days = best_land_fast_home.get("min_days", 0)
            max_days = best_land_fast_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            land_stats = pricing_result_fast_home.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_fast_home.get(
                "land_expected_profit", 0
            )

            land_cost_display_fast_home = (
                f"¥{pricing_result_fast_home.get('land_cost', 0):.2f}"
            )
            card_html = _render_pricing_card(
                "#e8f5e8",
                "#c8e6c9",
                "#4caf50",
                "rgba(76,175,80,0.15)",
                best_land_fast_home["name"],
                land_cost_display_fast_home,
                time_display,
                pricing_result_fast_home.get("land_price", 0),
                land_expected_profit,
                pricing_result_fast_home.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

    # ------- 空运（速度优先）：送到取货点 + 送货上门 -------
    with col_air_s:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">✈️ 空运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_fast = pricing_result_fast.get("best_air")
        if best_air_fast:
            # 计算时效（取平均值）
            min_days = best_air_fast.get("min_days", 0)
            max_days = best_air_fast.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            air_stats = pricing_result_fast.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_fast.get(
                "air_expected_profit", 0
            )

            air_cost_value_fast = pricing_result_fast.get('air_cost', 0)
            air_cost_display_fast = f"¥{air_cost_value_fast:.2f}"
            card_html = _render_pricing_card(
                "#f3e5f5",
                "#e1bee7",
                "#9c27b0",
                "rgba(156,39,176,0.15)",
                best_air_fast["name"],
                air_cost_display_fast,
                time_display,
                pricing_result_fast.get("air_price", 0),
                air_expected_profit,
                pricing_result_fast.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_fast_home = pricing_result_fast_home.get("best_air")
        if best_air_fast_home:
            # 使用送货上门的物流数据
            min_days = best_air_fast_home.get("min_days", 0)
            max_days = best_air_fast_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            air_stats = pricing_result_fast_home.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_fast_home.get(
                "air_expected_profit", 0
            )

            air_cost_value_fast_home = (
                pricing_result_fast_home.get('air_cost', 0)
            )
            air_cost_display_fast_home = f"¥{air_cost_value_fast_home:.2f}"
            card_html = _render_pricing_card(
                "#fff3e0",
                "#ffcc02",
                "#ff9800",
                "rgba(255,152,0,0.15)",
                best_air_fast_home["name"],
                air_cost_display_fast_home,
                time_display,
                pricing_result_fast_home.get("air_price", 0),
                air_expected_profit,
                pricing_result_fast_home.get("profit_margin", 0),
                avg_cost,
                cost_saving,
                avg_time_stats,
                time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

    # 极速模式提示信息
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #fff3cd 0%,
                    #ffeaa7 100%); border-radius: 12px; padding: 20px;
                    margin: 20px 0; border-left: 4px solid #f39c12;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <div style="display: flex; align-items: center;
                        margin-bottom: 8px;">
                <span style="font-size: 1.2em; margin-right: 8px;">⚡</span>
                <strong style="color: #d68910; font-size: 1.1em;">
                    极速模式说明</strong>
            </div>
            <div style="color: #8d4e00; font-size: 1.0em; line-height: 1.5;">
                极速模式不考虑产品尺寸、计泡、是否含电池、液体。上述内容仅限专业版精准模式
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_user_products(user_id: int) -> List[Dict[str, Any]]:
    """获取用户产品列表"""
    try:
        with get_db_connection() as (conn, c):
            c.execute("""
                SELECT id, name, weight_g, unit_price, category
                FROM products
                WHERE user_id = ?
                ORDER BY name
            """, (user_id,))
            return [dict(row) for row in c.fetchall()]
    except (sqlite3.Error, ValueError, TypeError) as e:
        st.error(f"获取产品列表失败: {e}")
        return []


def calculate_precise_pricing_from_form(
    name,
    unit_price,
    weight_g,
    package_type,
    length_cm,
    width_cm,
    height_cm,
    cylinder_diameter,
    cylinder_length,
    has_battery,
    has_flammable,
    battery_capacity_wh,
    battery_capacity_mah,
    battery_voltage,
    has_msds,
    labeling_fee,
    shipping_fee,
    promotion_discount,
    promotion_cost_rate,
    target_profit_margin,
    commission_rate,
    withdrawal_fee_rate,
    payment_processing_fee,
    return_rate,
):
    """精准模式定价计算（从表单数据）"""

    # 检查用户订阅状态和计算权限
    user_id = current_user_id()
    subscription_status = check_user_subscription_status(user_id)

    if not subscription_status.get('valid', False):
        st.error(f"❌ {subscription_status.get('message', '订阅已过期，请续费')}")
        return

    # 检查用户类型是否可以使用精准模式
    user_type = subscription_status.get('user_type', 'free')

    # admin用户、企业用户和感谢版用户可以使用精准模式
    if user_type in ['admin', 'enterprise', 'gratitude']:
        pass  # 允许使用精准模式
    elif user_type == 'free':
        st.error("❌ 免费版用户无法使用精准模式，请升级到专业版")
        st.info("💡 专业版¥149/月，享受完整功能")
        return
    elif user_type == 'efficiency':
        st.error("❌ 效率版用户无法使用精准模式，请升级到专业版")
        st.info("💡 专业版¥149/月，享受完整功能")
        return
    elif user_type == 'professional':
        pass  # 专业版用户可以使用精准模式
    else:
        st.error("❌ 当前用户类型无法使用精准模式，请升级到专业版")
        st.info("💡 专业版¥149/月，享受完整功能")
        return

    # 检查免费用户的每日计算次数（如果允许使用）
    if user_type == 'free':
        remaining_calculations = subscription_status.get(
            'remaining_calculations', 0
        )
        if remaining_calculations <= 0:
            st.error("❌ 今日计算次数已用完，请升级到效率版享受无限次计算")
            st.info("💡 效率版首月仅需¥1，次月¥9.9/月")
            return

    # 减少计算次数
        if not decrement_user_calculations(user_id):
            st.error("❌ 计算次数扣除失败")
            return

    # 检查必填字段（不检查产品名称，允许空名称进行计算）
    if weight_g <= 0:
        st.error("请填写产品重量")
        return

    if unit_price <= 0:
        st.error("请填写进货单价")
        return

    # 根据包装类型检查尺寸
    is_cylinder = package_type == "圆柱包装"
    if not is_cylinder:
        if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
            st.error("请填写完整的产品尺寸（长度、宽度、高度）")
            return
    else:
        if cylinder_diameter <= 0 or cylinder_length <= 0:
            st.error("请填写完整的圆柱包装尺寸（直径、长度）")
            return

    # 创建产品数据字典
    product_data = {
        'name': name.strip() if name else "未命名产品",
        'category': '精准模式产品',
        'weight_g': weight_g,
        'unit_price': unit_price,
        'labeling_fee': labeling_fee,
        'shipping_fee': shipping_fee,
        'target_profit_margin': target_profit_margin,
        'commission_rate': commission_rate,
        'withdrawal_fee_rate': withdrawal_fee_rate,
        'payment_processing_fee': payment_processing_fee,
        'return_rate': return_rate,
        'promotion_cost_rate': promotion_cost_rate,
        'promotion_discount': promotion_discount,
        'length_cm': length_cm if not is_cylinder else cylinder_diameter,
        'width_cm': width_cm if not is_cylinder else cylinder_diameter,
        'height_cm': height_cm if not is_cylinder else cylinder_length,
        'is_cylinder': is_cylinder,
        'cylinder_diameter': cylinder_diameter if is_cylinder else 0.0,
        'cylinder_length': cylinder_length if is_cylinder else 0.0,
        'has_battery': has_battery,
        'battery_capacity_wh': battery_capacity_wh,
        'battery_capacity_mah': battery_capacity_mah,
        'battery_voltage': battery_voltage,
        'has_msds': has_msds,
        'has_flammable': has_flammable
    }

    # 获取物流规则
    logistics_rules = get_precise_logistics_rules()
    # 为 UI 构建字符串化选项，避免 (str, float) 触发的类型告警
    ui_rule_options = []
    for r in logistics_rules:
        name = str(r.get('name', ''))
        wf = r.get('weight_factor', 0.0)
        wf_str = f"{wf:.3f}"
        display = f"{name} | 因子:{wf_str}"
        ui_rule_options.append(display)
    # 为 UI 构建字符串化选项，避免 (str, float) 触发的类型告警
    ui_rule_options = []
    for r in logistics_rules:
        name = str(r.get('name', ''))
        wf = r.get('weight_factor', 0.0)
        wf_str = f"{wf:.3f}"
        display = f"{name} | 因子:{wf_str}"
        ui_rule_options.append(display)
    # 为 UI 构建字符串化选项，避免 (str, float) 触发的类型告警
    ui_rule_options = []
    for r in logistics_rules:
        name = str(r.get('name', ''))
        wf = r.get('weight_factor', 0.0)
        wf_str = f"{wf:.3f}"
        display = f"{name} | 因子:{wf_str}"
        ui_rule_options.append(display)
    # 为 UI 构建字符串化选项，避免 (str, float) 触发的类型告警
    ui_rule_options = []
    for r in logistics_rules:
        name = str(r.get('name', ''))
        wf = r.get('weight_factor', 0.0)
        wf_str = f"{wf:.3f}"
        display = f"{name} | 因子:{wf_str}"
        ui_rule_options.append(display)
    if not logistics_rules:
        st.warning("请先在物流管理中添加物流规则")
        return

    # 分离陆运和空运物流
    land_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'land'
    ]
    air_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'air'
    ]

    # 转换为DataFrame格式以兼容精准模式的计算逻辑（使用顶层已导入的 pd）
    land_logistics_df = (
        pd.DataFrame(land_logistics)
        if land_logistics
        else pd.DataFrame()
    )
    air_logistics_df = (
        pd.DataFrame(air_logistics)
        if air_logistics
        else pd.DataFrame()
    )

    # 调用精准模式的计算逻辑
    try:
        from .logic import calculate_pricing
    except ImportError:
        from logic import calculate_pricing

    # 显示进度提示
    with st.spinner("正在计算定价，请稍候..."):
        # 根据delivery_method分离物流
        land_pickup = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        land_home = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        air_pickup = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )
        air_home = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )

    # 计算定价 - 低价优先和速度优先
    # 对于送到取货点，使用pickup_point的物流
        pricing_result_low = calculate_pricing(
            product_data, land_pickup, air_pickup, "低价优先"
        )
        pricing_result_fast = calculate_pricing(
            product_data, land_pickup, air_pickup, "速度优先"
        )

    # 计算送货上门的定价结果
        pricing_result_low_home = calculate_pricing(
            product_data, land_home, air_home, "低价优先"
        )
        pricing_result_fast_home = calculate_pricing(
            product_data, land_home, air_home, "速度优先"
        )

    # 显示计算结果 - 使用精准模式的显示样式（在spinner外面）
    display_precise_pricing_results(
        pricing_result_low, pricing_result_fast,
        pricing_result_low_home, pricing_result_fast_home
    )


def calculate_precise_pricing():
    """精准模式定价计算（从产品表单）"""
    # 从session state获取表单数据
    selected_data = st.session_state.get("selected_product_data", {})

    # 如果没有选择产品，提示用户
    if not selected_data:
        st.error("请先选择一个产品或填写完整的产品信息")
        return

    # 获取物流规则
    logistics_rules = get_precise_logistics_rules()
    if not logistics_rules:
        st.warning("请先在物流管理中添加物流规则")
        return

    # 分离陆运和空运物流
    land_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'land'
    ]
    air_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'air'
    ]

    # 转换为DataFrame格式以兼容精准模式的计算逻辑（使用顶层已导入的 pd）
    land_logistics_df = (
        pd.DataFrame(land_logistics)
        if land_logistics
        else pd.DataFrame()
    )
    air_logistics_df = (
        pd.DataFrame(air_logistics)
        if air_logistics
        else pd.DataFrame()
    )

    # 调用精准模式的计算逻辑
    try:
        from .logic import calculate_pricing
    except ImportError:
        from logic import calculate_pricing

    # 显示进度提示
    with st.spinner("正在计算定价，请稍候..."):
        # 根据delivery_method分离物流
        land_pickup = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        land_home = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        air_pickup = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )
        air_home = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )

    # 计算定价 - 低价优先和速度优先
    # 对于送到取货点，使用pickup_point的物流
        pricing_result_low = calculate_pricing(
            selected_data, land_pickup, air_pickup, "低价优先"
        )
        pricing_result_fast = calculate_pricing(
            selected_data, land_pickup, air_pickup, "速度优先"
        )

    # 计算送货上门的定价结果
        pricing_result_low_home = calculate_pricing(
            selected_data, land_home, air_home, "低价优先"
        )
        pricing_result_fast_home = calculate_pricing(
            selected_data, land_home, air_home, "速度优先"
        )

    # 显示计算结果 - 使用精准模式的显示样式（在spinner外面）
    display_precise_pricing_results(
        pricing_result_low, pricing_result_fast,
        pricing_result_low_home, pricing_result_fast_home
    )


def calculate_precise_pricing_with_product(product: Dict[str, Any]):
    """精准模式定价计算（选择产品）"""
    st.info(f"正在计算产品 '{product['name']}' 的定价...")

    # 获取物流规则
    logistics_rules = get_precise_logistics_rules()
    if not logistics_rules:
        st.warning("请先在物流管理中添加物流规则")
        return

    # 分离陆运和空运物流
    land_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'land'
    ]
    air_logistics = [
        rule for rule in logistics_rules if rule.get('type') == 'air'
    ]

    # 转换为DataFrame格式以兼容精准模式的计算逻辑
    land_logistics_df = (
        pd.DataFrame(land_logistics)
        if land_logistics
        else pd.DataFrame()
    )
    air_logistics_df = (
        pd.DataFrame(air_logistics)
        if air_logistics
        else pd.DataFrame()
    )

    # 调用精准模式的计算逻辑
    try:
        from .logic import calculate_pricing
    except ImportError:
        from logic import calculate_pricing

    # 显示进度提示
    with st.spinner("正在计算定价，请稍候..."):
        # 根据delivery_method分离物流
        land_pickup = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        land_home = (
            land_logistics_df[
                land_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not land_logistics_df.empty
            else pd.DataFrame()
        )
        air_pickup = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "pickup_point"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )
        air_home = (
            air_logistics_df[
                air_logistics_df["delivery_method"] == "home_delivery"
            ]
            if not air_logistics_df.empty
            else pd.DataFrame()
        )

    # 计算定价 - 低价优先和速度优先
    # 对于送到取货点，使用pickup_point的物流
    pricing_result_low = calculate_pricing(
        product, land_pickup, air_pickup, "低价优先"
    )
    pricing_result_fast = calculate_pricing(
        product, land_pickup, air_pickup, "速度优先"
    )

    # 计算送货上门的定价结果
    pricing_result_low_home = calculate_pricing(
        product, land_home, air_home, "低价优先"
    )
    pricing_result_fast_home = calculate_pricing(
        product, land_home, air_home, "速度优先"
    )

    # 显示计算结果 - 使用精准模式的显示样式
    display_precise_pricing_results(
        pricing_result_low, pricing_result_fast,
        pricing_result_low_home, pricing_result_fast_home
    )


def init_fast_mode_tables():
    """初始化极速模式数据表 - 已废弃，使用精准模式物流规则"""
    # 极速模式不再需要单独的数据表，使用精准模式的物流规则
    pass


def save_product_to_db(
    name: str,
    russian_name: str,
    category: str,
    model: str,
    unit_price: float,
    weight_g: float,
    is_cylinder: bool,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    cylinder_diameter: float,
    cylinder_length: float,
    has_battery: bool,
    battery_capacity_wh: float,
    battery_capacity_mah: int,
    battery_voltage: float,
    has_msds: bool,
    has_flammable: bool,
    labeling_fee: float,
    shipping_fee: float,
    promotion_discount: float,
    promotion_cost_rate: float,
    target_profit_margin: float,
    commission_rate: float,
    withdrawal_fee_rate: float,
    payment_processing_fee: float,
    return_rate: float,
):
    """保存产品到数据库"""
    try:
        with get_db_connection() as (conn, c):
            c.execute(
                """
                INSERT INTO products (
                    user_id, name, russian_name, category, model, unit_price,
                    weight_g, length_cm, width_cm, height_cm, is_cylinder,
                    cylinder_diameter, cylinder_length, has_battery,
                    battery_capacity_wh, battery_capacity_mah, battery_voltage,
                    has_msds, has_flammable, labeling_fee, shipping_fee,
                    promotion_discount, promotion_cost_rate,
                    target_profit_margin,
                    commission_rate, withdrawal_fee_rate,
                    payment_processing_fee,
                    return_rate
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
        """,
                (
                    current_user_id(),
                    name,
                    russian_name,
                    category,
                    model,
                    unit_price,
                    weight_g,
                    length_cm,
                    width_cm,
                    height_cm,
                    1 if is_cylinder else 0,
                    cylinder_diameter,
                    cylinder_length,
                    1 if has_battery else 0,
                    battery_capacity_wh,
                    battery_capacity_mah,
                    battery_voltage,
                    1 if has_msds else 0,
                    1 if has_flammable else 0,
                    labeling_fee,
                    shipping_fee,
                    promotion_discount,
                    promotion_cost_rate,
                    target_profit_margin,
                    commission_rate,
                    withdrawal_fee_rate,
                    payment_processing_fee,
                    return_rate,
                ),
            )
            conn.commit()
            return True  # 成功时返回True
    except (sqlite3.Error, ValueError, TypeError) as e:
        st.error(f"保存产品失败: {e}")
        return False  # 失败时返回False


def user_management_page_fast_mode():
    """极速模式用户管理页面 - 使用不同的表单key避免冲突"""
    # 检查管理员权限
    try:
        require_admin()
    except PermissionError:
        st.error("❌ 访问被拒绝：您没有管理员权限")
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

    # 添加用户 - 使用不同的表单key
        with st.expander("添加新用户"):
            with st.form("add_user_form_fast_mode"):
                username = st.text_input("用户名*", key="fast_username")
                password = st.text_input(
                    "密码*", type="password", key="fast_password",
                    help=get_password_requirements_text(),
                )
                role = st.selectbox("角色*", ["admin", "user"], key="fast_role")
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
                    format_func=lambda x: {
                        "test": "测试用户",
                        "gratitude": "感谢版用户",
                        "free": "免费版用户",
                        "efficiency": "效率版用户",
                        "professional": "专业版用户",
                        "enterprise": "企业版用户"
                    }.get(str(x), str(x)),
                    key="fast_user_type"
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
                        # 新建测试版：默认7天有效期
                            try:
                                from datetime import datetime, timedelta
                                expiry_date = (
                                    datetime.now() + timedelta(days=7)
                                ).isoformat()
                            except (ValueError, TypeError):
                                pass
                        elif user_type == "gratitude":
                            remaining_calculations = -1
                        elif user_type == "free":
                            remaining_calculations = 10
                        elif user_type == "efficiency":
                            remaining_calculations = -1
                        # 新建效率版：默认30天有效期
                            try:
                                from datetime import datetime, timedelta
                                expiry_date = (
                                    datetime.now() + timedelta(days=30)
                                ).isoformat()
                            except (ValueError, TypeError):
                                pass
                        elif user_type == "professional":
                            remaining_calculations = -1
                        # 新建专业版：默认30天有效期
                            try:
                                from datetime import datetime, timedelta
                                expiry_date = (
                                    datetime.now() + timedelta(days=30)
                                ).isoformat()
                            except (ValueError, TypeError):
                                pass
                        elif user_type == "enterprise":
                            remaining_calculations = -1
                        # 新建企业版：默认30天有效期
                            try:
                                from datetime import datetime, timedelta
                                expiry_date = (
                                    datetime.now() + timedelta(days=30)
                                ).isoformat()
                            except (ValueError, TypeError):
                                pass
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

    # 显示用户列表
        st.subheader("📋 用户列表")
        users = pd.read_sql(
            (
                "SELECT id, username, role, user_type, created_at "
                "FROM users ORDER BY created_at DESC"
            ),
            conn,
        )

        if len(users) > 0:
            # 格式化用户类型显示
            users['user_type_display'] = users['user_type'].apply(
                _format_user_type
            )
            users['role_display'] = users['role'].apply(
                lambda x: "管理员" if x == "admin" else "普通用户"
            )

        # 将DataFrame转换为字典列表以避免pandas Series类型问题
            users_list = users.to_dict('records')

        # 显示用户信息
            for user in users_list:
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                    with col1:
                        st.write(f"**{user['username']}**")
                    with col2:
                        st.write(user['role_display'])
                    with col3:
                        st.write(user['user_type_display'])
                    with col4:
                        created_at = user['created_at']
                        try:
                            if (pd.notna(created_at) and
                                    str(created_at).strip()):
                                st.write(str(created_at)[:10])
                            else:
                                st.write("未知")
                        except (ValueError, TypeError):
                            st.write("未知")
                    with col5:
                        if st.button("删除", key=f"del_user_{user['id']}_fast"):
                            try:
                                c.execute(
                                    "DELETE FROM users WHERE id = ?",
                                    (user['id'],),
                                )
                                conn.commit()
                                st.success("用户删除成功！")
                                st.rerun()
                            except sqlite3.Error as e:
                                st.error(f"删除失败: {e}")
        else:
            st.info("暂无用户")


def show_password_change_form():
    """显示密码修改表单"""
    st.subheader("🔒 修改密码")

    with st.form("password_change_form"):
        current_password = st.text_input("当前密码", type="password")
        new_password = st.text_input(
            "新密码", type="password", help=get_password_requirements_text()
        )
        confirm_password = st.text_input("确认新密码", type="password")

        submitted = st.form_submit_button("修改密码")

        if submitted:
            if (not current_password or not new_password or
                    not confirm_password):
                st.error("请填写所有字段")
                return

            if new_password != confirm_password:
                st.error("新密码和确认密码不匹配")
                return

        # 验证密码强度
            password_validation = validate_password_strength(new_password)
            if not password_validation['valid']:
                st.error("密码强度不符合要求：")
                for error in password_validation['errors']:
                    st.error(f"• {error}")
                return
        # 验证当前密码并更新
            user_id = st.session_state.user['id']
            if update_user_password(user_id, current_password, new_password):
                st.success("密码修改成功！")
            else:
                st.error("当前密码错误")


def _debug_filter_reason(logistic: dict, product: dict) -> Optional[str]:
    """检查物流被淘汰的原因"""
    """
    返回物流被淘汰的详细原因；若完全可用则返回 None。
    与 calculate_logistic_cost() 的判断逻辑保持 100% 一致。
    """

    # ---------- 1. 重量 ----------
    # 计算体积重量
    length_cm = product.get("length_cm", 0)
    width_cm = product.get("width_cm", 0)
    height_cm = product.get("height_cm", 0)
    volume_mode = logistic.get("volume_mode", "none")
    volume_coefficient = logistic.get("volume_coefficient", 5000)

    if volume_mode == "max_actual_vs_volume":
        volume_weight = (
            length_cm * width_cm * height_cm
        ) / volume_coefficient
        actual_weight = product.get("weight_g", 0) / 1000  # 转换为千克
        calculated_weight = (
            max(actual_weight, volume_weight) * 1000
        )  # 转换回克
    elif volume_mode == "longest_side":
        longest_side_threshold = logistic.get("longest_side_threshold", 0)
        longest_side = max(length_cm, width_cm, height_cm)
        if longest_side > longest_side_threshold:
            volume_weight = (
                length_cm * width_cm * height_cm
            ) / volume_coefficient
            actual_weight = product.get("weight_g", 0) / 1000  # 转换为千克
            calculated_weight = (
                max(actual_weight, volume_weight) * 1000
            )  # 转换回克
        else:
            calculated_weight = product.get("weight_g", 0)
    else:
        calculated_weight = product.get("weight_g", 0)

    w = calculated_weight
    min_w = logistic.get("min_weight", 0)
    max_w = logistic.get("max_weight", 10**9)
    if w < min_w:
        return f"重量 {w} g 低于下限 {min_w} g"
    if w > max_w:
        return f"重量 {w} g 高于上限 {max_w} g"

    # ---------- 2. 边长 ----------
    # 获取产品包装形状
    is_cylinder = product.get("is_cylinder", False)

    if is_cylinder:
        # 圆柱形包装产品
        cylinder_diameter = product.get("cylinder_diameter", 0)
        cylinder_length = product.get("cylinder_length", 0)

    # 首先检查物流是否有圆柱形包装限制
        has_cylinder_limits = (
            logistic.get("max_cylinder_sum", 0) > 0
            or logistic.get("min_cylinder_sum", 0) > 0
            or logistic.get("max_cylinder_length", 0) > 0
            or logistic.get("min_cylinder_length", 0) > 0
        )

        if has_cylinder_limits:
            # 使用圆柱形包装限制进行匹配
            cylinder_sum = 2 * cylinder_diameter + cylinder_length
            max_cylinder_sum = logistic.get("max_cylinder_sum", 0)
            if 0 < max_cylinder_sum < cylinder_sum:
                return (
                    f"2倍直径与长度之和 {cylinder_sum} cm 超过限制 "
                    f"{max_cylinder_sum} cm"
                )
            min_cylinder_sum = logistic.get("min_cylinder_sum", 0)
            if min_cylinder_sum > 0 and cylinder_sum < min_cylinder_sum:
                return (
                    f"2倍直径与长度之和 {cylinder_sum} cm 低于下限 "
                    f"{min_cylinder_sum} cm"
                )
            max_cylinder_length = logistic.get("max_cylinder_length", 0)
            if 0 < max_cylinder_length < cylinder_length:
                return (
                    f"圆柱长度 {cylinder_length} cm 超过限制 "
                    f"{max_cylinder_length} cm"
                )
            min_cyl = logistic.get("min_cylinder_length", 0)
            if min_cyl > 0 and cylinder_length < min_cyl:
                return (
                    f"圆柱长度 {cylinder_length} cm 低于下限 {min_cyl} cm"
                )
            # 圆柱形包装检查通过后，仍然需要定义sides用于后续标准包装限制检查
            sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
        else:
            # 物流没有圆柱形包装限制，使用标准包装限制
            # 将圆柱形包装转换为标准包装进行匹配
            # 圆柱直径相当于长和宽，圆柱长度相当于高
            sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
    else:
        # 标准包装产品
        sides = [
            product.get("length_cm", 0),
            product.get("width_cm", 0),
            product.get("height_cm", 0),
        ]

    # 标准包装限制检查
    max_sum = logistic.get("max_sum_of_sides", 10**9)
    if sum(sides) > max_sum > 0:
        return (
            f"三边之和 {sum(sides)} cm 超过限制 {max_sum} cm"
        )
    max_long = logistic.get("max_longest_side", 10**9)
    if max(sides) > max_long:
        return (
            f"最长边 {max(sides)} cm 超过限制 {max_long} cm"
        )
    # 第二边长上限检查
    max_second_side = logistic.get("max_second_side", 0)
    if max_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        if 0 < max_second_side < second_side:
            return (
                f"第二边长 {second_side} cm 超过限制 {max_second_side} cm"
            )
    # 第二长边下限检查
    min_second_side = logistic.get("min_second_side", 0)
    if min_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        if second_side < min_second_side:
            return (
                f"第二边长 {second_side} cm 低于下限 {min_second_side} cm"
            )
    # 最长边下限检查
    min_len = logistic.get("min_length", 0)
    if min_len > 0:
        longest_side = max(sides)
        if longest_side < min_len:
            return (
                    f"最长边 {longest_side} cm 低于下限 {min_len} cm"
                )

    # 3. 特殊物品
    if product.get("has_battery") and not logistic.get("allow_battery"):
        return "产品含电池但物流不允许电池"
    if product.get("has_flammable") and not logistic.get("allow_flammable"):
        return "产品含易燃液体但物流不允许易燃液体"

    # 4. 电池容量 & MSDS
    if product.get("has_battery"):
        limit_wh = logistic.get("battery_capacity_limit_wh", 0)
        if limit_wh > 0:
            wh = product.get("battery_capacity_wh", 0)
            if wh == 0:
                mah = product.get("battery_capacity_mah", 0)
                v = product.get("battery_voltage", 0)
            # 如果mAh和V都为0，跳过电池容量限制判断
                if mah <= 0 and v <= 0:
                    pass  # 跳过电池容量限制判断
                else:
                    wh = mah * v / 1000.0
                    if 0 < limit_wh < wh:
                        return (
                            f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
                        )
            else:
                # 如果填写了Wh但值为0，跳过电池容量限制判断
                if wh <= 0:
                    pass  # 跳过电池容量限制判断
                else:
                    if 0 < limit_wh < wh:
                        return (
                            f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
                        )
    if logistic.get("require_msds") and not product.get("has_msds"):
        return "物流要求 MSDS 但产品未提供"

    # 5. 限价（人民币→卢布）
    try:
        # 用户计算时只使用兜底汇率，不调用API
        try:
            from exchange_service import get_fallback_exchange_rate
        except ImportError:
            def get_fallback_exchange_rate():
                return 0.0904  # 默认兜底汇率
        rate = get_fallback_exchange_rate()  # 1 CNY = x RUB
        unit_price = float(product.get("unit_price", 0))
        labeling_fee = float(product.get("labeling_fee", 0))
        shipping_fee = float(product.get("shipping_fee", 0))

    # 先计算运费（复用与正式计算完全一致的公式）
    # 使用上面已经计算好的重量 w
        fee_mode = logistic.get("fee_mode", "base_plus_continue")
        continue_unit = int(logistic.get("continue_unit", 100))

        if fee_mode == "base_plus_continue":
            units = __import__("math").ceil(w / continue_unit)
            cost = logistic.get("base_fee", 0) + \
                logistic.get("continue_fee", 0) * units
        else:  # first_plus_continue
            first_w = logistic.get("first_weight_g", 0)
            first_cost = logistic.get("first_fee", 0)
            cost = (
                first_cost
                if w <= first_w
                else first_cost
                + __import__("math").ceil((w - first_w) / continue_unit)
                * logistic.get("continue_fee", 0)
            )

    # 估算人民币总成本
        total_cny = unit_price + labeling_fee + shipping_fee + 15 * rate + cost
    # 估算人民币售价
        denominator = (
            (1 - product.get("promotion_cost_rate", 0))
            * (1 - product.get("commission_rate", 0))
            * (1 - product.get("withdrawal_fee_rate", 0))
            * (1 - product.get("payment_processing_fee", 0))
        )
        if denominator == 0:
            return "费率参数异常导致除以 0"
        rough_cny = (
            total_cny
            / (1 - product.get("target_profit_margin", 0))
        ) / denominator
        rough_rub = rough_cny / rate

    # 获取价格限制和货币类型
        limit_value = logistic.get("price_limit_rub", 0)
        min_value = logistic.get("price_min_rub", 0)
        limit_currency = logistic.get("price_limit_currency", "RUB")
        min_currency = logistic.get("price_min_currency", "RUB")

    # 根据货币类型进行价格比较
    # 用户计算时只使用兜底汇率，不调用API
        try:
            from exchange_service import get_fallback_usd_rate
        except ImportError:
            def get_fallback_usd_rate():
                return 7.2  # 默认美元汇率
        usd_rate = get_fallback_usd_rate()

        if limit_currency == "USD" and limit_value > 0:
            # 美元限价：将估算售价转换为美元进行比较
            rough_usd = rough_cny / usd_rate
            if rough_usd > limit_value:
                return f"估算售价 {rough_usd:.2f} USD 超价格上限 {limit_value} USD"
        elif limit_value > 0:
            # 卢布限价：直接比较卢布价格
            if rough_rub > limit_value:
                return f"估算售价 {rough_rub:.2f} RUB 超价格上限 {limit_value} RUB"

        if min_currency == "USD" and min_value > 0:
            # 美元下限：将估算售价转换为美元进行比较
            rough_usd = rough_cny / usd_rate
            if rough_usd < min_value:
                return f"估算售价 {rough_usd:.2f} USD 低于价格下限 {min_value} USD"
        elif min_value > 0:
            # 卢布下限：直接比较卢布价格
            if rough_rub < min_value:
                return f"估算售价 {rough_rub:.2f} RUB 低于价格下限 {min_value} RUB"
    except (KeyError, TypeError, ZeroDivisionError) as price_exc:
        return f"限价判断异常: {price_exc}"

    # 6. 全部通过
    return None


def show_product_list_page(uid):
    """显示产品列表页面"""
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 class="main-title">📋 产品列表管理</h1>
            <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                管理您的所有产品信息
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with get_db_connection() as (conn, c):
        # 获取用户的所有产品
        products = pd.read_sql(
            """
            SELECT id, name, unit_price, weight_g,
                   CASE
                       WHEN is_cylinder = 1 THEN '圆柱包装'
                       ELSE '常规包装'
                   END as package_type,
                   has_battery, has_flammable, has_msds
            FROM products
            WHERE user_id = ?
            ORDER BY name
            """,
            conn,
            params=(uid,)
        )

        if products.empty:
            st.info("您还没有添加任何产品。")
            if st.button("➕ 添加第一个产品", type="primary"):
                st.session_state.show_product_list = False
                st.rerun()
            return

    # 显示产品列表
        st.markdown("### 产品列表")

        for _, product in products.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    st.markdown(f"**{product['name']}**")
                    st.markdown(
                        f"单价: ¥{product['unit_price']:.2f} | 重量: "
                        f"{product['weight_g']}g | 包装: "
                        f"{product['package_type']}"
                    )

                # 显示特殊属性
                    special_attrs = []
                    if bool(product['has_battery']):
                        special_attrs.append("🔋 含电池")
                    if bool(product['has_flammable']):
                        special_attrs.append("🔥 含易燃液体")
                    if bool(product['has_msds']):
                        special_attrs.append("📄 有MSDS")

                    if special_attrs:
                        st.markdown(
                            f"<small>{' | '.join(special_attrs)}</small>",
                            unsafe_allow_html=True,
                        )

                with col2:
                    st.write("")  # 空列

                with col3:
                    if st.button("✏️ 编辑", key=f"edit_{product['id']}"):
                        st.session_state.edit_product_id = product['id']
                        st.session_state.show_product_list = False
                        st.rerun()

                with col4:
                    if st.button("🗑️ 删除", key=f"delete_{product['id']}"):
                        # 删除产品
                        c.execute(
                            "DELETE FROM products WHERE id = ? AND "
                            "user_id = ?",
                            (product['id'], uid),
                        )
                        conn.commit()
                        st.success(f"产品 '{product['name']}' 已删除")
                        st.rerun()

                st.divider()

    # 底部操作按钮
        if st.button("❌ 关闭列表", use_container_width=True):
            st.session_state.show_product_list = False
            st.rerun()


def show_product_details(product_id, uid):
    """显示产品详细信息"""
    with get_db_connection() as (conn, c):
        product = pd.read_sql(
            """
            SELECT * FROM products WHERE id = ? AND user_id = ?
            """,
            conn,
            params=(product_id, uid)
        )

        if product.empty:
            st.error("产品不存在")
            return

        product = product.iloc[0]

        st.markdown("### 产品详细信息")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**产品名称:** {product['name']}")
            st.markdown(f"**进货单价:** ¥{product['unit_price']:.2f}")
            st.markdown(f"**重量:** {product['weight_g']}g")

            if product['is_cylinder']:
                st.markdown("**包装类型:** 圆柱包装")
                st.markdown(f"**直径:** {product['cylinder_diameter']}cm")
                st.markdown(f"**长度:** {product['cylinder_length']}cm")
            else:
                st.markdown("**包装类型:** 常规包装")
                st.markdown(
                    f"**尺寸:** {product['length_cm']}×"
                    f"{product['width_cm']}×"
                    f"{product['height_cm']}cm"
                )

        with col2:
            st.markdown(f"**包含电池:** {'是' if product['has_battery'] else '否'}")
            if product['has_battery']:
                st.markdown(f"**电池容量(Wh):** {product['battery_capacity_wh']}")
                st.markdown(
                    f"**电池容量(mAh):** {product['battery_capacity_mah']}"
                )
                st.markdown(f"**电池电压(V):** {product['battery_voltage']}")

            st.markdown(
                f"**包含易燃液体:** "
                f"{'是' if product['has_flammable'] else '否'}"
            )
            st.markdown(f"**有MSDS证书:** {'是' if product['has_msds'] else '否'}")

        if st.button("返回产品列表"):
            st.rerun()


def display_precise_pricing_results(
        pricing_result_low,
        pricing_result_fast,
        pricing_result_low_home,
        pricing_result_fast_home,
):
    """显示精准模式定价结果 - 完整版"""

    # 显示结果标题
    st.markdown(
        (
            '<h3 style="color: #2c3e50; margin-bottom: 20px; '
            "font-size: 1.5em; font-weight: 600; "
            "border-bottom: 2px solid #3498db; "
            'padding-bottom: 8px;">📊 计算结果</h3>'
        ),
        unsafe_allow_html=True,
    )

    # 产品信息（从第一个计算结果中获取产品信息）
    product_info = pricing_result_low.get('product_info', {})
    if product_info:
        st.markdown(
            (
                '<h4 style="color: #34495e; margin-bottom: 15px; '
                'font-size: 1.2em; font-weight: 600;">📦 产品信息</h4>'
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                '<div style="background: linear-gradient(135deg, '
                "#f8f9fa 0%, #e9ecef 100%); border-radius: 12px; "
                "padding: 20px; margin: 15px 0; "
                'border-left: 4px solid #28a745;">'
                '<div style="font-size: 1.1em; color: #2c3e50; '
                'margin-bottom: 8px;"><strong>产品名称：</strong>'
                f"{product_info.get('name', '未知产品')}</div>"
                '<div style="font-size: 1.1em; color: #2c3e50; '
                'margin-bottom: 8px;"><strong>产品类别：</strong>'
                f"{product_info.get('category', '未知类别')}</div>"
                '<div style="font-size: 1.1em; color: #2c3e50; '
                'margin-bottom: 8px;"><strong>进货单价：</strong>'
                f"¥{product_info.get('unit_price', 0):.2f}</div>"
                '<div style="font-size: 1.1em; color: #2c3e50;">'
                f"<strong>有效重量：</strong>"
                f"{product_info.get('weight_g', 0):.1f}g</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    # # 显示物流筛选详情
    # with st.expander("🔍 物流筛选详情", expanded=False):
    #     st.markdown("### 物流筛选过程")
    #
    #     # 获取物流规则
    #     logistics_rules = get_precise_logistics_rules()
    #     land_logistics = [
    #         rule for rule in logistics_rules if rule.get('type') == 'land'
    #     ]
    #     air_logistics = [
    #         rule for rule in logistics_rules if rule.get('type') == 'air'
    #     ]
    #
    #     st.write(
    #         f"**总物流规则数量：** {len(logistics_rules)}"
    #     )
    #     st.write(
    #         f"**陆运规则数量：** {len(land_logistics)}"
    #     )
    #     st.write(
    #         f"**空运规则数量：** {len(air_logistics)}"
    #     )
    #     # 显示每个物流规则的筛选结果
    #     st.markdown("#### 陆运物流筛选结果")
    #     for i, rule in enumerate(land_logistics):
    #         with st.container():
    #             col1, col2 = st.columns([3, 1])
    #             with col1:
    #                 st.write(f"**{i+1}. {rule.get('name', '未知物流')}**")
    #                 st.write(
    #                     f"   重量限制: {rule.get('min_weight', 0)}g - "
    #                     f"{rule.get('max_weight', '无限制')}g"
    #                 )
    #             with col2:
    #             # 检查重量限制
    #                 weight_g = (
    #                     product_info.get('weight_g', 0)
    #                     if product_info else 0
    #                 )
    #                 if weight_g < rule.get('min_weight', 0):
    #                     st.error("❌ 重量过低")
    #                 elif weight_g > rule.get('max_weight', 10**9):
    #                     st.error("❌ 重量过高")
    #                 else:
    #                     st.success("✅ 通过")
    #
    #     st.markdown("#### 空运物流筛选结果")
    #     for i, rule in enumerate(air_logistics):
    #         with st.container():
    #             col1, col2 = st.columns([3, 1])
    #             with col1:
    #                 st.write(f"**{i+1}. {rule.get('name', '未知物流')}**")
    #                 st.write(
    #                     f"   重量限制: {rule.get('min_weight', 0)}g - "
    #                     f"{rule.get('max_weight', '无限制')}g"
    #                 )
    #             with col2:
    #             # 检查重量限制
    #                 weight_g = (
    #                     product_info.get('weight_g', 0)
    #                     if product_info else 0
    #                 )
    #                 if weight_g < rule.get('min_weight', 0):
    #                     st.error("❌ 重量过低")
    #                 elif weight_g > rule.get('max_weight', 10**9):
    #                     st.error("❌ 重量过高")
    #                 else:
    #                     st.success("✅ 通过")

    # =============================
    # 低价优先
    # =============================
    st.markdown(
        (
            '<h3 style="color: #2c3e50; margin-bottom: 20px; '
            "font-size: 1.5em; font-weight: 600; "
            "border-bottom: 2px solid #3498db; "
            'padding-bottom: 8px;">💰 低价优先</h3>'
        ),
        unsafe_allow_html=True,
    )

    # 添加调试信息
    # with st.expander("🔧 计算调试信息", expanded=True):
    #     st.markdown("### 计算结果调试")
    #     st.write(
    #         f"**pricing_result_low keys:** "
    #         f"{list(pricing_result_low.keys())}"
    #     )
    #     st.write(f"**land_cost:** {pricing_result_low.get('land_cost')}")
    #     st.write(f"**air_cost:** {pricing_result_low.get('air_cost')}")
    #     st.write(f"**best_land:** {pricing_result_low.get('best_land')}")
    #     st.write(f"**best_air:** {pricing_result_low.get('best_air')}")
    #
    #     # 显示预期利润计算调试信息
    #     st.markdown("### 预期利润计算调试")
    #     land_debug = pricing_result_low.get('land_debug', [])
    #     air_debug = pricing_result_low.get('air_debug', [])
    #
    #     if land_debug:
    #         st.markdown("#### 陆运预期利润计算")
    #         for debug_line in land_debug:
    #             st.write(debug_line)
    #
    #     if air_debug:
    #         st.markdown("#### 空运预期利润计算")
    #         for debug_line in air_debug:
    #             st.write(debug_line)
    #
    #     # 检查all_costs_debug中的详细信息
    #     all_costs_debug = pricing_result_low.get('all_costs_debug', [])
    #     st.write(f"**all_costs_debug 数量:** {len(all_costs_debug)}")

    #     # 显示物流淘汰过程
    #     st.markdown("### 物流淘汰过程")
    #     if all_costs_debug:
    #     # 统计淘汰原因
    #         elimination_reasons = {}
    #         total_logistics = len(all_costs_debug)
    #         eliminated_count = 0
    #
    #         for debug_info in all_costs_debug:
    #             if isinstance(debug_info, dict):
    #                 logistic_name = debug_info.get("logistic", {}).get(
    #                     "name", "未知物流"
    #                 )
    #             cost = debug_info.get("cost")
    #             debug_list = debug_info.get("debug", [])
    #
    #             if cost is None:
    #                 eliminated_count += 1
    #             # 找到淘汰原因
    #                 reason = None
    #                 for debug_line in debug_list:
    #                     if "返回 None" in debug_line:
    #                         reason = debug_line.replace(
    #                             "返回 None", ""
    #                         ).strip()
    #                         break
    #                     elif "跳过" in debug_line:
    #                         reason = debug_line.strip()
    #                         break
    #
    #                 if reason:
    #                     if reason not in elimination_reasons:
    #                         elimination_reasons[reason] = []
    #                     elimination_reasons[reason].append(
    #                         logistic_name
    #                     )
#                 else:
    #                 # 如果没有找到明确的原因，使用最后一个调试信息
    #                     if debug_list:
    #                         reason = debug_list[-1].strip()
    #                         if reason not in elimination_reasons:
    #                             elimination_reasons[reason] = []
    #                         elimination_reasons[reason].append(
    #                             logistic_name
    #                         )
#
    #     st.write(f"**总计物流规则：{total_logistics} 个**")
    #     st.write(f"**被淘汰物流：{eliminated_count} 个**")
    #     st.write(f"**可用物流：{total_logistics - eliminated_count} 个**")
    pass

    # # 显示淘汰原因详情
    # if elimination_reasons:
    #     st.markdown("**淘汰原因统计：**")
    #     for reason, logistics in elimination_reasons.items():
    #         st.write(f"**原因：**{reason}")
    #         st.write(f"**影响物流：**{len(logistics)} 个")
    #         st.write(f"**物流名称：**{', '.join(logistics)}")
    #         st.markdown("---")
    #
    # # 显示运费计算过程
    # st.markdown("### 运费计算过程")
    # if all_costs_debug:
    #     for debug_info in all_costs_debug:
    #         if isinstance(debug_info, dict):
    #             logistic_name = debug_info.get("logistic", {}).get(
    #                 "name", "未知物流"
    #             )
    #             cost = debug_info.get("cost")
    #             debug_list = debug_info.get("debug", [])
    #
    #             status = "✅ 可用" if cost is not None else "❌ 被淘汰"
    #             cost_display = (
    #                 f"¥{cost:.2f}" if cost is not None else "无法计算"
    #             )
    #
    #             st.markdown(
    #                 f"**{logistic_name}** - {status} - 运费：{cost_display}"
    #             )
    #
    #             if debug_list:
    #                 for debug_line in debug_list:
    #                     st.text(f"  {debug_line}")
    #
    #             st.markdown("---")
    #
    # # 查找运费为0的物流规则
    # zero_cost_rules = []
    # for debug_info in all_costs_debug:
    #     if isinstance(debug_info, dict) and debug_info.get('cost') == 0:
    #         zero_cost_rules.append(debug_info)
    #
    # st.write(f"**运费为0的物流规则数量:** {len(zero_cost_rules)}")
    # if zero_cost_rules:
    #     st.write("**运费为0的物流规则:**")
    #     for rule in zero_cost_rules[:5]:  # 只显示前5个
    #         logistic_name = rule.get('logistic', {}).get('name', 'Unknown')
    #         st.write(f"  - {logistic_name}: cost={rule.get('cost')}")
    pass

    # # 查找特定物流规则的运费
    # target_rules = ['GUOO Economy Extra Small', 'China Post e特快']
    # for debug_info in all_costs_debug:
    #     if isinstance(debug_info, dict):
    #         logistic = debug_info.get('logistic', {})
    #         name = logistic.get('name', 'Unknown')
    #         if name in target_rules:
    #             st.write(
    #                 f"**{name}:** cost={debug_info.get('cost')}, "
    #                 f"type={logistic.get('type')}"
    #             )

    col_land_l, col_air_l = st.columns(2)

    # ------- 陆运（低价优先）：送到取货点 + 送货上门 -------
    with col_land_l:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">🚛 陆运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_low = pricing_result_low.get("best_land")
        if best_land_low:
            # 计算时效（取平均值）
            min_days = best_land_low.get("min_days", 0)
            max_days = best_land_low.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2 if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            land_stats = pricing_result_low.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_low.get(
                "land_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#e3f2fd", "#bbdefb", "#2196f3", "rgba(33,150,243,0.15)",
                best_land_low["name"],
                f"¥{pricing_result_low.get('land_cost', 0):.2f}",
                time_display, pricing_result_low.get("land_price", 0),
                land_expected_profit,
                pricing_result_low.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_low_home = pricing_result_low_home.get("best_land")
        if best_land_low_home:
            # 使用送货上门的物流数据
            min_days = best_land_low_home.get("min_days", 0)
            max_days = best_land_low_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2 if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            land_stats = pricing_result_low_home.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_low_home.get(
                "land_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#e8f5e8", "#c8e6c9", "#4caf50", "rgba(76,175,80,0.15)",
                best_land_low_home["name"],
                f"¥{pricing_result_low_home.get('land_cost', 0):.2f}",
                time_display, pricing_result_low_home.get("land_price", 0),
                land_expected_profit,
                pricing_result_low_home.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

    # ------- 空运（低价优先）：送到取货点 + 送货上门 -------
    with col_air_l:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">✈️ 空运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_low = pricing_result_low.get("best_air")
        if best_air_low:
            # 计算时效（取平均值）
            min_days = best_air_low.get("min_days", 0)
            max_days = best_air_low.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2 if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            air_stats = pricing_result_low.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_low.get(
                "air_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#fff3e0", "#ffe0b2", "#ff9800", "rgba(255,152,0,0.15)",
                best_air_low["name"],
                f"¥{pricing_result_low.get('air_cost', 0):.2f}",
                time_display, pricing_result_low.get("air_price", 0),
                air_expected_profit,
                pricing_result_low.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_low_home = pricing_result_low_home.get("best_air")
        if best_air_low_home:
            # 使用送货上门的物流数据
            min_days = best_air_low_home.get("min_days", 0)
            max_days = best_air_low_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2 if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            air_stats = pricing_result_low_home.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_low_home.get(
                "air_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#f3e5f5", "#e1bee7", "#9c27b0", "rgba(156,39,176,0.15)",
                best_air_low_home["name"],
                f"¥{pricing_result_low_home.get('air_cost', 0):.2f}",
                time_display, pricing_result_low_home.get("air_price", 0),
                air_expected_profit,
                pricing_result_low_home.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

    # =============================
    # 速度优先
    # =============================
    st.markdown(
        (
            '<h3 style="color: #2c3e50; margin: 24px 0 12px 0; '
            "font-size: 1.5em; font-weight: 600; "
            "border-bottom: 2px solid #3498db; "
            'padding-bottom: 8px;">⚡ 速度优先</h3>'
        ),
        unsafe_allow_html=True,
    )

    col_land_s, col_air_s = st.columns(2)

    # ------- 陆运（速度优先）：送到取货点 + 送货上门 -------
    with col_land_s:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">🚛 陆运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_fast = pricing_result_fast.get("best_land")
        if best_land_fast:
            # 计算时效（取平均值）
            min_days = best_land_fast.get("min_days", 0)
            max_days = best_land_fast.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            land_stats = pricing_result_fast.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_fast.get(
                "land_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#e3f2fd", "#bbdefb", "#2196f3", "rgba(33,150,243,0.15)",
                best_land_fast["name"],
                f"¥{pricing_result_fast.get('land_cost', 0):.2f}",
                time_display, pricing_result_fast.get("land_price", 0),
                land_expected_profit,
                pricing_result_fast.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_land_fast_home = pricing_result_fast_home.get("best_land")
        if best_land_fast_home:
            # 使用送货上门的物流数据
            min_days = best_land_fast_home.get("min_days", 0)
            max_days = best_land_fast_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2
                if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            land_stats = pricing_result_fast_home.get("land_stats", {})
            avg_cost = land_stats.get("avg_cost", 0)
            cost_saving = land_stats.get("cost_saving", 0)
            avg_time_stats = land_stats.get("avg_time", 0)
            time_saving = land_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取陆运预期利润
            land_expected_profit = pricing_result_fast_home.get(
                "land_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#e8f5e8", "#c8e6c9", "#4caf50", "rgba(76,175,80,0.15)",
                best_land_fast_home["name"],
                f"¥{pricing_result_fast_home.get('land_cost', 0):.2f}",
                time_display, pricing_result_fast_home.get("land_price", 0),
                land_expected_profit,
                pricing_result_fast_home.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

    # ------- 空运（速度优先）：送到取货点 + 送货上门 -------
    with col_air_s:
        st.markdown(
            (
                '<h4 style="color: #2c3e50; margin-bottom: 10px; '
                'font-size: 1.2em; font-weight: 600;">✈️ 空运</h4>'
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏬 送到取货点</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_fast = pricing_result_fast.get("best_air")
        if best_air_fast:
            # 计算时效（取平均值）
            min_days = best_air_fast.get("min_days", 0)
            max_days = best_air_fast.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2 if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

        # 获取统计信息
            air_stats = pricing_result_fast.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_fast.get(
                "air_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#fff3e0", "#ffcc02", "#ff9800", "rgba(255,152,0,0.15)",
                best_air_fast["name"],
                f"¥{pricing_result_fast.get('air_cost', 0):.2f}",
                time_display, pricing_result_fast.get("air_price", 0),
                air_expected_profit,
                pricing_result_fast.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display,
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")

        st.markdown(
            (
                '<div style="font-weight:700; margin:6px 0; '
                'font-size:1.2em; color:#2c3e50;">🏠 送货上门</div>'
            ),
            unsafe_allow_html=True,
        )

        best_air_fast_home = pricing_result_fast_home.get("best_air")
        if best_air_fast_home:
            # 使用送货上门的物流数据
            min_days = best_air_fast_home.get("min_days", 0)
            max_days = best_air_fast_home.get("max_days", 0)
            avg_time = (
                (min_days + max_days) / 2 if min_days > 0 and max_days > 0
                else 0
            )

        # 处理时效显示
            time_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{avg_time:.1f}天"
            )

            air_stats = pricing_result_fast_home.get("air_stats", {})
            avg_cost = air_stats.get("avg_cost", 0)
            cost_saving = air_stats.get("cost_saving", 0)
            avg_time_stats = air_stats.get("avg_time", 0)
            time_saving = air_stats.get("time_saving", 0)

        # 处理节省时效显示
            time_saving_display = (
                "该物流未填写时效"
                if min_days == 0 and max_days == 0
                else f"{time_saving:+.1f}天" if time_saving != 0 else "0天"
            )

        # 获取空运预期利润
            air_expected_profit = pricing_result_fast_home.get(
                "air_expected_profit", 0
            )

            card_html = _render_pricing_card(
                "#f3e5f5", "#e1bee7", "#9c27b0", "rgba(156,39,176,0.15)",
                best_air_fast_home["name"],
                f"¥{pricing_result_fast_home.get('air_cost', 0):.2f}",
                time_display, pricing_result_fast_home.get("air_price", 0),
                air_expected_profit,
                pricing_result_fast_home.get("profit_margin", 0),
                avg_cost, cost_saving, avg_time_stats, time_saving_display
            )
            st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.info("暂无可用物流")


def payment_center_page():
    """支付中心页面"""
    # 检查并恢复支付状态
    from ui_payment import check_and_restore_payment_status
    if check_and_restore_payment_status():
        # 如果有正在进行的支付，显示状态后直接返回
        return

    st.markdown(
        """
        <div class="card-container">
            <h2 style="color: #667eea; margin-bottom: 20px;">
                💳 支付与订单管理
            </h2>
            <p style="color: #718096; font-size: 1.1rem; margin-bottom: 30px;">
                查看您的订单历史和支付记录
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 订单历史
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.markdown(
        '<h3 style="color: #667eea;">📋 订单历史</h3>',
        unsafe_allow_html=True
    )

    from db_utils import get_db

    current_user = st.session_state.get('current_user', {})
    username = current_user.get('username', '')

    try:
        conn, cursor = get_db()
        # 查询订单
        cursor.execute(
            """
            SELECT order_id, plan_type, amount, status,
                   created_at, paid_at
            FROM subscription_orders
            WHERE username = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (username,)
        )
        orders = cursor.fetchall()

        if orders:
            # 创建订单表格
            orders_data = []
            for order in orders:
                orders_data.append({
                    '订单号': order[0],
                    '套餐类型': order[1],
                    '金额': f'¥{order[2]:.2f}',
                    '状态': '已支付' if order[3] == 'paid' else '待支付',
                    '创建时间': order[4],
                    '支付时间': order[5] if order[5] else '-'
                })
            df = pd.DataFrame(orders_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("暂无订单记录")

        conn.close()
    except Exception as e:
        st.error(f"查询订单失败: {str(e)}")

    st.markdown('</div>', unsafe_allow_html=True)

    # 提示信息
    st.markdown(
        """
        <div class="card-container">
            <p style="color: #718096;">
                💡 提示：如需订阅或升级套餐，请前往"订阅管理"页面
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )


def subscription_management_page():
    """订阅管理页面"""
    # 检查是否刚刚支付成功
    if st.session_state.get('payment_just_succeeded', False):
        st.success("🎉 支付成功！您的订阅已更新")
        del st.session_state['payment_just_succeeded']

    # 检查是否在独立页面模式（没有标签页）
    is_standalone = st.session_state.get("current_page") == "subscription"

    if is_standalone:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 2rem;">
                <h1 class="main-title">💎 订阅管理</h1>
                <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                    选择最适合您的套餐，享受更多功能
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 只在独立页面模式显示返回按钮
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🏠 返回主页", key="back_to_main_from_subscription"):
                st.session_state["current_page"] = "main"
                st.rerun()

    user_id = current_user_id()

    # 获取用户信息 - 优先使用subscription_type字段
    with get_db_connection() as (conn, c):
        c.execute(
            "SELECT subscription_type, user_type FROM users WHERE id = ?",
            (user_id,)
        )
        result = c.fetchone()
        if not result:
            st.error("无法获取用户信息")
            return
        # 优先使用subscription_type，如果没有则使用user_type
        user_type = result[0] or result[1] if result[0] else result[1]

    # 自动刷新提示
    if user_type == 'free':
        st.info("💡 支付成功后，请点击上方'刷新状态'按钮查看最新账户状态")

    subscription_status = check_user_subscription_status(user_id)

    # 套餐信息映射
    plans = {
        'free': {
            'name': '免费版',
            'price': '免费',
            'calculations': '每日10次',
            'logistics_templates': 1,
            'features': ['极速模式计算', '基础物流模板'],
            'limitations': ['仅限极速模式', '物流模板限制'],
            'color': '#9E9E9E',
            'gradient': 'linear-gradient(135deg, #f5f5f5, #e0e0e0)'
        },
        'efficiency': {
            'name': '效率版',
            'price': '¥9.9/月 或 ¥99/年',
            'calculations': '无限次',
            'logistics_templates': 3,
            'features': ['无限极速模式计算', '3个物流模板'],
            'limitations': ['仅限极速模式'],
            'color': '#4CAF50',
            'gradient': 'linear-gradient(135deg, #E8F5E8, #C8E6C9)'
        },
        'professional': {
            'name': '专业版',
            'price': '¥149/月 或 ¥1499/年',
            'calculations': '无限次',
            'logistics_templates': -1,
            'features': ['极速模式 + 精准模式', '无限物流模板', '多物流比价'],
            'limitations': [],
            'color': '#2196F3',
            'gradient': 'linear-gradient(135deg, #E3F2FD, #BBDEFB)'
        },
        'enterprise': {
            'name': '企业版',
            'price': '¥999/月',
            'calculations': '无限次',
            'logistics_templates': -1,
            'features': ['专业版所有功能', '多人协作子账号', 'API接入', '专属客服'],
            'development_status': '开发中……',
            'limitations': [],
            'color': '#9C27B0',
            'gradient': 'linear-gradient(135deg, #F3E5F5, #E1BEE7)'
        },
        'gratitude': {
            'name': '感谢版',
            'price': '¥149永久',
            'calculations': '无限次',
            'logistics_templates': -1,
            'features': ['专业版所有功能'],
            'limitations': [],
            'color': '#FF9800',
            'gradient': 'linear-gradient(135deg, #FFF3E0, #FFE0B2)'
        }
    }

    current_plan = plans.get(user_type, plans['free'])

    # 显示当前套餐信息
    st.subheader("📋 当前套餐")

    col1, col2 = st.columns([2, 1])
    with col1:
        # 如果是admin用户，显示为管理员
        if st.session_state.user.get('role') == 'admin':
            plan_name = '管理员'
            plan_price = '永久免费'
            plan_calculations = '无限次'
            plan_logistics = '无限'
            plan_status = "永久有效"
        else:
            plan_name = current_plan.get('name', '未知')
            plan_price = current_plan.get('price', '未知')
            plan_calculations = current_plan.get('calculations', '未知')
            logistics_templates = current_plan.get('logistics_templates', 1)
            plan_logistics = (
                logistics_templates if logistics_templates != -1 else '无限'
            )

        # 免费版与感谢版无订阅期限，视为永久有效
            if user_type in ['free', 'gratitude']:
                plan_status = "永久有效"
            elif (subscription_status and
                  subscription_status.get('remaining_days', 0) > 0):
                plan_status = (
                    f"到期时间: {subscription_status['remaining_days']}天后"
                )
            elif (subscription_status and
                  subscription_status.get('remaining_days') == -1):
                plan_status = "永久有效"
            else:
                plan_status = "已过期，请续费"

        st.markdown(f"**{plan_name}** - {plan_price}")
        st.markdown(f"计算次数: {plan_calculations}")
        st.markdown(f"物流模板: {plan_logistics}")

        if plan_status == "永久有效":
            pass
        elif "到期时间" in plan_status:
            pass
        else:
            pass

    with col2:
        # 右侧列展示状态信息（到期时间/永久有效/已过期等）
        if plan_status == "永久有效":
            st.success(plan_status)
        elif "到期时间" in plan_status:
            st.success(plan_status)
        else:
            st.error(plan_status)

    # 非免费版用户不显示"已用完"，统一视为无限次
        if user_type != 'free':
            st.success("无限次计算")
        else:
            if (subscription_status and
                    subscription_status.get('remaining_calculations', 0) > 0):
                st.info(
                    f"今日剩余: "
                    f"{subscription_status['remaining_calculations']}次"
                )
            elif (subscription_status and
                  subscription_status.get('remaining_calculations') == -1):
                st.success("无限次计算")
            else:
                st.error("今日次数已用完")

    st.divider()

    # 添加套餐升级入口（非免费版且非管理员）
    if (user_type not in ['free', 'gratitude'] and
            st.session_state.user.get('role') != 'admin'):
        col_upgrade1, col_upgrade2 = st.columns([1, 3])
        with col_upgrade1:
            if st.button(
                "📈 查看升级选项",
                key="view_upgrade_options",
                type="primary",
                use_container_width=True
            ):
                st.session_state["current_page"] = "upgrade"
                st.rerun()
        with col_upgrade2:
            st.markdown(
                '<p style="color: #718096; padding-top: 8px;">'
                '💡 升级套餐可享受剩余时间自动折抵优惠</p>',
                unsafe_allow_html=True
            )
        st.divider()

    # 套餐对比表
    st.subheader("📊 套餐对比")

    # 计算最大高度（通过内容长度估算）
    max_features = max(
        len(plan.get('features', [])) for plan in plans.values()
    )
    max_limitations = max(
        len(plan.get('limitations', [])) for plan in plans.values()
    )
    # 重新计算高度：基础高度 + 动态内容高度 + 按钮区域高度
    # 确保包含限制卡片的高度，即使某些套餐没有限制也要预留空间
    # 增加额外空间确保限制卡片完全包含在背景中
    card_height = 450 + (max_features + max_limitations) * 30

    # 创建套餐对比表格
    columns = st.columns(4)
    if len(columns) >= 4:
        col1, col2, col3, col4 = columns[0], columns[1], columns[2], columns[3]
    else:
        # 测试环境兼容性处理
        col1, col2, col3, col4 = columns[0], columns[0], columns[0], columns[0]

    # 只显示主要的4个套餐进行对比
    display_plans = ['free', 'efficiency', 'professional', 'enterprise']

    for i, plan_key in enumerate(display_plans):
        plan = plans[plan_key]
        with [col1, col2, col3, col4][i]:
            # 判断是否为当前套餐
            if st.session_state.user.get('role') == 'admin':
                is_current = False  # admin用户不显示在任何套餐中
            else:
                is_current = current_plan.get('name') == plan.get('name')

            # 确定按钮文本
            button_text = ""
            if is_current:
                # 当前套餐，显示续费按钮（免费版除外）
                if plan_key in ['efficiency', 'professional']:
                    button_text = f"续费{plan['name']}"
            else:
                # 非当前套餐
                if plan_key == 'enterprise':
                    button_text = f"联系客服升级到{plan['name']}"
                else:
                    # 只允许升级，不允许降级
                    plan_order = {
                        'free': 0,
                        'efficiency': 1,
                        'professional': 2,
                        'enterprise': 3,
                    }
                    current_order = plan_order.get(user_type, 0)
                    target_order = plan_order.get(plan_key, 0)

                    if target_order > current_order:
                        button_text = f"升级到{plan['name']}"

            border_color = plan['color'] if is_current else "#e0e0e0"
            border_width = "3px" if is_current else "2px"

            # 构建HTML内容
            features_html = ''.join(
                [
                    f'<li style="margin-bottom: 5px;">{feature}</li>'
                    for feature in plan.get('features', [])
                ]
            )

            # 为企业版添加开发状态
            development_status_html = ''
            if plan.get('development_status'):
                development_status_html = (
                    '<div style="background: rgba(255,255,255,0.8); '
                    'padding: 10px; border-radius: 10px; margin-bottom: 15px; '
                    'text-align: center;">'
                    f'<span style="color: #2196F3; font-weight: bold; '
                    f'font-size: 14px;">{plan["development_status"]}</span>'
                    '</div>'
                )

            limitations_html = ''
            if plan.get('limitations'):
                limitation_items = ''.join(
                    [
                        (
                            f'<li style="margin-bottom: 5px;">'
                            f'{limitation}'
                            f'</li>'
                        )
                        for limitation in plan.get('limitations', [])
                    ]
                )
                limitations_html = (
                    '<div style="background: rgba(255,255,255,0.8); '
                    'padding: 15px; border-radius: 10px; '
                    'margin-bottom: 15px;">'
                    '<h5 style="color: #f44336; margin-bottom: 10px; '
                    'font-weight: bold;">限制:</h5>'
                    '<ul style="margin: 0; padding-left: 20px; '
                    'color: #f44336;">'
                    f'{limitation_items}'
                    '</ul>'
                    '</div>'
                )

            # 计算"物流模板"展示文本，避免 f-string 复杂嵌套导致语法问题
            templates_value = plan.get("logistics_templates", 1)
            templates_display = (
                templates_value if templates_value != -1 else "无限"
            )

            # 组合卡片 HTML（分段避免超长行）
            card_html = (
                f'<div style="border: {border_width} solid {border_color}; '
                'border-radius: 15px; padding: 25px; margin: 10px 0; '
                f'background: {plan["gradient"]}; '
                'box-shadow: 0 4px 15px rgba(0,0,0,0.1); '
                f'height: {card_height}px; display: flex; '
                'flex-direction: column; '
                'justify-content: space-between; transition: transform 0.2s '
                'ease;">'
                '<div>'
                f'<h3 style="text-align: center; color: {plan["color"]}; '
                'margin-bottom: 15px; font-size: 1.4em; font-weight: bold;">'
                f'{plan.get("name", "未知")}</h3>'
                '<h4 style="text-align: center; color: #333; '
                'margin-bottom: 20px; '
                'font-size: 1.2em;">'
                f'{plan.get("price", "未知")}</h4>'
                '<div style="background: rgba(255,255,255,0.7); '
                'padding: 15px; '
                'border-radius: 10px; margin-bottom: 20px;">'
                '<p style="text-align: center; margin-bottom: 10px; '
                'font-weight: '
                'bold; color: #333;">'
                f'{plan.get("calculations", "未知")}'
                '</p>'
                '<p style="text-align: center; margin-bottom: 0; '
                'color: #666;">'
                '物流模板: '
                f'{templates_display}'
                '</p>'
                '</div>'
                '<div style="background: rgba(255,255,255,0.8); '
                'padding: 15px; '
                'border-radius: 10px; margin-bottom: 15px;">'
                '<h5 style="color: #333; margin-bottom: 10px; '
                'font-weight: bold;">功能特色:</h5>'
                f'<ul style="margin: 0; padding-left: 20px; '
                f'color: #555;">{features_html}</ul>'
                '</div>'
                f'{development_status_html}'
                f'{limitations_html}'
                '</div>'
                '<div style="text-align: center; margin-top: auto;">'
                '<div style="height: 40px;"></div>'
                '</div>'
                '</div>'
            )

            st.markdown(card_html, unsafe_allow_html=True)

            # 升级/续费按钮
            if button_text:
                if plan_key == 'enterprise':
                    if st.button(
                        button_text,
                        key=f"upgrade_{plan_key}",
                        help="企业版需要联系客服开通",
                    ):
                        st.info("企业版功能开发中")
                else:
                    if st.button(button_text, key=f"action_{plan_key}"):
                        # 判断是升级还是续费
                        plan_order = {
                            'free': 0,
                            'efficiency': 1,
                            'professional': 2,
                            'enterprise': 3,
                        }
                        current_order = plan_order.get(user_type, 0)
                        target_order = plan_order.get(plan_key, 0)

                        if target_order > current_order:
                            # 升级：跳转到升级页面，并记录目标套餐
                            st.session_state["target_upgrade_plan"] = plan_key
                            st.session_state["current_page"] = "upgrade"
                        else:
                            # 续费：跳转到支付页面
                            st.session_state["payment_plan"] = plan['name']
                            st.session_state["current_page"] = "payment"
                        st.rerun()


def init_exchange_rates():
    """系统启动时预获取汇率"""
    try:
        print("🔄 系统启动：正在初始化汇率服务...")

    # 获取CNY到RUB汇率
        cny_rub_service = ExchangeRateService()
        cny_rub_rate = cny_rub_service.get_exchange_rate()
        print(f"✅ CNY到RUB汇率: {cny_rub_rate:.4f}")

    # 获取USD到CNY汇率
        usd_cny_rate = get_usd_rate()
        print(f"✅ USD到CNY汇率: {usd_cny_rate:.4f}")
        print("✅ 汇率服务初始化完成")

    except (Exception,) as e:
        print(f"⚠️ 汇率服务初始化失败: {e}")
        print("📝 将使用本地兜底汇率")


def restart_gunicorn_callback_server():
    """重启独立的 Gunicorn 回调服务器，确保加载最新代码"""
    import subprocess
    import time

    try:
        # 使用文件锁，确保整个应用生命周期内只重启一次
        project_dir = os.path.dirname(os.path.abspath(__file__))
        lock_file = os.path.join(project_dir, '.gunicorn_restart_lock')

        # 检查锁文件（如果存在且创建时间在5分钟内，跳过重启）
        if os.path.exists(lock_file):
            lock_time = os.path.getmtime(lock_file)
            if time.time() - lock_time < 300:  # 5分钟内
                print("⏭️  Gunicorn 最近已重启，跳过本次重启")
                return

        print("🔄 检查并重启 Gunicorn 回调服务器...")

        venv_python = os.path.join(project_dir, 'venv', 'bin', 'gunicorn')

        # 1. 检查是否有旧的 gunicorn 进程
        check_cmd = "ps aux | grep 'gunicorn.*wechat_callback' | grep -v grep"
        result = subprocess.run(
            check_cmd, shell=True, capture_output=True, text=True
        )

        if result.stdout.strip():
            print("   发现旧的 gunicorn 进程，正在停止...")
            # 停止旧进程
            subprocess.run(
                "pkill -9 -f 'gunicorn.*wechat_callback'",
                shell=True
            )
            time.sleep(2)
            print("   ✅ 旧进程已停止")
        else:
            print("   未发现运行中的 gunicorn 进程")

        # 2. 启动新的 gunicorn 进程
        print("   启动新的 gunicorn 进程...")
        gunicorn_cmd = (
            f"cd {project_dir} && "
            f"nohup {venv_python} "
            "-w 2 -b 0.0.0.0:8081 wechat_callback_server:app "
            "--access-logfile gunicorn_access.log "
            "--error-logfile gunicorn_error.log "
            "--log-level info "
            "> gunicorn_wechat.log 2>&1 &"
        )

        subprocess.run(gunicorn_cmd, shell=True)
        time.sleep(3)

        # 3. 验证启动
        verify_cmd = "ps aux | grep 'gunicorn.*wechat_callback' | grep -v grep"
        verify_result = subprocess.run(
            verify_cmd, shell=True, capture_output=True, text=True
        )

        if verify_result.stdout.strip():
            print("   ✅ Gunicorn 回调服务器已启动（加载最新代码）")
            # 创建锁文件
            with open(lock_file, 'w') as f:
                f.write(str(time.time()))
        else:
            print("   ⚠️  Gunicorn 回调服务器启动可能失败")

    except Exception as e:
        print(f"⚠️ 重启 Gunicorn 回调服务器失败: {e}")


def start_wechat_callback_server():
    """启动微信支付回调服务器（后台线程）"""
    if not st.session_state.get('callback_server_started', False):
        try:
            from flask import Flask, request, jsonify
            import logging
            from payment_handler import payment_handler

            # 配置日志
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger(__name__)

            app = Flask(__name__)

            @app.route('/wechat/notify', methods=['POST'])
            def wechat_notify():
                """接收微信支付回调通知（v3 API）"""
                try:
                    # 获取请求头信息
                    headers = {
                        'Wechatpay-Timestamp': request.headers.get(
                            'Wechatpay-Timestamp', ''
                        ),
                        'Wechatpay-Nonce': request.headers.get(
                            'Wechatpay-Nonce', ''
                        ),
                        'Wechatpay-Signature': request.headers.get(
                            'Wechatpay-Signature', ''
                        ),
                    }

                    # 获取请求体
                    body = request.get_data(as_text=True)
                    logger.info(f"收到微信支付通知: {body}")
                    logger.info(f"回调请求头: {dict(request.headers)}")

                    # 构建通知数据
                    notify_data = {
                        'headers': headers,
                        'body': body
                    }

                    # 处理通知
                    result = payment_handler.process_wechat_notify(notify_data)
                    logger.info(f"支付通知处理结果: {result}")

                    if result['success']:
                        # 返回成功响应
                        return jsonify({
                            'code': 'SUCCESS',
                            'message': 'OK'
                        }), 200
                    else:
                        # 返回失败响应
                        logger.error(f"支付通知处理失败: {result['message']}")
                        return jsonify({
                            'code': 'FAIL',
                            'message': result['message']
                        }), 400

                except Exception as error:
                    logger.error(f"处理微信支付通知异常: {str(error)}")
                    return jsonify({
                        'code': 'FAIL',
                        'message': f'系统错误: {str(error)}'
                    }), 500

            @app.route('/health')
            def health_check():
                """健康检查接口"""
                return {"status": "ok", "message": "微信支付回调服务运行正常"}

            # 在后台线程中启动Flask应用
            def run_server():
                app.run(
                    host='0.0.0.0', port=8081, debug=False, use_reloader=False
                )

            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()

            st.session_state.callback_server_started = True
            print("✅ 微信支付回调服务器已启动 (端口: 8081)")

        except ImportError:
            print("⚠️ Flask未安装，无法启动微信支付回调服务器")
            print("📝 请运行: pip install flask")
        except Exception as ex:
            print(f"⚠️ 启动微信支付回调服务器失败: {ex}")


def main():
    # 启动自动备份服务（只在第一次调用时启动）
    # 使用 session_state 标记，因为 backup_system.is_running 会在线程中持久化
    if not st.session_state.get('_backup_init_attempted', False):
        try:
            from auto_backup import backup_system
            if not backup_system.is_running:
                start_backup_service()
                print("🚀 自动备份服务已启动")
        except Exception as backup_exc:
            print(f"⚠️ 自动备份服务启动失败: {backup_exc}")
        st.session_state['_backup_init_attempted'] = True

    # 启动微信支付回调服务器（后台线程）
    # 检查是否禁用内置回调服务器（当使用独立Gunicorn回调服务时）
    if not st.session_state.get('_callback_init_attempted', False):
        if not (
            os.getenv("DISABLE_EMBEDDED_WECHAT_CALLBACK", "false").lower()
            == "true"
        ):
            start_wechat_callback_server()
        else:
            # 使用独立Gunicorn服务，启动时重启确保加载最新代码
            restart_gunicorn_callback_server()
        st.session_state['_callback_init_attempted'] = True

    init_db()
    # 初始化会话安全相关数据表，防止首次启动时表缺失
    SessionSecurity.init_session_tables()
    # 初始化极速模式数据表
    init_fast_mode_tables()
    # 迁移用户偏好设置
    migrate_user_preferences()
    # 系统启动时预获取汇率（只执行一次）
    if not st.session_state.get('_exchange_init_attempted', False):
        init_exchange_rates()
        st.session_state['_exchange_init_attempted'] = True

    # 正常模式：检查会话安全性
    if not check_session_security():
        login_or_register_page()
        return

    # 显示会话信息（包括订阅状态）
    try:
        from .session_security import show_session_info
        show_session_info()
    except ImportError:
        from session_security import show_session_info
        show_session_info()

    # 检查页面路由
    current_page = st.session_state.get("current_page", "main")

    if current_page == "payment":
        # 显示支付页面
        from payment_page import show_payment_page
        show_payment_page()
    elif current_page == "subscription":
        # 显示订阅管理页面
        subscription_management_page()
    elif current_page == "upgrade":
        # 显示套餐升级页面
        from ui_subscription_upgrade import show_subscription_upgrade_page
        show_subscription_upgrade_page()
    else:
        # 显示主界面
        show_main_interface()


if __name__ == "__main__":
    main()
