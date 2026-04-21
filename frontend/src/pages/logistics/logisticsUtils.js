import { CONTINUE_UNIT_MAP, DEFAULT_FORM, LOGISTICS_NUMERIC_FIELDS } from './logisticsConstants'

/**
 * 安全提取 API 错误信息，避免将对象渲染到 React toast。
 */
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

export function normalizeContinueUnit(raw) {
  if (!raw) return '100g'
  const value = String(raw).trim().toLowerCase()
  return CONTINUE_UNIT_MAP[value] || (/^\d+$/.test(value) ? `${value}g` : value)
}

export function mapLogisticsRecordToForm(record) {
  return {
    ...DEFAULT_FORM,
    name: record.name ?? '',
    fulfillment_type: record.fulfillment_type ?? 'rfbs',
    destination: record.destination ?? 'RU',
    fbp_service_level: record.fbp_service_level ?? '',
    fbp_company: record.fbp_company ?? '',
    scoring_group: record.scoring_group ?? '',
    is_smart: record.is_smart ?? 0,
    type: record.type ?? 'land',
    fee_mode: record.fee_mode ?? 'base_plus_continue',
    delivery_method: record.delivery_method ?? 'pickup',
    base_fee: record.base_fee != null ? Number(Number(record.base_fee).toFixed(2)) : '',
    first_fee: record.first_fee != null ? Number(Number(record.first_fee).toFixed(2)) : '',
    first_weight_g: record.first_weight_g ?? '',
    continue_fee: record.continue_fee != null ? Number(Number(record.continue_fee).toFixed(5)) : '',
    continue_unit: normalizeContinueUnit(record.continue_unit),
    min_weight: record.min_weight ?? '',
    max_weight: record.max_weight ?? '',
    min_days: record.min_days ?? '',
    max_days: record.max_days ?? '',
    max_sum_of_sides: record.max_sum_of_sides ?? '',
    max_longest_side: record.max_longest_side ?? '',
    min_length: record.min_length ?? '',
    longest_side_threshold: record.longest_side_threshold ?? '',
    max_second_side: record.max_second_side ?? '',
    min_second_side: record.min_second_side ?? '',
    max_third_side: record.max_third_side ?? '',
    volume_mode: record.volume_mode ?? 'none',
    volume_coefficient: record.volume_coefficient ?? '',
    sum_of_sides_threshold: record.sum_of_sides_threshold ?? '',
    min_cylinder_sum: record.min_cylinder_sum ?? '',
    max_cylinder_sum: record.max_cylinder_sum ?? '',
    min_cylinder_length: record.min_cylinder_length ?? '',
    max_cylinder_length: record.max_cylinder_length ?? '',
    price_limit_cny: record.price_limit_cny != null ? Number(record.price_limit_cny).toFixed(2) : '',
    price_min_cny: record.price_min_cny != null ? Number(record.price_min_cny).toFixed(2) : '',
    allow_battery: !!record.allow_battery,
    battery_wh_limit: record.battery_wh_limit ?? '',
    allow_liquid: !!record.allow_liquid,
  }
}

export function buildLogisticsPayload(form) {
  const values = {}

  for (const [key, value] of Object.entries(form)) {
    values[key] = LOGISTICS_NUMERIC_FIELDS.includes(key)
      ? (value !== '' ? Number(value) : undefined)
      : value
  }

  return values
}

export function buildLogisticsParams({
  pageSize,
  currentPage,
  activeTab,
  filterFulfillment,
  filterDestination,
}) {
  const params = {
    limit: pageSize,
    offset: (currentPage - 1) * pageSize,
    type: activeTab,
  }

  if (filterFulfillment !== 'all') params.fulfillment_type = filterFulfillment
  if (filterDestination !== 'all') params.destination = filterDestination

  return params
}

export function buildPaginationItems(currentPage, totalPages) {
  const pages = []
  const maxVisible = 7

  if (totalPages <= maxVisible) {
    for (let page = 1; page <= totalPages; page += 1) {
      pages.push(page)
    }
    return pages
  }

  pages.push(1)
  if (currentPage > 3) pages.push('ellipsis-start')

  let start = Math.max(2, currentPage - 1)
  let end = Math.min(totalPages - 1, currentPage + 1)

  if (currentPage <= 3) end = 4
  if (currentPage >= totalPages - 2) start = totalPages - 3

  for (let page = start; page <= end; page += 1) {
    pages.push(page)
  }

  if (currentPage < totalPages - 2) pages.push('ellipsis-end')
  pages.push(totalPages)
  return pages
}
