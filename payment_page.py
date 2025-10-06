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
from payment_success_page import show_payment_success_page
from db_utils import current_user_id


def show_payment_page():
    """显示支付页面"""
    st.set_page_config(
        page_title="支付中心",
        page_icon="💳",
        layout="wide"
    )

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
        st.button("🏠 返回首页", on_click=lambda: st.switch_page("app"))
        return

    # 显示计划信息
    st.markdown(f"### 📋 订阅计划：{plan_name}")

    # 创建支付处理器
    payment_handler = PaymentHandler()

    # 检查是否已有订单
    order_id = st.session_state.get(f"payment_order_{plan_name}", None)

    if order_id:
        # 已有订单，显示支付信息
        show_existing_payment(order_id, plan_name, payment_handler)
    else:
        # 创建新订单
        create_new_payment(plan_name, payment_handler)


def show_existing_payment(
    order_id: str, plan_name: str, payment_handler: PaymentHandler
):
    """显示已有订单的支付信息"""
    st.success("✅ 订单已创建，请完成支付")

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
                result = payment_handler.query_payment_status(order_id)

                if result["success"]:
                    status = result["status"]
                    if status == "SUCCESS":
                        st.success("🎉 支付成功！")
                        # 清除订单信息
                        if f"payment_order_{plan_name}" in st.session_state:
                            del st.session_state[f"payment_order_{plan_name}"]
                        if f"payment_qr_{order_id}" in st.session_state:
                            del st.session_state[f"payment_qr_{order_id}"]

                        # 跳转到成功页面
                        time.sleep(2)
                        show_payment_success_page(order_id, plan_name)
                        return
                    elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
                        st.error("❌ 支付失败，请重新创建订单")
                        # 清除订单信息
                        if f"payment_order_{plan_name}" in st.session_state:
                            del st.session_state[f"payment_order_{plan_name}"]
                        if f"payment_qr_{order_id}" in st.session_state:
                            del st.session_state[f"payment_qr_{order_id}"]
                        st.rerun()
                    else:
                        st.info(f"⏳ 支付状态：{status}")
                else:
                    error_msg = result.get('message', '未知错误')
                    if "签名错误" in error_msg:
                        st.warning("⚠️ 查询失败，请稍后重试")
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

    # 返回按钮
    st.markdown("---")
    if st.button("🏠 返回首页", key="back_to_home"):
        st.switch_page("app")


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
