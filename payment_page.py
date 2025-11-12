"""
独立支付页面
处理订阅升级的支付流程
"""

import os
import streamlit as st
import time
import qrcode
import io
import base64
from payment_handler import PaymentHandler
from db_utils import (
    get_db_connection,
    current_user_id,
    get_plan_price,
    get_plan_by_code,
    _safe_adapt_sql,
)
from payment_auto_refresh import (
    show_enhanced_auto_check_indicator
)
from payment_state_manager import (
    save_payment_state_to_browser,
    clear_payment_state_from_browser
)


def cleanup_payment_state(plan_name: str, order_id: str):
    """清理支付状态"""
    keys_to_remove = [
        f"payment_order_{plan_name}",
        f"payment_qr_{order_id}",
        f"order_creation_time_{order_id}",
        f"last_check_{order_id}",  # 清理检查缓存
        'auto_check_count',
        f"payment_duration_{plan_name}"  # 清理时长选择
    ]
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]


def show_duration_selection(plan_name: str):
    """显示购买时长选择对话框"""
    st.markdown("---")
    st.markdown("### ⏱️ 选择购买时长")

    # 检查用户是否使用过效率版首月优惠
    user_id = current_user_id()
    promo_used = False

    if "效率版" in plan_name:
        with get_db_connection() as (conn, cursor):
            sql = _safe_adapt_sql(
                "SELECT efficiency_promo_used FROM users WHERE id = ?",
                conn
            )
            cursor.execute(sql, (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                promo_used = True

    # 根据套餐类型显示不同的选项
    if "效率版" in plan_name:
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #E8F5E8, #C8E6C9);
                 border-radius: 15px; padding: 20px; margin-bottom: 20px;">
                <h4 style="color: #4CAF50; margin-bottom: 15px;">💚 效率版套餐</h4>
                <p style="color: #2E7D32; font-size: 1.1rem; margin: 0;">
                    无限次极速模式计算 + 3个物流模板
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:
            # 月付选项
            if not promo_used:
                st.markdown(
                    """
                    <div style="background: linear-gradient(135deg,
                         #FFF3E0, #FFE0B2);
                         border-radius: 12px; padding: 20px;
                         margin-bottom: 15px;
                         border: 3px solid #FF9800;">
                        <h4 style="color: #E65100; text-align: center;
                            margin-bottom: 10px;">
                            🎉 首月特惠
                        </h4>
                        <h2 style="color: #F57C00; text-align: center;
                            margin: 15px 0;">
                            ¥1
                        </h2>
                        <p style="text-align: center; color: #EF6C00;
                            margin: 0; font-size: 0.9rem;">
                            仅首月，次月起¥9.9/月
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div style="background: linear-gradient(135deg,
                         #E8F5E8, #C8E6C9);
                         border-radius: 12px; padding: 20px;
                         margin-bottom: 15px;">
                        <h4 style="color: #4CAF50; text-align: center;
                            margin-bottom: 10px;">
                            📅 月付套餐
                        </h4>
                        <h2 style="color: #2E7D32; text-align: center;
                            margin: 15px 0;">
                            ¥9.9
                        </h2>
                        <p style="text-align: center; color: #388E3C;
                            margin: 0; font-size: 0.9rem;">
                            按月续费
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            if st.button(
                "购买1个月" if promo_used else "首月仅需¥1",
                key="duration_1_month",
                width='stretch',
                type="primary" if not promo_used else "secondary"
            ):
                st.session_state[f"payment_duration_{plan_name}"] = "1_month"
                st.rerun()

        with col2:
            # 年付选项
            st.markdown(
                """
                <div style="background: linear-gradient(135deg,
                     #E3F2FD, #BBDEFB);
                     border-radius: 12px; padding: 20px;
                     margin-bottom: 15px;">
                    <h4 style="color: #1976D2; text-align: center;
                        margin-bottom: 10px;">
                        💎 年付套餐
                    </h4>
                    <h2 style="color: #0D47A1; text-align: center;
                        margin: 15px 0;">
                        ¥99
                    </h2>
                    <p style="text-align: center; color: #1565C0;
                        margin: 0; font-size: 0.9rem;">
                        相当于¥8.25/月，省16%
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                "购买1年",
                key="duration_1_year",
                width='stretch'
            ):
                st.session_state[f"payment_duration_{plan_name}"] = "1_year"
                st.rerun()

    elif "专业版" in plan_name:
        st.markdown(
            """
            <div style="background: linear-gradient(135deg,
                 #E3F2FD, #BBDEFB);
                 border-radius: 15px; padding: 20px; margin-bottom: 20px;">
                <h4 style="color: #2196F3; margin-bottom: 15px;">
                    ⭐ 专业版套餐
                </h4>
                <p style="color: #1565C0; font-size: 1.1rem; margin: 0;">
                    极速+精准双模式 + 无限物流模板 + 多物流比价
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:
            # 月付选项
            st.markdown(
                """
                <div style="background: linear-gradient(135deg,
                     #E3F2FD, #BBDEFB);
                     border-radius: 12px; padding: 20px;
                     margin-bottom: 15px;">
                    <h4 style="color: #2196F3; text-align: center;
                        margin-bottom: 10px;">
                        📅 月付套餐
                    </h4>
                    <h2 style="color: #1976D2; text-align: center;
                        margin: 15px 0;">
                        ¥149
                    </h2>
                    <p style="text-align: center; color: #1565C0;
                        margin: 0; font-size: 0.9rem;">
                        按月续费
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                "购买1个月",
                key="duration_1_month",
                width='stretch'
            ):
                st.session_state[f"payment_duration_{plan_name}"] = "1_month"
                st.rerun()

        with col2:
            # 年付选项
            st.markdown(
                """
                <div style="background: linear-gradient(135deg,
                     #F3E5F5, #E1BEE7);
                     border-radius: 12px; padding: 20px;
                     margin-bottom: 15px;">
                    <h4 style="color: #9C27B0; text-align: center;
                        margin-bottom: 10px;">
                        💎 年付套餐
                    </h4>
                    <h2 style="color: #7B1FA2; text-align: center;
                        margin: 15px 0;">
                        ¥1499
                    </h2>
                    <p style="text-align: center; color: #8E24AA;
                        margin: 0; font-size: 0.9rem;">
                        相当于¥124.9/月，省16%
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                "购买1年",
                key="duration_1_year",
                width='stretch'
            ):
                st.session_state[f"payment_duration_{plan_name}"] = "1_year"
                st.rerun()

    st.markdown("---")
    if st.button("🏠 返回首页", key="back_to_home_from_duration"):
        st.session_state["current_page"] = "main"
        st.rerun()


def handle_payment_success(order_id: str, plan_name: str):
    """处理支付成功"""
    print(f"🎉 检测到支付成功: {order_id}")
    st.balloons()
    st.success("🎉 支付成功！正在跳转到主界面...")

    # 获取用户ID并清除用户数据缓存
    user_id = current_user_id()
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

    # 如果是效率版首月优惠订单，标记用户已使用优惠
    promo_mark_key = f"mark_efficiency_promo_{order_id}"
    if promo_mark_key in st.session_state and st.session_state[promo_mark_key]:
        if user_id:
            try:
                with get_db_connection() as (conn, cursor):
                    cursor.execute(
                        "UPDATE users SET efficiency_promo_used = 1 "
                        "WHERE id = ?",
                        (user_id,)
                    )
                    conn.commit()
                    print(f"✅ 已标记用户 {user_id} 使用过效率版首月优惠")
            except Exception as e:
                print(f"⚠️ 标记首月优惠使用失败: {e}")
        # 清除标记
        del st.session_state[promo_mark_key]

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

    # 清除浏览器端的支付状态
    clear_payment_state_from_browser()

    # 清理支付相关状态
    cleanup_payment_state(plan_name, order_id)

    # 重置"已显示"标记，确保下次支付能正常显示通知
    if '_payment_success_shown' in st.session_state:
        del st.session_state['_payment_success_shown']

    payment_keys_after = [
        k for k in st.session_state.keys()
        if isinstance(k, str) and 'payment' in k
    ]
    print(f"清理状态后: {payment_keys_after}")

    # 跳转到主界面（带有完整的侧边栏和标签页）
    time.sleep(1.5)
    st.session_state["current_page"] = "main"
    print("🔄 触发页面跳转到主界面")
    st.rerun()


def auto_check_and_redirect(order_id: str, plan_name: str):
    """
    自动检查支付状态并在成功时重定向
    这个函数在每次页面刷新时静默执行
    """
    print(f"🔍 开始自动检查订单: {order_id}")

    # 检查缓存（最近2秒内查过就不重复查询，减少数据库压力）
    cache_key = f"last_check_{order_id}"
    last_check = st.session_state.get(cache_key, 0)
    if time.time() - last_check < 2:
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
            sql = _safe_adapt_sql(
                """
                SELECT status, created_at FROM payment_orders
                WHERE order_id = ?
                """,
                conn
            )
            cursor.execute(sql, (order_id,))
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

    # 注意：由于iframe沙箱限制，无法使用JavaScript导航或URL参数恢复
    # 当前采用Python time.sleep + st.rerun 的自动刷新机制
    # 依赖session_state在服务稳定运行时的持久化

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
        # 检查是否已选择购买时长
        duration_key = f"payment_duration_{plan_name}"
        if duration_key not in st.session_state:
            # 显示时长选择对话框
            show_duration_selection(plan_name)
        else:
            # 已选择时长，创建订单
            create_new_payment(plan_name, payment_handler)


def show_existing_payment(
    order_id: str, plan_name: str, payment_handler: PaymentHandler
):
    """显示已有订单的支付信息（带智能自动检查）"""

    # 初始化自动检查计数器（从session_state获取，用于显示）
    if 'auto_check_count' not in st.session_state:
        st.session_state['auto_check_count'] = 0

    # 先检查支付状态（如果成功会触发跳转）
    auto_check_and_redirect(order_id, plan_name)

    # 如果支付未成功，继续显示页面并准备下一次检查
    st.session_state['auto_check_count'] += 1
    check_count = st.session_state['auto_check_count']

    # 显示增强的自动检查指示器（带进度条）
    max_checks = 60
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

        # 醒目的支付提示
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        ">
            <div style="font-size: 24px; margin-bottom: 10px;">💳</div>
            <div style="
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 8px;
            ">
                支付完成后，若未自动跳转，请点击下方按钮
            </div>
            <div style="font-size: 14px; opacity: 0.9;">
                通常会在5秒内自动跳转
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 检查支付状态按钮 - 使用type="primary"使其更显眼
        if st.button(
            "🔍 检查支付状态",
            key="check_payment_status",
            type="primary",
            width='stretch'
        ):
            with st.spinner("正在检查支付状态..."):
                # 1) 优先查询数据库（可靠、低延迟）
                order_key = f"payment_order_{plan_name}"
                qr_key = f"payment_qr_{order_id}"
                paid_in_db = False
                try:
                    with get_db_connection() as (conn, cursor):
                        sql = _safe_adapt_sql(
                            """
                            SELECT status FROM payment_orders
                            WHERE order_id = ?
                            """,
                            conn
                        )
                        cursor.execute(sql, (order_id,))
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
                        "🎉 支付成功！正在跳转到主界面..."
                    )
                    st.success(success_msg)
                    if order_key in st.session_state:
                        del st.session_state[order_key]
                    if qr_key in st.session_state:
                        del st.session_state[qr_key]
                    time.sleep(1)
                    st.session_state["current_page"] = "main"
                    st.rerun()
                else:
                    # 2) 回退调用微信查询接口
                    result = payment_handler.query_payment_status(order_id)

                    if result.get("success"):
                        status = result.get("status")
                        if status == "SUCCESS":
                            success_msg = (
                                "🎉 支付成功！正在跳转到主界面..."
                            )
                            st.success(success_msg)
                            if order_key in st.session_state:
                                del st.session_state[order_key]
                            if qr_key in st.session_state:
                                del st.session_state[qr_key]
                            time.sleep(1)
                            st.session_state["current_page"] = "main"
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
                            "签名错误" in error_msg or
                            "signature" in error_msg.lower()
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

    # 关键：在所有UI显示完成后，添加Python自动刷新
    # 优化轮询间隔到3秒，提升支付体验
    if check_count < max_checks:
        print(f"⏰ 准备在3秒后自动刷新（第{check_count}次检查）")
        time.sleep(3)
        print("🔄 执行Python自动刷新")
        st.rerun()


def create_new_payment(plan_name: str, payment_handler: PaymentHandler):
    """创建新的支付订单"""
    st.info("🔄 正在创建支付订单...")

    # 获取选择的购买时长
    duration_key = f"payment_duration_{plan_name}"
    duration = st.session_state.get(duration_key, None)

    if not duration:
        st.error("❌ 未选择购买时长，请返回重新选择")
        if st.button("返回选择时长"):
            if duration_key in st.session_state:
                del st.session_state[duration_key]
            st.rerun()
        return

    with st.spinner("创建订单中..."):
        # 获取当前用户ID
        user_id = current_user_id()
        if not user_id:
            st.error("❌ 请先登录")
            return

        # 检查是否使用过效率版首月优惠
        promo_used = False
        if "效率版" in plan_name:
            with get_db_connection() as (conn, cursor):
                sql = _safe_adapt_sql(
                    "SELECT efficiency_promo_used FROM users WHERE id = ?",
                    conn
                )
                cursor.execute(sql, (user_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    promo_used = True

        # 从数据库获取价格配置
        # 映射plan_name到plan_code
        plan_code_map = {
            "效率版": "efficiency",
            "专业版": "professional",
            "企业版": "enterprise",
        }

        plan_code = None
        for key, value in plan_code_map.items():
            if key in plan_name:
                plan_code = value
                break

        if not plan_code:
            st.error("❌ 未知的订阅计划")
            return

        # 获取套餐配置
        plan_config = get_plan_by_code(plan_code)
        if not plan_config:
            st.error("❌ 套餐配置不存在")
            return

        # 检查套餐是否上架
        if not plan_config['is_active']:
            st.error("❌ 该套餐暂未开放")
            return

        # 判断是否使用测试价格（根据TEST_MODE环境变量）
        # 如果TEST_MODE=true，所有用户都使用测试价格
        # 如果TEST_MODE=false，只有管理员使用测试价格
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        is_user_admin = False
        with get_db_connection() as (conn, c):
            sql = _safe_adapt_sql(
                "SELECT role FROM users WHERE id = ?",
                conn
            )
            c.execute(sql, (user_id,))
            user_role = c.fetchone()
            if user_role and user_role[0] == 'admin':
                is_user_admin = True

        # 根据duration映射到month/year
        duration_map = {
            "1_month": "month",
            "1_year": "year"
        }
        price_duration = duration_map.get(duration, "month")

        # 获取价格：TEST_MODE=true时所有用户使用测试价，否则只有管理员使用测试价
        use_test_price = test_mode or is_user_admin
        price = get_plan_price(
            plan_code, price_duration, use_test_price=use_test_price
        )

        # 特殊处理：效率版首月优惠
        # 条件：1. 目标套餐是效率版 2. 选择1个月 3. 用户未使用过优惠
        # 4. 用户当前是免费版（从免费版升级到效率版）
        is_efficiency_promo = False
        if (plan_code == "efficiency" and duration == "1_month" and
                not promo_used):
            # 检查用户当前套餐是否为免费版
            with get_db_connection() as (conn, c):
                sql = _safe_adapt_sql(
                    "SELECT subscription_type, user_type FROM users "
                    "WHERE id = ?",
                    conn
                )
                c.execute(sql, (user_id,))
                user_info = c.fetchone()
                if user_info and len(user_info) >= 2:
                    subscription_type = user_info[0]
                    user_type = user_info[1]
                    # 如果订阅类型是free或None，或者user_type是free，则可以使用优惠
                    if (not subscription_type or subscription_type == 'free' or
                            user_type == 'free'):
                        is_efficiency_promo = True

        if is_efficiency_promo:
            amount = 100  # 首月1元优惠
            description = f"物流系统{plan_name}订阅 - 首月优惠(1个月)"
        else:
            # 转换为分（微信支付单位）
            amount = int(price * 100)
            duration_text = "1个月" if duration == "1_month" else "12个月"
            description = f"物流系统{plan_name}订阅 - {duration_text}"

        # 创建支付订单
        result = payment_handler.create_payment_order(
            user_id=user_id,
            amount=amount,
            description=description,
            duration=duration  # 传递时长参数（1_month 或 1_year）
        )

        if result["success"]:
            order_id = result["order_id"]
            code_url = result["code_url"]

            # 保存订单信息到session_state
            st.session_state[f"payment_order_{plan_name}"] = order_id
            # 保存订单创建时间（用于超时检查）
            st.session_state[f"order_creation_time_{order_id}"] = time.time()

            # 保存到浏览器localStorage（关键！）
            save_payment_state_to_browser(order_id, plan_name)

            # 如果是效率版首月优惠，标记在session_state中（支付成功后使用）
            if "效率版" in plan_name and duration == "1_month" and not promo_used:
                st.session_state[f"mark_efficiency_promo_{order_id}"] = True

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
