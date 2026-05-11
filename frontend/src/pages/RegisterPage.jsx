import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Package, Loader2, AlertCircle, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import { useAuthStore } from '../stores/authStore';
import { authAPI, settingsAPI } from '../services/api';
import eulaContent from '../最终用户协议.md?raw';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { Checkbox } from '../components/ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import PasswordStrengthIndicator from '../components/PasswordStrengthIndicator';

const registerSchema = z.object({
  username: z.string().min(3, '用户名至少3位').max(50, '用户名最多50位'),
  password: z.string()
    .min(13, '密码至少13位')
    .regex(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z0-9]).{13,}$/, '密码必须包含大小写字母、数字和特殊字符'),
  confirmPassword: z.string().min(13, '确认密码至少13位'),
  security_question: z.string().min(1, '请选择安全问题'),
  security_answer: z.string().min(1, '请输入安全答案'),
}).refine((data) => data.password === data.confirmPassword, {
  message: '两次密码不一致',
  path: ['confirmPassword'],
});

const securityQuestionsFallback = [
  '您母亲的姓氏是什么？',
  '您父亲的名字是什么？',
  '您就读的小学名称是什么？',
  '您最喜欢的宠物名字是什么？',
  '您配偶的名字是什么？',
];

function RegisterPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [agreedToEULA, setAgreedToEULA] = useState(false);
  const [eulaDialogOpen, setEulaDialogOpen] = useState(false);
  const [openRegistration, setOpenRegistration] = useState(null);
  const [securityQuestions, setSecurityQuestions] = useState(securityQuestionsFallback);

  useEffect(() => {
    let cancelled = false;
    authAPI.getSecurityQuestions()
      .then(res => {
        const list = res?.data?.questions;
        if (!cancelled && Array.isArray(list) && list.length > 0) {
          setSecurityQuestions(list);
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    settingsAPI.get()
      .then(data => {
        if (!cancelled) {
          setOpenRegistration(data.open_registration !== false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOpenRegistration(true);
        }
      });
    return () => { cancelled = true; };
  }, []);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerSchema),
    mode: 'onChange',
  });

  const passwordValue = watch('password') || '';
  const usernameValue = watch('username') || '';
  const [usernameStatus, setUsernameStatus] = useState({ state: 'idle', reason: null });
  const usernameCheckRef = useRef(0);

  useEffect(() => {
    const trimmed = usernameValue.trim();
    if (trimmed.length < 3) {
      setUsernameStatus({ state: 'idle', reason: null });
      return;
    }
    setUsernameStatus({ state: 'checking', reason: null });
    const requestId = ++usernameCheckRef.current;
    const handle = setTimeout(async () => {
      try {
        const result = await authAPI.checkUsername(trimmed);
        if (requestId !== usernameCheckRef.current) return;
        if (result.available) {
          setUsernameStatus({ state: 'available', reason: null });
        } else {
          setUsernameStatus({ state: 'taken', reason: result.reason || '该用户名不可用' });
        }
      } catch {
        if (requestId !== usernameCheckRef.current) return;
        setUsernameStatus({ state: 'idle', reason: null });
      }
    }, 400);
    return () => clearTimeout(handle);
  }, [usernameValue]);

  const onSubmit = async (data) => {
    if (!agreedToEULA) {
      toast.error('请阅读并同意最终用户协议');
      return;
    }
    if (usernameStatus.state === 'taken') {
      toast.error(usernameStatus.reason || '用户名已被占用');
      return;
    }
    setLoading(true);
    try {
      const response = await authAPI.register({
        username: data.username,
        password: data.password,
        security_question: data.security_question,
        security_answer: data.security_answer,
      });
      // apiClient interceptor 已经 unwrap 了 response.data
      const { access_token, user } = response;
      setAuth(user, access_token);
      toast.success('注册成功');
      navigate('/pricing');
    } catch (error) {
      toast.error(error.response?.data?.detail || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  if (openRegistration === false) {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-4 fixed inset-0 z-50">
        <div className="w-full max-w-lg bg-surface-container border border-surface-high shadow-xl shadow-black/40 rounded-2xl px-12 py-8 animate-fade-in-up">
          <div className="text-center mb-8">
            <div className="w-12 h-12 bg-status-warning/10 rounded-xl flex items-center justify-center mx-auto mb-4 border border-status-warning/20">
              <AlertCircle className="w-6 h-6 text-status-warning" />
            </div>
            <h1 className="text-3xl font-headline font-bold text-text-primary tracking-tight mb-2">
              物流定价系统
            </h1>
            <p className="text-text-secondary text-sm">
              注册功能已关闭
            </p>
          </div>
          <div className="bg-surface-high/50 border border-surface-highest rounded-xl px-6 py-5 text-center">
            <p className="text-text-secondary text-sm mb-4">
              抱歉，当前系统已关闭注册功能。<br />
              如需帮助，请联系管理员。
            </p>
            <Link
              to="/login"
              className="inline-flex items-center justify-center gap-2 w-full bg-primary text-white rounded-lg py-2.5 hover:bg-primary-dim transition-all duration-200 ease-out font-medium"
            >
              返回登录
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-4 fixed inset-0 z-50">
      <div className="w-full max-w-lg bg-surface-container border border-surface-high shadow-xl shadow-black/40 rounded-2xl px-12 py-8 animate-fade-in-up my-auto max-h-[90vh] overflow-y-auto">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mx-auto mb-4 border border-primary/20">
            <Package className="w-6 h-6 text-primary" />
          </div>
          <h1 className="text-3xl font-headline font-bold text-text-primary tracking-tight mb-2">
            物流定价系统
          </h1>
          <p className="text-text-secondary text-sm">
            创建新账户
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="username" className="text-sm font-medium text-text-secondary block">
              用户名
            </label>
            <div className="relative">
              <input
                id="username"
                {...register('username')}
                type="text"
                className="w-full bg-surface-high/50 border border-surface-highest rounded-lg px-3.5 py-2.5 pr-10 text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary focus:bg-surface-high hover:border-surface-bright transition-all duration-200 ease-out"
                placeholder="请输入用户名（至少3位）"
                autoComplete="username"
              />
              {usernameStatus.state === 'checking' && (
                <Loader2
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted animate-spin"
                  data-testid="username-checking"
                />
              )}
              {usernameStatus.state === 'available' && (
                <Check
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-status-success"
                  data-testid="username-available"
                />
              )}
              {usernameStatus.state === 'taken' && (
                <X
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-status-error"
                  data-testid="username-taken"
                />
              )}
            </div>
            {errors.username && (
              <p className="text-status-error text-xs mt-1">
                {errors.username.message}
              </p>
            )}
            {!errors.username && usernameStatus.state === 'taken' && (
              <p className="text-status-error text-xs mt-1" data-testid="username-taken-msg">
                {usernameStatus.reason}
              </p>
            )}
            {!errors.username && usernameStatus.state === 'available' && (
              <p className="text-status-success text-xs mt-1">用户名可用</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium text-text-secondary block">
              密码
            </label>
            <div className="relative">
              <input
                id="password"
                {...register('password')}
                type={showPassword ? 'text' : 'password'}
                className="w-full bg-surface-high/50 border border-surface-highest rounded-lg px-3.5 py-2.5 pr-10 text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary focus:bg-surface-high hover:border-surface-bright transition-all duration-200 ease-out"
                placeholder="13位以上，含大小写字母、数字和特殊字符"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary transition-colors p-1"
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
            {errors.password && (
              <p className="text-status-error text-xs mt-1">
                {errors.password.message}
              </p>
            )}
            <PasswordStrengthIndicator password={passwordValue} />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="confirmPassword" className="text-sm font-medium text-text-secondary block">
              确认密码
            </label>
            <div className="relative">
              <input
                id="confirmPassword"
                {...register('confirmPassword')}
                type={showConfirmPassword ? 'text' : 'password'}
                className="w-full bg-surface-high/50 border border-surface-highest rounded-lg px-3.5 py-2.5 pr-10 text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary focus:bg-surface-high hover:border-surface-bright transition-all duration-200 ease-out"
                placeholder="请再次输入密码"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary transition-colors p-1"
                aria-label={showConfirmPassword ? "隐藏密码" : "显示密码"}
              >
                {showConfirmPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="text-status-error text-xs mt-1">
                {errors.confirmPassword.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="security_question" className="text-sm font-medium text-text-secondary block">
              安全问题
            </label>
            <select
              id="security_question"
              {...register('security_question')}
              className="w-full bg-surface-high/50 border border-surface-highest rounded-lg px-3.5 py-2.5 text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary focus:bg-surface-high hover:border-surface-bright transition-all duration-200 ease-out appearance-none"
            >
              <option value="" className="bg-surface-high">请选择安全问题</option>
              {securityQuestions.map((question, index) => (
                <option key={index} value={question} className="bg-surface-high">
                  {question}
                </option>
              ))}
            </select>
            {errors.security_question && (
              <p className="text-status-error text-xs mt-1">
                {errors.security_question.message}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="security_answer" className="text-sm font-medium text-text-secondary block">
              安全答案
            </label>
            <input
              id="security_answer"
              {...register('security_answer')}
              type="text"
              className="w-full bg-surface-high/50 border border-surface-highest rounded-lg px-3.5 py-2.5 text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary focus:bg-surface-high hover:border-surface-bright transition-all duration-200 ease-out"
              placeholder="请输入安全答案"
            />
            {errors.security_answer && (
              <p className="text-status-error text-xs mt-1">
                {errors.security_answer.message}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Checkbox
              checked={agreedToEULA}
              onCheckedChange={(checked) => setAgreedToEULA(!!checked)}
              className="text-text-secondary"
              data-testid="eula-checkbox"
            />
            <span className="text-text-secondary text-sm">
              我已阅读并同意
              <button
                type="button"
                onClick={() => setEulaDialogOpen(true)}
                className="text-primary hover:text-primary-dim ml-1 transition-colors font-medium"
              >
                《最终用户协议》
              </button>
            </span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-white rounded-lg py-2.5 hover:bg-primary-dim transition-all duration-200 ease-out active:scale-[0.98] font-medium flex items-center justify-center gap-2 disabled:opacity-70 disabled:active:scale-100 mt-4 shadow-lg shadow-primary/20"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                注册中...
              </>
            ) : (
              '注册'
            )}
          </button>

          <div className="text-center pt-2">
            <span className="text-text-muted text-sm">已有账号？</span>
            <Link to="/login" className="text-primary hover:text-primary-dim text-sm ml-1.5 transition-colors font-medium">
              立即登录
            </Link>
          </div>
        </form>
      </div>

      {/* 备案信息 */}
      <div className="flex justify-center items-center space-x-6 mt-6 opacity-60 hover:opacity-100 transition-opacity duration-300 pb-4">
        <div className="text-xs text-text-secondary">
          <a
            href="https://beian.miit.gov.cn/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-text-primary transition-colors"
          >
            ICP备案号：粤ICP备2025471825号-1
          </a>
        </div>
        <div className="text-xs text-text-secondary flex items-center">
          <img
            src="/PSB Filing Icon.png"
            alt="公安备案图标"
            className="inline-block w-4 h-4 align-middle mr-1.5 opacity-80"
          />
          <a
            href="https://beian.mps.gov.cn/#/query/webSearch"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-text-primary transition-colors"
          >
            粤公网安备44030002008086号
          </a>
        </div>
      </div>

      <Dialog open={eulaDialogOpen} onOpenChange={setEulaDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto bg-surface border-surface-highest">
          <DialogHeader>
            <DialogTitle className="text-text-primary font-headline">最终用户协议</DialogTitle>
          </DialogHeader>
          <style>{`.eula-content p { margin-bottom: 16px; } .eula-content h1 { margin: 20px 0 12px; font-size: 1.1em; font-weight: 700; } .eula-content h2 { margin: 20px 0 10px; font-size: 1em; font-weight: 700; } .eula-content h3 { margin: 16px 0 8px; font-size: 0.95em; font-weight: 600; } .eula-content ul, .eula-content ol { margin: 12px 0; padding-left: 24px; } .eula-content li { margin-bottom: 6px; }`}</style>
          <div
            className="eula-content text-text-secondary text-sm leading-relaxed mt-4 max-w-none"
            dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(eulaContent)) }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default RegisterPage;

