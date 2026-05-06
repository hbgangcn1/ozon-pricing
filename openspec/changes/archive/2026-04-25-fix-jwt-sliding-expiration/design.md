## Context

当前 JWT access token 在 `security/tokens.py` 中签发时 `exp` 就已固定：
```python
# security/tokens.py:81
expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)  # 默认15分钟
payload = { ..., "exp": now + expires_delta }
```

用户在操作过程中，token 不会因为"有活动"而延期。15 分钟固定有效期到期后，即使用户在页面上持续操作，所有后续 API 请求都返回 401。

现有认证架构：
- 后端: `api/dependencies.py` 的 `_get_user()` 验证 token（固定有效期，无刷新机制）
- 前端: `api.js` axios 拦截器，401 时清除 token 并重定向到登录
- 存储: `localStorage` 中的 `api_token`（Phase 19 已迁移 httpOnly cookie）

## Goals / Non-Goals

**Goals:**
- 实现 sliding expiration：用户有操作时 token 持续有效
- 不改变现有 token 存储方式（保持 httpOnly cookie 或 localStorage）
- 对用户透明：不需要主动点击刷新，页面保持操作不中断
- refresh 操作幂等、安全（验证用户未被冻结/删除）

**Non-Goals:**
- 不引入 refresh token 概念（保持纯 JWT 无状态，不写 `active_sessions` 表）
- 不改变 token 有效期上限（access token 仍 15 分钟，只是用新签发的 token 延续会话）
- 不支持多设备同时在线的主动失效（这是独立需求，不在此 change 范围内）

## Decisions

### D1: Refresh 触发策略 — 前端 proactive + 拦截器 fallback

**决定**: 前端在每次 API 请求前检查 token 剩余有效期，若 < 5 分钟则先执行刷新，再发业务请求。

**方案选择**:

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A: 拦截器 401 后刷新 | 请求收到 401 后调用 refresh，重试 | 实现简单 | 用户已经看到 401 错误，体验差 |
| **B: proactive 刷新** | 请求前检查 exp，若快到期先刷新再发 | 用户无感知，体验好 | 需要前端维护时间逻辑 |
| C: 后端每次响应注入新 token | 中间件在响应中附加新 token | 前端改动最少 | 需要改所有响应格式，破坏性大 |

**结论**: 采用方案 B，在 axios 拦截器中实现。对于极短窗口（token 已过期但还未刷新），拦截器 fallback 到 401→refresh→retry 作为保障。

### D2: Refresh 端点 — 新增 `/auth/refresh` 而非复用 `/login`

**决定**: 新增 `POST /api/auth/refresh`，不接受 username/password，只接受当前 access token。

**理由**: `/login` 需要密码且有登录限流（`LoginRateLimiter`），不适合在 normal flow 中调用。专门的 refresh 端点更轻量、安全边界更清晰。

### D3: 刷新后 token 签发 — `create_access_token_from_payload()` 避免重复查 DB

**决定**: refresh 端点解码当前 token 提取 `user_id`，然后执行 `session.get(User, user_id)` 验证用户未被冻结/删除，再签发新 token。

**备选考虑**:
- 直接用 payload 重建 token 不验 DB：风险是用户被冻结后仍能刷新
- 只验证 `exp` 不过期：安全隐患，用户被冻结后仍能操作

**结论**: 轻量 DB 查询（单条 `get(User, id)`）换取安全保障，值得。

### D4: 前端并发刷新去重 — 单例 Promise

**决定**: 如果多个 API 请求同时触发 token 刷新，只执行一次 refresh，其他请求等待结果。

**实现**: `authStore` 中用 `refreshPromise` 变量保存进行中的 refresh Promise，所有请求共享。

```javascript
// authStore.js
let refreshPromise = null;
async refreshToken() {
  if (refreshPromise) return refreshPromise;
  refreshPromise = this._doRefresh();
  try { await refreshPromise } finally { refreshPromise = null; }
}
```

### D5: 前端 token 剩余有效期检测

**决定**: 在 axios 请求拦截器中解码 token 的 `exp`，计算 `exp - now`，若 < 5 分钟（300 秒）则先刷新。

**理由**: 5 分钟窗口足够覆盖一次 API 往返 + refresh + 重试，保证用户操作不中断。

### D6: 后端 refresh 端点不需要 CSRF 验证

**决定**: `/auth/refresh` 端点在 `_extract_token` 走 `api_key`（Bearer token）路径，跳过 `validate_cookie_csrf`。

**理由**: refresh 请求通过 Bearer token 认证（前端在 Authorization header 中发送），不需要 CSRF double-submit 保护。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 用户在 A 页面停留超过 15 分钟无操作，刷新后跳转 B 页面，B 页面用旧 token 立即 401 | 页面 mount 时 `useTokenRefresh` hook 也检查并刷新；刷新后更新 `localStorage`/`cookie`，后续请求用新 token |
| 并发刷新导致旧 token 覆盖新 token | D4 的单例 Promise 保证所有并发请求共用同一个 refresh 结果 |
| 刷新时用户已在其他设备登出（token 有效但用户被删） | D3 中 DB 验证确保用户状态仍有效 |
| 攻击者拿到过期 token 不断刷新延长会话 | refresh 需要有效 token，且有频率限制（利用现有 LoginRateLimiter 或新增 limit）；可增加 max_refreshes 检查 |

## Migration Plan

1. **Phase 1** (无破坏): 新增 `security/tokens.create_access_token_from_payload()` + `POST /auth/refresh` 端点，全部认证路由仍走原有 `_get_user`，功能不变
2. **Phase 2** (前端): 上线 `useTokenRefresh` hook + axios 拦截器刷新逻辑，所有请求在 token 临过期前自动刷新
3. **验证**: 手动测试（停留 14 分钟仍有操作，不 401）；全套测试通过
4. **回滚**: 若有问题，前端 revert 到 Phase 1 状态即可（后端 refresh 端点无业务影响）

## Open Questions

| 问题 | 状态 |
|------|------|
| refresh 频率限制？ | 默认复用 LoginRateLimiter，或在 refresh 端点单独加限制（如最多每分钟 3 次） |
| refresh 后旧 token 是否立即失效？ | **否**，保持向后兼容。服务端 stateless JWT 无法主动失效旧 token，依赖 exp 自然过期。安全性可接受（exp 15 分钟内有效） |
| 是否需要在 refresh 时返回新 session 到前端？ | 否，refresh 端点只返回新 access token，session ID 保持不变 |
