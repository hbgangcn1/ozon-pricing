import React, { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, KeyRound, ShieldCheck, LockKeyhole } from 'lucide-react';
import { toast } from 'sonner';
import { authAPI } from '../services/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';

const passwordSchema = z.object({
  newPassword: z.string()
    .min(13, '密码至少13位')
    .regex(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z0-9]).{13,}$/, '密码必须包含大小写字母、数字和特殊字符'),
  confirmPassword: z.string().min(13, '确认密码至少13位'),
}).refine((data) => data.newPassword === data.confirmPassword, {
  message: '两次密码不一致',
  path: ['confirmPassword'],
});

const usernameSchema = z.object({
  username: z.string().min(1, '请输入用户名'),
});

const answerSchema = z.object({
  answer1: z.string().min(1, '请输入第一个答案'),
  answer2: z.string().min(1, '请输入第二个答案'),
});

const steps = [
  { key: 'username', label: '确认账号' },
  { key: 'questions', label: '验证问题' },
  { key: 'newPassword', label: '设置新密码' },
];

function StepIndicator({ currentStep }) {
  return (
    <div className="grid grid-cols-3 gap-2" aria-label="找回密码步骤">
      {steps.map((step, index) => {
        const active = steps.indexOf(currentStep) >= index;
        return (
          <div
            key={step.key}
            className={active
              ? 'rounded-md bg-primary/15 px-3 py-2 text-center text-xs font-medium text-primary'
              : 'rounded-md bg-surface-high px-3 py-2 text-center text-xs text-text-muted'}
          >
            {index + 1}. {step.label}
          </div>
        );
      })}
    </div>
  );
}

function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState('username');
  const [username, setUsername] = useState('');
  const [questions, setQuestions] = useState(['', '']);
  const [resetToken, setResetToken] = useState('');
  const [loading, setLoading] = useState(false);

  const title = useMemo(() => {
    if (step === 'questions') return '回答安全问题';
    if (step === 'newPassword') return '设置新密码';
    return '找回密码';
  }, [step]);

  const usernameForm = useForm({
    resolver: zodResolver(usernameSchema),
    defaultValues: { username: '' },
  });
  const answerForm = useForm({
    resolver: zodResolver(answerSchema),
    defaultValues: { answer1: '', answer2: '' },
  });
  const passwordForm = useForm({
    resolver: zodResolver(passwordSchema),
    defaultValues: { newPassword: '', confirmPassword: '' },
  });

  const handleStartRecovery = usernameForm.handleSubmit(async (data) => {
    setLoading(true);
    try {
      const response = await authAPI.startRecovery(data.username.trim());
      setUsername(data.username.trim());
      setQuestions(response.questions || ['', '']);
      answerForm.reset({ answer1: '', answer2: '' });
      setStep('questions');
    } catch (error) {
      toast.error(error.response?.data?.detail || '无法开始密码找回流程');
    } finally {
      setLoading(false);
    }
  });

  const handleVerifyAnswers = answerForm.handleSubmit(async (data) => {
    setLoading(true);
    try {
      const response = await authAPI.verifySecurity(username, data.answer1, data.answer2);
      setResetToken(response.reset_token);
      passwordForm.reset({ newPassword: '', confirmPassword: '' });
      setStep('newPassword');
    } catch (error) {
      toast.error(error.response?.data?.detail || '验证失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  });

  const handleResetPassword = passwordForm.handleSubmit(async (data) => {
    setLoading(true);
    try {
      await authAPI.resetPassword(resetToken, data.newPassword);
      setResetToken('');
      toast.success('密码重置成功，请重新登录');
      navigate('/login');
    } catch (error) {
      toast.error(error.response?.data?.detail || '密码重置失败');
    } finally {
      setLoading(false);
    }
  });

  return (
    <div className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-surface p-4">
      <Card className="w-full max-w-lg border-surface-high shadow-xl shadow-black/40">
        <CardHeader className="space-y-4">
          <div className="flex items-center justify-center">
            <div className="rounded-xl border border-primary/20 bg-primary/10 p-3">
              {step === 'username' && <KeyRound className="h-6 w-6 text-primary" />}
              {step === 'questions' && <ShieldCheck className="h-6 w-6 text-primary" />}
              {step === 'newPassword' && <LockKeyhole className="h-6 w-6 text-primary" />}
            </div>
          </div>
          <div className="space-y-2 text-center">
            <CardTitle className="text-3xl font-headline">{title}</CardTitle>
            <p className="text-sm text-text-secondary">请按步骤完成密码找回验证</p>
          </div>
          <StepIndicator currentStep={step} />
        </CardHeader>
        <CardContent className="space-y-5">
          {step === 'username' && (
            <form className="space-y-5" onSubmit={handleStartRecovery}>
              <div className="space-y-2">
                <Label htmlFor="recovery-username">用户名</Label>
                <Input
                  id="recovery-username"
                  placeholder="请输入需要找回的用户名"
                  autoComplete="username"
                  {...usernameForm.register('username')}
                />
                {usernameForm.formState.errors.username && (
                  <p className="text-xs text-status-error">
                    {usernameForm.formState.errors.username.message}
                  </p>
                )}
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />继续</> : '下一步'}
              </Button>
            </form>
          )}

          {step === 'questions' && (
            <form className="space-y-5" onSubmit={handleVerifyAnswers}>
              <Alert>
                <AlertTitle>正在验证账号</AlertTitle>
                <AlertDescription>当前账号：{username}</AlertDescription>
              </Alert>
              <div className="space-y-2">
                <Label htmlFor="answer1">安全问题 1</Label>
                <p className="text-sm text-text-secondary">{questions[0]}</p>
                <Input id="answer1" placeholder="请输入第一个答案" {...answerForm.register('answer1')} />
                {answerForm.formState.errors.answer1 && (
                  <p className="text-xs text-status-error">{answerForm.formState.errors.answer1.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="answer2">安全问题 2</Label>
                <p className="text-sm text-text-secondary">{questions[1]}</p>
                <Input id="answer2" placeholder="请输入第二个答案" {...answerForm.register('answer2')} />
                {answerForm.formState.errors.answer2 && (
                  <p className="text-xs text-status-error">{answerForm.formState.errors.answer2.message}</p>
                )}
              </div>
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  className="flex-1"
                  onClick={() => setStep('username')}
                  disabled={loading}
                >
                  上一步
                </Button>
                <Button type="submit" className="flex-1" disabled={loading}>
                  {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />验证中</> : '验证答案'}
                </Button>
              </div>
            </form>
          )}

          {step === 'newPassword' && (
            <form className="space-y-5" onSubmit={handleResetPassword}>
              <div className="space-y-2">
                <Label htmlFor="newPassword">新密码</Label>
                <Input
                  id="newPassword"
                  type="password"
                  placeholder="13位以上，含大小写字母、数字和特殊字符"
                  autoComplete="new-password"
                  {...passwordForm.register('newPassword')}
                />
                {passwordForm.formState.errors.newPassword && (
                  <p className="text-xs text-status-error">
                    {passwordForm.formState.errors.newPassword.message}
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">确认新密码</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="请再次输入新密码"
                  autoComplete="new-password"
                  {...passwordForm.register('confirmPassword')}
                />
                {passwordForm.formState.errors.confirmPassword && (
                  <p className="text-xs text-status-error">
                    {passwordForm.formState.errors.confirmPassword.message}
                  </p>
                )}
              </div>
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  className="flex-1"
                  onClick={() => setStep('questions')}
                  disabled={loading}
                >
                  上一步
                </Button>
                <Button type="submit" className="flex-1" disabled={loading}>
                  {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />提交中</> : '重置密码'}
                </Button>
              </div>
            </form>
          )}

          <div className="text-center text-sm text-text-secondary">
            想起密码了？
            <Link to="/login" className="ml-1 font-medium text-primary hover:text-primary/85">
              返回登录
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default ForgotPasswordPage;
