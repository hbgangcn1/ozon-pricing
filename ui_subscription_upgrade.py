# -*- coding: utf-8 -*-
"""
套餐升级页面
展示升级选项和折抵信息
"""

import streamlit as st
import time
from subscription_upgrade import SubscriptionUpgrade
from payment_handler import PaymentHandler
from db_utils import current_user_id, get_db_connection
from payment_auto_refresh import show_enhanced_auto_check_indicator
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

    # 检查是否有正在进行的升级支付订单
    if 'upgrade_payment_monitoring' in st.session_state:
        monitoring_keys = (
            st.session_state.upgrade_payment_monitoring.keys()
        )
        for order_id in list(monitoring_keys):
            # 检查订单是否已完成支付
            payment_success = check_payment_status_in_db(order_id)
            if payment_success:
                handle_upgrade_payment_success(order_id)
                return

            # 显示订单信息和二维码
            order_info = st.session_state.get(f'upgrade_order_{order_id}')
            if order_info:
                st.success("✅ 升级订单已创建")

                option = order_info['option']
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"📋 订单号: {order_id}")
                with col2:
                    st.info(f"💰 应付: ¥{option['actual_payment']:.2f}")
                with col3:
                    st.info(f"💚 折抵: ¥{option['remaining_value']:.2f}")

                # 显示二维码
                qr_data = st.session_state.get(
                    f'upgrade_payment_qr_{order_id}'
                )
                if qr_data:
                    st.markdown("### 📱 请使用微信扫描二维码完成支付")
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        st.image(
                            f"data:image/png;base64,{qr_data}",
                            width='stretch'
                        )

                # 获取自动检查次数
                monitoring = st.session_state.upgrade_payment_monitoring
                monitoring_info = monitoring.get(order_id, {})
                check_count = monitoring_info.get('auto_check_count', 0)

                # 显示自动检查指示器
                max_checks = 60
                show_enhanced_auto_check_indicator(
                    check_count=check_count,
                    max_checks=max_checks
                )

                # 提示信息
                if check_count >= max_checks:
                    st.warning(
                        "⏰ 已达到最大检查次数。"
                        "如已支付成功但未跳转，请点击下方按钮检查支付状态"
                    )
                else:
                    st.info(
                        "💡 支付完成后将自动跳转，无需手动操作"
                        "（最多等待5分钟）"
                    )

                # 显示手动检查按钮作为备选
                st.markdown("---")
                st.info("💡 也可以点击下方按钮立即检查支付状态")
                if st.button(
                    "🔄 立即检查支付状态",
                    key=f"recheck_upgrade_payment_{order_id}"
                ):
                    monitor_upgrade_payment_status(order_id)

                # 更新检查次数
                monitoring_info['auto_check_count'] = check_count + 1
                st.session_state.upgrade_payment_monitoring[order_id] = (
                    monitoring_info
                )

                # 关键：使用Python自动刷新（每5秒检查一次）
                if check_count < max_checks:
                    print(f"⏰ 准备在5秒后自动刷新（第{check_count}次检查）")
                    time.sleep(5)
                    print("🔄 执行Python自动刷新")
                    st.rerun()

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
        # 特殊处理：如果目标是 efficiency，也包括 efficiency_promo
        if target_plan_key == 'efficiency':
            upgrade_options = [
                opt for opt in upgrade_options
                if opt['plan_key'] in ['efficiency', 'efficiency_promo']
            ]
        else:
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
                use_column_width=True
            ):
                handle_free_upgrade(user_id, option)
        else:
            if st.button(
                f"💳 立即升级 - ¥{actual_payment:.2f}",
                key=button_key,
                type="primary",
                use_column_width=True
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

        # 保存二维码和订单信息到 session_state
        st.session_state[f'upgrade_payment_qr_{order_id}'] = img_str
        st.session_state[f'upgrade_order_{order_id}'] = {
            'option': option,
            'order_id': order_id
        }

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
                width='stretch'
            )

        # 初始化监控状态
        if 'upgrade_payment_monitoring' not in st.session_state:
            st.session_state.upgrade_payment_monitoring = {}

        if order_id not in st.session_state.upgrade_payment_monitoring:
            st.session_state.upgrade_payment_monitoring[order_id] = {
                'check_count': 0,
                'auto_check_count': 0,
                'start_time': time.time()
            }

        # 获取自动检查次数
        monitoring_info = st.session_state.upgrade_payment_monitoring[order_id]
        check_count = monitoring_info.get('auto_check_count', 0)

        # 显示自动检查指示器
        max_checks = 60
        show_enhanced_auto_check_indicator(
            check_count=check_count,
            max_checks=max_checks
        )

        # 提示信息
        if check_count >= max_checks:
            st.warning(
                "⏰ 已达到最大检查次数。"
                "如已支付成功但未跳转，请点击下方按钮检查支付状态"
            )
        else:
            st.info(
                "💡 支付完成后将自动跳转，无需手动操作"
                "（最多等待5分钟）"
            )

        # 显示手动检查按钮作为备选
        st.markdown("---")
        st.info("💡 也可以点击下方按钮立即检查支付状态")
        if st.button(
            "🔄 立即检查支付状态",
            key=f"start_check_upgrade_{order_id}"
        ):
            monitor_upgrade_payment_status(order_id)

        # 更新检查次数
        monitoring_info['auto_check_count'] = check_count + 1
        st.session_state.upgrade_payment_monitoring[order_id] = monitoring_info

        # 关键：使用Python自动刷新（每5秒检查一次）
        if check_count < max_checks:
            print(f"⏰ 准备在5秒后自动刷新（第{check_count}次检查）")
            time.sleep(5)
            print("🔄 执行Python自动刷新")
            st.rerun()

    else:
        st.error(f"❌ 订单创建失败: {result.get('message')}")


def check_payment_status_in_db(order_id: str) -> bool:
    """检查数据库中订单的支付状态"""
    try:
        with get_db_connection() as (conn, cursor):
            cursor.execute("""
                SELECT status FROM payment_orders
                WHERE order_id = ?
            """, (order_id,))

            result = cursor.fetchone()
            if result:
                status = result[0]
                print(
                    f"🔧 数据库订单状态检查: 订单ID={order_id}, 状态={status}"
                )
                # 检查多种可能的成功状态
                return status in ["PAID", "SUCCESS", "SUCCESSFUL"]
            print(f"🔧 数据库订单状态检查: 订单ID={order_id}, 未找到记录")
            return False
    except Exception as e:
        print(f"检查支付状态失败: {e}")
        return False


def handle_upgrade_payment_success(order_id: str):
    """处理升级支付成功后的跳转逻辑"""
    print(f"🔧 handle_upgrade_payment_success 开始: 订单ID={order_id}")
    st.success("🎉 支付成功！正在跳转到订阅管理页面...")

    # 清除监控状态
    if 'upgrade_payment_monitoring' not in st.session_state:
        st.session_state.upgrade_payment_monitoring = {}

    if order_id in st.session_state.upgrade_payment_monitoring:
        del st.session_state.upgrade_payment_monitoring[order_id]
        print(f"🔧 已清除监控状态: {order_id}")

    # 清除支付相关的session state
    if f'upgrade_order_{order_id}' in st.session_state:
        del st.session_state[f'upgrade_order_{order_id}']
        print(f"🔧 已清除订单状态: {order_id}")
    if f'upgrade_payment_qr_{order_id}' in st.session_state:
        del st.session_state[f'upgrade_payment_qr_{order_id}']
        print(f"🔧 已清除二维码状态: {order_id}")

    # 跳转到订阅管理页面
    print("🔧 准备跳转到订阅管理页面")
    time.sleep(2)
    st.session_state["current_page"] = "subscription"
    print("🔧 已设置页面路由: subscription")
    st.rerun()


def monitor_upgrade_payment_status(order_id: str):
    """监控升级支付状态"""
    print(f"🔧 monitor_upgrade_payment_status 开始: 订单ID={order_id}")

    # 首先检查数据库中的支付状态
    print(f"🔧 开始检查数据库支付状态: {order_id}")
    payment_success = check_payment_status_in_db(order_id)
    print(f"🔧 数据库支付状态检查结果: {payment_success}")

    if payment_success:
        print(f"🔧 支付成功，准备跳转: {order_id}")
        handle_upgrade_payment_success(order_id)
        return

    # 如果数据库中没有成功记录，查询微信支付API
    with st.spinner("正在查询支付状态..."):
        try:
            payment_handler = PaymentHandler()
            result = payment_handler.query_payment_status(order_id)
            if result["success"]:
                status = result["status"]
                if status == "SUCCESS":
                    # 支付成功，跳转到订阅管理页面
                    handle_upgrade_payment_success(order_id)
                    return
                elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
                    st.error("❌ 支付失败或已关闭")
                    return
                else:
                    # 支付处理中
                    if 'upgrade_payment_monitoring' not in st.session_state:
                        st.session_state.upgrade_payment_monitoring = {}

                    monitoring = st.session_state.upgrade_payment_monitoring
                    if order_id not in monitoring:
                        return

                    monitoring_info = monitoring[order_id]
                    check_count = monitoring_info.get('check_count', 0)
                    monitoring_info['check_count'] = check_count + 1
                    check_count = monitoring_info['check_count']

                    status_msg = (
                        f"⏳ 支付处理中... (已检查 {check_count} 次)"
                    )
                    st.info(status_msg)
            else:
                # API查询失败，显示错误信息
                error_msg = result.get('message', '未知错误')
                if "签名错误" in error_msg:
                    # 对于签名错误，显示友好提示
                    if 'upgrade_payment_monitoring' not in st.session_state:
                        st.session_state.upgrade_payment_monitoring = {}

                    monitoring = st.session_state.upgrade_payment_monitoring
                    if order_id not in monitoring:
                        return

                    monitoring_info = monitoring[order_id]
                    check_count = monitoring_info.get('check_count', 0)
                    monitoring_info['check_count'] = check_count + 1
                    check_count = monitoring_info['check_count']

                    if check_count <= 3:
                        status_msg = "⏳ 正在检查支付状态..."
                    else:
                        status_msg = (
                            f"⚠️ 查询失败: {error_msg}，继续监控中... "
                            f"(已检查 {check_count} 次)"
                        )

                    st.info(status_msg)
                else:
                    st.error(f"❌ 查询失败: {error_msg}")
                    return
        except Exception as e:
            st.error(f"❌ 查询异常: {str(e)}")
            return

    # 显示手动检查按钮
    st.info("💡 请点击下方按钮继续检查支付状态")
    if st.button("🔄 检查支付状态", key=f"check_upgrade_payment_{order_id}"):
        # 用户点击按钮时，继续监控
        monitor_upgrade_payment_status(order_id)
