# -*- coding: utf-8 -*-
"""
支付界面模块
提供支付相关的用户界面
"""
import streamlit as st
import time
from payment_handler import PaymentHandler


def show_payment_page():
    """显示支付页面"""
    st.title("💳 支付中心")
    # 检查用户登录状态
    if 'user_id' not in st.session_state:
        st.error("请先登录")
        return
    user_id = st.session_state.user_id
    payment_handler = PaymentHandler()
    # 支付套餐选择
    st.subheader("📦 选择套餐")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        ### 🆓 免费版
        - 每月10次计算
        - 基础功能
        """)
        if st.button("当前套餐", key="free", disabled=True):
            pass
    with col2:
        st.markdown("""
        ### ⭐ 专业版
        - 无限次计算
        - 所有功能
        - ¥99/年
        """)
        if st.button("购买专业版", key="professional"):
            create_professional_payment(payment_handler, user_id)
    with col3:
        st.markdown("""
        ### 💰 购买计算次数
        - 每次计算 ¥1
        - 按需购买
        """)
        calc_amount = st.number_input(
            "购买次数", min_value=1, max_value=1000, value=10
        )
        if st.button("购买计算次数", key="calculations"):
            create_calculation_payment(payment_handler, user_id, calc_amount)
    # 支付历史
    st.subheader("📋 支付历史")
    history = payment_handler.get_user_payment_history(user_id)
    if history:
        for record in history:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                with col1:
                    st.write(f"**{record['description']}**")
                    st.caption(f"订单号: {record['order_id']}")
                with col2:
                    st.write(f"¥{record['amount']/100:.2f}")
                with col3:
                    status_color = {
                        "PAID": "✅", "PENDING": "⏳", "FAILED": "❌"
                    }
                    st.write(
                        f"{status_color.get(record['status'], '❓')} "
                        f"{record['status']}"
                    )
                with col4:
                    time_str = time.strftime(
                        '%Y-%m-%d %H:%M',
                        time.localtime(record['created_at'])
                    )
                    st.write(
                        f"<small>{time_str}</small>",
                        unsafe_allow_html=True
                    )
                st.divider()
    else:
        st.info("暂无支付记录")


def create_professional_payment(payment_handler: PaymentHandler, user_id: int):
    """创建专业版支付订单"""
    result = payment_handler.create_payment_order(
        user_id=user_id,
        amount=9900,  # ¥99.00
        description="专业版会员 - 1年",
        payment_type="native"
    )
    if result["success"]:
        st.success("订单创建成功！")
        # 显示二维码
        if result.get("code_url"):
            st.subheader("📱 请使用微信扫描二维码完成支付")
            # 这里可以集成二维码生成库
            st.code(result["code_url"])
            st.info("请在微信中打开链接完成支付")
            # 轮询支付状态
            if st.button("检查支付状态"):
                check_payment_status(payment_handler, result["order_id"])
        else:
            st.error("二维码生成失败")
    else:
        st.error(f"订单创建失败: {result['message']}")


def create_calculation_payment(
    payment_handler: PaymentHandler, user_id: int, amount: int
):
    """创建计算次数支付订单"""
    result = payment_handler.create_payment_order(
        user_id=user_id,
        amount=amount * 100,  # 转换为分
        description=f"购买计算次数 - {amount}次",
        payment_type="native"
    )
    if result["success"]:
        st.success("订单创建成功！")
        if result.get("code_url"):
            st.subheader("📱 请使用微信扫描二维码完成支付")
            st.code(result["code_url"])
            st.info("请在微信中打开链接完成支付")
            if st.button("检查支付状态", key="check_calc"):
                check_payment_status(payment_handler, result["order_id"])
        else:
            st.error("二维码生成失败")
    else:
        st.error(f"订单创建失败: {result['message']}")


def check_payment_status(payment_handler: PaymentHandler, order_id: str):
    """检查支付状态"""
    result = payment_handler.query_payment_status(order_id)
    if result["success"]:
        status = result["status"]
        if status == "SUCCESS":
            st.success("✅ 支付成功！您的账户已更新")
            st.rerun()
        elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
            st.error("❌ 支付失败")
        else:
            st.warning("⏳ 支付处理中，请稍后再试")
    else:
        st.error(f"查询失败: {result['message']}")
