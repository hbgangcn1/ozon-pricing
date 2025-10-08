"""
独立支付页面
处理订阅升级的支付流程
"""

import streamlit as st
import time
import qrcode
import io
import base64
from payment_handler import PaymentHandler
from db_utils import get_db_connection
from db_utils import current_user_id
from payment_auto_refresh import (
    inject_smart_auto_refresh,
    show_enhanced_auto_check_indicator
)


def cleanup_payment_state(plan_name: str, order_id: str):
    """清理支付状态"""
    keys_to_remove = [
        f"payment_order_{plan_name}",
        f"payment_qr_{order_id}",
        f"order_creation_time_{order_id}",
        f"last_check_{order_id}",  # 清理检查缓存
        'auto_check_count'
    ]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]


def handle_payment_success(order_id: str, plan_name: str):
    """处理支付成功"""
    print(f"🎉 检测到支付成功: {order_id}")
    st.balloons()
    st.success("🎉 支付成功！正在跳转...")

    # 记录支付成功时间（用于数据分析和用户体验优化）
    st.session_state['last_successful_payment'] = {
        'order_id': order_id,
        'plan_name': plan_name,
        'timestamp': time.time(),
        'success_time': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    # 添加调试信息
    payment_keys_before = [
        k for k in st.session_state.keys()
        if isinstance(k, str) and 'payment' in k
    ]
    print(f"清理状态前: {payment_keys_before}")

    # 清理支付相关状态
    cleanup_payment_state(plan_name, order_id)

    payment_keys_after = [
        k for k in st.session_state.keys()
        if isinstance(k, str) and 'payment' in k
    ]
    print(f"清理状态后: {payment_keys_after}")

    # 跳转到订阅管理页面
    time.sleep(1.5)
    st.session_state["current_page"] = "subscription"
    print("🔄 触发页面跳转到订阅管理")
    st.rerun()


def auto_check_and_redirect(order_id: str, plan_name: str):
    """
    自动检查支付状态并在成功时重定向
    这个函数在每次页面刷新时静默执行
    """
    print(f"🔍 开始自动检查订单: {order_id}")

    # 检查缓存（最近3秒内查过就不重复查询，减少数据库压力）
    cache_key = f"last_check_{order_id}"
    last_check = st.session_state.get(cache_key, 0)
    if time.time() - last_check < 3:
        print("⏩ 跳过检查（缓存中）")
        return

    st.session_state[cache_key] = time.time()
    print("✅ 执行数据库查询...")

    # 检查是否超时（30分钟）
    order_creation_time = st.session_state.get(
        f"order_creation_time_{order_id}"
    )
    if order_creation_time and time.time() - order_creation_time > 1800:
        st.warning("⏰ 订单已超时，请重新创建订单")
        cleanup_payment_state(plan_name, order_id)
        time.sleep(2)
        st.rerun()

    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute(
                """
                SELECT status, created_at FROM payment_orders
                WHERE order_id = ?
                """,
                (order_id,),
            )
            row = cursor.fetchone()
            if row:
                status_in_db = row[0]
                print(f"📊 数据库订单状态: {status_in_db}")
                if status_in_db in ["PAID", "SUCCESS", "SUCCESSFUL"]:
                    # 支付成功
                    print("✅ 检测到支付成功，准备跳转")
                    handle_payment_success(order_id, plan_name)
                elif status_in_db in ["CLOSED", "REVOKED", "PAYERROR"]:
                    # 支付失败，提供明确指导
                    print(f"❌ 检测到支付失败: {status_in_db}")
                    st.error("❌ 支付失败，请重新创建订单")
                    st.info(
                        "💡 如果问题持续，请检查微信余额或联系客服"
                    )
                    cleanup_payment_state(plan_name, order_id)
                    time.sleep(2)
                    st.rerun()
                else:
                    print(f"⏳ 订单状态: {status_in_db}，继续等待")
            else:
                print(f"⚠️ 未找到订单记录: {order_id}")

    except Exception as e:
        # 静默失败，不影响页面显示
        print(f"❌ 自动检查支付状态失败: {e}")


def show_payment_page():
    """显示支付页面"""
    # 注意：不能在这里调用 st.set_page_config()
    # 因为主应用 app.py 已经调用过了
    # Streamlit 不允许重复调用 st.set_page_config()

    print("🔧 显示支付页面")

    # 页面标题
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #667eea; margin-bottom: 10px;">💳 支付中心</h1>
            <p style="color: #718096; font-size: 1.1rem;">安全便捷的订阅升级服务</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 从URL参数或session_state获取支付信息
    plan_name = st.query_params.get("plan", None)
    if not plan_name:
        plan_name = st.session_state.get("payment_plan", None)

    if not plan_name:
        st.error("❌ 未找到支付计划信息，请重新选择订阅套餐")
        st.button(
            "🏠 返回首页",
            on_click=lambda: st.session_state.update(
                {"current_page": "main"}
            ) or st.rerun()
        )
        return

    # 显示计划信息
    st.markdown(f"### 📋 订阅计划：{plan_name}")

    # 创建支付处理器
    payment_handler = PaymentHandler()

    # 检查是否已有订单
    order_id = st.session_state.get(f"payment_order_{plan_name}", None)

    if order_id:
        # 已有订单，显示支付信息（带自动刷新）
        show_existing_payment(order_id, plan_name, payment_handler)
    else:
        # 创建新订单
        create_new_payment(plan_name, payment_handler)


def show_existing_payment(
    order_id: str, plan_name: str, payment_handler: PaymentHandler
):
    """显示已有订单的支付信息（带智能自动检查）"""

    # 首先自动检查支付状态（静默）
    auto_check_and_redirect(order_id, plan_name)

    # 初始化自动检查计数器
    if 'auto_check_count' not in st.session_state:
        st.session_state['auto_check_count'] = 0

    st.session_state['auto_check_count'] += 1
    check_count = st.session_state['auto_check_count']

    # 使用智能刷新（最多检查60次，约5分钟）
    max_checks = 60
    inject_smart_auto_refresh(
        check_interval_seconds=5,
        max_checks=max_checks
    )

    # 显示增强的自动检查指示器（带进度条）
    show_enhanced_auto_check_indicator(
        check_count=check_count,
        max_checks=max_checks
    )

    # 提示信息
    if check_count >= max_checks:
        st.warning(
            "⏰ 已达到最大检查次数。"
            "如已支付成功但未跳转，请点击下方'检查支付状态'按钮"
        )
    else:
        st.success("✅ 订单已创建，请完成支付")
        st.info("💡 支付成功后将自动跳转，无需手动操作（最多等待5分钟）")

    # 显示订单信息
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### 📄 订单详情")
        st.info(f"**订单号：** {order_id}")
        st.info(f"**订阅计划：** {plan_name}")

        # 显示二维码
        qr_data = st.session_state.get(f"payment_qr_{order_id}", {})
        if qr_data.get("qr_image"):
            st.markdown("#### 📱 扫码支付")
            st.markdown(
                f"""
                <div style="text-align: center;">
                    <img src="data:image/png;base64,{qr_data['qr_image']}"
                         style="max-width: 300px; border: 1px solid #ddd;
                                border-radius: 8px;">
                    <div style="color:#888; font-size:12px; margin-top: 10px;">
                        请使用微信扫描二维码完成支付
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    with col2:
        st.markdown("#### 🔄 支付状态")

        # 检查支付状态按钮
        if st.button("🔍 检查支付状态", key="check_payment_status"):
            with st.spinner("正在检查支付状态..."):
                # 1) 优先查询数据库（可靠、低延迟）
                order_key = f"payment_order_{plan_name}"
                qr_key = f"payment_qr_{order_id}"
                paid_in_db = False
                try:
                    with get_db_connection() as (conn, cursor):
                        cursor.execute(
                            """
                            SELECT status FROM payment_orders
                            WHERE order_id = ?
                            """,
                            (order_id,),
                        )
                        row = cursor.fetchone()
                        if row:
                            status_in_db = row[0]
                            paid_in_db = status_in_db in [
                                "PAID",
                                "SUCCESS",
                                "SUCCESSFUL",
                            ]
                except Exception as ex:
                    # 安静失败，继续走 API 回退
                    print(f"检查数据库订单状态出错: {ex}")

                if paid_in_db:
                    success_msg = (
                        "🎉 支付成功！正在跳转到订阅管理页面..."
                    )
                    st.success(success_msg)
                    if order_key in st.session_state:
                        del st.session_state[order_key]
                    if qr_key in st.session_state:
                        del st.session_state[qr_key]
                    time.sleep(1)
                    st.session_state["current_page"] = "subscription"
                    st.rerun()
                else:
                    # 2) 回退调用微信查询接口
                    result = payment_handler.query_payment_status(order_id)

                    if result.get("success"):
                        status = result.get("status")
                        if status == "SUCCESS":
                            success_msg = (
                                "🎉 支付成功！正在跳转到订阅管理页面..."
                            )
                            st.success(success_msg)
                            if order_key in st.session_state:
                                del st.session_state[order_key]
                            if qr_key in st.session_state:
                                del st.session_state[qr_key]
                            time.sleep(1)
                            st.session_state["current_page"] = "subscription"
                            st.rerun()
                        elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
                            st.error("❌ 支付失败，请重新创建订单")
                            if order_key in st.session_state:
                                del st.session_state[order_key]
                            if qr_key in st.session_state:
                                del st.session_state[qr_key]
                            st.rerun()
                        else:
                            status_msg = f"⏳ 支付状态：{status}"
                            st.info(status_msg)
                    else:
                        error_msg = result.get("message", "未知错误")
                        # 对签名错误等短期不稳定情况，给温和提示
                        if (
                            "签名错误" in error_msg
                            or "signature" in error_msg.lower()
                        ):
                            st.warning("⏳ 支付状态尚未同步，请稍后再试")
                        else:
                            st.error(f"❌ 查询失败：{error_msg}")

        # 重新创建订单按钮
        if st.button("🔄 重新创建订单", key="recreate_order"):
            # 清除现有订单信息
            if f"payment_order_{plan_name}" in st.session_state:
                del st.session_state[f"payment_order_{plan_name}"]
            if f"payment_qr_{order_id}" in st.session_state:
                del st.session_state[f"payment_qr_{order_id}"]
            st.rerun()

    # 返回按钮和状态刷新
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🏠 返回首页", key="back_to_home"):
            st.session_state["current_page"] = "main"
            st.rerun()

    with col2:
        if st.button("🔄 刷新账户状态", key="refresh_status"):
            # 清除可能的缓存状态
            if 'subscription_status' in st.session_state:
                del st.session_state['subscription_status']
            st.success("✅ 账户状态已刷新，请重新登录查看最新状态")
            st.info(
                "💡 如果支付成功但状态未更新，请尝试重新登录"
            )


def create_new_payment(plan_name: str, payment_handler: PaymentHandler):
    """创建新的支付订单"""
    st.info("🔄 正在创建支付订单...")

    with st.spinner("创建订单中..."):
        # 根据计划名称确定价格和描述
        if "效率版" in plan_name:
            amount = 100  # 1元 = 100分
            description = "物流系统效率版订阅 - 首月优惠"
        elif "专业版" in plan_name:
            amount = 300  # 3元 = 300分
            description = "物流系统专业版订阅 - 首月优惠"
        else:
            st.error("❌ 未知的订阅计划")
            return

        # 获取当前用户ID
        user_id = current_user_id()
        if not user_id:
            st.error("❌ 请先登录")
            return

        # 创建支付订单
        result = payment_handler.create_payment_order(
            user_id=user_id,
            amount=amount,
            description=description
        )

        if result["success"]:
            order_id = result["order_id"]
            code_url = result["code_url"]

            # 保存订单信息到session_state
            st.session_state[f"payment_order_{plan_name}"] = order_id
            # 保存订单创建时间（用于超时检查）
            st.session_state[f"order_creation_time_{order_id}"] = time.time()

            # 生成二维码
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(code_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                img_buffer = io.BytesIO()
                qr_img.save(img_buffer, kind='PNG')
                img_str = base64.b64encode(img_buffer.getvalue()).decode()

                # 保存二维码信息
                st.session_state[f"payment_qr_{order_id}"] = {
                    "qr_image": img_str,
                    "code_url": code_url,
                    "created_time": time.time()
                }

                st.success("✅ 订单创建成功！")
                st.rerun()

            except Exception as e:
                st.error(f"❌ 二维码生成失败：{e}")
        else:
            st.error(f"❌ 订单创建失败：{result.get('message', '未知错误')}")


if __name__ == "__main__":
    show_payment_page()
