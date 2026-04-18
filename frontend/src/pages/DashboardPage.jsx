import React, { useEffect, useState, useMemo } from 'react';
import { Package, Truck, User, Activity } from 'lucide-react';
import { Skeleton } from '../components/ui/skeleton';
import { productsAPI, logisticsAPI } from '../services/api';

function DashboardPage() {
  const [stats, setStats] = useState({
    products: 0,
    logistics: 0,
    loading: true,
  });

  useEffect(() => {
    const controller = new AbortController()
    const fetchData = async () => {
      try {
        const [productsRes, logisticsRes] = await Promise.all([
          productsAPI.getAll(),
          logisticsAPI.getAll(),
        ]);
        if (!controller.signal.aborted) {
          setStats({
            products: Array.isArray(productsRes) ? productsRes.length : 0,
            logistics: Array.isArray(logisticsRes) ? logisticsRes.length : 0,
            loading: false,
          });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setStats((prev) => ({ ...prev, loading: false }));
        }
      }
    };
    fetchData();
    return () => { controller.abort() }
  }, []);

  const statisticCards = useMemo(() => [
    {
      title: '产品数量',
      value: stats.products,
      icon: Package,
      loading: stats.loading,
      trend: 'stable',
    },
    {
      title: '物流规则',
      value: stats.logistics,
      icon: Truck,
      loading: stats.loading,
      trend: 'stable',
    },
    {
      title: '用户角色',
      value: '管理员',
      icon: User,
      loading: false,
      trend: 'normal',
    },
    {
      title: '系统状态',
      value: '正常',
      icon: Activity,
      loading: false,
      trend: 'normal',
    },
  ], [stats]);

  return (
    <div>
      <h1 className="text-xl font-semibold font-headline tracking-tight text-text-primary mb-6">
        系统概览
      </h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statisticCards.map((card) => (
          <div key={card.title} className="bg-surface-container border border-surface-high rounded-lg p-6">
            {card.loading ? (
              <div className="space-y-3">
                <Skeleton className="w-8 h-8" />
                <Skeleton className="w-16 h-8" />
                <Skeleton className="w-20 h-4" />
              </div>
            ) : (
              <>
                <card.icon className="w-8 h-8 text-primary-dim mb-3" />
                <div className="text-2xl font-headline font-bold text-text-primary tracking-tight">
                  {card.value}
                </div>
                <div className="text-sm text-text-secondary mt-1">
                  {card.title}
                </div>
                {card.trend && (
                  <div className="mt-2">
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-status-success/15 text-status-success">
                      {card.trend === 'stable' ? '稳定' : '正常'}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default DashboardPage;

