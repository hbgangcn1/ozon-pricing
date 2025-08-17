import streamlit as st
from typing import Optional

try:
    from .db_utils import (
        init_db, check_user_subscription_status, update_user_password,
    )
    from .exchange_service import ExchangeRateService, get_usd_rate
    from .ui_user import user_management_page, login_or_register_page
    from .ui_products import products_page
    from .ui_logistics import logistics_page
    from .ui_pricing import pricing_calculator_page
    from .password_utils import (
        validate_password_strength, get_password_requirements_text,
    )
    from .auto_backup import (
        create_manual_backup, get_backup_info, start_backup_service,
    )
    from .session_security import (
        check_session_security, SessionSecurity, secure_logout,
    )
except ImportError:  # Fallback when run as a top-level module
    from db_utils import (
        init_db, check_user_subscription_status, update_user_password,
    )
    from exchange_service import ExchangeRateService, get_usd_rate
    from ui_user import user_management_page, login_or_register_page
    from ui_products import products_page
    from ui_logistics import logistics_page
    from ui_pricing import pricing_calculator_page
    from password_utils import (
        validate_password_strength, get_password_requirements_text,
    )
    from auto_backup import (
        create_manual_backup, get_backup_info, start_backup_service,
    )
    from session_security import (
        check_session_security, SessionSecurity, secure_logout,
    )

# 设置页面配置
st.set_page_config(
    page_title="物流定价系统",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
/* 全局背景 - 经典白色主题 */
.stApp {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    min-height: 100vh;
}

/* 侧边栏样式 */
.sidebar .sidebar-content {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(0, 0, 0, 0.1);
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

/* 按钮样式 - 现代蓝色主题 */
.stButton > button {
    background: linear-gradient(45deg, #2196F3, #1976D2);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(33, 150, 243, 0.3);
}

.stButton > button:hover {
    background: linear-gradient(45deg, #1976D2, #1565C0);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(33, 150, 243, 0.4);
}

/* 输入框样式 */
.stTextInput > div > div > input {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 10px 12px;
    transition: border-color 0.3s ease;
}

.stTextInput > div > div > input:focus {
    border-color: #2196F3;
    box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
}

/* 选择框样式 */
.stSelectbox > div > div > select {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 8px 12px;
    transition: border-color 0.3s ease;
}

.stSelectbox > div > div > select:focus {
    border-color: #2196F3;
    box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.1);
}

/* 卡片容器 - 现代卡片设计 */
.card-container {
    background: white;
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.05);
    transition: box-shadow 0.3s ease;
}

.card-container:hover {
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

/* 标题样式 - 深色文字 */
.custom-title {
    color: #2c3e50;
    text-align: center;
    font-size: 2.2em;
    font-weight: 700;
    margin-bottom: 30px;
    letter-spacing: -0.5px;
}

/* 消息样式 */
.custom-message {
    background: white;
    border-radius: 8px;
    padding: 16px;
    margin: 12px 0;
    border-left: 4px solid #2196F3;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 数据框样式 */
.dataframe {
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 表单样式 */
.stForm {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    border: 1px solid rgba(0, 0, 0, 0.05);
}

/* 扩展器样式 */
.streamlit-expanderHeader {
    background: white !important;
    border-radius: 8px !important;
    border: 1px solid #e0e0e0 !important;
    font-weight: 600 !important;
}

/* 侧边栏标题样式 */
.sidebar .sidebar-content h1,
.sidebar .sidebar-content h2,
.sidebar .sidebar-content h3 {
    color: #2c3e50 !important;
}

/* 主标题样式 */
.main-title {
    color: #2c3e50;
    font-size: 2.2em;
    font-weight: 700;
    text-align: center;
    margin-bottom: 1rem;
    letter-spacing: -0.5px;
}

/* 副标题样式 */
.sub-title {
    color: #34495e;
    font-size: 1.4em;
    font-weight: 600;
    margin-bottom: 1rem;
}

/* 成功消息样式 */
.stSuccess {
    background: #e8f5e8 !important;
    border-left: 4px solid #4caf50 !important;
    color: #2e7d32 !important;
}

/* 错误消息样式 */
.stError {
    background: #ffebee !important;
    border-left: 4px solid #f44336 !important;
    color: #c62828 !important;
}

/* 警告消息样式 */
.stWarning {
    background: #fff3e0 !important;
    border-left: 4px solid #ff9800 !important;
    color: #ef6c00 !important;
}

/* 信息消息样式 */
.stInfo {
    background: #e3f2fd !important;
    border-left: 4px solid #2196f3 !important;
    color: #1565c0 !important;
}
</style>
""", unsafe_allow_html=True)


def settings_page():
    """设置页面"""
    st.markdown('<h1 class="custom-title">⚙️ 系统设置</h1>',
                unsafe_allow_html=True)

    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.markdown(
        '<h2 style="color: #667eea; margin-bottom: 20px;">'
        '🔐 账户管理</h2>',
        unsafe_allow_html=True
    )

    # 修改密码 - 使用show_password_change_form函数
    show_password_change_form()

    st.markdown('</div>', unsafe_allow_html=True)

    # 备份管理
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.markdown(
        '<h2 style="color: #667eea; margin-bottom: 20px;">'
        '💾 备份管理</h2>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📦 立即备份", help="手动创建数据库备份"):
            if create_manual_backup():
                st.success("✅ 备份创建成功！")
            else:
                st.error("❌ 备份创建失败！")

    with col2:
        if st.button("🔄 刷新状态", help="刷新备份状态信息"):
            st.rerun()

    # 显示备份统计信息
    backup_stats = get_backup_info()
    if backup_stats:
        st.write(f"**备份文件数量：** {backup_stats['count']} 个")
        st.write(f"**总备份大小：** {backup_stats['total_size_mb']} MB")

        if backup_stats['files']:
            st.write("**最新备份文件：**")
            for i, file in enumerate(backup_stats['files'][:3]):
                st.write(f"  {i+1}. {file['name']} "
                         f"({file['mtime'].strftime('%Y-%m-%d %H:%M:%S')})")
    else:
        st.warning("⚠️ 无法获取备份信息")

    st.markdown('</div>', unsafe_allow_html=True)

    # 系统信息
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.markdown(
        '<h2 style="color: #667eea; margin-bottom: 20px;">'
        'ℹ️ 系统信息</h2>',
        unsafe_allow_html=True
    )

    st.write(f"**当前用户：** {st.session_state.user['username']}")
    st.write(f"**用户角色：** {st.session_state.user['role']}")

    # 显示会话安全信息
    session_info = SessionSecurity.get_session_info(
        st.session_state.get('session_id', '')
    )
    if session_info:
        import time
        last_activity_str = time.strftime(
            '%H:%M:%S', time.localtime(session_info['last_activity']))
        st.write(f"**最后活动：** {last_activity_str}")

        # 简化的会话信息显示
        st.write(f"**会话ID：** {session_info['session_id'][:8]}...")

    st.markdown('</div>', unsafe_allow_html=True)


def show_main_interface():
    """显示主界面"""
    from typing import Dict, Any
    current_user: Dict[str, Any] = st.session_state.user

    # 检查用户订阅状态
    subscription_status = check_user_subscription_status(current_user['id'])

    # 美化侧边栏
    st.sidebar.markdown(
        f"""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="color: #2196F3; margin-bottom: 8px;
                font-size: 2.5em;">🚢</h1>
            <h2 style="color: #2c3e50; margin-bottom: 4px;
                font-size: 1.1em;">欢迎回来</h2>
            <h3 style="color: #2196F3; margin-bottom: 8px;
                font-size: 1.3em; font-weight: 600;">
                {current_user['username']}
            </h3>
            <div style="background: linear-gradient(135deg, #2196F3 0%,
                        #1976D2 100%); color: white; padding: 6px 16px;
                        border-radius: 20px; font-size: 12px;
                        font-weight: 500; display: inline-block;
                        box-shadow: 0 2px 8px rgba(33, 150, 243, 0.3);">
                {current_user['role']}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 显示订阅状态
    if not subscription_status.get('valid', False):
        st.sidebar.error("⚠️ 账号已到期，请联系客服续费")
    else:
        # 显示到期时间（如果有）
        if 'remaining_days' in subscription_status:
            st.sidebar.info(
                f"📅 到期时间：{subscription_status['remaining_days']}天后"
            )

        # 显示剩余计算次数（如果是按月付费用户）
        if 'remaining_calculations' in subscription_status:
            st.sidebar.info(
                f"🔢 剩余计算次数："
                f"{subscription_status['remaining_calculations']}次"
            )

    menu_options = [
        "产品管理", "物流规则", "定价计算器", "设置"
    ]
    if current_user["role"] == "admin":
        menu_options.insert(-1, "用户管理")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 功能导航")
    selected_page = st.sidebar.selectbox("选择功能", menu_options)

    if selected_page == "产品管理":
        products_page()
    elif selected_page == "物流规则":
        logistics_page()
    elif selected_page == "定价计算器":
        pricing_calculator_page()
    elif selected_page == "用户管理":
        user_management_page()
    elif selected_page == "设置":
        settings_page()

    # 添加分隔线和退出登录按钮
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔐 账户管理")
    if st.sidebar.button(
        "🚪 退出登录",
        key="logout",
        help="点击退出当前用户登录"
    ):
        secure_logout()


def show_password_change_form():
    """显示密码修改表单"""
    st.subheader("🔒 修改密码")

    with st.form("password_change_form"):
        current_password = st.text_input("当前密码", type="password")
        new_password = st.text_input(
            "新密码", type="password", help=get_password_requirements_text()
        )
        confirm_password = st.text_input("确认新密码", type="password")

        submitted = st.form_submit_button("修改密码")

        if submitted:
            if (not current_password or not new_password or
                    not confirm_password):
                st.error("请填写所有字段")
                return

            if new_password != confirm_password:
                st.error("新密码和确认密码不匹配")
                return

            # 验证密码强度
            password_validation = validate_password_strength(new_password)
            if not password_validation['valid']:
                st.error("密码强度不符合要求：")
                for error in password_validation['errors']:
                    st.error(f"• {error}")
                return
            # 验证当前密码并更新
            user_id = st.session_state.user['id']
            if update_user_password(user_id, current_password, new_password):
                st.success("密码修改成功！")
            else:
                st.error("当前密码错误")


def main():
    init_db()
    # 初始化会话安全相关数据表，防止首次启动时表缺失
    SessionSecurity.init_session_tables()

    # 检查会话安全性
    if not check_session_security():
        login_or_register_page()
        return

    # 如果会话有效，显示主界面
    show_main_interface()


def _debug_filter_reason(logistic: dict, product: dict) -> Optional[str]:
    """检查物流被淘汰的原因"""
    """
    返回物流被淘汰的详细原因；若完全可用则返回 None。
    与 calculate_logistic_cost() 的判断逻辑保持 100% 一致。
    """

    # ---------- 1. 重量 ----------
    # 计算体积重量
    length_cm = product.get("length_cm", 0)
    width_cm = product.get("width_cm", 0)
    height_cm = product.get("height_cm", 0)
    volume_mode = logistic.get("volume_mode", "none")
    volume_coefficient = logistic.get("volume_coefficient", 5000)

    if volume_mode == "max_actual_vs_volume":
        volume_weight = (
            length_cm * width_cm * height_cm
        ) / volume_coefficient
        actual_weight = product.get("weight_g", 0) / 1000  # 转换为千克
        calculated_weight = (
            max(actual_weight, volume_weight) * 1000
        )  # 转换回克
    elif volume_mode == "longest_side":
        longest_side_threshold = logistic.get("longest_side_threshold", 0)
        longest_side = max(length_cm, width_cm, height_cm)
        if longest_side > longest_side_threshold:
            volume_weight = (
                length_cm * width_cm * height_cm
            ) / volume_coefficient
            actual_weight = product.get("weight_g", 0) / 1000  # 转换为千克
            calculated_weight = (
                max(actual_weight, volume_weight) * 1000
            )  # 转换回克
        else:
            calculated_weight = product.get("weight_g", 0)
    else:
        calculated_weight = product.get("weight_g", 0)

    w = calculated_weight
    min_w = logistic.get("min_weight", 0)
    max_w = logistic.get("max_weight", 10**9)
    if w < min_w:
        return f"重量 {w} g 低于下限 {min_w} g"
    if w > max_w:
        return f"重量 {w} g 高于上限 {max_w} g"

    # ---------- 2. 边长 ----------
    # 获取产品包装形状
    is_cylinder = product.get("is_cylinder", False)

    if is_cylinder:
        # 圆柱形包装产品
        cylinder_diameter = product.get("cylinder_diameter", 0)
        cylinder_length = product.get("cylinder_length", 0)

        # 首先检查物流是否有圆柱形包装限制
        has_cylinder_limits = (
            logistic.get("max_cylinder_sum", 0) > 0
            or logistic.get("min_cylinder_sum", 0) > 0
            or logistic.get("max_cylinder_length", 0) > 0
            or logistic.get("min_cylinder_length", 0) > 0
        )

        if has_cylinder_limits:
            # 使用圆柱形包装限制进行匹配
            cylinder_sum = 2 * cylinder_diameter + cylinder_length
            max_cylinder_sum = logistic.get("max_cylinder_sum", 0)
            if 0 < max_cylinder_sum < cylinder_sum:
                return (
                    f"2倍直径与长度之和 {cylinder_sum} cm 超过限制 "
                    f"{max_cylinder_sum} cm"
                )
            min_cylinder_sum = logistic.get("min_cylinder_sum", 0)
            if min_cylinder_sum > 0 and cylinder_sum < min_cylinder_sum:
                return (
                    f"2倍直径与长度之和 {cylinder_sum} cm 低于下限 "
                    f"{min_cylinder_sum} cm"
                )
            max_cylinder_length = logistic.get("max_cylinder_length", 0)
            if 0 < max_cylinder_length < cylinder_length:
                return (
                    f"圆柱长度 {cylinder_length} cm 超过限制 "
                    f"{max_cylinder_length} cm"
                )
            min_cyl = logistic.get("min_cylinder_length", 0)
            if min_cyl > 0 and cylinder_length < min_cyl:
                return (
                    f"圆柱长度 {cylinder_length} cm 低于下限 {min_cyl} cm"
                )
            # 圆柱形包装检查通过后，仍然需要定义sides用于后续标准包装限制检查
            sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
        else:
            # 物流没有圆柱形包装限制，使用标准包装限制
            # 将圆柱形包装转换为标准包装进行匹配
            # 圆柱直径相当于长和宽，圆柱长度相当于高
            sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
    else:
        # 标准包装产品
        sides = [
            product.get("length_cm", 0),
            product.get("width_cm", 0),
            product.get("height_cm", 0),
        ]

    # 标准包装限制检查
    max_sum = logistic.get("max_sum_of_sides", 10**9)
    if sum(sides) > max_sum > 0:
        return (
            f"三边之和 {sum(sides)} cm 超过限制 {max_sum} cm"
        )
    max_long = logistic.get("max_longest_side", 10**9)
    if max(sides) > max_long:
        return (
            f"最长边 {max(sides)} cm 超过限制 {max_long} cm"
        )
    # 第二边长上限检查
    max_second_side = logistic.get("max_second_side", 0)
    if max_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        if 0 < max_second_side < second_side:
            return (
                f"第二边长 {second_side} cm 超过限制 {max_second_side} cm"
            )
    # 第二长边下限检查
    min_second_side = logistic.get("min_second_side", 0)
    if min_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        if second_side < min_second_side:
            return (
                f"第二边长 {second_side} cm 低于下限 {min_second_side} cm"
            )
    # 最长边下限检查
    min_len = logistic.get("min_length", 0)
    if min_len > 0:
        longest_side = max(sides)
        if longest_side < min_len:
            return (
                    f"最长边 {longest_side} cm 低于下限 {min_len} cm"
                )

    # 3. 特殊物品
    if product.get("has_battery") and not logistic.get("allow_battery"):
        return "产品含电池但物流不允许电池"
    if product.get("has_flammable") and not logistic.get("allow_flammable"):
        return "产品含易燃液体但物流不允许易燃液体"

    # 4. 电池容量 & MSDS
    if product.get("has_battery"):
        limit_wh = logistic.get("battery_capacity_limit_wh", 0)
        if limit_wh > 0:
            wh = product.get("battery_capacity_wh", 0)
            if wh == 0:
                mah = product.get("battery_capacity_mah", 0)
                v = product.get("battery_voltage", 0)
                # 如果mAh和V都为0，跳过电池容量限制判断
                if mah <= 0 and v <= 0:
                    pass  # 跳过电池容量限制判断
                else:
                    wh = mah * v / 1000.0
                    if 0 < limit_wh < wh:
                        return (
                            f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
                        )
            else:
                # 如果填写了Wh但值为0，跳过电池容量限制判断
                if wh <= 0:
                    pass  # 跳过电池容量限制判断
                else:
                    if 0 < limit_wh < wh:
                        return (
                            f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
                        )
        if logistic.get("require_msds") and not product.get("has_msds"):
            return "物流要求 MSDS 但产品未提供"

    # 5. 限价（人民币→卢布）
    try:
        rate = ExchangeRateService().get_exchange_rate()  # 1 CNY = x RUB
        unit_price = float(product.get("unit_price", 0))
        labeling_fee = float(product.get("labeling_fee", 0))
        shipping_fee = float(product.get("shipping_fee", 0))

        # 先计算运费（复用与正式计算完全一致的公式）
        # 使用上面已经计算好的重量 w
        fee_mode = logistic.get("fee_mode", "base_plus_continue")
        continue_unit = int(logistic.get("continue_unit", 100))

        if fee_mode == "base_plus_continue":
            units = __import__("math").ceil(w / continue_unit)
            cost = logistic.get("base_fee", 0) + \
                logistic.get("continue_fee", 0) * units
        else:  # first_plus_continue
            first_w = logistic.get("first_weight_g", 0)
            first_cost = logistic.get("first_fee", 0)
            cost = (
                first_cost
                if w <= first_w
                else first_cost
                + __import__("math").ceil((w - first_w) / continue_unit)
                * logistic.get("continue_fee", 0)
            )

        # 估算人民币总成本
        total_cny = unit_price + labeling_fee + shipping_fee + 15 * rate + cost
        # 估算人民币售价
        denominator = (
            (1 - product.get("promotion_cost_rate", 0))
            * (1 - product.get("commission_rate", 0))
            * (1 - product.get("withdrawal_fee_rate", 0))
            * (1 - product.get("payment_processing_fee", 0))
        )
        if denominator == 0:
            return "费率参数异常导致除以 0"
        rough_cny = (
            total_cny
            / (1 - product.get("target_profit_margin", 0))
        ) / denominator
        rough_rub = rough_cny / rate

        # 获取价格限制和货币类型
        limit_value = logistic.get("price_limit_rub", 0)
        min_value = logistic.get("price_min_rub", 0)
        limit_currency = logistic.get("price_limit_currency", "RUB")
        min_currency = logistic.get("price_min_currency", "RUB")

        # 根据货币类型进行价格比较
        usd_rate = get_usd_rate()

        if limit_currency == "USD" and limit_value > 0:
            # 美元限价：将估算售价转换为美元进行比较
            rough_usd = rough_cny / usd_rate
            if rough_usd > limit_value:
                return f"估算售价 {rough_usd:.2f} USD 超价格上限 {limit_value} USD"
        elif limit_value > 0:
            # 卢布限价：直接比较卢布价格
            if rough_rub > limit_value:
                return f"估算售价 {rough_rub:.2f} RUB 超价格上限 {limit_value} RUB"

        if min_currency == "USD" and min_value > 0:
            # 美元下限：将估算售价转换为美元进行比较
            rough_usd = rough_cny / usd_rate
            if rough_usd < min_value:
                return f"估算售价 {rough_usd:.2f} USD 低于价格下限 {min_value} USD"
        elif min_value > 0:
            # 卢布下限：直接比较卢布价格
            if rough_rub < min_value:
                return f"估算售价 {rough_rub:.2f} RUB 低于价格下限 {min_value} RUB"
    except (KeyError, TypeError, ZeroDivisionError) as price_exc:
        return f"限价判断异常: {price_exc}"

    # 6. 全部通过
    return None


if __name__ == "__main__":
    # 启动自动备份服务
    try:
        start_backup_service()
        print("🚀 自动备份服务已启动")
    except (RuntimeError, OSError) as backup_exc:
        print(f"⚠️ 自动备份服务启动失败: {backup_exc}")

    main()
