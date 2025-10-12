# -*- coding: utf-8 -*-
"""
套餐升级页面
展示升级选项和折抵信息
"""

import streamlit as st
import time
from subscription_upgrade import SubscriptionUpgrade, SUBSCRIPTION_PLANS
from payment_handler import PaymentHandler
from db_utils import current_user_id
import qrcode
import io
import base64


def show_subscription_upgrade_page():
    """显示套餐升级页面"""
    
    st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #667eea; margin-bottom: 10px;">
                📈 套餐升级
            </h1>
            <p style="color: #718096; font-size: 1.1rem;">
                升级享受更多功能，剩余时间自动折抵
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # 检查用户登录
    user_id = current_user_id()
    if not user_id:
        st.error("请先登录")
        return
    
    # 获取升级选项
    options_result = SubscriptionUpgrade.get_upgrade_options(user_id)
    
    if not options_result['success']:
        st.error(f"获取升级选项失败: {options_result.get('message')}")
        return
    
    # 显示当前套餐信息
    current_plan_name = options_result['current_plan_name']
    
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
             color: white; padding: 20px; border-radius: 15px;
             margin-bottom: 30px;">
            <h3 style="margin: 0;">当前套餐: {current_plan_name}</h3>
        </div>
    """, unsafe_allow_html=True)
    
    # 获取升级选项
    upgrade_options = options_result['upgrade_options']
    
    if not upgrade_options:
        st.info("✅ 您已经是最高级别套餐，无需升级")
        if st.button("🏠 返回首页"):
            st.session_state["current_page"] = "main"
            st.rerun()
        return
    
    # 显示升级选项
    st.markdown("### 📊 可选升级方案")
    
    for option in upgrade_options:
        show_upgrade_option(option, user_id)
    
    # 返回按钮
    st.markdown("---")
    if st.button("🏠 返回首页", key="back_to_home"):
        st.session_state["current_page"] = "main"
        st.rerun()


def show_upgrade_option(option: dict, user_id: int):
    """显示单个升级选项卡片"""
    
    plan_key = option['plan_key']
    plan_name = option['plan_name']
    cycle_display = option['cycle_display']
    target_price = option['target_price']
    remaining_value = option['remaining_value']
    actual_payment = option['actual_payment']
    features = option['features']
    
    # 选择卡片颜色
    if plan_key == 'efficiency':
        gradient = "linear-gradient(135deg, #E8F5E8, #C8E6C9)"
        color = "#4CAF50"
    elif plan_key == 'professional':
        gradient = "linear-gradient(135deg, #E3F2FD, #BBDEFB)"
        color = "#2196F3"
    elif plan_key == 'enterprise':
        gradient = "linear-gradient(135deg, #F3E5F5, #E1BEE7)"
        color = "#9C27B0"
    else:
        gradient = "linear-gradient(135deg, #FFF3E0, #FFE0B2)"
        color = "#FF9800"
    
    # 构建卡片HTML
    with st.container():
        st.markdown(f"""
            <div style="background: {gradient};
                 border-radius: 15px; padding: 25px; margin-bottom: 20px;
                 border: 2px solid {color};">
                <h3 style="color: {color}; margin-bottom: 15px;">
                    {plan_name} - {cycle_display}
                </h3>
                
                <div style="background: white; padding: 15px;
                     border-radius: 10px; margin-bottom: 15px;">
                    <h4 style="color: #333; margin-bottom: 10px;">
                        💰 价格明细
                    </h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">
                                套餐原价
                            </td>
                            <td style="padding: 8px; text-align: right;
                                 border-bottom: 1px solid #ddd;">
                                ¥{target_price:.2f}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;
                                 color: #27ae60;">
                                剩余价值折抵
                            </td>
                            <td style="padding: 8px; text-align: right;
                                 border-bottom: 1px solid #ddd; color: #27ae60;">
                                -¥{remaining_value:.2f}
                            </td>
                        </tr>
                        <tr style="background: #f8f9fa;">
                            <td style="padding: 12px; font-weight: bold;
                                 font-size: 1.2em;">
                                实际应付
                            </td>
                            <td style="padding: 12px; text-align: right;
                                 font-weight: bold; font-size: 1.2em;
                                 color: #e74c3c;">
                                ¥{actual_payment:.2f}
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="background: white; padding: 15px;
                     border-radius: 10px;">
                    <h4 style="color: #333; margin-bottom: 10px;">
                        ✨ 功能特色
                    </h4>
                    <ul style="margin: 0; padding-left: 20px; color: #555;">
                        {''.join([f'<li>{feature}</li>' for feature in features])}
                    </ul>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # 升级按钮
        button_key = f"upgrade_{plan_key}_{option['cycle']}"
        if actual_payment <= 0:
            # 无需支付，直接升级
            if st.button(
                f"🎁 免费升级到{plan_name}（{cycle_display}）",
                key=button_key,
                type="primary"
            ):
                handle_free_upgrade(user_id, option)
        else:
            if st.button(
                f"💳 升级到{plan_name}（{cycle_display}）- ¥{actual_payment:.2f}",
                key=button_key,
                type="primary"
            ):
                handle_paid_upgrade(user_id, option)


def handle_free_upgrade(user_id: int, option: dict):
    """处理免费升级（剩余价值已足够抵扣）"""
    st.info("正在处理升级...")
    
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
        st.info(f"📋 订单号: {order_id}")
        st.info(f"💰 应付金额: ¥{option['actual_payment']:.2f}")
        st.info(f"📝 {description}")
        
        # 显示二维码
        st.markdown(
            f"""
            <div style="text-align: center; margin: 20px 0;">
                <h4>📱 请使用微信扫描二维码完成支付</h4>
                <img src="data:image/png;base64,{img_str}"
                     style="max-width: 300px; border: 1px solid #ddd;
                            border-radius: 8px; margin: 10px 0;">
                <p style="color: #888; font-size: 14px;">
                    支付完成后将自动升级套餐
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # 保存订单信息到 session_state
        st.session_state[f'upgrade_order_{order_id}'] = {
            'option': option,
            'order_id': order_id
        }
        
    else:
        st.error(f"❌ 订单创建失败: {result.get('message')}")

