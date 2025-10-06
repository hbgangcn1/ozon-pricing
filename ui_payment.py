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

            # 生成二维码
            import qrcode
            import io
            import base64

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(result["code_url"])
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            img_buffer = io.BytesIO()
            qr_img.save(img_buffer, kind='PNG')
            img_str = base64.b64encode(img_buffer.getvalue()).decode()

            st.markdown(f"""
                <div style="text-align: center;">
                    <img src="data:image/png;base64,{img_str}"
                         style="max-width: 300px;">
                </div>
            """, unsafe_allow_html=True)

            st.info("请在微信中扫描二维码完成支付")
            # 将code_url保存到监控状态，便于后续自动刷新二维码
            if ('payment_monitoring' in st.session_state and
                    result.get("order_id")):
                st.session_state.payment_monitoring.setdefault(
                    result["order_id"], {}
                )['code_url'] = result["code_url"]
                st.session_state.payment_monitoring[result["order_id"]][
                    'qr_last_refresh'
                ] = time.time()

            # 启动实时状态检查
            start_payment_monitoring(
                payment_handler, result["order_id"], "专业版"
            )
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

            # 生成二维码
            import qrcode
            import io
            import base64

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(result["code_url"])
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            img_buffer = io.BytesIO()
            qr_img.save(img_buffer, kind='PNG')
            img_str = base64.b64encode(img_buffer.getvalue()).decode()

            st.markdown(f"""
                <div style="text-align: center;">
                    <img src="data:image/png;base64,{img_str}"
                         style="max-width: 300px;">
                </div>
            """, unsafe_allow_html=True)

            st.info("请在微信中扫描二维码完成支付")
            # 将code_url保存到监控状态，便于后续自动刷新二维码
            if ('payment_monitoring' in st.session_state and
                    result.get("order_id")):
                st.session_state.payment_monitoring.setdefault(
                    result["order_id"], {}
                )['code_url'] = result["code_url"]
                st.session_state.payment_monitoring[result["order_id"]][
                    'qr_last_refresh'
                ] = time.time()

            # 启动实时状态检查
            start_payment_monitoring(
                payment_handler, result["order_id"], f"{amount}次计算"
            )
        else:
            st.error("二维码生成失败")
    else:
        st.error(f"订单创建失败: {result['message']}")


def start_payment_monitoring(
    payment_handler: PaymentHandler, order_id: str, plan_name: str
):
    """启动支付状态实时监控"""
    # 设置监控状态
    if 'payment_monitoring' not in st.session_state:
        st.session_state.payment_monitoring = {}

    st.session_state.payment_monitoring[order_id] = {
        'start_time': time.time(),
        'plan_name': plan_name,
        'check_count': 0,
        'first_check_done': False
    }

    # 显示监控状态
    st.info("🔄 正在实时监控支付状态...")

    # 创建状态显示区域
    status_placeholder = st.empty()
    progress_placeholder = st.empty()
    qr_placeholder = st.empty()

    # 初始化显示状态
    if f'payment_status_{order_id}' not in st.session_state:
        st.session_state[f'payment_status_{order_id}'] = "⏳ 等待微信支付系统处理订单..."
    if f'payment_progress_{order_id}' not in st.session_state:
        st.session_state[f'payment_progress_{order_id}'] = 0

    # 开始监控循环
    monitor_payment_status(
        payment_handler, order_id, plan_name, status_placeholder,
        progress_placeholder, qr_placeholder
    )


def monitor_payment_status(
    payment_handler: PaymentHandler, order_id: str, plan_name: str,
    status_placeholder, progress_placeholder, qr_placeholder=None
):
    """监控支付状态"""
    # 不设置严格超时，允许长时间等待；通过较大次数与较短间隔实现“长期等待”
    max_checks = 3600  # 最多检查3600次（约2小时，间隔2秒）
    check_interval = 2  # 每2秒检查一次
    qr_refresh_interval = 60  # 每60秒刷新一次二维码

    if order_id not in st.session_state.payment_monitoring:
        return

    monitoring_info = st.session_state.payment_monitoring[order_id]
    check_count = monitoring_info['check_count']
    first_check_done = monitoring_info.get('first_check_done', False)

    if check_count >= max_checks:
        # 长等待模式：不结束监控，重置计数继续
        monitoring_info['check_count'] = 0
        check_count = 0

    # 如果是第一次检查，等待5秒让微信支付系统处理订单
    if not first_check_done:
        status_msg = "⏳ 等待微信支付系统处理订单..."
        status_placeholder.info(status_msg)
        progress_placeholder.progress(0, text="等待中...")
        # 保存状态到session_state
        st.session_state[f'payment_status_{order_id}'] = status_msg
        st.session_state[f'payment_progress_{order_id}'] = 0
        time.sleep(5)  # 等待5秒后开始检查
        st.session_state.payment_monitoring[order_id][
            'first_check_done'
        ] = True
        # 直接继续执行，不调用st.rerun()
        # 这样可以避免重跑导致的状态丢失

    # 更新检查次数
    monitoring_info['check_count'] += 1

    # 显示进度
    progress = check_count / max_checks
    progress_text = f"检查进度: {check_count}/{max_checks}"
    progress_placeholder.progress(progress, text=progress_text)
    # 保存进度到session_state
    st.session_state[f'payment_progress_{order_id}'] = progress

    # 到点刷新二维码（如果有code_url）
    code_url = monitoring_info.get('code_url')
    last_refresh = monitoring_info.get(
        'qr_last_refresh', monitoring_info.get('start_time', time.time())
    )
    if (code_url and (time.time() - last_refresh) >= qr_refresh_interval and
            qr_placeholder is not None):
        try:
            import qrcode
            import io
            import base64
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(code_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            img_buffer = io.BytesIO()
            qr_img.save(img_buffer, kind='PNG')
            img_str = base64.b64encode(img_buffer.getvalue()).decode()
            qr_placeholder.markdown(
                f"""
                <div style="text-align: center;">
                    <img src="data:image/png;base64,{img_str}"
                         style="max-width: 300px;">
                    <div style="color:#888; font-size:12px;">二维码已自动刷新</div>
                </div>
                """, unsafe_allow_html=True
            )
            monitoring_info['qr_last_refresh'] = time.time()
        except Exception:
            # 刷新失败不影响主流程
            pass

    # 检查支付状态
    with st.spinner("正在检查支付状态..."):
        result = payment_handler.query_payment_status(order_id)

        if result["success"]:
            status = result["status"]
            if status == "SUCCESS":
                # 支付成功
                status_placeholder.success("🎉 支付成功！正在跳转到成功页面...")
                progress_placeholder.empty()

                # 清除监控状态
                del st.session_state.payment_monitoring[order_id]

                # 跳转到成功页面
                time.sleep(2)
                from payment_success_page import show_payment_success_page
                show_payment_success_page(order_id, plan_name)
                return

            elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
                # 支付失败
                status_placeholder.error("❌ 支付失败，请重新尝试")
                progress_placeholder.empty()
                del st.session_state.payment_monitoring[order_id]
                return
            else:
                # 仍在处理中
                status_placeholder.info(f"⏳ 支付处理中... (已检查 {check_count} 次)")
        else:
            # 查询失败，但不停止监控，继续尝试
            error_msg = result.get('message', '未知错误')
            if "签名错误" in error_msg or "HTTP" in error_msg:
                # 对于签名错误或HTTP错误，继续监控
                if check_count <= 5:
                    # 前5次检查失败时，显示更友好的信息
                    warning_msg = (
                        f"⏳ 正在检查支付状态... "
                        f"(已检查 {check_count} 次)"
                    )
                    status_placeholder.info(warning_msg)
                else:
                    # 5次后仍失败，显示警告信息
                    warning_msg = (
                        f"⚠️ 查询失败: {error_msg}，继续监控中... "
                        f"(已检查 {check_count} 次)"
                    )
                    status_placeholder.warning(warning_msg)
                # 保存状态到session_state
                st.session_state[f'payment_status_{order_id}'] = warning_msg
            else:
                # 其他错误，停止监控
                status_placeholder.error(f"❌ 查询失败: {error_msg}")
                progress_placeholder.empty()
                del st.session_state.payment_monitoring[order_id]
                return

    # 继续监控
    time.sleep(check_interval)
    # 使用st.rerun()来更新页面，但保持监控状态
    st.rerun()


def check_payment_status(payment_handler: PaymentHandler, order_id: str):
    """检查支付状态（保留用于手动检查）"""
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
