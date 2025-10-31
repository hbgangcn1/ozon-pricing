import warnings
import streamlit as st
import pandas as pd
import sqlite3

# 过滤pandas警告 - 必须在导入pandas之前设置
warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable.*",
)
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame.insert with a non-unique index is "
    "deprecated*",
    module="pandas.core.frame",
)

try:
    from .db_utils import (
        get_db_connection,
        current_user_id,
        check_user_subscription_status,
    )
except ImportError:
    from db_utils import (
        get_db_connection,
        current_user_id,
        check_user_subscription_status,
    )

# 向后兼容：提供 get_db 以便旧测试可以 monkeypatch
try:
    from .db_utils import get_db as _legacy_get_db
except (ImportError, ModuleNotFoundError):
    try:
        from db_utils import get_db as _legacy_get_db
    except (ImportError, ModuleNotFoundError):
        _legacy_get_db = None


def get_db():
    """测试兼容占位。生产代码不调用。"""
    if _legacy_get_db is None:
        raise AttributeError("get_db is deprecated; use get_db_connection")
    return _legacy_get_db()


def products_page():
    """产品管理页面"""
    uid = current_user_id()

    with get_db_connection() as (conn, c):
        subscription_status = check_user_subscription_status(uid)

        # 使用容器优化渲染性能
        header_container = st.container()
        with header_container:
            # 页面描述
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 2rem;">
                    <p style="color: #718096; font-size: 1.1rem; margin: 0;">
                        管理您的产品信息，为运费计算提供准确数据
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.session_state.get("edit_product_id"):
            edit_product_form()
            return

        if st.session_state.get("batch_edit_products"):
            batch_edit_pricing_form()
            return

        # 使用容器包装产品数据查询
        products_container = st.container()
        with products_container:
            # 缓存产品表
            products = pd.read_sql(
                "SELECT id, name, category, weight_g "
                "FROM products "
                "WHERE user_id = ?",
                conn,
                params=(uid,),
            )

        # 添加/编辑产品
        with st.expander("➕ 添加新产品", expanded=True):
            st.markdown(
                '<h3 class="sub-title">产品基本信息</h3>', unsafe_allow_html=True
            )
            st.subheader("基本信息")
            name = st.text_input("产品名称*")
            russian_name = st.text_input("俄文名称")
            category = st.text_input("产品类别")
            model = st.text_input("型号")
            unit_price = st.number_input(
                "进货单价（元）*", min_value=0.0, value=0.0, step=0.01
            )
            st.subheader("物理规格")
            weight_g = st.number_input("重量(g)*", min_value=0.0, value=0.0)
            shape = st.radio(
                "包装形状", ["标准包装", "圆柱形包装"], horizontal=True
            )
            is_cylinder = shape == "圆柱形包装"

            # 初始化圆柱形包装变量（用于兼容性）
            cylinder_diameter = 0.0
            cylinder_length = 0.0

            # 标准包装尺寸
            if not is_cylinder:
                col1, col2, col3 = st.columns(3)
                length_cm = col1.number_input(
                    "长(cm)*", min_value=0.0, value=0.0
                )
                width_cm = col2.number_input(
                    "宽(cm)*", min_value=0.0, value=0.0
                )
                height_cm = col3.number_input(
                    "高(cm)*", min_value=0.0, value=0.0
                )
            else:
                # 圆柱形包装尺寸
                col1, col2 = st.columns(2)
                cylinder_diameter = col1.number_input(
                    "圆柱直径(cm)*", min_value=0.0, value=0.0
                )
                cylinder_length = col2.number_input(
                    "圆柱长度(cm)*", min_value=0.0, value=0.0
                )
                # 为圆柱形包装设置默认的长宽高值（用于兼容性）
                length_cm = cylinder_diameter
                width_cm = cylinder_diameter
                height_cm = cylinder_length
            has_battery = st.checkbox("含电池")
            choice = None
            battery_capacity_wh = 0.0
            battery_capacity_mah = 0
            battery_voltage = 0.0
            if has_battery:
                choice = st.radio(
                    "电池容量填写方式",
                    ["填写 Wh（瓦时）", "填写 mAh + V"],
                    horizontal=True,
                )
                if choice == "填写 Wh（瓦时）":
                    battery_capacity_wh = st.number_input(
                        "电池容量(Wh)*", min_value=0.0, value=0.0
                    )
                else:
                    col1, col2 = st.columns(2)
                    battery_capacity_mah = col1.number_input(
                        "电池容量(mAh)*", min_value=0.0, value=0.0
                    )
                    battery_voltage = col2.number_input(
                        "电池电压(V)*", min_value=0.0, value=0.0
                    )
                    # 电池容量验证警告
                    if battery_capacity_mah > 0 >= battery_voltage:
                        st.warning("请填写电池电压(V)")
                    elif battery_voltage > 0 >= battery_capacity_mah:
                        st.warning("请填写电池容量(mAh)")
            col1, col2 = st.columns(2)
            has_msds = col1.checkbox("有MSDS文件")
            has_flammable = col2.checkbox("有易燃液体")
            shipping_fee = col1.number_input(
                "发货方运费(元)", min_value=0.0, value=0.0
            )
            labeling_fee = st.number_input(
                "代贴单费用(元)", min_value=0.0, value=0.0
            )
            st.subheader("定价参数")
            col1, col2 = st.columns(2)
            promotion_cost_rate = (
                col1.number_input(
                    "推广费用率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=11.5,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )
            target_profit_margin = (
                col1.number_input(
                    "运营利润率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=50.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )
            commission_rate = (
                col2.number_input(
                    "佣金率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=17.5,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )
            withdrawal_fee_rate = (
                col1.number_input(
                    "打款提现费率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=1.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )
            payment_processing_fee = (
                col2.number_input(
                    "收单手续费率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=1.3,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )
            return_rate = (
                col1.number_input(
                    "历史退货率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )
            if st.button("添加产品"):
                if not subscription_status.get("valid", True):
                    st.error("账号到期，请联系客服续费")
                    return
                required = [name, weight_g, unit_price]
                if not is_cylinder:
                    required.extend([length_cm, width_cm, height_cm])
                else:
                    required.extend([cylinder_diameter, cylinder_length])
                # 电池容量验证逻辑
                if has_battery:
                    if choice == "填写 Wh（瓦时）":
                        if battery_capacity_wh <= 0:
                            # 如果填写了Wh但值为0，跳过电池容量限制判断
                            pass
                    elif choice == "填写 mAh + V":
                        if battery_capacity_mah > 0 >= battery_voltage:
                            required.append(None)
                        elif battery_voltage > 0 >= battery_capacity_mah:
                            required.append(None)
                        elif (battery_capacity_mah <= 0 and
                              battery_voltage <= 0):
                            # 如果都填了0，跳过电池容量限制判断
                            pass
                        else:
                            # 正常情况，不需要额外验证
                            pass
                # 检查必填字段
                missing_fields = []
                if not name:
                    missing_fields.append("产品名称")
                if weight_g <= 0:
                    missing_fields.append("重量")
                if unit_price <= 0:
                    missing_fields.append("进货单价")
                if not is_cylinder:
                    if length_cm <= 0:
                        missing_fields.append("长度")
                    if width_cm <= 0:
                        missing_fields.append("宽度")
                    if height_cm <= 0:
                        missing_fields.append("高度")
                else:
                    if cylinder_diameter <= 0:
                        missing_fields.append("圆柱直径")
                    if cylinder_length <= 0:
                        missing_fields.append("圆柱长度")
                # 电池容量验证逻辑
                if has_battery:
                    if choice == "填写 Wh（瓦时）":
                        if battery_capacity_wh <= 0:
                            # 如果填写了Wh但值为0，跳过电池容量限制判断
                            pass
                    elif choice == "填写 mAh + V":
                        if battery_capacity_mah > 0 >= battery_voltage:
                            missing_fields.append("电池电压(V)")
                        elif battery_voltage > 0 >= battery_capacity_mah:
                            missing_fields.append("电池容量(mAh)")
                        elif (battery_capacity_mah <= 0 and
                              battery_voltage <= 0):
                            # 如果都填了0，跳过电池容量限制判断
                            pass
                        else:
                            # 正常情况，不需要额外验证
                            pass

                if missing_fields:
                    st.error(f"请填写以下必填字段：{', '.join(missing_fields)}")
                else:
                    c.execute(
                        "INSERT INTO products ("
                        "user_id, name, russian_name, category, model, "
                        "unit_price, weight_g, length_cm, width_cm, "
                        "height_cm, "
                        "is_cylinder, cylinder_diameter, has_battery, "
                        "battery_capacity_wh, battery_capacity_mah, "
                        "battery_voltage, has_msds, has_flammable, "
                        "shipping_fee, labeling_fee, "
                        "promotion_cost_rate, target_profit_margin, "
                        "commission_rate, withdrawal_fee_rate, "
                        "payment_processing_fee, \"return_rate\", "
                        "cylinder_length) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
                        "?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            uid,
                            name,
                            russian_name,
                            category,
                            model,
                            unit_price,
                            weight_g,
                            length_cm,
                            width_cm,
                            height_cm,
                            int(is_cylinder),
                            cylinder_diameter,
                            int(has_battery),
                            battery_capacity_wh,
                            battery_capacity_mah,
                            battery_voltage,
                            int(has_msds),
                            int(has_flammable),
                            shipping_fee,
                            labeling_fee,
                            promotion_cost_rate,
                            target_profit_margin,
                            commission_rate,
                            withdrawal_fee_rate,
                            payment_processing_fee,
                            return_rate,
                            cylinder_length if is_cylinder else 0.0,
                        ),
                    )
                    new_product_id = c.lastrowid
                    conn.commit()
                    # 记录审计日志（如果是admin操作）
                    try:
                        from app import is_admin
                        if is_admin():
                            from db_utils import log_admin_action
                            log_admin_action(
                                admin_id=uid,
                                action_type='创建产品',
                                action_detail=(
                                    f"创建产品: {name} (ID: {new_product_id})"
                                ),
                                target_user_id=uid,
                                target_type='product'
                            )
                    except (
                        ImportError,
                        AttributeError,
                        TypeError,
                        ValueError
                    ):
                        pass  # 审计日志记录失败不影响主流程
                    st.success("产品添加成功！")
                    query = (
                        "SELECT id, name, category, weight_g "
                        "FROM products "
                        "WHERE user_id = ?"
                    )
                    st.session_state.products_data = pd.read_sql(
                        query, conn, params=(uid,)
                    )
                    st.rerun()

        # 产品列表 - 延迟加载
        st.subheader("产品列表")

        # 使用容器优化渲染性能
        products_list_container = st.container()
        with products_list_container:
            if not products.empty:
                selected_list = []
                for _, row in products.iterrows():
                    if st.checkbox(
                        f"{row['id']} - {row['name']} "
                        f"({row['category']}, {row['weight_g']}g)",
                        key=f"product_checkbox_{row['id']}",
                    ):
                        selected_list.append(row.to_dict())

                if selected_list:
                    # 显示选中的产品数量
                    st.info(f"已选择 {len(selected_list)} 个产品")

                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("编辑产品", key="edit_btn_batch"):
                            if not subscription_status.get("valid", True):
                                st.error("账号到期，请联系客服续费")
                                return
                            if len(selected_list) == 1:
                                # 单个产品编辑
                                st.session_state.edit_product_id = (
                                    selected_list[0]["id"]
                                )
                                st.rerun()
                            else:
                                # 多个产品批量编辑定价参数
                                st.session_state.batch_edit_products = (
                                    selected_list
                                )
                                st.rerun()
                    with col_del:
                        if len(selected_list) == 1:
                            if st.button("删除产品", key="del_btn_single"):
                                if not subscription_status.get("valid", True):
                                    st.error("账号到期，请联系客服续费")
                                    return
                                st.session_state.delete_confirm_product_id = (
                                    selected_list[0]["id"]
                                )
                                st.rerun()
                        else:
                            if st.button("批量删除", key="del_btn_batch"):
                                if not subscription_status.get("valid", True):
                                    st.error("账号到期，请联系客服续费")
                                    return
                                st.session_state.batch_delete_products = (
                                    selected_list
                                )
                                st.rerun()

            # 删除确认对话框
            if st.session_state.get("delete_confirm_product_id"):
                if not subscription_status.get("valid", True):
                    st.error("账号到期，请联系客服续费")
                    del st.session_state.delete_confirm_product_id
                    return
                st.warning("确定要删除这个产品吗？")
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("确定删除", key="confirm_delete_product"):
                        if not subscription_status.get("valid", True):
                            st.error("账号到期，请联系客服续费")
                            return
                        product_id = st.session_state.delete_confirm_product_id
                        # 先获取产品名称用于审计日志
                        product_info = c.execute(
                            "SELECT name FROM products "
                            "WHERE id=? AND user_id=?",
                            (product_id, uid),
                        ).fetchone()
                        product_name = (
                            product_info[0] if product_info else '未知'
                        )
                        c.execute(
                            "DELETE FROM products WHERE id=? AND user_id=?",
                            (product_id, uid),
                        )
                        conn.commit()
                        # 记录审计日志（如果是admin操作）
                        try:
                            from app import is_admin
                            if is_admin():
                                from db_utils import log_admin_action
                                log_admin_action(
                                    admin_id=uid,
                                    action_type='删除产品',
                                    action_detail=(
                                        f"删除产品: {product_name} "
                                        f"(ID: {product_id})"
                                    ),
                                    target_user_id=uid,
                                    target_type='product'
                                )
                        except (
                            ImportError,
                            AttributeError,
                            TypeError,
                            ValueError
                        ):
                            pass  # 审计日志记录失败不影响主流程
                        query = (
                            "SELECT id, name, category, weight_g "
                            "FROM products "
                            "WHERE user_id = ?"
                        )
                        st.session_state.products_data = pd.read_sql(
                            query, conn, params=(uid,)
                        )
                        del st.session_state.delete_confirm_product_id
                        st.rerun()
                with col_cancel:
                    if st.button("取消", key="cancel_delete_product"):
                        del st.session_state.delete_confirm_product_id
                        st.rerun()

            # 批量删除确认对话框
            if st.session_state.get("batch_delete_products"):
                selected_products = st.session_state.batch_delete_products
                st.warning(
                    f"确定要删除这 {len(selected_products)} 个产品吗？"
                )

                with st.expander("查看要删除的产品", expanded=True):
                    for product in selected_products:
                        st.write(
                            f"• {product['name']} ({product['category']})"
                        )

                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("确定批量删除", key="confirm_batch_delete"):
                        try:
                            product_ids = [p["id"] for p in selected_products]
                            placeholders = ",".join(["?" for _ in product_ids])

                            # 先获取产品名称用于审计日志
                            product_names = [
                                p.get('name', '未知') for p in selected_products
                            ]
                            c.execute(
                                f"""
                                DELETE FROM products
                                WHERE id IN ({placeholders}) AND user_id = ?
                            """,
                                (*product_ids, uid),
                            )

                            conn.commit()
                            # 记录审计日志（如果是admin操作）
                            try:
                                from app import is_admin
                                if is_admin():
                                    from db_utils import log_admin_action
                                    log_admin_action(
                                        admin_id=uid,
                                        action_type='批量删除产品',
                                        action_detail=(
                                            f"批量删除 "
                                            f"{len(selected_products)} 个产品: "
                                            f"{', '.join(product_names[:5])}"
                                            + (
                                                "..." if len(product_names) > 5
                                                else ""
                                            )
                                        ),
                                        target_user_id=uid,
                                        target_type='product'
                                    )
                            except (
                                ImportError,
                                AttributeError,
                                TypeError,
                                ValueError
                            ):
                                pass  # 审计日志记录失败不影响主流程
                            st.success(
                                f"成功删除 {len(selected_products)} 个产品！"
                            )

                            del st.session_state.batch_delete_products
                            st.rerun()

                        except (sqlite3.Error, RuntimeError) as e:
                            st.error(f"删除失败: {str(e)}")
                            conn.rollback()

                with col_cancel:
                    if st.button("取消", key="cancel_batch_delete"):
                        del st.session_state.batch_delete_products
                        st.rerun()
            else:
                st.info("暂无产品数据")


def edit_product_form():
    """编辑产品表单"""
    uid = current_user_id()
    pid = st.session_state.edit_product_id

    with get_db_connection() as (conn, c):
        subscription_status = check_user_subscription_status(uid)
        if not subscription_status.get("valid", True):
            st.error("账号到期，请联系客服续费")
            if st.button("返回列表"):
                if "edit_product_id" in st.session_state:
                    del st.session_state.edit_product_id
                st.rerun()
            return

        row = c.execute(
            "SELECT * FROM products WHERE id=? AND user_id=?", (pid, uid)
        ).fetchone()
    if not row:
        st.error("产品不存在或无权编辑")
        if st.button("返回列表"):
            del st.session_state.edit_product_id
            st.rerun()
        return
    vals = dict(zip(row.keys(), row))
    # 确保所有必需的字段都存在
    required_fields = [
        "name",
        "russian_name",
        "category",
        "model",
        "unit_price",
        "weight_g",
        "length_cm",
        "width_cm",
        "height_cm",
        "is_cylinder",
        "cylinder_diameter",
        "cylinder_length",
        "has_battery",
        "battery_capacity_wh",
        "battery_capacity_mah",
        "battery_voltage",
        "has_msds",
        "has_flammable",
        "shipping_fee",
        "labeling_fee",
        "promotion_cost_rate",
        "target_profit_margin",
        "commission_rate",
        "withdrawal_fee_rate",
        "payment_processing_fee",
        "vat_rate",
    ]
    for field in required_fields:
        if field not in vals:
            vals[field] = (
                None
                if field in ["name", "russian_name", "category", "model"]
                else 0
            )
    st.subheader("编辑产品")
    # 产品名称和进货单价在一行中分两个列显示
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("产品名称*", value=vals["name"])
    with col2:
        # 确保价格不低于最小值
        price_value = max(0.0, float(vals["unit_price"]))
        unit_price = st.number_input(
            "进货单价（元）*",
            min_value=0.0,
            value=price_value,
            step=0.01,
        )

    # 初始化已删除的字段变量
    russian_name = ""
    category = ""
    model = ""

    st.subheader("物流规格")
    # 使用st.radio显示包装类型选择
    package_type = st.radio(
        "包装类型",
        ["常规包装", "圆柱包装"],
        index=1 if vals["is_cylinder"] else 0,
        horizontal=True
    )
    is_cylinder = package_type == "圆柱包装"

    # 初始化圆柱形包装变量（用于兼容性）
    cylinder_diameter = 0.0
    cylinder_length = 0.0

    # 根据包装类型显示不同的输入字段
    if package_type == "常规包装":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            weight_g = st.number_input(
                "重量（克）*",
                min_value=0.0,
                value=max(0.0, float(vals["weight_g"])),
                step=0.1,
            )
        with col2:
            length_cm = st.number_input(
                "长度（厘米）*",
                min_value=0.0,
                value=max(0.0, float(vals["length_cm"])),
                step=0.1,
            )
        with col3:
            width_cm = st.number_input(
                "宽度（厘米）*",
                min_value=0.0,
                value=max(0.0, float(vals["width_cm"])),
                step=0.1,
            )
        with col4:
            height_cm = st.number_input(
                "高度（厘米）*",
                min_value=0.0,
                value=max(0.0, float(vals["height_cm"])),
                step=0.1,
            )
        # 初始化圆柱包装的变量
        cylinder_diameter = 0
        cylinder_length = 0
    else:  # 圆柱包装
        col1, col2, col3 = st.columns(3)
        with col1:
            weight_g = st.number_input(
                "重量（克）*",
                min_value=0.0,
                value=max(0.0, float(vals["weight_g"])),
                step=0.1,
            )
        with col2:
            cylinder_diameter = st.number_input(
                "圆柱直径（厘米）*",
                min_value=0.0,
                value=max(
                    0.0,
                    float(vals["cylinder_diameter"]),
                ),
                step=0.1,
            )
        with col3:
            cylinder_length = st.number_input(
                "圆柱长度（厘米）*",
                min_value=0.0,
                value=max(
                    0.0,
                    float(vals.get("cylinder_length") or 0.0),
                ),
                step=0.1,
            )
        # 初始化常规包装的变量
        length_cm = 0
        width_cm = 0
        height_cm = 0
    # 电池和液体标题
    st.subheader("电池和液体")

    # 包含电池和包含易燃液体复选框放在同一行
    col1, col2 = st.columns(2)
    with col1:
        has_battery = st.checkbox("包含电池", value=bool(vals["has_battery"]))
    with col2:
        has_flammable = st.checkbox(
            "包含易燃液体",
            value=bool(vals["has_flammable"]),
        )

    # 初始化电池相关变量
    choice = None
    battery_capacity_wh = 0
    battery_capacity_mah = 0
    battery_voltage = 0
    has_msds = False

    if has_battery:
        # 电池容量填写方式和MSDS证书在同一行
        col1, col2 = st.columns(2, vertical_alignment="bottom")
        with col1:
            choice = st.radio(
                "电池容量填写方式",
                ["填写 Wh（瓦时）", "填写 mAh + V"],
                index=0 if vals["battery_capacity_wh"] > 0 else 1,
                horizontal=True,
            )
        with col2:
            has_msds = st.checkbox("有 MSDS 证书", value=bool(vals["has_msds"]))

        if choice == "填写 Wh（瓦时）":
            battery_capacity_wh = st.number_input(
                "电池容量（Wh）",
                min_value=0.0,
                value=max(0.0, float(vals["battery_capacity_wh"])),
                step=0.1,
            )
            battery_capacity_mah = 0
            battery_voltage = 0
        else:
            # 电池容量（mAh）和电池电压（V）在一行中分两个列显示
            col1, col2 = st.columns(2)
            with col1:
                battery_capacity_mah = st.number_input(
                    "电池容量（mAh）",
                    min_value=0.0,
                    value=max(0.0, float(vals["battery_capacity_mah"])),
                    step=0.1,
                )
            with col2:
                battery_voltage = st.number_input(
                    "电池电压（V）",
                    min_value=0.0,
                    value=max(0.0, float(vals["battery_voltage"])),
                    step=0.1,
                )
            battery_capacity_wh = 0
    # 删除易燃液体体积控件
    st.subheader("定价参数")
    # 第一行：贴标费用（元）、供货方不包邮运（元）
    col1, col2 = st.columns(2)
    with col1:
        labeling_fee = st.number_input(
            "贴标费用（元）",
            min_value=0.0,
            value=max(0.0, float(vals["labeling_fee"])),
            step=0.01,
        )
    with col2:
        shipping_fee = st.number_input(
            "供货方不包邮运（元）",
            min_value=0.0,
            value=max(0.0, float(vals["shipping_fee"])),
            step=0.01,
        )

    # 第二行：佣金率（%）、运营利润率（%）
    col1, col2 = st.columns(2)
    with col1:
        commission_rate = (
            st.number_input(
                "佣金率(%)",
                min_value=0.0,
                max_value=100.0,
                value=max(0.0, float(vals["commission_rate"])) * 100.0,
                step=0.1,
                format="%.1f",
            ) / 100.0
        )
    with col2:
        target_profit_margin = (
            st.number_input(
                "运营利润率(%)",
                min_value=0.0,
                max_value=100.0,
                value=max(0.0, float(vals["target_profit_margin"])) * 100.0,
                step=0.1,
                format="%.1f",
            ) / 100.0
        )

    # 第三行：推广费率（%）、打款提现费率(%)
    col1, col2 = st.columns(2)
    with col1:
        promotion_cost_rate = (
            st.number_input(
                "推广费率(%)",
                min_value=0.0,
                max_value=100.0,
                value=max(0.0, float(vals["promotion_cost_rate"])) * 100.0,
                step=0.1,
                format="%.1f",
            ) / 100.0
        )
    with col2:
        withdrawal_fee_rate = (
            st.number_input(
                "打款提现费率(%)",
                min_value=0.0,
                max_value=100.0,
                value=max(0.0, float(vals["withdrawal_fee_rate"])) * 100.0,
                step=0.1,
                format="%.1f",
            ) / 100.0
        )

    # 第四行：收单手续费率(%)、历史退货率(%)
    col1, col2 = st.columns(2)
    with col1:
        payment_processing_fee = (
            st.number_input(
                "收单手续费率(%)",
                min_value=0.0,
                max_value=100.0,
                value=max(0.0, float(vals["payment_processing_fee"])) * 100.0,
                step=0.1,
                format="%.1f",
            ) / 100.0
        )
    with col2:
        return_rate = (
            st.number_input(
                "历史退货率(%)",
                min_value=0.0,
                max_value=100.0,
                value=max(0.0, float(vals.get("return_rate") or 0)) * 100.0,
                step=0.1,
                format="%.1f",
            ) / 100.0
        )

    # 第五行：增值税率(%)
    vat_rate = (
        st.number_input(
            "增值税率(%)",
            min_value=0.0,
            max_value=30.0,
            value=max(0.0, float(vals.get("vat_rate") or 0)) * 100.0,
            step=0.1,
            format="%.1f",
            help="增值税率，根据实际情况填写",
        ) / 100.0
    )

    # 保存修改和取消按钮横向排列
    col1, col2 = st.columns(2)
    with col1:
        if st.button("保存修改"):
            if not subscription_status.get("valid", True):
                st.error("账号到期，请联系客服续费")
                st.rerun()
            required = [name, weight_g, unit_price]
            if not is_cylinder:
                required.extend([length_cm, width_cm, height_cm])
            else:
                required.extend([cylinder_diameter, cylinder_length])
            # 电池容量验证逻辑
            if has_battery:
                if choice == "填写 Wh（瓦时）":
                    if battery_capacity_wh <= 0:
                        # 如果填写了Wh但值为0，跳过电池容量限制判断
                        pass
                elif choice == "填写 mAh + V":
                    if battery_capacity_mah > 0 >= battery_voltage:
                        required.append(None)
                    elif battery_voltage > 0 >= battery_capacity_mah:
                        required.append(None)
                    elif battery_capacity_mah <= 0 and battery_voltage <= 0:
                        # 如果都填了0，跳过电池容量限制判断
                        pass
                    else:
                        # 正常情况，不需要额外验证
                        pass
            # 检查必填字段
            missing_fields = []
            if not name:
                missing_fields.append("产品名称")
            if weight_g <= 0:
                missing_fields.append("重量")
            if unit_price <= 0:
                missing_fields.append("进货单价")
            if not is_cylinder:
                if length_cm <= 0:
                    missing_fields.append("长度")
                if width_cm <= 0:
                    missing_fields.append("宽度")
                if height_cm <= 0:
                    missing_fields.append("高度")
            else:
                if cylinder_diameter <= 0:
                    missing_fields.append("圆柱直径")
                if cylinder_length <= 0:
                    missing_fields.append("圆柱长度")
            # 电池容量验证逻辑
            if has_battery:
                if choice == "填写 Wh（瓦时）":
                    if battery_capacity_wh <= 0:
                        # 如果填写了Wh但值为0，跳过电池容量限制判断
                        pass
                elif choice == "填写 mAh + V":
                    if battery_capacity_mah > 0 >= battery_voltage:
                        missing_fields.append("电池电压(V)")
                    elif battery_voltage > 0 >= battery_capacity_mah:
                        missing_fields.append("电池容量(mAh)")
                    elif battery_capacity_mah <= 0 and battery_voltage <= 0:
                        # 如果都填了0，跳过电池容量限制判断
                        pass
                    else:
                        # 正常情况，不需要额外验证
                        pass

            if missing_fields:
                st.error(f"请填写以下必填字段：{', '.join(missing_fields)}")
            else:
                with get_db_connection() as (conn, c):
                    c.execute(
                        """UPDATE products SET
                        name=?, russian_name=?, category=?, model=?,
                        weight_g=?, length_cm=?, width_cm=?, height_cm=?,
                        is_cylinder=?, cylinder_diameter=?, cylinder_length=?,
                        has_battery=?, battery_capacity_wh=?,
                        battery_capacity_mah=?, battery_voltage=?,
                        has_msds=?, has_flammable=?,
                        unit_price=?, shipping_fee=?, labeling_fee=?,
                        promotion_cost_rate=?,
                        target_profit_margin=?, commission_rate=?,
                        withdrawal_fee_rate=?, payment_processing_fee=?,
                        "return_rate"=?, vat_rate=?
                        WHERE id=? AND user_id=?""",
                        (
                            name,
                            russian_name,
                            category,
                            model,
                            weight_g,
                            length_cm,
                            width_cm,
                            height_cm,
                            int(is_cylinder),
                            cylinder_diameter,
                            cylinder_length if is_cylinder else 0.0,
                            int(has_battery),
                            battery_capacity_wh,
                            battery_capacity_mah,
                            battery_voltage,
                            int(has_msds),
                            int(has_flammable),
                            unit_price,
                            shipping_fee,
                            labeling_fee,
                            promotion_cost_rate,
                            target_profit_margin,
                            commission_rate,
                            withdrawal_fee_rate,
                            payment_processing_fee,
                            return_rate,
                            vat_rate,
                            pid,
                            uid,
                        ),
                    )
                    conn.commit()
                    # 记录审计日志（如果是admin操作）
                    try:
                        from app import is_admin
                        if is_admin():
                            from db_utils import log_admin_action
                            product_name = name or '未知'
                            log_admin_action(
                                admin_id=uid,
                                action_type='更新产品',
                                action_detail=(
                                    f"更新产品: {product_name} (ID: {pid})"
                                ),
                                target_user_id=uid,
                                target_type='product'
                            )
                    except (
                        ImportError,
                        AttributeError,
                        TypeError,
                        ValueError
                    ):
                        pass  # 审计日志记录失败不影响主流程
                st.success("产品修改成功！")
                del st.session_state.edit_product_id
                # 设置标志，指示应该返回到产品列表页面
                st.session_state.return_to_product_list = True
                st.rerun()

    with col2:
        if st.button("取消"):
            del st.session_state.edit_product_id
            # 设置标志，指示应该返回到产品列表页面
            st.session_state.return_to_product_list = True
            st.rerun()


def batch_edit_pricing_form():
    """批量编辑产品定价参数表单"""
    uid = current_user_id()
    selected_products = st.session_state.batch_edit_products

    with get_db_connection() as (conn, c):
        subscription_status = check_user_subscription_status(uid)

        if not st.session_state.get("batch_edit_products"):
            st.error("没有选择要编辑的产品")
            if st.button("返回列表"):
                st.rerun()
            return

        # 显示选中的产品
        st.subheader("批量编辑定价参数")
        st.info(f"已选择 {len(selected_products)} 个产品进行批量编辑")

        # 显示选中的产品列表
        with st.expander("查看选中的产品", expanded=True):
            for product in selected_products:
                st.write(f"• {product['name']} ({product['category']})")

        st.markdown("---")
        st.markdown("### 定价参数设置")
        st.markdown("以下参数将应用到所有选中的产品：")

        # 获取选中产品的定价参数平均值作为默认值
        product_ids = [p["id"] for p in selected_products]
        placeholders = ",".join(["?" for _ in product_ids])

        avg_params = c.execute(
            f"""
            SELECT
                AVG(promotion_cost_rate) as avg_promotion_cost_rate,
                AVG(target_profit_margin) as avg_target_profit_margin,
                AVG(commission_rate) as avg_commission_rate,
                AVG(withdrawal_fee_rate) as avg_withdrawal_fee_rate,
                AVG(payment_processing_fee) as avg_payment_processing_fee,
                AVG("return_rate") as avg_return_rate
            FROM products
            WHERE id IN ({placeholders}) AND user_id = ?
        """,
            (*product_ids, uid),
        ).fetchone()

        # 定价参数输入
        col1, col2 = st.columns(2)

        with col1:
            promotion_cost_rate = (
                st.number_input(
                    "推广费用率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(avg_params[0] or 0.0) * 100.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )

            target_profit_margin = (
                st.number_input(
                    "运营利润率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(avg_params[1] or 0.0) * 100.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )

            withdrawal_fee_rate = (
                st.number_input(
                    "打款提现费率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(avg_params[3] or 0.0) * 100.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )
            return_rate = (
                st.number_input(
                    "历史退货率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(avg_params[5] or 0.0) * 100.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )

        with col2:
            commission_rate = (
                st.number_input(
                    "佣金率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(avg_params[2] or 0.0) * 100.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )

            payment_processing_fee = (
                st.number_input(
                    "收单手续费率(%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(avg_params[4] or 0.0) * 100.0,
                    step=0.1,
                    format="%.1f",
                ) / 100.0
            )

        # 保存按钮
        if st.button("保存到所有选中产品"):
            if not subscription_status.get("valid", True):
                st.error("账号到期，请联系客服续费")
                st.rerun()
            try:
                # 批量更新所有选中产品的定价参数
                product_ids = [p["id"] for p in selected_products]

                # 使用参数化查询防止SQL注入
                placeholders = ",".join(["?" for _ in product_ids])
                update_query = f"""
                    UPDATE products SET
                        promotion_cost_rate = ?,
                        target_profit_margin = ?,
                        commission_rate = ?,
                        withdrawal_fee_rate = ?,
                        payment_processing_fee = ?,
                        "return_rate" = ?
                    WHERE id IN ({placeholders}) AND user_id = ?
                """

                c.execute(
                    update_query,
                    (
                        promotion_cost_rate,
                        target_profit_margin,
                        commission_rate,
                        withdrawal_fee_rate,
                        payment_processing_fee,
                        return_rate,
                        *product_ids,
                        uid,
                    ),
                )

                conn.commit()
                # 记录审计日志（如果是admin操作）
                try:
                    from app import is_admin
                    if is_admin():
                        from db_utils import log_admin_action
                        product_names = [
                            p.get('name', '未知')[:20]
                            for p in selected_products[:3]
                        ]
                        log_admin_action(
                            admin_id=uid,
                            action_type='批量更新产品',
                            action_detail=(
                                f"批量更新 {len(selected_products)} 个产品的定价参数: "
                                f"{', '.join(product_names)}"
                                + ("..." if len(selected_products) > 3 else "")
                            ),
                            target_user_id=uid,
                            target_type='product'
                        )
                except (
                    ImportError,
                    AttributeError,
                    TypeError,
                    ValueError
                ):
                    pass  # 审计日志记录失败不影响主流程
                st.success(f"成功更新 {len(selected_products)} 个产品的定价参数！")

                # 清除session state并返回列表
                del st.session_state.batch_edit_products
                # 设置标志，指示应该返回到产品列表页面
                st.session_state.return_to_product_list = True
                st.rerun()

            except Exception as e:
                st.error(f"更新失败: {str(e)}")
                conn.rollback()

        # 取消按钮
        if st.button("取消", key="cancel_batch_edit"):
            del st.session_state.batch_edit_products
            # 设置标志，指示应该返回到产品列表页面
            st.session_state.return_to_product_list = True
            st.rerun()


def _close_conn_if_sqlite(candidate):
    try:
        if isinstance(candidate, sqlite3.Connection):
            candidate.close()
        else:
            close = getattr(candidate, "close", None)
            if callable(close):
                close()
    except (sqlite3.Error, AttributeError, TypeError):
        pass
