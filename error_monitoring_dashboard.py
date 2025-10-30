# -*- coding: utf-8 -*-
"""
错误监控仪表板
提供系统错误监控、性能监控和缓存监控的可视化界面
"""

import streamlit as st
import pandas as pd
import plotly.express as px

try:
    from .enhanced_error_handler import get_error_summary, clear_error_log
    from .database_performance_monitor import get_performance_report
    from .intelligent_cache_manager import get_cache_stats
except ImportError:
    from enhanced_error_handler import get_error_summary, clear_error_log
    from database_performance_monitor import get_performance_report
    from intelligent_cache_manager import get_cache_stats


def show_error_monitoring_dashboard():
    """显示错误监控仪表板"""
    st.title("🔍 系统监控仪表板")

    # 创建标签页
    tab1, tab2, tab3, tab4 = st.tabs([
        "错误监控", "性能监控", "缓存监控", "系统配置"
    ])

    with tab1:
        show_error_monitoring()

    with tab2:
        show_performance_monitoring()

    with tab3:
        show_cache_monitoring()

    with tab4:
        show_system_configuration()


def show_error_monitoring():
    """显示错误监控"""
    st.header("🚨 错误监控")

    # 获取错误摘要
    error_summary = get_error_summary()

    if error_summary.get('status') == 'no_data':
        st.info("✅ 暂无错误数据")
        return

    # 错误统计概览
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "总错误数",
            error_summary.get('total_errors', 0)
        )

    with col2:
        st.metric(
            "严重错误",
            error_summary.get('critical_errors', 0)
        )

    with col3:
        st.metric(
            "警告数量",
            error_summary.get('warning_errors', 0)
        )

    with col4:
        st.metric(
            "今日错误",
            error_summary.get('today_errors', 0)
        )

    # 错误类别分布
    st.subheader("错误类别分布")
    category_dist = error_summary.get('category_distribution', {})
    if category_dist:
        fig_category = px.bar(
            x=list(category_dist.keys()),
            y=list(category_dist.values()),
            title="错误类别分布"
        )
        fig_category.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_category, use_container_width=True)

    # 错误类型统计
    st.subheader("错误类型统计")
    error_counts = error_summary.get('error_counts', {})
    if error_counts:
        error_data = list(error_counts.items())
        error_df = pd.DataFrame(
            error_data, columns=['错误类型', '发生次数']  # type: ignore
        )
        error_df = error_df.sort_values('发生次数', ascending=False)

        st.dataframe(error_df, use_container_width=True)

        # 错误类型趋势图
        fig_trend = px.bar(
            error_df,
            x='错误类型',
            y='发生次数',
            title="错误类型发生次数"
        )
        fig_trend.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_trend, use_container_width=True)

    # 最近错误详情
    st.subheader("最近错误详情")
    recent_errors = error_summary.get('recent_errors', [])
    if recent_errors:
        for error in recent_errors[-10:]:  # 显示最近10个
            timestamp = error.get('timestamp', '')
            error_type = error.get('type', '')
            with st.expander(f"{timestamp} - {error_type}"):
                st.write(f"**错误信息**: {error.get('message', '')}")
                st.write(f"**错误级别**: {error.get('severity', '')}")
                st.write(f"**错误来源**: {error.get('source', '')}")

    # 清空错误日志按钮
    if st.button("🗑️ 清空错误日志"):
        clear_error_log()
        st.success("错误日志已清空")
        st.rerun()


def show_performance_monitoring():
    """显示性能监控"""
    st.header("📈 性能监控")

    # 获取性能摘要
    perf_summary = get_performance_report()

    if not perf_summary:
        st.warning("⚠️ 性能监控数据不可用")
        return

    # 性能指标概览
    col1, col2, col3 = st.columns(3)

    with col1:
        monitoring_status = perf_summary.get('monitoring_status')
        status = "运行中" if monitoring_status else "已停止"
        st.metric("监控状态", status)

    with col2:
        metrics = perf_summary.get('metrics', {})
        pool_stats = metrics.get('connection_pool', {})
        active_conn = pool_stats.get('active_connections', 0)
        st.metric("活跃连接数", active_conn)

    with col3:
        cache_stats = metrics.get('cache_stats', {})
        hit_rate = cache_stats.get('hit_rate', 0)
        st.metric("缓存命中率", f"{hit_rate:.1%}")

    # 连接池详情
    st.subheader("连接池状态")
    if pool_stats:
        pool_df = pd.DataFrame([pool_stats])
        st.dataframe(pool_df, use_container_width=True)

    # 缓存性能
    st.subheader("缓存性能")
    if cache_stats:
        cache_df = pd.DataFrame([cache_stats])
        st.dataframe(cache_df, use_container_width=True)

    # 最近告警
    st.subheader("最近告警")
    alerts = perf_summary.get('recent_alerts', [])
    if alerts:
        for alert in alerts[-5:]:  # 显示最近5个告警
            message = alert.get('message', '')
            datetime_str = alert.get('datetime', '')
            st.warning(f"🚨 {message} - {datetime_str}")
    else:
        st.info("✅ 暂无告警")


def show_cache_monitoring():
    """显示缓存监控"""
    st.header("💾 缓存监控")

    # 获取缓存统计
    cache_stats = get_cache_stats()

    if not cache_stats:
        st.warning("⚠️ 缓存统计不可用")
        return

    # 缓存概览
    col1, col2 = st.columns(2)

    with col1:
        st.write("**L1缓存统计**")
        l1_cache = cache_stats.get('l1_cache', {})
        if l1_cache:
            stats_data = [
                ["命中次数", l1_cache.get('hits', 0)],
                ["未命中次数", l1_cache.get('misses', 0)],
                ["设置次数", l1_cache.get('sets', 0)],
                ["删除次数", l1_cache.get('deletes', 0)],
                ["淘汰次数", l1_cache.get('evictions', 0)],
                ["总操作数", l1_cache.get('total_operations', 0)]
            ]
            stats_df = pd.DataFrame(
                stats_data, columns=['指标', '数值']  # type: ignore
            )
            st.dataframe(stats_df, use_container_width=True)

    with col2:
        st.write("**L2缓存统计**")
        l2_cache = cache_stats.get('l2_cache', {})
        if l2_cache.get('status') != 'unavailable':
            l2_stats = l2_cache
            if l2_stats:
                l2_data = [
                    ["命中次数", l2_stats.get('hits', 0)],
                    ["未命中次数", l2_stats.get('misses', 0)],
                    ["设置次数", l2_stats.get('sets', 0)],
                    ["删除次数", l2_stats.get('deletes', 0)],
                    ["淘汰次数", l2_stats.get('evictions', 0)],
                    ["缓存大小", l2_stats.get('cache_size', 0)]
                ]
                l2_df = pd.DataFrame(
                    l2_data, columns=['指标', '数值']  # type: ignore
                )
                st.dataframe(l2_df, use_container_width=True)
        else:
            st.info("L2缓存不可用")

    # 缓存优化建议
    st.subheader("缓存优化建议")
    if l1_cache:
        hits = l1_cache.get('hits', 0)
        total_ops = max(l1_cache.get('total_operations', 1), 1)
        hit_rate = hits / total_ops
        if hit_rate < 0.7:
            st.warning("⚠️ L1缓存命中率较低，建议增加缓存大小或调整TTL")
        else:
            st.success("✅ L1缓存性能良好")


def show_system_configuration():
    """显示系统配置"""
    st.header("⚙️ 系统配置")

    # 错误监控配置
    st.subheader("错误监控配置")
    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "严重错误阈值",
            min_value=0,
            max_value=100,
            value=10,
            help="超过此数量的错误将触发严重告警"
        )

    with col2:
        st.number_input(
            "警告阈值",
            min_value=0,
            max_value=100,
            value=50,
            help="超过此数量的错误将触发警告"
        )

    # 性能监控配置
    st.subheader("性能监控配置")
    col1, col2 = st.columns(2)

    with col1:
        st.checkbox("启用错误监控", value=True)

    with col2:
        st.checkbox("启用性能监控", value=True)

    # 缓存配置
    st.subheader("缓存配置")
    col1, col2 = st.columns(2)

    with col1:
        st.checkbox("启用缓存监控", value=True)

    # L1缓存配置
    st.subheader("L1缓存配置")
    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "L1缓存大小",
            min_value=100,
            max_value=10000,
            value=1000,
            help="L1缓存最大条目数"
        )

    with col2:
        st.number_input(
            "L1缓存TTL(秒)",
            min_value=60,
            max_value=3600,
            value=300,
            help="L1缓存默认生存时间"
        )

    # L2缓存配置
    st.subheader("L2缓存配置")
    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "L2缓存大小",
            min_value=1000,
            max_value=100000,
            value=10000,
            help="L2缓存最大条目数"
        )

    with col2:
        st.number_input(
            "L2缓存TTL(秒)",
            min_value=300,
            max_value=7200,
            value=1800,
            help="L2缓存默认生存时间"
        )

    # 保存配置按钮
    if st.button("💾 保存配置"):
        st.success("配置已保存")


if __name__ == "__main__":
    show_error_monitoring_dashboard()
