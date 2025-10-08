"""
支付自动刷新组件
使用JavaScript实现前端轮询，避免阻塞Streamlit主线程
"""

import streamlit.components.v1 as components
import streamlit as st


def inject_simple_auto_refresh(check_interval_seconds: int = 3):
    """
    注入简单的自动刷新脚本
    每隔指定秒数自动刷新页面

    Args:
        check_interval_seconds: 刷新间隔（秒）
    """
    html_code = f"""
    <script>
    (function() {{
        const intervalSeconds = {check_interval_seconds};
        console.log("🔄 页面将在" + intervalSeconds + "秒后自动刷新");

        setTimeout(() => {{
            console.log("🔄 执行自动刷新");
            window.location.reload();
        }}, intervalSeconds * 1000);
    }})();
    </script>
    <div style="display:none;">Simple auto-refresh enabled</div>
    """

    components.html(html_code, height=0)


def inject_smart_auto_refresh(
    check_interval_seconds: int = 5,
    max_checks: int = 60
):
    """
    智能自动刷新 - 使用localStorage持久化检查次数

    Args:
        check_interval_seconds: 刷新间隔（秒）
        max_checks: 最大检查次数（防止无限刷新）
    """
    print(f"🔧 注入自动刷新脚本: 间隔{check_interval_seconds}秒, "
          f"最多{max_checks}次")

    html_code = f"""
    <script>
    (function() {{
        // 从localStorage获取支付状态和检查次数
        let paymentState = JSON.parse(
            localStorage.getItem('current_payment') || 'null'
        );

        if (!paymentState) {{
            console.log('⚠️ localStorage中没有支付状态，跳过自动刷新');
            return;
        }}

        let checkCount = paymentState.auto_check_count || 0;
        checkCount++;

        // 更新localStorage中的检查次数
        paymentState.auto_check_count = checkCount;
        localStorage.setItem('current_payment', JSON.stringify(paymentState));

        console.log("🔄 自动检查次数: " + checkCount + "/{max_checks}");
        console.log("⏰ 将在{check_interval_seconds}秒后自动刷新页面");

        if (checkCount >= {max_checks}) {{
            console.log("🛑 达到最大检查次数，停止自动刷新");
            // 不清除支付状态，只停止自动刷新
            return;
        }}

        setTimeout(() => {{
            console.log("🔄 执行自动刷新");
            // 刷新时确保携带恢复参数
            // 关键：必须刷新父窗口（top），而不是iframe（window）
            const url = new URL(window.top.location);
            url.searchParams.set('restore_order', paymentState.order_id);
            url.searchParams.set('restore_plan', paymentState.plan_name);
            const targetUrl = url.toString();
            console.log("🔗 刷新目标URL:", targetUrl);
            console.log("📦 携带的恢复参数:", {{
                restore_order: paymentState.order_id,
                restore_plan: paymentState.plan_name
            }});
            // 刷新父窗口
            window.top.location.href = targetUrl;
        }}, {check_interval_seconds} * 1000);
    }})();
    </script>
    <div style="display:none;">
        Smart auto-refresh with localStorage (max {max_checks} checks)
    </div>
    """

    components.html(html_code, height=0)


def show_auto_check_indicator(check_count: int = 0):
    """
    显示自动检查指示器

    Args:
        check_count: 当前检查次数
    """
    st.markdown(f"""
    <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 25px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        font-size: 14px;
        font-weight: 500;
        z-index: 9999;
        animation: pulse 2s infinite;
    ">
        <span style="display: inline-block; margin-right: 8px;">🔄</span>
        自动检查中... (第 {check_count} 次)
    </div>
    <style>
        @keyframes pulse {{
            0%, 100% {{
                transform: scale(1);
                opacity: 1;
            }}
            50% {{
                transform: scale(1.05);
                opacity: 0.9;
            }}
        }}
    </style>
    """, unsafe_allow_html=True)


def show_enhanced_auto_check_indicator(
    check_count: int = 0,
    max_checks: int = 60
):
    """
    显示增强的自动检查指示器（带进度条）

    Args:
        check_count: 当前检查次数
        max_checks: 最大检查次数
    """
    progress = min(check_count / max_checks, 1.0) * 100

    st.markdown(f"""
    <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 20px;
        border-radius: 25px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        font-size: 14px;
        font-weight: 500;
        z-index: 9999;
        animation: pulse 2s infinite;
    ">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 18px;">🔄</span>
            <div>
                <div style="margin-bottom: 6px;">
                    自动检查中... ({check_count}/{max_checks})
                </div>
                <div style="
                    background: rgba(255,255,255,0.3);
                    height: 4px;
                    border-radius: 2px;
                    width: 120px;
                    overflow: hidden;
                ">
                    <div style="
                        background: white;
                        height: 100%;
                        border-radius: 2px;
                        width: {progress}%;
                        transition: width 0.3s ease;
                    "></div>
                </div>
            </div>
        </div>
    </div>
    <style>
        @keyframes pulse {{
            0%, 100% {{
                transform: scale(1);
                opacity: 1;
            }}
            50% {{
                transform: scale(1.05);
                opacity: 0.9;
            }}
        }}
    </style>
    """, unsafe_allow_html=True)
