## Why

JWT access token 的有效期是固定 15 分钟（`security/tokens.py`），用户在有效期内持续操作页面时，仍会在 15 分钟后收到 401 "无效的认证凭证"。这是因为 token 在签发时 `exp` 就已固定，之后不再更新。合理的用户体验是：**有操作就不应该过期**（sliding expiration）。

## What Changes

### Backend
- 新增 `POST /api/auth/refresh` 端点：接受当前 access token，验证用户仍然有效，签发新的 access token（含刷新后的 `exp`）
- `security/tokens.py` 新增 `create_access_token_from_payload()` 函数，从已有 payload 重建 token（避免重新查 DB）
- `api/dependencies.py` 的 `_get_user()` 不变，不引入额外 DB 查询开销

### Frontend
- `frontend/src/services/api.js` 的 axios 响应拦截器新增 token 刷新逻辑：捕获 401 后调用 `/auth/refresh`，用新 token 重试原请求
- `frontend/src/stores/authStore.js` 新增 `refreshToken()` 方法，调用后端刷新接口并更新本地存储
- 新增 `frontend/src/hooks/useTokenRefresh.js` hook，在各页面 mount 时检查 token 剩余有效期，若 < 5 分钟则提前刷新

### New Spec
- `specs/jwt-session-refresh/spec.md`：定义滑动过期的行为契约（刷新阈值、新 token 生命周期、失败处理）

## Capabilities

### New Capabilities
- `jwt-session-refresh`: 前端在 token 即将过期前主动刷新，后端提供验证并重新签发 access token，用户持续操作时永不过期

### Modified Capabilities
- (无 spec 级行为变更，仅实现机制变化)

## Impact

- **后端**: `api/routes/auth.py` 新增 `/auth/refresh` 路由；`security/tokens.py` 新增辅助函数
- **前端**: `api.js` 拦截器改造、`authStore` 新增方法、新增 `useTokenRefresh` hook
- **安全**: refresh 时仍验证用户未被冻结/删除；旧 token 仍可用于一次请求（并发请求兼容）
- **数据库**: 无变更
- **会话管理**: 不涉及 `active_sessions` 表，refresh token 仍为纯 JWT（服务端无状态）
