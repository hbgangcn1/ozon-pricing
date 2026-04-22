import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopHeader from './TopHeader';
import { SecurityQuestionRequiredDialog } from './SecurityQuestionRequiredDialog';
import { useAuthStore } from '../stores/authStore';

const AppLayout = () => {
  const showSecurityDialog = useAuthStore((state) => state.showSecurityDialog);
  const setShowSecurityDialog = useAuthStore((state) => state.setShowSecurityDialog);
  const logout = useAuthStore((state) => state.logout);

  const handleSuccess = () => setShowSecurityDialog(false);
  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <div className="flex min-h-screen bg-surface">
      {/* 左侧侧边栏 */}
      <Sidebar />

      {/* 右侧主内容区域 */}
      <div className="flex-1 flex flex-col ml-64">
        {/* 顶部导航栏 */}
        <TopHeader />

        {/* 主内容区 */}
        <main className="flex-1 m-6 p-6 overflow-y-auto bg-surface min-h-0">
          <Outlet />
        </main>
      </div>

      {showSecurityDialog && (
        <SecurityQuestionRequiredDialog
          open={showSecurityDialog}
          onSuccess={handleSuccess}
          onLogout={handleLogout}
        />
      )}
    </div>
  );
};

export default AppLayout;

