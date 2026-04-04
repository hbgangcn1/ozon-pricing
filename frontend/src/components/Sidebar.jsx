import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  DollarSign, 
  Truck, 
  Key, 
  Crown, 
  CreditCard, 
  Settings, 
  Users, 
  Gift, 
  BarChart3, 
  Info,
  ChevronsLeftRight,
  ChevronDown,
  RefreshCw
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { cn } from '@/lib/utils';
import apiClient from '@/services/api';

function ExchangeRateDropdown() {
  const [rates, setRates] = useState({
    'RUB/CNY': null,
    'CNY/RUB': null,
    'USD/CNY': null,
    'CNY/USD': null,
  });
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchRates = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get('/exchange/rates');
      setRates(data);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('获取汇率失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRates();
    const interval = setInterval(fetchRates, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 text-text-secondary hover:text-text-primary hover:bg-surface rounded-md transition-colors"
      >
        <div className="flex items-center">
          <DollarSign className="w-5 h-5" />
          <span className="ml-3 text-sm">实时汇率</span>
        </div>
        <ChevronDown className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} />
      </button>
      
      {isOpen && (
        <div className="absolute left-0 right-0 mt-1 bg-surface-container border border-surface-highest rounded-md shadow-lg z-50">
          <div className="p-3 border-b border-surface-highest">
            <div className="text-xs text-text-secondary">实时汇率</div>
            <div className="text-xs text-text-muted mt-1">
              {lastUpdated ? `更新: ${lastUpdated.toLocaleTimeString()}` : '加载中...'}
            </div>
          </div>
          <div className="p-2">
            {Object.entries(rates).map(([pair, value]) => (
              <div key={pair} className="flex justify-between items-center py-1 px-2 hover:bg-surface-high rounded">
                <span className="text-sm text-text-secondary">{pair}</span>
                <span className="text-sm font-medium text-text-primary">
                  {value !== null ? value.toFixed(4) : '-'}
                </span>
              </div>
            ))}
          </div>
          <div className="p-2 border-t border-surface-highest">
            <button
              onClick={fetchRates}
              disabled={loading}
              className="w-full flex items-center justify-center py-1 text-xs text-text-secondary hover:text-[#d4d8dd] transition-colors"
            >
              <RefreshCw className={cn('w-3 h-3 mr-1', loading && 'animate-spin')} />
              {loading ? '刷新中...' : '刷新'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const menuItems = [
  { path: '/pricing', icon: DollarSign, label: '物流定价', adminOnly: false },
  { path: '/logistics', icon: Truck, label: '物流管理', adminOnly: false },
  { path: '/account', icon: Key, label: '账号管理', adminOnly: false },
  { path: '/subscription', icon: Crown, label: '订阅管理', adminOnly: false },
  { path: '/payment', icon: CreditCard, label: '支付设置', adminOnly: false },
  { path: '/settings', icon: Settings, label: '系统设置', adminOnly: true },
  { path: '/users', icon: Users, label: '用户管理', adminOnly: true },
  { path: '/plans', icon: Gift, label: '方案管理', adminOnly: true },
  { path: '/statistics', icon: BarChart3, label: '数据统计', adminOnly: true },
  { path: '/about', icon: Info, label: '关于系统', adminOnly: false },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { isAdmin } = useAuthStore();

  const visibleMenuItems = menuItems.filter(item => 
    !item.adminOnly || isAdmin()
  );

  return (
    <div className={cn(
      'bg-surface border-r border-surface-high h-screen fixed left-0 top-0 z-40 transition-all duration-200',
      collapsed ? 'w-16' : 'w-64'
    )}>
      {/* Logo */}
      <div className="p-4 border-b border-surface-high">
        <div className="flex items-center">
          <span className="text-2xl">📦</span>
          {!collapsed && (
            <span className="ml-3 text-lg font-semibold text-text-primary">
              物流定价
            </span>
          )}
        </div>
      </div>

      {/* Menu Items */}
      <nav className="p-4 space-y-2">
        {visibleMenuItems.map((item) => {
          const isActive = location.pathname === item.path;
          const IconComponent = item.icon;
          
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center px-3 py-2 rounded-md transition-colors relative',
                'hover:bg-surface',
                isActive && 'bg-surface-container border-l-2 border-indigo-500'
              )}
            >
              <IconComponent className="w-5 h-5 text-text-secondary" />
              {!collapsed && (
                <span className="ml-3 text-sm text-text-secondary">
                  {item.label}
                </span>
              )}
              {/* Active indicator */}
              {isActive && (
                <div className="absolute left-0 top-0 h-full w-0.5 bg-indigo-500"></div>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Exchange Rate Dropdown */}
      <div className="px-3 py-2">
        <ExchangeRateDropdown />
      </div>

      {/* Collapse Button */}
      <div className="absolute bottom-4 left-4 right-4">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center w-full px-3 py-2 text-text-secondary hover:text-text-primary hover:bg-surface rounded-md transition-colors"
        >
          <ChevronsLeftRight className={cn(
            'w-5 h-5 transition-transform',
            collapsed && 'rotate-180'
          )} />
          {!collapsed && (
            <span className="ml-3 text-sm">
              {collapsed ? '展开' : '收起'}
            </span>
          )}
        </button>
      </div>
    </div>
  );
}
