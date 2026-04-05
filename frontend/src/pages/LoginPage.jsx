import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Package, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuthStore } from '../stores/authStore';
import { authAPI } from '../services/api';

const loginSchema = z.object({
  username: z.string().min(1, '请输入用户名'),
  password: z.string().min(13, '密码至少13位'),
});

function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

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
      navigate('/pricing');
    } catch (error) {
      const msg = error.response?.data?.detail || '登录失败';
      toast.error(msg);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

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

          {/* 注册链接 */}
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
        </form>
      </div>

      {/* 备案信息 */}
      <div className="flex justify-center items-center space-x-6 mt-8 opacity-60 hover:opacity-100 transition-opacity duration-300">
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
    </div>
  );
}

export default LoginPage;

