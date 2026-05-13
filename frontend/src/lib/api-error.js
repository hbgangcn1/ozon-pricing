export function getApiErrorMessage(error, fallback = '操作失败') {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string' && detail.length > 0) {
    return detail
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const firstMsg = detail[0]?.msg
    if (typeof firstMsg === 'string' && firstMsg.length > 0) {
      return firstMsg
    }
  }

  const message = error?.message
  if (typeof message === 'string' && (message.startsWith('Network Error') || message.includes('ECONNREFUSED'))) {
    return '网络连接失败'
  }

  return fallback
}
