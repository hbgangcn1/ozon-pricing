import { DEFAULT_PRECISE } from './pricingConstants'

export function getApiError(error) {
  try {
    const detail = error?.response?.data?.detail
    if (!detail) return null
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail[0]?.msg || detail[0]?.message || String(detail[0])
    }
    if (typeof detail === 'object') {
      return detail?.msg || detail?.message || JSON.stringify(detail)
    }
    return String(detail)
  } catch {
    return null
  }
}

function toMoneyString(value) {
  return value != null ? Number(value).toFixed(2) : ''
}

function toPercentString(value) {
  return String(Math.round((value || 0) * 100))
}

export function mapProductToEditorForm(product) {
  return {
    name: product.name || '',
    unit_price: toMoneyString(product.unit_price),
    labeling_fee: toMoneyString(product.labeling_fee || 0),
    shipping_fee: toMoneyString(product.shipping_fee || 0),
    weight_g: String(product.weight_g || ''),
    length_cm: String(product.length_cm || ''),
    width_cm: String(product.width_cm || ''),
    height_cm: String(product.height_cm || ''),
    is_cylinder: product.is_cylinder ? 'cylinder' : 'regular',
    cylinder_diameter: String(product.cylinder_diameter || ''),
    cylinder_length: String(product.cylinder_length || ''),
    has_battery: !!product.has_battery,
    battery_capacity_wh: String(product.battery_capacity_wh || ''),
    battery_capacity_mah: String(product.battery_capacity_mah || ''),
    battery_voltage: String(product.battery_voltage || ''),
    battery_capacity_type: product.battery_capacity_type || 'wh',
    has_msds: !!product.has_msds,
    has_liquid: !!product.has_liquid,
    commission_category_id: product.commission_category_id ? String(product.commission_category_id) : '',
    commission_rate: toPercentString(product.commission_rate),
    target_profit_margin: toPercentString(product.target_profit_margin),
    promotion_cost_rate: toPercentString(product.promotion_cost_rate),
    withdrawal_fee_rate: toPercentString(product.withdrawal_fee_rate),
    payment_processing_fee: toPercentString(product.payment_processing_fee),
    return_rate: toPercentString(product.return_rate),
    vat_rate: toPercentString(product.vat_rate),
  }
}

export function mapProductToPreciseForm(product, productId) {
  return {
    ...DEFAULT_PRECISE,
    product_id: productId,
    name: product.name || '',
    unit_price: toMoneyString(product.unit_price),
    labeling_fee: toMoneyString(product.labeling_fee || 0),
    shipping_fee: toMoneyString(product.shipping_fee || 0),
    weight_g: String(product.weight_g || ''),
    length_cm: String(product.length_cm || ''),
    width_cm: String(product.width_cm || ''),
    height_cm: String(product.height_cm || ''),
    is_cylinder: product.is_cylinder ? 'cylinder' : 'regular',
    cylinder_diameter: String(product.cylinder_diameter || ''),
    cylinder_length: String(product.cylinder_length || ''),
    has_battery: !!product.has_battery,
    battery_capacity_wh: String(product.battery_capacity_wh || ''),
    battery_capacity_mah: String(product.battery_capacity_mah || ''),
    battery_voltage: String(product.battery_voltage || ''),
    battery_capacity_type: product.battery_capacity_type || 'wh',
    has_msds: !!product.has_msds,
    has_liquid: !!product.has_liquid,
    commission_category_id: product.commission_category_id ? String(product.commission_category_id) : '',
    commission_rate: toPercentString(product.commission_rate),
    target_profit_margin: toPercentString(product.target_profit_margin),
    promotion_cost_rate: toPercentString(product.promotion_cost_rate),
    withdrawal_fee_rate: toPercentString(product.withdrawal_fee_rate),
    payment_processing_fee: toPercentString(product.payment_processing_fee),
    return_rate: toPercentString(product.return_rate),
    vat_rate: toPercentString(product.vat_rate),
  }
}

function validateDimensions(form) {
  if (form.is_cylinder === 'regular') {
    if (Number(form.length_cm) <= 0) return '长度不能为 0'
    if (Number(form.width_cm) <= 0) return '宽度不能为 0'
    if (Number(form.height_cm) <= 0) return '高度不能为 0'
  }

  if (form.is_cylinder === 'cylinder') {
    if (Number(form.cylinder_diameter) <= 0) return '圆柱直径不能为 0'
    if (Number(form.cylinder_length) <= 0) return '圆柱长度不能为 0'
  }

  return null
}

export function validateEditorProduct(form, products, editingProduct) {
  if (!form.name || !form.unit_price || !form.weight_g) {
    return '请填写名称、进货单价和重量'
  }
  if (Number(form.weight_g) <= 0) return '商品重量不能为 0'

  const dimensionError = validateDimensions(form)
  if (dimensionError) return dimensionError

  const isDuplicate = products.some((product) => {
    if (editingProduct && product.id === editingProduct.id) return false
    return product.name === form.name
  })

  return isDuplicate ? '存在重名产品' : null
}

export function validatePreciseProduct(form, products) {
  if (!form.name || !form.unit_price || !form.weight_g) {
    return '请填写名称、进货单价和重量'
  }
  if (Number(form.weight_g) <= 0) return '商品重量不能为 0'

  const dimensionError = validateDimensions(form)
  if (dimensionError) return dimensionError

  return products.some((product) => product.name === form.name) ? '已有同名产品' : null
}

export function validatePreciseCalculation(form) {
  if (!form.name && !form.product_id) return '请填写产品名称或从列表选择产品'
  if (!form.weight_g) return '请填写重量'
  if (Number(form.weight_g) <= 0) return '商品重量不能为 0'

  const dimensionError = validateDimensions(form)
  if (dimensionError) return dimensionError

  if (!form.product_id && !form.unit_price) return '请选择产品或填写进货单价'
  return null
}

export function buildFastPayload(form) {
  return {
    unit_price: Number(form.unit_price),
    weight_g: Number(form.weight_g),
    commission_rate: Number(form.commission_rate) / 100,
    target_profit_margin: Number(form.target_profit_margin) / 100,
    promotion_cost_rate: Number(form.promotion_cost_rate) / 100,
    withdrawal_fee_rate: Number(form.withdrawal_fee_rate) / 100,
    payment_processing_fee: Number(form.payment_processing_fee) / 100,
    return_rate: Number(form.return_rate) / 100,
    vat_rate: Number(form.vat_rate) / 100,
  }
}

export function buildProductPayload(form) {
  const isCylinder = form.is_cylinder === 'cylinder'

  return {
    name: form.name,
    unit_price: Number(form.unit_price),
    labeling_fee: Number(form.labeling_fee) || 0,
    shipping_fee: Number(form.shipping_fee) || 0,
    weight_g: Number(form.weight_g),
    length_cm: isCylinder ? 0 : (Number(form.length_cm) || 0),
    width_cm: isCylinder ? 0 : (Number(form.width_cm) || 0),
    height_cm: isCylinder ? 0 : (Number(form.height_cm) || 0),
    is_cylinder: isCylinder,
    cylinder_diameter: isCylinder ? (Number(form.cylinder_diameter) || 0) : 0,
    cylinder_length: isCylinder ? (Number(form.cylinder_length) || 0) : 0,
    has_battery: form.has_battery,
    has_liquid: form.has_liquid,
    commission_category_id: form.commission_category_id && form.commission_category_id !== 'none'
      ? Number(form.commission_category_id)
      : null,
    commission_rate: (Number(form.commission_rate) || 0) / 100,
    target_profit_margin: (Number(form.target_profit_margin) || 0) / 100,
    promotion_cost_rate: (Number(form.promotion_cost_rate) || 0) / 100,
    withdrawal_fee_rate: (Number(form.withdrawal_fee_rate) || 0) / 100,
    payment_processing_fee: (Number(form.payment_processing_fee) || 0) / 100,
    return_rate: (Number(form.return_rate) || 0) / 100,
    vat_rate: (Number(form.vat_rate) || 0) / 100,
  }
}

export function getGroupedData(groupedResult, key, showBreakeven) {
  const displayKey = showBreakeven ? `breakeven_${key}` : key
  return groupedResult?.[displayKey] || groupedResult?.[key] || null
}

export function getActiveFilteredLogistics({
  activeTab,
  result,
  groupedResult,
  groupActiveTab,
  cisActiveTab,
}) {
  if (activeTab !== 'precise' || !groupedResult) {
    return result?.filtered_logistics || null
  }

  return groupActiveTab === 'rfbs_cis'
    ? groupedResult?.[cisActiveTab]?.filtered_logistics || null
    : groupedResult?.[groupActiveTab]?.filtered_logistics || null
}
