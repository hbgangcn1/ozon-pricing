# -*- coding: utf-8 -*-
"""
支付成功页面模块
提供支付成功后的用户界面和状态管理
"""
import streamlit as st
import time
from db_utils import get_user_subscription_info
from typing import Optional


def show_payment_success_page(order_id: Optional[str] = None, plan_name: Optional[str] = None):
    """
    显示支付成功页面

    Args:
        order_id: 订单ID
        plan_name: 套餐名称
    """
    st.title("🎉 支付成功！")

    # 显示成功信息
    st.success("✅ 您的支付已成功处理！")

    if order_id:
        st.info(f"订单号：{order_id}")

    if plan_name:
        st.info(f"套餐：{plan_name}")
    # 显示当前订阅状态
    if 'user_id' in st.session_state:
        user_id = st.session_state.user_id
        subscription_info = get_user_subscription_info(user_id)

        if subscription_info:
            st.subheader("📋 当前订阅状态")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "订阅类型",
                    subscription_info.get('subscription_type', '免费版')
                )
            with col2:
                expires_at = subscription_info.get('subscription_expires')
                if expires_at:
                    import datetime
                    expires_date = datetime.datetime.fromtimestamp(expires_at)
                    st.metric("到期时间", expires_date.strftime('%Y-%m-%d'))
                else:
                    st.metric("到期时间", "永久")
            with col3:
                remaining = subscription_info.get('calculations_remaining', 0)
                st.metric(
                    "剩余次数",
                    remaining if remaining != -1 else "无限"
                )
    # 重要提示
    st.warning("""
    ⚠️ **重要提示**

    为了确保您能正常使用新功能，请：
    1. **刷新页面** - 点击下方的"刷新页面"按钮
    2. **重新登录** - 或者退出登录后重新登录

    这样可以确保您的账号状态已正确更新。
    """)

    # 操作按钮
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 刷新页面", type="primary"):
            st.rerun()

    with col2:
        if st.button("🚪 重新登录"):
            # 清除session状态
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    with col3:
        if st.button("🏠 返回首页"):
            st.switch_page("app.py")
    # 自动刷新倒计时
    if 'auto_refresh_countdown' not in st.session_state:
        st.session_state.auto_refresh_countdown = 10

    if st.session_state.auto_refresh_countdown > 0:
        st.info(
            f"⏰ 页面将在 {st.session_state.auto_refresh_countdown} 秒后自动刷新..."
        )
        time.sleep(1)
        st.session_state.auto_refresh_countdown -= 1
        st.rerun()
    else:
        st.success("🔄 正在自动刷新页面...")
        st.rerun()


def show_payment_processing_page(order_id: str, plan_name: Optional[str] = None):
    """
    显示支付处理中页面，包含实时状态检查

    Args:
        order_id: 订单ID
        plan_name: 套餐名称
    """
    st.title("⏳ 支付处理中...")

    st.info(f"订单号：{order_id}")
    if plan_name:
        st.info(f"套餐：{plan_name}")

    # 显示支付状态检查
    if 'payment_check_count' not in st.session_state:
        st.session_state.payment_check_count = 0

    st.session_state.payment_check_count += 1

    # 模拟支付状态检查
    with st.spinner("正在检查支付状态..."):
        time.sleep(2)  # 模拟检查延迟

        # 这里应该调用实际的支付状态检查API
        # 为了演示，我们模拟一个成功的支付
        if st.session_state.payment_check_count >= 3:  # 3次检查后模拟成功
            st.success("✅ 支付成功！正在跳转到成功页面...")
            time.sleep(2)
            show_payment_success_page(order_id, plan_name)
        else:
            st.warning("⏳ 支付仍在处理中，请稍候...")
            st.info(f"已检查 {st.session_state.payment_check_count} 次")

            # 自动重新检查
            time.sleep(3)
            st.rerun()
