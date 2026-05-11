import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopHeader from './TopHeader';
import TrialBanner from './TrialBanner';
import TrialExpiredModal from './TrialExpiredModal';
import { SecurityQuestionRequiredDialog } from './SecurityQuestionRequiredDialog';
import { useAuthStore } from '../stores/authStore';

const AppLayout = () => {
  const showSecurityDialog = useAuthStore((state) => state.showSecurityDialog);
  const setShowSecurityDialog = useAuthStore((state) => state.setShowSecurityDialog);
  const logout = useAuthStore((state) => state.logout);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleSuccess = () => setShowSecurityDialog(false);
  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <div className="flex min-h-screen bg-surface">
      {/* 移动端遮罩层 */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* 左侧侧边栏 */}
      <Sidebar 
        mobileMenuOpen={mobileMenuOpen} 
        setMobileMenuOpen={setMobileMenuOpen} 
      />

      {/* 右侧主内容区域 */}
      <div className="flex-1 flex flex-col md:ml-64 w-full">
        {/* 顶部导航栏 */}
        <TopHeader onMenuClick={() => setMobileMenuOpen(true)} />

        {/* 主内容区 */}
        <main className="flex-1 m-4 md:m-6 p-4 md:p-6 overflow-y-auto bg-surface min-h-0">
          <TrialBanner />
          <TrialExpiredModal />
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

