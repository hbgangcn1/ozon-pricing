import React from 'react'

const COST_COLORS = {
  '进货单价': '#5B8DEF',  // 柔和的蓝色
  '运营利润': '#6DD5A0',  // 柔和的绿色
  '物流运费': '#F2A96B',  // 柔和的橙色
  '佣金': '#B794F6',      // 柔和的紫色
  '代理费': '#63E6BE',    // 柔和的青色
  '推广费': '#F6E05E',    // 柔和的黄色
  '收单费': '#F6AD55',    // 柔和的琥珀色
  '退货损失': '#FC8181',  // 柔和的红色
  '提现费': '#63B3ED',    // 柔和的天蓝色
}

const DEFAULT_COLOR = '#A0AEC0'

function SimplePieChart({ data, size = 200, innerRadius = 3, outerRadius = 95 }) {
  const cx = size / 2
  const cy = size / 2
  const total = data.reduce((s, d) => s + d.value, 0)
  if (total === 0) return <div style={{ textAlign: 'center', color: '#8b949e', fontSize: 13, lineHeight: '200px' }}>暂无数据</div>

  // 按金额从大到小排序
  const sortedData = [...data].sort((a, b) => b.value - a.value)

  let cumAngle = -90 // 从12点位置开始
  const paths = []

  sortedData.forEach((item, i) => {
    const angle = (item.value / total) * 360
    if (angle < 0.1) return
    // 逆时针：角度递减
    const startRad = (cumAngle * Math.PI) / 180
    const endRad = ((cumAngle - angle) * Math.PI) / 180

    const x1Outer = cx + outerRadius * Math.cos(startRad)
    const y1Outer = cy + outerRadius * Math.sin(startRad)
    const x2Outer = cx + outerRadius * Math.cos(endRad)
    const y2Outer = cy + outerRadius * Math.sin(endRad)
    const x1Inner = cx + innerRadius * Math.cos(endRad)
    const y1Inner = cy + innerRadius * Math.sin(endRad)
    const x2Inner = cx + innerRadius * Math.cos(startRad)
    const y2Inner = cy + innerRadius * Math.sin(startRad)
    const largeArc = angle > 180 ? 1 : 0

    // sweep=0 表示逆时针方向
    const d = [
      `M${x1Outer},${y1Outer}`,
      `A${outerRadius},${outerRadius} 0 ${largeArc},0 ${x2Outer},${y2Outer}`,
      `L${x1Inner},${y1Inner}`,
      `A${innerRadius},${innerRadius} 0 ${largeArc},1 ${x2Inner},${y2Inner}`,
      'Z'
    ].join(' ')

    paths.push(
      <path key={item.name} d={d} fill={item.color} stroke="#ffffff" strokeWidth={1.5}>
        <title>{item.name}: ¥{item.value.toFixed(2)} ({item.percentage}%)</title>
      </path>
    )
    cumAngle -= angle
  })

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {paths}
    </svg>
  )
}

function CostPieChart({ breakdown = [], totalPrice = 0, netProfit = 0, shippingComparison, timeComparison }) {
  if (!breakdown || breakdown.length === 0) {
    return (
      <div style={{ textAlign: 'center', color: '#8b949e', padding: '16px 0', fontSize: 13 }}>
        暂无数据
      </div>
    )
  }

  const totalCost = breakdown.reduce((sum, item) => sum + (item.value || 0), 0)
  const pieData = breakdown.map(item => ({
    name: item.label,
    value: item.value || 0,
    color: COST_COLORS[item.label] || DEFAULT_COLOR,
    percentage: totalCost > 0 ? ((item.value || 0) / totalCost * 100).toFixed(1) : 0,
  }))

  return (
    <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(68,72,79,0.3)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '18px' }}>
        {/* 左侧饼图 */}
        <div style={{ width: 200, height: 200, flexShrink: 0 }}>
           <SimplePieChart data={pieData} size={200} innerRadius={3} outerRadius={95} />
         </div>

        {/* 右侧图例 */}
        <div style={{ flex: 1 }}>
          {pieData.map((item) => (
            <div key={item.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '15px', lineHeight: '2.0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
                <span style={{ 
                  width: 15, 
                  height: 15, 
                  borderRadius: '50%', 
                  backgroundColor: item.color, 
                  display: 'inline-block', 
                  flexShrink: 0 
                }} />
                <span style={{ color: '#8b949e' }}>{item.name}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ color: '#f0f6fc', fontWeight: 'bold' }}>¥{item.value.toFixed(2)}</span>
                <span style={{ color: '#8b949e' }}>{item.percentage}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 对比指标行 */}
      {(shippingComparison || timeComparison) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(68,72,79,0.3)', fontSize: '11px' }}>
          {shippingComparison && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#a8abb3' }}>运费对比</span>
              <span style={{ color: shippingComparison.trend === 'up' ? '#FC8181' : '#6DD5A0' }}>
                {shippingComparison.value}{shippingComparison.trend === 'up' ? ' ↑' : ' ↓'}
              </span>
            </div>
          )}
          {timeComparison && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#a8abb3' }}>时效对比</span>
              <span style={{ color: timeComparison.trend === 'up' ? '#FC8181' : '#6DD5A0' }}>
                {timeComparison.value}{timeComparison.trend === 'up' ? ' ↑' : ' ↓'}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default CostPieChart
