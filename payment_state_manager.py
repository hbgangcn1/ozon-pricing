"""
支付状态管理器
使用localStorage在浏览器端持久化支付状态，解决服务重启导致的状态丢失
"""

import streamlit.components.v1 as components


def save_payment_state_to_browser(order_id: str, plan_name: str):
    """将支付状态保存到浏览器localStorage"""
    print(f"💾 保存支付状态到浏览器: order_id={order_id}, plan={plan_name}")

    html_code = f"""
    <script>
    (function() {{
        const paymentState = {{
            order_id: '{order_id}',
            plan_name: '{plan_name}',
            timestamp: Date.now(),
            auto_check_count: 0
        }};
        localStorage.setItem('current_payment', JSON.stringify(paymentState));
        console.log('💾 支付状态已保存到浏览器:', paymentState);
    }})();
    </script>
    <div style="display:none;">Payment state saved</div>
    """
    components.html(html_code, height=0)


def restore_payment_state_from_browser():
    """从浏览器localStorage恢复支付状态"""
    print("🔄 尝试从浏览器恢复支付状态")

    html_code = """
    <script>
    (function() {{
        const savedPayment = localStorage.getItem('current_payment');
        if (savedPayment) {{
            const paymentState = JSON.parse(savedPayment);
            console.log('🔄 从浏览器恢复支付状态:', paymentState);

            // 检查是否超时（30分钟）
            const now = Date.now();
            if (now - paymentState.timestamp > 30 * 60 * 1000) {{
                console.log('🕒 支付状态已超时，清除');
                localStorage.removeItem('current_payment');
                return;
            }}

            // 通过URL参数传递订单信息给Streamlit
            // 关键：必须使用父窗口的URL（top），不是iframe的URL
            const url = new URL(window.top.location);
            url.searchParams.set('restore_order', paymentState.order_id);
            url.searchParams.set('restore_plan', paymentState.plan_name);

            // 如果URL参数已经包含恢复信息，不重复添加
            if (window.top.location.search.includes('restore_order')) {{
                console.log('✅ URL参数已包含恢复信息');
                return;
            }}

            console.log('🔁 更新URL参数并刷新父窗口');
            console.log('🔗 目标URL:', url.toString());
            window.top.location.href = url.toString();
        }} else {{
            console.log('ℹ️ 浏览器中没有保存的支付状态');
        }}
    }})();
    </script>
    <div style="display:none;">Restore attempt</div>
    """
    components.html(html_code, height=0)


def clear_payment_state_from_browser():
    """清除浏览器的支付状态"""
    print("🧹 清除浏览器支付状态")

    html_code = """
    <script>
    (function() {{
        localStorage.removeItem('current_payment');
        console.log('🧹 已清除浏览器支付状态');
    }})();
    </script>
    <div style="display:none;">Payment state cleared</div>
    """
    components.html(html_code, height=0)


def update_check_count_in_browser():
    """更新浏览器中的检查次数"""
    html_code = """
    <script>
    (function() {{
        const savedPayment = localStorage.getItem('current_payment');
        if (savedPayment) {{
            const paymentState = JSON.parse(savedPayment);
            paymentState.auto_check_count = (
                paymentState.auto_check_count || 0
            ) + 1;
            localStorage.setItem(
                'current_payment',
                JSON.stringify(paymentState)
            );
            console.log('🔢 更新检查次数:', paymentState.auto_check_count);
        }}
    }})();
    </script>
    <div style="display:none;">Check count updated</div>
    """
    components.html(html_code, height=0)
