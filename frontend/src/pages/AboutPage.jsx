import React from 'react';
import { Building2 } from 'lucide-react';

function AboutPage() {
  const companyInfo = [
    {
      label: '公司名称',
      value: '深圳超凡酷玩电子商务有限公司',
    },
    {
      label: '主营业务',
      value: '中俄、中美跨境电商（Ozon、亚马逊、eBay、沃尔玛），同时为跨境卖家提供专业的物流定价解决方案',
    },
    {
      label: '办公地址',
      value: '广东省深圳市龙岗区平湖街道平湖社区平安大道一号华南城铁东物流区14栋219',
    },
    {
      label: '联系电话',
      value: '19328702460',
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-semibold text-text-primary mb-6">
        关于我们
      </h1>

      {/* 公司信息卡片 */}
      <div className="bg-surface border border-surface-high rounded-lg p-6 mb-4">
        <div className="flex items-center mb-4">
          <Building2 className="w-5 h-5 text-indigo-400 mr-2" />
          <h2 className="text-lg font-medium text-text-primary">
            公司信息
          </h2>
        </div>
        
        <table className="w-full">
          <tbody>
            {companyInfo.map((item, index) => (
              <tr key={index} className="border-b border-surface-high">
                <td className="py-3 text-sm text-text-secondary w-32">
                  {item.label}
                </td>
                <td className="py-3 text-sm text-text-primary">
                  {item.value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 业务简介卡片 */}
      <div className="bg-surface border border-surface-high rounded-lg p-6">
        <div className="flex items-center mb-4">
          <span className="text-lg mr-2">🚀</span>
          <h2 className="text-lg font-medium text-text-primary">
            业务简介
          </h2>
        </div>
        
        <div className="text-text-secondary leading-relaxed space-y-2">
          <p>
            我们是一家专注于跨境电商服务的公司，致力于为跨境卖家提供专业的物流定价解决方案。
          </p>
          <p>
            通过智能化的定价系统，帮助卖家快速准确地计算物流成本，优化定价策略，提升竞争力。
          </p>
        </div>
      </div>
    </div>
  );
}

export default AboutPage;

