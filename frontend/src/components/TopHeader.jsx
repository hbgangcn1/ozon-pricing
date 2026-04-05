import React from 'react';
import { LogOut, Package } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

const TopHeader = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="h-14 bg-surface border-b border-surface-high flex items-center justify-between px-6 sticky top-0 z-30">
      {/* 左侧：系统标题 */}
      <div className="flex items-center gap-2">
        <Package className="w-4 h-4 text-text-secondary" />
        <span className="text-sm font-medium text-text-secondary">物流定价系统</span>
      </div>

      {/* 右侧：用户信息和操作 */}
      <div className="flex items-center gap-4">
        {/* 管理员 badge */}
        {user?.role === 'admin' && (
          <span className="bg-primary/20 text-primary-dim px-2 py-0.5 rounded-full text-xs">
            管理员
          </span>
        )}
        
        {/* 用户名和欢迎语 */}
        <span className="text-text-secondary text-sm">
          {user?.username} 欢迎回来！
        </span>

        {/* 退出按钮 */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span className="text-sm">退出</span>
        </button>
      </div>
    </div>
  );
};

export default TopHeader;

