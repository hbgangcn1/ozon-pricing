import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Package, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuthStore } from '../stores/authStore';
import { safeReturnTo } from '../lib/safeReturnTo';
import { authAPI, settingsAPI } from '../services/api';

const loginSchema = z.object({
  username: z.string().min(1, '请输入用户名'),
  password: z.string().min(13, '密码至少13位'),
});

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setAuth, isAuthenticated, user, logout } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [openRegistration, setOpenRegistration] = useState(true);
  const searchParams = new URLSearchParams(location.search);
  const returnTo = searchParams.get('returnTo') || '';
  const reason = searchParams.get('reason') || '';

  useEffect(() => {
    if (reason === 'expired') {
      toast.info('您的会话已过期，请重新登录');
    }
  }, [reason]);

  useEffect(() => {
    const controller = new AbortController();
    settingsAPI.get({ signal: controller.signal })
      .then(data => {
        if (!controller.signal.aborted) {
          setOpenRegistration(data.open_registration !== false);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setOpenRegistration(true);
        }
      });
    return () => controller.abort();
  }, []);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data) => {
    setLoading(true);
    setErrorMsg('');
    try {
      const response = await authAPI.login(data.username, data.password);
      // apiClient interceptor 已经 return response.data，所以 response 就是 { access_token, user }
      const { access_token, user } = response;
      setAuth(user, access_token);
      toast.success('登录成功');
      if (reason === 'expired' || returnTo) {
        navigate(safeReturnTo(returnTo), { replace: true });
      } else {
        navigate(safeReturnTo(returnTo));
      }
    } catch (error) {
      const msg = error.response?.data?.detail || '登录失败';
      toast.error(msg);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleContinue = async () => {
    setLoading(true);
    try {
      await authAPI.getMe();
      navigate(safeReturnTo(returnTo), { replace: true });
    } catch (error) {
      if (error.response?.status === 401) {
        logout();
        toast.error('登录已失效,请重新登录');
      } else {
        toast.error('网络错误,请重试');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchAccount = () => {
    logout();
  };

  if (isAuthenticated && user) {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-4 fixed inset-0 z-50">
        <div className="w-full max-w-lg bg-surface-container border border-surface-high shadow-xl shadow-black/40 rounded-2xl px-12 py-8 animate-fade-in-up">
          <div className="text-center mb-8">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mx-auto mb-4 border border-primary/20">
              <Package className="w-6 h-6 text-primary" />
            </div>
            <h1 className="text-3xl font-headline font-bold text-text-primary tracking-tight mb-2">
              物流定价系统
            </h1>
            <p className="text-text-secondary text-sm">
              已登录为 {user.username}
            </p>
          </div>

          <div className="space-y-3">
            <button
              type="button"
              onClick={handleContinue}
              disabled={loading}
              className="w-full bg-primary text-white rounded-lg py-2.5 hover:bg-primary-dim transition-all duration-200 ease-out active:scale-[0.98] font-medium flex items-center justify-center gap-2 disabled:opacity-70 disabled:active:scale-100 shadow-lg shadow-primary/20"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  验证中...
                </>
              ) : (
                '继续使用'
              )}
            </button>

            <button
              type="button"
              onClick={handleSwitchAccount}
              disabled={loading}
              className="w-full bg-surface-high text-text-primary rounded-lg py-2.5 hover:bg-surface-highest border border-surface-highest transition-all duration-200 ease-out active:scale-[0.98] font-medium disabled:opacity-70 disabled:active:scale-100"
            >
              切换账号
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-4 fixed inset-0 z-50">
      <div className="w-full max-w-lg bg-surface-container border border-surface-high shadow-xl shadow-black/40 rounded-2xl px-12 py-8 animate-fade-in-up">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mx-auto mb-4 border border-primary/20">
            <Package className="w-6 h-6 text-primary" />
          </div>
          <h1 className="text-3xl font-headline font-bold text-text-primary tracking-tight mb-2">
            物流定价系统
          </h1>
          <p className="text-text-secondary text-sm">
            请登录您的账户以继续
          </p>
        </div>

        {reason === 'expired' && (
          <div className="mb-5 rounded-lg border border-status-warning/30 bg-status-warning/10 px-4 py-3 text-sm text-status-warning">
            您的会话已过期，请重新登录
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {/* 用户名输入 */}
          <div className="space-y-1.5">
            <label htmlFor="username" className="text-sm font-medium text-text-secondary block">
              用户名
            </label>
            <input
              id="username"
              {...register('username')}
              type="text"
              className="w-full bg-surface-high/50 border border-surface-highest rounded-lg px-3.5 py-2.5 text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary focus:bg-surface-high hover:border-surface-bright transition-all duration-200 ease-out"
              placeholder="请输入用户名"
            />
            {errors.username && (
              <p className="text-status-error text-xs mt-1">
                {errors.username.message}
              </p>
            )}
          </div>

          {/* 密码输入 */}
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
                placeholder="请输入密码"
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
          </div>

          {/* 错误提示 */}
          {errorMsg && (
            <div className="bg-status-error/10 border border-status-error/20 rounded-lg px-4 py-3 text-status-error text-sm flex items-center">
              {errorMsg}
            </div>
          )}

          {/* 登录按钮 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-white rounded-lg py-2.5 hover:bg-primary-dim transition-all duration-200 ease-out active:scale-[0.98] font-medium flex items-center justify-center gap-2 disabled:opacity-70 disabled:active:scale-100 mt-2 shadow-lg shadow-primary/20"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                登录中...
              </>
            ) : (
              '登录'
            )}
          </button>

          <div className="text-center">
            <Link
              to="/forgot-password"
              className="text-sm text-primary hover:text-primary-dim transition-colors font-medium"
            >
              忘记密码？
            </Link>
          </div>

          {/* 注册链接 */}
          {openRegistration && (
            <div className="text-center pt-2">
              <span className="text-text-muted text-sm">没有账号？</span>
              <button
                type="button"
                onClick={() => navigate('/register')}
                className="text-primary hover:text-primary-dim text-sm ml-1.5 transition-colors font-medium"
              >
                去注册
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

export default LoginPage;

