# jwt-session-refresh

## Overview

实现 JWT access token 的滑动过期（sliding expiration），确保在用户有操作期间 session 不会因固定有效期到期而失效。

## Token Lifecycle

### Token Issuance
- 用户登录成功后签发 access token（JWT）
- `exp` = `iat` + 15 分钟（`ACCESS_TOKEN_EXPIRE_MINUTES`）
- Token 存储在 `localStorage`（`api_token`）

### Token Refresh (Sliding Expiration)
- **触发条件**: 前端检测到 token 的 `exp - now < 5 分钟`（300 秒），在发送业务 API 请求前自动调用 `/auth/refresh`
- **刷新后**: 获得新的 access token（新的 `exp`，时间窗口重新开始 15 分钟）
- **用户无感知**: 用户在页面持续操作时，token 自动续期，不会弹出 401 或登录框

### Token Invalidation
- Token 过期后自动失效，服务端 stateless JWT 无法主动撤销
- 用户登出时前端清除 token

## API Specification

### POST /api/auth/refresh

**认证**: Bearer token（当前有效的 access token）

**请求体**: 无需 body，token 在 Authorization header 中传递

**成功响应** (200):
```json
{
  "access_token": "<new_jwt_string>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**错误响应**:
- 401: 当前 token 无效（已过期、格式错误、用户不存在或已冻结）

**行为**:
1. 解码当前 token 的 payload（不验证 `exp`，用 `jwt.decode` 的 `options={"verify_exp": false}`）
2. 提取 `sub`（user_id）验证用户存在且未被冻结
3. 签发新的 access token（新的 `iat` + `exp`）
4. 返回新 token

**频率限制**: 建议每分钟最多 10 次 refresh，防止滥用

## Frontend Behavior

### Token Refresh Logic
- 每次发送 API 请求前，在 axios 请求拦截器中检查 token 剩余有效期
- 若 `exp - now < 300 秒`：先调用 `POST /auth/refresh`，用返回的新 token 替换当前 token，再发送业务请求
- 若 `exp - now >= 300 秒`：直接发送业务请求
- 并发请求共享同一个 refresh Promise（去重）

### Refresh Failure Handling
- 若 refresh 返回 401：清除本地 token，重定向到登录页
- 若网络错误：业务请求正常发送（可能收到 401，由 401 拦截器统一处理）

### useTokenRefresh Hook
- 页面 mount 时执行一次检查
- 页面持续活跃时定期检查（每分钟）

## Security Considerations

1. **用户冻结/删除**: refresh 时必须 DB 验证用户状态
2. **旧 token 继续可用**: 由于 stateless JWT 无法主动撤销，refresh 后旧 token 在其 exp 窗口内仍有效（<= 15 分钟），这是可接受的安全权衡
3. **频率限制**: refresh 端点应有请求频率限制
4. **CSRF**: refresh 通过 Bearer token 认证，不需要 CSRF double-submit 保护

## Dependencies

- `security/tokens.py`: 新增 `create_access_token_from_payload()` 函数
- `api/routes/auth.py`: 新增 `/auth/refresh` 路由
- `api/dependencies.py`: `_get_user()` 逻辑不变
- `frontend/src/services/api.js`: axios 拦截器 + refresh 逻辑
- `frontend/src/stores/authStore.js`: 新增 `refreshToken()` 方法
