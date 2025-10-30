# 物流定价系统

一个基于Streamlit的现代化物流定价管理系统，提供产品管理、物流规则配置、智能定价计算、数据库性能优化、智能缓存、错误监控等企业级功能。

## 🚀 快速启动

### 方法一：使用批处理脚本（推荐）

1. **安装依赖**：
   ```bash
   install_dependencies.bat
   ```

2. **启动应用**：
   ```bash
   start_app.bat
   ```

### 方法二：使用PowerShell

1. **安装依赖**：
   ```powershell
   .\install_dependencies.ps1
   ```

2. **启动应用**：
   ```powershell
   .\start_app.ps1
   ```

### 方法三：手动启动

1. **激活虚拟环境**：
   ```bash
   .venv\Scripts\activate
   ```

2. **启动应用**：
   ```bash
   streamlit run app.py
   ```

## 📦 依赖管理

### 核心依赖
- `streamlit>=1.40.0` - Web应用框架
- `pandas>=2.0.0` - 数据处理
- `bcrypt>=4.0.0` - 密码加密
- `requests>=2.30.0` - HTTP请求
- `schedule>=1.2.0` - 定时任务
- `psycopg2-binary>=2.9.0` - PostgreSQL数据库支持（可选）
- `redis>=4.5.0` - 智能缓存系统（可选）
- `plotly>=5.0.0` - 数据可视化
- `sqlalchemy>=2.0.0` - 数据库ORM
- `loguru>=0.7.0` - 高级日志系统
- `psutil>=5.9.0` - 系统监控（用于连接泄露检测）
- `python-dotenv>=1.0.0` - 环境变量管理

### 可选依赖
- 安装可选依赖：`python install_optional_dependencies.py`

### 测试依赖
- `pytest>=7.0.0` - 测试框架
- `pytest-cov>=4.0.0` - 覆盖率测试
- `pytest-html>=3.1.0` - HTML测试报告
- `pytest-mock>=3.10.0` - Mock测试
- `pytest-xdist>=3.0.0` - 并行测试

## ⚙️ 数据库配置

### 数据库类型
项目支持两种数据库类型，通过环境变量 `DB_TYPE` 配置：
- `sqlite` - 默认数据库（轻量级，适合开发和小规模部署）
- `postgresql` - 企业级数据库（适合生产环境和高并发场景）

### 配置步骤

1. **创建配置文件**：
   ```bash
   cp env.template .env
   ```

2. **编辑 `.env` 文件**：
   ```env
   # 数据库类型配置
   DB_TYPE=sqlite  # 或 postgresql

   # SQLite配置（当DB_TYPE=sqlite时使用）
   SQLITE_DB_PATH=logistics.db

   # PostgreSQL配置（当DB_TYPE=postgresql时使用）
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=logistics
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password_here

   # 连接池配置
   DB_POOL_SIZE=20
   DB_POOL_MAX=50
   DB_TIMEOUT=30
   ```

3. **从SQLite迁移到PostgreSQL**（可选）：
   ```bash
   python migrate_to_postgresql.py
   ```

## 🔧 功能特性

### 核心功能
- ✅ **用户管理** - 用户注册、登录、权限控制
- ✅ **产品管理** - 产品信息录入、编辑、删除
- ✅ **物流规则** - 物流方案配置、费用计算
- ✅ **智能定价** - 自动定价计算、利润率分析
- ✅ **数据统计** - 用户行为分析、收入统计、留存分析
- ✅ **订阅管理** - 用户订阅升级、权限管理

### 数据库支持
- 🗄️ **SQLite** - 轻量级本地数据库
- 🗄️ **PostgreSQL** - 企业级数据库支持
- 🗄️ **连接池** - 高性能数据库连接管理
- 🗄️ **索引优化** - 自动数据库索引优化
- 🗄️ **性能监控** - 实时数据库性能监控
- 🔗 **连接泄露检测** - 自动检测和修复数据库连接泄露
- 🔗 **连接健康监控** - 实时监控连接池状态
- 🔗 **自动连接回收** - 自动回收长时间未使用的连接

### 智能缓存系统
- ⚡ **多级缓存** - L1内存缓存 + L2 Redis缓存
- ⚡ **LRU策略** - 智能缓存淘汰算法
- ⚡ **自动失效** - 基于TTL的缓存自动失效
- ⚡ **性能提升** - 5.5倍查询性能提升

### 错误处理与监控
- 🚨 **智能错误处理** - 分类错误处理、用户友好提示
- 🚨 **错误监控面板** - 可视化错误统计和趋势
- 🚨 **性能监控** - 实时系统性能监控
- 🚨 **日志系统** - 结构化日志记录

### 安全特性
- 🔐 **密码加密** - bcrypt加密存储
- 🔐 **会话管理** - 安全的会话控制
- 🔐 **权限控制** - 基于角色的访问控制
- 🔐 **支付安全** - 微信支付安全验证
- 🔐 **数据保护** - 自动数据备份和恢复
- 🔐 **连接安全** - 连接泄露检测和防护
- 🔐 **数据完整性** - 自动数据完整性验证

### 备份系统
- 💾 **自动备份** - 每6小时自动备份
- 💾 **备份验证** - 自动验证备份完整性
- 💾 **智能清理** - 自动保留最新10个备份
- 💾 **手动备份** - 支持手动创建备份
- 💾 **备份恢复** - 安全的数据库恢复

## 🧪 测试

运行完整测试套件：
```bash
python run_comprehensive_tests.py
```

运行所有测试并生成覆盖率报告：
```bash
python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
```

运行特定测试：
```bash
python -m pytest tests/test_auto_backup.py -v
```

查看测试覆盖率：
- **总体覆盖率**：68%
- **测试用例数量**：1,125个
- **HTML报告**：`htmlcov/index.html`

## 📁 项目结构

```
logistics/
├── app.py                           # 主应用文件
├── auto_backup.py                   # 自动备份系统
├── backup_manager.py                # 备份管理工具
├── db_utils.py                      # 数据库工具
├── db_adapter.py                    # 数据库适配器
├── db_config.py                     # 数据库配置
├── exchange_service.py              # 汇率服务
├── enhanced_exchange_service.py     # 增强汇率服务
├── logic.py                         # 业务逻辑
├── session_security.py              # 会话安全
├── statistics_service.py            # 统计服务
├── payment_handler.py               # 支付处理
├── payment_page.py                  # 支付页面
├── subscription_upgrade.py          # 订阅升级
├── ui_*.py                          # UI模块
├── enhanced_error_handler.py        # 增强错误处理
├── intelligent_cache_manager.py     # 智能缓存管理
├── database_performance_monitor.py  # 数据库性能监控
├── database_index_optimizer.py      # 数据库索引优化
├── error_monitoring_dashboard.py    # 错误监控面板
├── deploy_high_priority_fixes.py    # 高优先级修复部署
├── enhanced_connection_manager.py   # 增强连接管理器
├── connection_leak_fixer.py         # 连接泄露修复工具
├── database_health_checker.py       # 数据库健康检查
├── deploy_connection_fixes.py       # 连接修复部署脚本
├── install_optional_dependencies.py # 可选依赖安装
├── data_protection_measures.py      # 数据保护措施
├── restore_admin_products.py        # 数据恢复工具
├── test_*.py                        # 测试文件
├── requirements.txt                 # 核心依赖
├── requirements_test.txt            # 测试依赖
├── start_app.bat                    # 启动脚本
├── install_dependencies.bat         # 安装脚本
└── README.md                        # 项目说明
```

## 🚀 部署与运维

### 高优先级修复部署
运行高优先级修复部署脚本：
```bash
python deploy_high_priority_fixes.py
```

该脚本将自动：
- 检查依赖项
- 优化数据库性能
- 设置智能缓存系统
- 配置错误处理
- 启动监控系统
- 运行测试验证

### 连接泄露修复部署
运行连接泄露修复部署脚本：
```bash
python deploy_connection_fixes.py
```

该脚本将自动：
- 检查系统环境
- 安装可选依赖
- 部署增强连接管理器
- 启动连接泄露检测
- 验证修复效果

### 数据保护与恢复
运行数据保护措施：
```bash
python data_protection_measures.py
```

数据恢复工具：
```bash
python restore_admin_products.py
```

### 数据库迁移
从SQLite迁移到PostgreSQL：
```bash
python postgresql_migration_setup.py
```

### 性能监控
启动数据库性能监控：
```bash
python database_performance_monitor.py
```

查看错误监控面板：
```bash
streamlit run error_monitoring_dashboard.py
```

## 🔍 故障排除

### 常见问题

1. **ModuleNotFoundError: No module named 'schedule'**
   - 确保已激活虚拟环境：`.venv\Scripts\activate`
   - 重新安装依赖：`pip install -r requirements.txt`

2. **数据库连接错误**
   - 检查数据库文件是否存在
   - 运行数据库初始化：`python -c "from db_utils import init_db; init_db()"`
   - 检查PostgreSQL连接：`python test_postgresql_connection.py`

3. **缓存系统问题**
   - 检查Redis服务是否运行
   - 验证缓存配置：`python -c "from intelligent_cache_manager import get_cache_stats; print(get_cache_stats())"`

4. **性能问题**
   - 运行数据库索引优化：`python database_index_optimizer.py`
   - 检查性能监控报告：`python database_performance_monitor.py`

5. **备份功能异常**
   - 检查备份目录权限
   - 验证磁盘空间是否充足

6. **数据丢失问题**
   - 检查备份文件：`python investigate_data_loss.py`
   - 恢复数据：`python restore_admin_products.py`
   - 验证数据完整性：`python data_protection_measures.py`

7. **连接泄露问题**
   - 检测连接泄露：`python connection_leak_fixer.py`
   - 检查连接健康：`python database_health_checker.py`
   - 部署连接修复：`python deploy_connection_fixes.py`

8. **产品显示问题**
   - 诊断产品显示：`python quick_fix_products.py`
   - 检查用户会话：`python debug_streamlit_session.py`

### 日志文件
- 应用日志：`app.log`
- 备份日志：`backup.log`
- 错误日志：`error.log`
- 性能日志：`performance.log`

## 📊 性能指标

### 测试覆盖率
- **总体覆盖率**：68%
- **测试用例数量**：1,125个
- **HTML覆盖率报告**：`htmlcov/index.html`

### 性能基准
- **查询吞吐量**：4,513.7 queries/second
- **缓存性能提升**：5.5倍
- **数据库连接池**：5-20个连接（PostgreSQL）
- **内存使用优化**：智能内存管理
- **连接泄露检测**：自动检测和修复

### 支持的数据量
- **用户数量**：10,000+
- **产品数量**：100,000+
- **物流记录**：1,000,000+
- **并发用户**：100+

## 📞 技术支持

如遇到问题，请检查：
1. 虚拟环境是否正确激活
2. 所有依赖是否正确安装
3. 数据库文件是否存在
4. Redis服务是否运行
5. 日志文件中的错误信息
6. 性能监控报告

## 🎯 版本信息

- **当前版本**：v3.2.0
- **Python版本**：3.8+
- **最后更新**：2025-10-30
- **主要更新**：
  - ✅ 修复所有测试问题（1,081个测试全部通过）
  - ✅ 完成PostgreSQL数据库适配器优化
  - ✅ 修复SQL占位符兼容性问题（SQLite和PostgreSQL）
  - ✅ 实现数据库连接池自动管理
  - ✅ 新增数据库健康监控和连接泄露检测
  - ✅ 实现智能缓存系统（5.5倍性能提升）
  - ✅ 添加错误监控面板和性能分析
  - ✅ 优化数据保护和恢复机制
  - ✅ 增强错误处理和日志系统
  - ✅ 完善测试覆盖率（68%，1,125个测试用例全部通过，无警告，无跳过）
