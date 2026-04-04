import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff } from 'lucide-react';
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
      <div className="w-full max-w-md border border-surface-high rounded-xl p-8" style={{ backgroundColor: '#111113' }}>
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-text-primary mb-2">
            物流定价系统
          </h1>
          <p className="text-text-secondary text-sm">
            请登录您的账户
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* 用户名输入 */}
          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              用户名
            </label>
            <input
              {...register('username')}
              type="text"
              className="w-full border border-surface-highest rounded-md px-3 py-2 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              style={{ color: '#fafafa', backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
              placeholder="请输入用户名"
            />
            {errors.username && (
              <p className="text-red-400 text-xs mt-1">
                {errors.username.message}
              </p>
            )}
          </div>

          {/* 密码输入 */}
          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              密码
            </label>
            <div className="relative">
              <input
                {...register('password')}
                type={showPassword ? 'text' : 'password'}
                className="w-full border border-surface-highest rounded-md px-3 py-2 pr-10 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                style={{ color: '#fafafa', backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
                placeholder="请输入密码"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer"
                style={{ color: '#71717a' }}
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
            {errors.password && (
              <p className="text-red-400 text-xs mt-1">
                {errors.password.message}
              </p>
            )}
          </div>

          {/* 错误提示 */}
          {errorMsg && (
            <div className="bg-red-500/10 border border-red-500/50 rounded-md px-3 py-2 text-red-400 text-sm">
              {errorMsg}
            </div>
          )}

          {/* 登录按钮 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-500 text-white rounded-md py-2 hover:bg-indigo-600 transition-colors disabled:opacity-50 font-medium"
          >
            {loading ? '登录中...' : '登录'}
          </button>

          {/* 注册链接 */}
          <div className="text-center mt-4">
            <span className="text-text-secondary text-sm">没有账号？</span>
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="text-indigo-400 hover:text-indigo-300 text-sm ml-1"
            >
              去注册
            </button>
          </div>
        </form>
      </div>

      {/* 备案信息 */}
      <div className="flex justify-center items-center space-x-4 mt-4">
        <div className="text-xs text-muted-foreground">
          <a
            href="https://beian.miit.gov.cn/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-text-secondary"
          >
            ICP备案号：粤ICP备2025471825号-1
          </a>
        </div>
        <div className="text-xs text-muted-foreground">
          <img
            src="/PSB Filing Icon.png"
            alt="公安备案图标"
            className="inline-block w-5 h-5 align-middle mr-1"
            style={{ verticalAlign: 'middle' }}
          />
          <a
            href="https://beian.mps.gov.cn/#/query/webSearch"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-text-secondary"
          >
            粤公网安备44030002008086号
          </a>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;

