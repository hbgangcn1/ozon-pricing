# -*- coding: utf-8 -*-
"""
套餐升级页面
展示升级选项和折抵信息
"""

import streamlit as st
import time
from subscription_upgrade import SubscriptionUpgrade
from payment_handler import PaymentHandler
from db_utils import current_user_id
import qrcode
import io
import base64


def show_subscription_upgrade_page():
    """显示套餐升级页面"""

    st.title("📈 套餐升级")
    st.write("升级享受更多功能，剩余时间自动折抵")

    # 检查用户登录
    user_id = current_user_id()
    if not user_id:
        st.error("请先登录")
        return

    # 获取目标套餐（如果用户指定了）
    target_plan_key = st.session_state.get("target_upgrade_plan")

    # 获取升级选项
    options_result = SubscriptionUpgrade.get_upgrade_options(user_id)

    if not options_result['success']:
        st.error(f"获取升级选项失败: {options_result.get('message')}")
        return

    # 显示当前套餐信息
    current_plan_name = options_result['current_plan_name']

    st.info(f"📦 当前套餐: **{current_plan_name}**")

    # 获取升级选项
    upgrade_options = options_result['upgrade_options']

    if not upgrade_options:
        st.success("✅ 您已经是最高级别套餐，无需升级")
        if st.button("🏠 返回首页"):
            st.session_state["current_page"] = "main"
            st.rerun()
        return

    # 如果用户指定了目标套餐，只显示该套餐的选项
    if target_plan_key:
        upgrade_options = [
            opt for opt in upgrade_options
            if opt['plan_key'] == target_plan_key
        ]

        if not upgrade_options:
            st.warning(f"未找到 {target_plan_key} 的升级选项")
            target_plan_key = None  # 显示所有选项

    # 如果没有指定目标套餐，或者没有找到，显示所有选项
    if not target_plan_key:
        st.markdown("### 📊 可选升级方案")
        st.write("请选择您想要升级的套餐：")

    # 按套餐分组显示
    plans_by_key = {}
    for option in upgrade_options:
        key = option['plan_key']
        if key not in plans_by_key:
            plans_by_key[key] = []
        plans_by_key[key].append(option)

    for plan_key, options in plans_by_key.items():
        show_plan_upgrade_options(plan_key, options, user_id)

    # 返回按钮
    st.markdown("---")
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🏠 返回首页", key="back_to_home"):
            st.session_state["current_page"] = "main"
            st.rerun()
    with col2:
        if st.button("📋 查看所有套餐", key="view_all"):
            st.session_state.pop("target_upgrade_plan", None)
            st.rerun()


def show_plan_upgrade_options(
    plan_key: str,
    options: list,
    user_id: int
):
    """显示某个套餐的所有升级选项（月付/年付）"""

    if not options:
        return

    # 获取套餐信息
    first_option = options[0]
    plan_name = first_option['plan_name']

    # 选择卡片颜色
    colors = {
        'efficiency': {
            'bg': '#E8F5E8', 'border': '#4CAF50', 'text': '#2E7D32'
        },
        'professional': {
            'bg': '#E3F2FD', 'border': '#2196F3', 'text': '#1565C0'
        },
        'enterprise': {
            'bg': '#F3E5F5', 'border': '#9C27B0', 'text': '#6A1B9A'
        },
    }
    color_scheme = colors.get(
        plan_key,
        {'bg': '#FFF3E0', 'border': '#FF9800', 'text': '#E65100'}
    )

    # 显示套餐标题
    st.markdown(
        f"""
        <div style="background: {color_scheme['bg']};
             border-left: 5px solid {color_scheme['border']};
             padding: 15px; margin: 20px 0; border-radius: 8px;">
            <h3 style="color: {color_scheme['text']}; margin: 0;">
                {plan_name}
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 为每个周期选项创建列
    if len(options) == 1:
        # 只有一个选项，占满整行
        show_single_upgrade_option(options[0], user_id, color_scheme)
    else:
        # 多个选项，使用列布局
        cols = st.columns(len(options))
        for idx, option in enumerate(options):
            with cols[idx]:
                show_single_upgrade_option(option, user_id, color_scheme)


def show_single_upgrade_option(
    option: dict,
    user_id: int,
    color_scheme: dict
):
    """显示单个升级选项（月付或年付）"""

    cycle_display = option['cycle_display']
    target_price = option['target_price']
    remaining_value = option['remaining_value']
    actual_payment = option['actual_payment']
    features = option['features']

    # 使用容器
    with st.container():
        # 周期标题
        st.markdown(
            f"**{cycle_display}**",
            unsafe_allow_html=True
        )

        # 价格明细
        st.markdown("**💰 价格明细**")

        # 使用 metrics 显示价格信息
        col1, col2 = st.columns(2)
        with col1:
            st.metric("套餐原价", f"¥{target_price:.2f}")
        with col2:
            st.metric(
                "剩余价值折抵",
                f"-¥{remaining_value:.2f}",
                delta=None,
                delta_color="normal"
            )

        # 实际应付
        st.markdown(
            f"""
            <div style="background: {color_scheme['bg']};
                 padding: 15px; border-radius: 8px;
                 border: 2px solid {color_scheme['border']};
                 margin: 10px 0;">
                <div style="text-align: center;">
                    <div style="color: #666; font-size: 14px;">
                        实际应付
                    </div>
                    <div style="color: {color_scheme['text']};
                         font-size: 28px; font-weight: bold;">
                        ¥{actual_payment:.2f}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 功能特色
        with st.expander("✨ 功能特色", expanded=False):
            for feature in features:
                st.write(f"• {feature}")

        # 升级按钮
        button_key = f"upgrade_{option['plan_key']}_{option['cycle']}"

        if actual_payment <= 0:
            # 无需支付，直接升级
            if st.button(
                "🎁 免费升级",
                key=button_key,
                type="primary",
                use_container_width=True
            ):
                handle_free_upgrade(user_id, option)
        else:
            if st.button(
                f"💳 立即升级 - ¥{actual_payment:.2f}",
                key=button_key,
                type="primary",
                use_container_width=True
            ):
                handle_paid_upgrade(user_id, option)

        st.markdown("---")


def handle_free_upgrade(user_id: int, option: dict):
    """处理免费升级（剩余价值已足够抵扣）"""
    with st.spinner("正在处理升级..."):
        result = SubscriptionUpgrade.execute_upgrade(
            user_id=user_id,
            target_plan=option['plan_key'],
            target_cycle=option['cycle'],
            payment_order_id=None
        )

        if result['success']:
            st.success(f"🎉 恭喜！已成功升级到{option['plan_name']}")
            st.balloons()
            st.session_state["current_page"] = "subscription"
            time.sleep(2)
            st.rerun()
        else:
            st.error(f"升级失败: {result.get('message')}")


def handle_paid_upgrade(user_id: int, option: dict):
    """处理需要支付的升级"""

    # 计算支付金额（转为分）
    amount_cents = int(option['actual_payment'] * 100)

    # 构建升级信息
    upgrade_info = {
        'current_plan': st.session_state.get('user', {}).get(
            'subscription_type', 'free'
        ),
        'target_plan': option['plan_key'],
        'target_cycle': option['cycle'],
        'remaining_value': option['remaining_value'],
        'actual_payment': option['actual_payment']
    }

    # 创建升级支付订单
    description = (
        f"套餐升级: {option['plan_name']} - {option['cycle_display']}"
        f"（折抵¥{option['remaining_value']:.2f}）"
    )

    with st.spinner("正在创建支付订单..."):
        result = PaymentHandler.create_payment_order(
            user_id=user_id,
            amount=amount_cents,
            description=description,
            duration=f"1_{option['cycle']}",
            is_upgrade=True,
            upgrade_info=upgrade_info
        )

    if result["success"]:
        order_id = result["order_id"]
        code_url = result["code_url"]

        # 生成二维码
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(code_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, kind='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()

        # 显示支付信息
        st.success("✅ 升级订单创建成功！")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"📋 订单号: {order_id}")
        with col2:
            st.info(f"💰 应付: ¥{option['actual_payment']:.2f}")
        with col3:
            st.info(f"💚 折抵: ¥{option['remaining_value']:.2f}")

        # 显示二维码
        st.markdown("### 📱 请使用微信扫描二维码完成支付")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(
                f"data:image/png;base64,{img_str}",
                use_container_width=True
            )

        st.info("💡 支付完成后将自动升级套餐")

        # 保存订单信息到 session_state
        st.session_state[f'upgrade_order_{order_id}'] = {
            'option': option,
            'order_id': order_id
        }

    else:
        st.error(f"❌ 订单创建失败: {result.get('message')}")
