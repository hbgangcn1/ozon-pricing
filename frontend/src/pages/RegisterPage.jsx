import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';
import { useAuthStore } from '../stores/authStore';
import { authAPI } from '../services/api';
import eulaContent from '../最终用户协议.md?raw';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { Checkbox } from 'antd';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';

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

const securityQuestions = [
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

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data) => {
    if (!agreedToEULA) {
      toast.error('请阅读并同意最终用户协议');
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

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-4 fixed inset-0 z-50">
      <div className="w-full max-w-md border border-surface-high rounded-xl p-8" style={{ backgroundColor: '#111113' }}>
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-text-primary mb-2">
            物流定价系统
          </h1>
          <p className="text-text-secondary text-sm">
            创建新账户
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              用户名
            </label>
            <input
              {...register('username')}
              type="text"
              className="w-full border border-surface-highest rounded-md px-3 py-2 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              style={{ color: '#fafafa', backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
              placeholder="请输入用户名（至少3位）"
            />
            {errors.username && (
              <p className="text-red-400 text-xs mt-1">
                {errors.username.message}
              </p>
            )}
          </div>

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
                placeholder="13位以上，含大小写字母、数字和特殊字符"
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

          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              确认密码
            </label>
            <div className="relative">
              <input
                {...register('confirmPassword')}
                type={showConfirmPassword ? 'text' : 'password'}
                className="w-full border border-surface-highest rounded-md px-3 py-2 pr-10 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                style={{ color: '#fafafa', backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
                placeholder="请再次输入密码"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer"
                style={{ color: '#71717a' }}
              >
                {showConfirmPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="text-red-400 text-xs mt-1">
                {errors.confirmPassword.message}
              </p>
            )}
          </div>

          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              安全问题
            </label>
            <select
              {...register('security_question')}
              className="w-full border border-surface-highest rounded-md px-3 py-2 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              style={{ color: '#fafafa', backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
            >
              <option value="">请选择安全问题</option>
              {securityQuestions.map((question, index) => (
                <option key={index} value={question}>
                  {question}
                </option>
              ))}
            </select>
            {errors.security_question && (
              <p className="text-red-400 text-xs mt-1">
                {errors.security_question.message}
              </p>
            )}
          </div>

          <div>
            <label className="text-sm text-text-secondary mb-1.5 block">
              安全答案
            </label>
            <input
              {...register('security_answer')}
              type="text"
              className="w-full border border-surface-highest rounded-md px-3 py-2 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              style={{ color: '#fafafa', backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
              placeholder="请输入安全答案"
            />
            {errors.security_answer && (
              <p className="text-red-400 text-xs mt-1">
                {errors.security_answer.message}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              checked={agreedToEULA}
              onChange={(e) => setAgreedToEULA(e.target.checked)}
              className="text-text-secondary"
            />
            <span className="text-text-secondary text-sm">
              我已阅读并同意
              <button
                type="button"
                onClick={() => setEulaDialogOpen(true)}
                className="text-indigo-400 hover:text-indigo-300 ml-1"
              >
                《最终用户协议》
              </button>
            </span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-500 text-white rounded-md py-2 hover:bg-indigo-600 transition-colors disabled:opacity-50 font-medium"
          >
            {loading ? '注册中...' : '注册'}
          </button>

          <div className="text-center mt-4">
            <span className="text-text-secondary text-sm">已有账号？</span>
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 text-sm ml-1">
              立即登录
            </Link>
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

      <Dialog open={eulaDialogOpen} onOpenChange={setEulaDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto bg-surface border-surface-highest">
          <DialogHeader>
            <DialogTitle className="text-text-primary">最终用户协议</DialogTitle>
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

