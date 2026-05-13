import axios from 'axios'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog'
import { Button } from './ui/button'
import { paymentAPI } from '../services/api'
import { toast } from 'sonner'

function usePaymentPolling(orderId, isPolling, onStatusUpdate) {
  const timeoutRef = useRef(null)
  const isMountedRef = useRef(true)
  const abortControllerRef = useRef(null)

  const poll = useCallback(async (currentDelay = 3000) => {
    if (!isPolling || !orderId || !isMountedRef.current) return

    try {
      const signal = abortControllerRef.current?.signal
      const res = await paymentAPI.getStatus(orderId, signal ? { signal } : {})
      
      if (!isMountedRef.current) return
      onStatusUpdate(res)

      if (res.trade_state === 'SUCCESS' || res.trade_state === 'CLOSED') {
        return
      }
    } catch (error) {
      if (error?.name === 'CanceledError' || axios.isCancel(error)) return
      // polling continues on error
    }

    if (!isMountedRef.current) return
    const nextDelay = Math.min(currentDelay * 2, 30000)
    timeoutRef.current = setTimeout(() => poll(nextDelay), nextDelay)
  }, [orderId, isPolling, onStatusUpdate])

  useEffect(() => {
    isMountedRef.current = true
    if (isPolling && orderId) {
      abortControllerRef.current = new AbortController()
      timeoutRef.current = setTimeout(() => poll(3000), 3000)
    }

    return () => {
      isMountedRef.current = false
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
    }
  }, [isPolling, orderId, poll])
}

export default function PaymentQRDialog({
  open,
  onOpenChange,
  planCode,
  _planName,
  billingCycle,
  amount,
  onSuccess,
}) {
  const navigate = useNavigate()
  const [state, setState] = useState('loading')
  const [orderId, setOrderId] = useState('')
  const [codeUrl, setCodeUrl] = useState('')
  const [countdown, setCountdown] = useState(7200)
  
  const timersRef = useRef({
    countdown: null,
    success: null,
  })

  useEffect(() => {
    const timers = timersRef.current
    return () => {
      if (timers.countdown) clearTimeout(timers.countdown)
      if (timers.success) clearTimeout(timers.success)
    }
  }, [])

  const createOrder = useCallback(async (options = {}) => {
    setState('loading')
    setCountdown(7200)
    try {
      const res = await paymentAPI.createOrder({
        plan_code: planCode,
        billing_cycle: billingCycle,
        amount
      }, options)
      setOrderId(res.order_id)
      setCodeUrl(res.code_url)
      setState('scanning')
    } catch (error) {
      if (error?.name === 'CanceledError' || axios.isCancel(error)) return;
      toast.error(error?.response?.data?.message || error?.response?.data?.error || '创建订单失败')
      setState('expired')
    }
  }, [planCode, billingCycle, amount])

  useEffect(() => {
    if (open) {
      const ac = new AbortController()
      createOrder({ signal: ac.signal })
      return () => ac.abort()
    } else {
      setState('loading')
      setOrderId('')
      setCodeUrl('')
      setCountdown(7200)
    }
  }, [open, createOrder])

  useEffect(() => {
    const timers = timersRef.current
    if (timers.countdown) clearTimeout(timers.countdown)
    
    if (state === 'scanning' && countdown > 0) {
      timers.countdown = setTimeout(() => setCountdown(c => c - 1), 1000)
    } else if (state === 'scanning' && countdown === 0) {
      setState('expired')
    }
    
    return () => {
      if (timers.countdown) clearTimeout(timers.countdown)
    }
  }, [state, countdown])

  const handleStatusUpdate = useCallback((res) => {
    if (res.trade_state === 'SUCCESS' || res.status === 'SUCCESS') {
      setState('success')
      onSuccess?.()
      if (timersRef.current.success) clearTimeout(timersRef.current.success)
      timersRef.current.success = setTimeout(() => {
        onOpenChange(false)
      }, 3000)
    } else if (res.trade_state === 'CLOSED') {
      setState('expired')
    }
  }, [onSuccess, onOpenChange])

  usePaymentPolling(orderId, state === 'scanning', handleStatusUpdate)

  const handleOpenChange = (newOpen) => {
    if (!newOpen && state === 'scanning') {
      if (window.confirm('关闭后可在订单页面查看支付状态，确定关闭？')) {
        onOpenChange(false)
      }
    } else {
      onOpenChange(newOpen)
    }
  }

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0')
    const s = (seconds % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  const renderContent = () => {
    if (state === 'loading') {
      return (
        <div className="py-12 text-center space-y-4">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
          <p className="text-text-secondary">正在创建订单...</p>
        </div>
      )
    }

    if (state === 'success') {
      return (
        <div className="py-8 text-center space-y-6">
          <CheckCircle2 className="w-16 h-16 text-status-success mx-auto" />
          <p className="text-lg font-semibold text-text-primary">支付成功</p>
          <Button onClick={() => navigate('/payment')} className="w-full">
            查看订单
          </Button>
        </div>
      )
    }

    if (state === 'expired') {
      return (
        <div className="py-8 text-center space-y-6">
          <XCircle className="w-16 h-16 text-status-error mx-auto" />
          <p className="text-lg font-semibold text-text-primary">二维码已过期</p>
          <Button onClick={createOrder} className="w-full">
            重新发起支付
          </Button>
        </div>
      )
    }

    return (
      <div className="py-4 text-center space-y-6">
        <div className="space-y-1">
          <p className="text-2xl font-bold text-primary">¥{amount.toFixed(2)}</p>
          {orderId && (
            <p className="text-xs text-text-muted font-mono">订单号: {orderId}</p>
          )}
        </div>
        
        <div className="mx-auto rounded-xl bg-white p-4 inline-block">
          <QRCodeSVG value={codeUrl} size={240} bgColor="#ffffff" fgColor="#000000" level="M" />
        </div>

        <div>
          <p className="text-sm text-text-secondary">二维码有效期: {formatTime(countdown)}</p>
        </div>
      </div>
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md bg-surface-container border-surface-high">
        <DialogHeader>
          <DialogTitle className="font-headline">微信支付</DialogTitle>
          <DialogDescription>
            请使用微信扫描下方二维码完成支付
          </DialogDescription>
        </DialogHeader>
        {renderContent()}
      </DialogContent>
    </Dialog>
  )
}
