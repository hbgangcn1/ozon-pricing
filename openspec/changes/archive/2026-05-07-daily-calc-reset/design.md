## Context

当前系统有两套计算次数限制体系：

1. **Plan.calc_limit**（套餐级别）：定义每个套餐允许的默认计算次数，`-1` 表示无限
2. **User.remaining_calculations**（用户级别）：记录用户当前剩余次数

问题在于：`reset_free_users_daily_calculations()` 函数存在但从未被调用，系统没有实际的每日重置机制。用户用完分配的次数后将永久失去计算能力。

## Goals / Non-Goals

**Goals:**
- 用户登录时自动检查并重置计算次数
- 仅对有限次数套餐（`calc_limit != -1`）的用户重置
- 避免同一天内重复重置（使用日期跟踪）
- 修复前端显示文本错误

**Non-Goals:**
- 不实现真正的 00:00 定时任务（登录触发即可）
- 不重置付费的无限次用户（`calc_limit == -1`）
- 不提供手动重置按钮（管理员通过调整用户次数实现）

## Decisions

### Decision 1: 登录时触发重置而非后台定时任务

**选择**：在 `api/routes/auth.py` 的 login 成功后调用重置函数

**原因**：
- 架构简单，无需新增调度服务
- 用户下次登录时必然重置，不依赖 cron 或后台线程
- 类似 `postgres_backup_service` 的调度模式过于复杂

**替代方案**：
- 定时任务（APScheduler/schedule）：需要后台线程，服务复杂度增加
- Celery Beat：需要额外依赖和消息队列

### Decision 2: 使用日期字符串跟踪而非时间戳

**选择**：`User.last_calculations_reset_date` 存储 `YYYY-MM-DD` 格式字符串

**原因**：
- 简单直接，比较日期只需字符串对比
- 不需要处理时区问题
- 迁移简单，String 类型

**替代方案**：
- Unix 时间戳：需要转换计算，不直观
- `datetime.date`：需要处理日期比较逻辑

### Decision 3: 重置值来源于套餐而非固定值

**选择**：重置时获取用户套餐的 `calc_limit` 作为重置值

**原因**：
- 符合套餐设计意图：管理员配置的 `calc_limit` 就是每日配额
- 动态适配：套餐修改后，新登录用户立即使用新值

### Decision 4: 仅在 calc_limit != -1 时重置

**选择**：无限次用户（`calc_limit == -1`）不参与重置逻辑

**原因**：
- 无限次用户的 `remaining_calculations` 固定为 `-1`，无需重置
- 避免对无限次用户的不必要数据库操作

## Risks / Trade-offs

| 风险 | 影响 | 缓解方案 |
|------|------|----------|
| 用户长期不登录则长期不重置 | 边缘情况，影响小 | 用户可通过管理员手动调整 |
| 迁移脚本在旧数据上设置 `last_calculations_reset_date=NULL` | 首次登录时会重置，符合预期 | 无需特殊处理 |
| 重置函数执行失败（DB 异常） | 用户登录不受影响，但不会重置 | 添加 try/except 捕获，日志记录 |

## Migration Plan

1. **部署阶段**：
   - Git pull 最新代码（含新迁移脚本）
   - Gunicorn 重启
   - `lifespan` 自动执行 `run_migrations()` 创建新字段
   - 新字段 `last_calculations_reset_date` 默认 `NULL`

2. **运行时行为**：
   - 用户登录时触发重置检查
   - `NULL` 日期 → 视为"从未重置" → 执行重置
   - 已重置过的用户（日期 == 今天）→ 跳过

3. **回滚方案**：
   - 如有问题，删除迁移文件中的 upgrade 内容即可回滚字段添加

## Open Questions

- （无）