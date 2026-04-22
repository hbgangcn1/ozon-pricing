import React, { useState, useEffect } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '../stores/authStore'
import { authAPI } from '../services/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from './ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from './ui/select'
import { Input } from './ui/input'
import { Button } from './ui/button'
import { Label } from './ui/label'

const FALLBACK_QUESTIONS = [
  '您母亲的姓名是？',
  '您父亲的姓名是？',
  '您出生的城市是？',
  '您小学班主任的姓名是？',
  '您最喜欢的宠物名字是？'
]

export function SecurityQuestionRequiredDialog({ open, onSuccess, onLogout }) {
  const [questions, setQuestions] = useState([])
  const [loadingQuestions, setLoadingQuestions] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const logout = useAuthStore((state) => state.logout)

  const {
    control,
    register,
    handleSubmit,
    formState: { errors }
  } = useForm({
    defaultValues: {
      question: '',
      answer: ''
    }
  })

  useEffect(() => {
    let isMounted = true
    if (open && questions.length === 0) {
      setLoadingQuestions(true)
      authAPI.getSecurityQuestions()
        .then((res) => {
          if (!isMounted) return
          let list = FALLBACK_QUESTIONS
          if (Array.isArray(res) && res.length > 0) {
            list = res
          } else if (res?.data && Array.isArray(res.data) && res.data.length > 0) {
            list = res.data
          } else if (res?.questions && Array.isArray(res.questions) && res.questions.length > 0) {
            list = res.questions
          }
          setQuestions(list)
          if (isMounted) setLoadingQuestions(false)
        })
        .catch(() => {
          if (isMounted) setQuestions(FALLBACK_QUESTIONS)
          if (isMounted) setLoadingQuestions(false)
        })
    }
    return () => {
      isMounted = false
    }
  }, [open, questions.length])

  const onSubmit = async (data) => {
    const trimmedAnswer = data.answer.trim()
    if (!trimmedAnswer) {
      toast.error('答案不能为空')
      return
    }

    try {
      setSubmitting(true)
      await authAPI.setSecurityQuestion(data.question, trimmedAnswer)
      toast.success('安全问题设置成功')
      onSuccess?.()
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail
      if (status === 409) {
        toast.error('安全问题已设置，请刷新')
        onSuccess?.()
      } else if (status === 422) {
        toast.error(typeof detail === 'string' ? detail : '输入格式有误')
      } else {
        toast.error(typeof detail === 'string' ? detail : '设置失败，请稍后重试')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleLogout = () => {
    if (onLogout) {
      onLogout()
    } else {
      logout()
      window.location.href = '/login'
    }
  }

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent
        className="sm:max-w-md [&>button.absolute]:hidden"
        onEscapeKeyDown={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>请设置安全问题</DialogTitle>
          <DialogDescription>
            为保护账号，需在继续使用前设置一个安全问题，用于忘记密码时找回。
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="question">安全问题</Label>
            <Controller
              name="question"
              control={control}
              rules={{ required: '请选择一个安全问题' }}
              render={({ field }) => (
                <Select
                  onValueChange={field.onChange}
                  value={field.value}
                  disabled={loadingQuestions || submitting}
                >
                  <SelectTrigger id="question">
                    <SelectValue placeholder={loadingQuestions ? '加载中...' : '请选择...'} />
                  </SelectTrigger>
                  <SelectContent>
                    {questions.map((q) => (
                      <SelectItem key={q} value={q}>
                        {q}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.question && (
              <p className="text-sm text-destructive">{errors.question.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="answer">答案</Label>
            <Input
              id="answer"
              placeholder="请输入答案"
              disabled={submitting}
              {...register('answer', {
                required: '答案不能为空',
                validate: (v) => v.trim().length > 0 || '答案不能为空'
              })}
            />
            {errors.answer && (
              <p className="text-sm text-destructive">{errors.answer.message}</p>
            )}
          </div>

          <DialogFooter className="flex w-full justify-between sm:justify-between items-center mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={handleLogout}
              disabled={submitting}
            >
              退出登录
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              提交
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
