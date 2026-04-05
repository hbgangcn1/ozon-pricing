import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopHeader from './TopHeader';

const AppLayout = () => {
  return (
    <div className="flex min-h-screen bg-surface">
      {/* 左侧侧边栏 */}
      <Sidebar />
      
      {/* 右侧主内容区域 */}
      <div className="flex-1 flex flex-col ml-64">
        {/* 顶部导航栏 */}
        <TopHeader />
        
        {/* 主内容区 */}
        <main className="flex-1 m-6 p-6 overflow-y-auto bg-zinc-950 min-h-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AppLayout;

