# -*- coding: utf-8 -*-
"""
简化的支付界面模块
提供支付相关的用户界面
"""
import streamlit as st
import time
from payment_handler import PaymentHandler
from db_utils import get_db_connection


def check_payment_status_in_db(order_id: str) -> bool:
    """检查数据库中订单的支付状态"""
    try:
        from db_adapter import adapt_sql
        with get_db_connection() as (_, cursor):
            sql = adapt_sql("""
                SELECT status FROM payment_orders
                WHERE order_id = ?
            """)
            cursor.execute(sql, (order_id,))

            result = cursor.fetchone()
            if result:
                status = result[0]
                print(f"🔧 数据库订单状态检查: 订单ID={order_id}, 状态={status}")
                # 检查多种可能的成功状态
                return status in ["PAID", "SUCCESS", "SUCCESSFUL"]
            print(f"🔧 数据库订单状态检查: 订单ID={order_id}, 未找到记录")
            return False
    except Exception as e:
        print(f"检查支付状态失败: {e}")
        return False


def handle_payment_success(order_id: str):
    """处理支付成功后的跳转逻辑"""
    print(f"🔧 handle_payment_success 开始: 订单ID={order_id}")
    st.success("🎉 支付成功！正在跳转到订阅管理页面...")

    # 获取用户ID并清除用户数据缓存
    user_id = None
    if 'user' in st.session_state and st.session_state.user:
        user_id = st.session_state.user.get('id')
    elif 'user_id' in st.session_state:
        user_id = st.session_state.user_id

    if user_id:
        # 清除用户数据缓存，强制下次从数据库重新获取
        cache_key = f'user_data_{user_id}'
        try:
            if (hasattr(st.session_state, '__contains__') and
                    cache_key in st.session_state):
                del st.session_state[cache_key]
                print(f"✅ 已清除用户数据缓存: {cache_key}")
        except (TypeError, AttributeError):
            pass

    # 清除监控状态
    if order_id in st.session_state.payment_monitoring:
        del st.session_state.payment_monitoring[order_id]
        print(f"🔧 已清除监控状态: {order_id}")

    # 清除支付相关的session state
    if f'payment_order_{order_id}' in st.session_state:
        del st.session_state[f'payment_order_{order_id}']
        print(f"🔧 已清除订单状态: {order_id}")
    if f'payment_qr_{order_id}' in st.session_state:
        del st.session_state[f'payment_qr_{order_id}']
        print(f"🔧 已清除二维码状态: {order_id}")

    # 跳转到订阅管理页面
    print("🔧 准备跳转到订阅管理页面")
    time.sleep(2)
    st.session_state["current_page"] = "subscription"
    print("🔧 已设置页面路由: subscription")
    st.rerun()


def monitor_payment_status(
    payment_handler: PaymentHandler, order_id: str, plan_name: str
):
    """监控支付状态"""
    print(f"🔧 monitor_payment_status 开始: 订单ID={order_id}")

    # 首先检查数据库中的支付状态
    print(f"🔧 开始检查数据库支付状态: {order_id}")
    payment_success = check_payment_status_in_db(order_id)
    print(f"🔧 数据库支付状态检查结果: {payment_success}")

    if payment_success:
        print(f"🔧 支付成功，准备跳转: {order_id}")
        handle_payment_success(order_id)
        return

    # 如果数据库中没有成功记录，查询微信支付API
    with st.spinner("正在查询支付状态..."):  # type: ignore[assignment]
        try:
            result = payment_handler.query_payment_status(order_id)
            if result["success"]:
                status = result["status"]
                if status == "SUCCESS":
                    # 支付成功，跳转到订阅管理页面
                    handle_payment_success(order_id)
                    return
                elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
                    st.error("❌ 支付失败或已关闭")
                    return
                else:
                    # 支付处理中
                    if order_id not in st.session_state.payment_monitoring:
                        return

                    monitoring_info = (
                        st.session_state.payment_monitoring[order_id]
                    )
                    check_count = monitoring_info.get('check_count', 0)
                    monitoring_info['check_count'] = check_count + 1
                    check_count = monitoring_info['check_count']

                    status_msg = (
                        f"⏳ 支付处理中... (已检查 {check_count} 次)"
                    )
                    st.session_state[f'payment_status_{order_id}'] = status_msg
                    st.info(status_msg)
            else:
                # API查询失败，显示错误信息
                error_msg = result.get('message', '未知错误')
                if "签名错误" in error_msg:
                    # 对于签名错误，显示友好提示
                    if order_id not in st.session_state.payment_monitoring:
                        return

                    monitoring_info = (
                        st.session_state.payment_monitoring[order_id]
                    )
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

                    st.session_state[f'payment_status_{order_id}'] = status_msg
                    st.info(status_msg)
                else:
                    st.error(f"❌ 查询失败: {error_msg}")
                    return
        except Exception as e:
            st.error(f"❌ 查询异常: {str(e)}")
            return

    # 显示手动检查按钮
    st.info("💡 请点击下方按钮继续检查支付状态")
    if st.button("🔄 检查支付状态", key=f"check_payment_{order_id}"):
        # 用户点击按钮时，继续监控
        monitor_payment_status(payment_handler, order_id, plan_name)


def start_payment_monitoring(
    payment_handler: PaymentHandler, order_id: str, plan_name: str
):
    """启动支付监控"""
    if not order_id:
        st.error("❌ 订单ID无效")
        return

    # 初始化监控状态
    if 'payment_monitoring' not in st.session_state:
        st.session_state.payment_monitoring = {}

    if order_id not in st.session_state.payment_monitoring:
        st.session_state.payment_monitoring[order_id] = {
            'check_count': 0,
            'start_time': time.time()
        }

    # 显示等待信息和手动检查按钮
    st.info("⏳ 等待微信支付系统处理订单...")
    st.progress(0, text="等待中...")

    st.info("💡 请点击下方按钮开始检查支付状态")
    if st.button("🔄 开始检查支付状态", key=f"start_check_{order_id}"):
        # 用户点击按钮时，启动监控
        monitor_payment_status(payment_handler, order_id, plan_name)


def restore_payment_display(order_id: str):
    """恢复支付显示"""
    if not order_id:
        return

    # 显示订单信息
    order_info = st.session_state.get(f'payment_order_{order_id}')
    if order_info:
        st.info(f"📋 订单号: {order_id}")
        amount_yuan = order_info.get('amount', 0) / 100
        st.info(
            f"💰 金额: ¥{amount_yuan}"
        )
        description_text = order_info.get('description', '')
        st.info(
            f"📝 描述: {description_text}"
        )

    # 显示二维码
    qr_data = st.session_state.get(f'payment_qr_{order_id}')
    if qr_data:
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="data:image/png;base64,{qr_data}"
                     style="max-width: 300px;">
            </div>
            """, unsafe_allow_html=True
        )

    # 显示当前状态
    status_msg = st.session_state.get(
        f'payment_status_{order_id}', '⏳ 等待支付...'
    )
    st.info(status_msg)


def create_professional_payment(payment_handler: PaymentHandler):
    """创建专业版支付"""
    st.info("🔄 正在创建专业版支付订单...")

    # 创建支付订单
    result = payment_handler.create_payment_order(
        user_id=st.session_state['user_id'],
        amount=36500,  # 365元
        description="物流系统专业版订阅 - 首月优惠"
    )

    if result["success"]:
        order_id = result["order_id"]
        code_url = result["code_url"]

        # 保存订单信息到session state
        st.session_state[f'payment_order_{order_id}'] = {
            'amount': 36500,
            'description': "物流系统专业版订阅 - 首月优惠"
        }

        # 生成二维码
        import qrcode
        import io
        import base64

        qr_img = qrcode.make(code_url)
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, kind='PNG')
        img_buffer.seek(0)
        img_str = base64.b64encode(img_buffer.getvalue()).decode()

        # 保存二维码到session state
        st.session_state[f'payment_qr_{order_id}'] = img_str

        # 显示支付信息
        st.success("✅ 支付订单创建成功！")
        st.info(f"📋 订单号: {order_id}")
        st.info("💰 金额: ¥365.00")
        st.info("📝 描述: 物流系统专业版订阅 - 首月优惠")

        # 显示二维码
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="data:image/png;base64,{img_str}"
                     style="max-width: 300px;">
            </div>
            """, unsafe_allow_html=True
        )

        # 启动监控
        if order_id:
            start_payment_monitoring(payment_handler, order_id, "专业版")
    else:
        st.error(f"❌ 订单创建失败：{result.get('message', '未知错误')}")


def create_efficiency_payment(payment_handler: PaymentHandler):
    """创建效率版支付"""
    st.info("🔄 正在创建效率版支付订单...")

    # 创建支付订单
    result = payment_handler.create_payment_order(
        user_id=st.session_state['user_id'],
        amount=10000,  # 100元
        description="物流系统效率版订阅 - 首月优惠"
    )

    if result["success"]:
        order_id = result["order_id"]
        code_url = result["code_url"]

        # 保存订单信息到session state
        st.session_state[f'payment_order_{order_id}'] = {
            'amount': 10000,
            'description': "物流系统效率版订阅 - 首月优惠"
        }

        # 生成二维码
        import qrcode
        import io
        import base64

        qr_img = qrcode.make(code_url)
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, kind='PNG')
        img_buffer.seek(0)
        img_str = base64.b64encode(img_buffer.getvalue()).decode()

        # 保存二维码到session state
        st.session_state[f'payment_qr_{order_id}'] = img_str

        # 显示支付信息
        st.success("✅ 支付订单创建成功！")
        st.info(f"📋 订单号: {order_id}")
        st.info("💰 金额: ¥100.00")
        st.info("📝 描述: 物流系统效率版订阅 - 首月优惠")

        # 显示二维码
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="data:image/png;base64,{img_str}"
                     style="max-width: 300px;">
            </div>
            """, unsafe_allow_html=True
        )

        # 启动监控
        if order_id:
            start_payment_monitoring(payment_handler, order_id, "效率版")
    else:
        st.error(f"❌ 订单创建失败：{result.get('message', '未知错误')}")


def check_and_restore_payment_status():
    """检查并恢复支付状态（在页面加载时调用）

    Returns:
        bool: 如果有正在进行的支付返回True，否则返回False
    """
    if ('payment_monitoring' in st.session_state and
            st.session_state.payment_monitoring):
        # 有正在进行的支付，恢复显示
        for order_id in list(st.session_state.payment_monitoring.keys()):
            restore_payment_display(order_id)

            # 显示当前状态和手动检查按钮
            monitoring_info = st.session_state.payment_monitoring[order_id]
            if not monitoring_info.get('first_check_done', False):
                # 第一次检查还没完成，继续等待
                st.info("⏳ 等待微信支付系统处理订单...")
                st.progress(0, text="等待中...")
            else:
                # 已经开始检查，显示当前状态
                current_status = st.session_state.get(
                    f'payment_status_{order_id}', "⏳ 正在检查支付状态..."
                )
                st.info(current_status)

                # 显示手动检查按钮
                st.info("💡 请点击下方按钮手动检查支付状态")
                if st.button(
                    "🔄 检查支付状态", key=f"check_payment_{order_id}"
                ):
                    # 用户点击按钮时，启动监控
                    payment_handler = PaymentHandler()
                    plan_name = monitoring_info.get('plan_name', '未知套餐')
                    monitor_payment_status(
                        payment_handler, order_id, plan_name
                    )
            return True
    return False


def show_payment_page():
    """显示支付页面"""
    st.title("💳 支付中心")

    # 检查用户登录状态
    if 'user_id' not in st.session_state:
        st.error("请先登录")
        return

    # 检查是否有正在进行的支付
    if ('payment_monitoring' in st.session_state and
            st.session_state.payment_monitoring):
        for order_id in list(st.session_state.payment_monitoring.keys()):
            restore_payment_display(order_id)
            return

    # 显示支付选项
    st.markdown("### 选择订阅套餐")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🚀 效率版")
        st.markdown("- 30天有效期")
        st.markdown("- 基础功能")
        st.markdown("- 技术支持")
        st.markdown("**价格: ¥100.00**")

        if st.button("💳 立即购买效率版", key="buy_efficiency"):
            payment_handler = PaymentHandler()
            create_efficiency_payment(payment_handler)

    with col2:
        st.markdown("#### ⭐ 专业版")
        st.markdown("- 365天有效期")
        st.markdown("- 全部功能")
        st.markdown("- 优先技术支持")
        st.markdown("**价格: ¥365.00**")

        if st.button("💳 立即购买专业版", key="buy_professional"):
            payment_handler = PaymentHandler()
            create_professional_payment(payment_handler)
