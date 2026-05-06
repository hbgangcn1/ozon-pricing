## 1. Backend — Security Token Helper

- [x] 1.1 在 `security/tokens.py` 新增 `create_access_token_from_payload(payload, expires_delta=None)` 函数：从已有 payload 提取 user_id/username/role，重新签发 token（避免 refresh 时重复查 DB 获取这些信息）

## 2. Backend — Auth Refresh Endpoint

- [x] 2.1 在 `api/routes/auth.py` 新增 `POST /auth/refresh-access` 路由：接受 Bearer token，解码（不验证 exp）、验证用户存在且未冻结、签发新 token、返回 `{access_token, token_type, expires_in}`
- [x] 2.2 在 `api/routes/auth.py` 新增路由前缀 `/auth/refresh-access`（已在 router 中注册）
- [x] 2.3 `security/tokens.py` 新增 `ACCESS_TOKEN_EXPIRE_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60` 常量，供前端计算剩余时间使用

## 3. Frontend — authStore refreshToken

- [x] 3.1 在 `frontend/src/stores/authStore.js` 新增 `refreshToken()` 方法：调用 `POST /api/auth/refresh-access`，用返回的新 `access_token` 更新 `localStorage` 中的 `api_token`
- [x] 3.2 在 `authStore` 中实现并发刷新去重（`refreshPromise` 单例模式）
- [x] 3.3 `authStore` 新增 `getTokenExpiry()` 方法：从 `localStorage` 的 token 解码 `exp` 并返回剩余秒数

## 4. Frontend — axios Interceptor Refresh Logic

- [x] 4.1 修改 `frontend/src/services/api.js` 请求拦截器：在发送请求前检查 token 剩余有效期，若 < 300 秒则先调用 `authStore.refreshToken()` 再发送请求
- [x] 4.2 修改 `api.js` 401 响应拦截器：收到 401 后调用 `authStore.refreshToken()`，用新 token 重试原请求一次；若重试仍 401 或 refresh 失败，则清除 token 重定向到登录

## 5. Frontend — useTokenRefresh Hook

- [x] 5.1 新增 `frontend/src/hooks/useTokenRefresh.js` hook：页面 mount 时检查 token 剩余有效期，若 < 5 分钟则触发刷新
- [x] 5.2 在 `App.jsx` 或各需要保持会话的页面引入 `useTokenRefresh` hook

## 6. Tests — Backend

- [x] 6.1 在 `tests/` 新增 `test_auth_refresh.py`：测试 refresh 端点成功返回新 token、401（无效 token）、401（用户不存在）、401（用户已冻结）等场景
- [x] 6.2 在 `tests/test_jwt_tokens.py` 新增 `test_create_access_token_from_payload` 测试用例

## 7. Tests — Frontend

- [x] 7.1 在 `frontend/src/__tests__/authStore.test.js` 新增 `refreshToken` 测试：mock `api.auth.refresh`，验证更新 `localStorage` 和去重逻辑
- [x] 7.2 在 `frontend/src/__tests__/api.test.js` 新增 refresh 拦截器测试：验证 token 临过期时自动触发 refresh

## 8. Verification

- [x] 8.1 `python -m flake8 security/tokens.py api/routes/auth.py` — 零 lint 错误
- [x] 8.2 `python -m pytest tests/test_auth_refresh.py --tb=short` — 全部通过
- [x] 8.3 `npm run lint` (frontend/) — 零 lint 警告
- [x] 8.4 `npm run test` (frontend/) — 全部通过
- [x] 8.5 `npm run build` (frontend/) — 构建成功
- [ ] 8.6 手动验证：登录后操作页面，等待 14 分钟，确认不弹出 401；等待 16 分钟（token 过期），确认刷新成功后会话延续
