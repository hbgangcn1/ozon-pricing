# 自部署指南（Self-hosting）

> 这套 `deploy/` 是**通用部署脚手架**：原作者的实例（cbprice.cn）已停止运营，
> 但这些脚本/配置仍然完整可用——你只需要把下面「需要替换的值」改成你自己的。
>
> 适用于：Linux 单机（Ubuntu/Debian 系，systemd + nginx + PostgreSQL），
> 把 FastAPI 后端 + 已构建的 React 前端跑在同一台机器上。

---

## 1. 目录里有什么

| 文件 | 作用 |
|---|---|
| `deploy.sh` | **一键部署（11 步）**：预检 → 备份 → 拉代码 → 装依赖 → 跑迁移 → 校验 schema → 检查前端产物 → 建日志目录 → 停旧服务 → 装新服务 → 装 nginx → 启动 → 健康检查 |
| `rollback.sh` | **回滚**：代码回滚到 git tag，可选 schema 回滚 / 从 pg_dump 恢复 |
| `nginx-cbprice.conf` | nginx 站点模板（SPA 静态 + `/api` 反代 + 限流 + 安全头 + 微信回调豁免） |
| `fastapi-app.service` | 后端 systemd unit（gunicorn + uvicorn worker） |
| `trial-check.service` / `.timer` | 每小时跑一次「试用到期 + 溢出窗口」检查（避免多 worker 重复触发） |

两个 shell 脚本都通过了 `bash -n` 语法检查；**所有路径/域名都支持环境变量覆盖**，默认值只是原作者实例的值。

---

## 2. 需要替换的值（一览）

| 变量 / 位置 | 默认值（原作者实例） | 换法 |
|---|---|---|
| `PROJECT_DIR` | `/var/www/ozon-pricing-private` | 环境变量或改脚本第 23 行 |
| `LOG_DIR` | `/var/log/cbprice` | 环境变量或改脚本 |
| `NGINX_CONF` | `/etc/nginx/sites-enabled/cbprice.cn` | 环境变量或改脚本 |
| `NGINX_BACKUP_DIR` | `/var/backups/cbprice-nginx` | 环境变量或改脚本 |
| `SITE_URL` | `https://www.cbprice.cn` | 环境变量（第 11 步健康检查用） |
| `User=` / `Group=` | `ozon` | 改 `*.service` |
| `postgresql@12-main.service` | PG 12 主实例 | 改 `*.service` 里的 `After=`/`Requires=` |
| 证书路径 | 原作者证书 | 改 `nginx-cbprice.conf` 的 `ssl_certificate*` |

**一行替换**（在服务器上，进入项目目录后）：

```bash
# 目录 + 用户（三个 service 文件）
sed -i 's#/var/www/ozon-pricing-private#/srv/your-app#g; s/^User=ozon/User=www-data/; s/^Group=ozon/Group=www-data/' \
  deploy/fastapi-app.service deploy/trial-check.service

# nginx 域名
sed 's/cbprice\.cn/your-domain.com/g' deploy/nginx-cbprice.conf \
  | sudo tee /etc/nginx/sites-available/your-app.conf

# 你的 PG 实例名不同则一并改
sed -i 's/postgresql@12-main/postgresql@16-main/g' deploy/fastapi-app.service deploy/trial-check.service
```

> 也可以完全不改文件，直接用环境变量跑：
> ```bash
> PROJECT_DIR=/srv/your-app SITE_URL=https://your-domain.com \
> NGINX_CONF=/etc/nginx/sites-enabled/your-app.conf bash deploy/deploy.sh
> ```
> 注意：环境变量只覆盖 `deploy.sh`/`rollback.sh` 里的路径；`*.service` 是静态文件，仍需 sed。

---

## 3. 一次性准备（新机器）

```bash
# 系统依赖
sudo apt update && sudo apt install -y python3-venv python3-pip nginx postgresql postgresql-contrib git curl

# 建目录与用户（示例用 www-data；也可自建用户）
sudo mkdir -p /srv/your-app /var/log/your-app /var/backups/cbprice-nginx
sudo chown -R www-data:www-data /srv/your-app /var/log/your-app

# 数据库
sudo -u postgres psql -c "CREATE USER app_user WITH PASSWORD '改成强密码';"
sudo -u postgres psql -c "CREATE DATABASE app_db OWNER app_user;"
# 跑测试才需要（pytest 会用 xdist 各建一个 schema）：
sudo -u postgres psql -d app_db -c "GRANT CREATE ON DATABASE app_db TO app_user;"

# Python 依赖（venv 必须建在 $PROJECT_DIR/venv，deploy.sh 与 service 都指向这里）
cd /srv/your-app && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

# 环境变量：.env 必须放在 $PROJECT_DIR/.env（service 的 EnvironmentFile 指向它）
cp .env.example .env && vim .env
# 必填：JWT_SECRET_KEY(>=32字符)、POSTGRES_*、SESSION_HMAC_SECRET、ALLOWED_ORIGINS
# 支付相关留空即禁用微信支付：WECHAT_APP_ID / WECHAT_MCH_ID / WECHAT_API_V3_KEY / 证书路径

# 前端产物（dist 已提交进仓库；如果你改了前端源码，务必重新构建再上传）
cd frontend && npm ci && npm run build
```

**证书**：`nginx-cbprice.conf` 里 `ssl_certificate` 指向 Let's Encrypt 风格的路径，用 certbot 签好再改。
没有 HTTPS 也能起，但要同步删掉 80→443 的 `return 301` 段。

---

## 4. 部署

```bash
# 本地（或 CI）
cd frontend && npm ci && npm run build
git commit -am "build: frontend dist"       # dist 被纳入版本管理，部署脚本直接用它
git push

# 服务器
cd /srv/your-app
git pull
bash deploy/deploy.sh                        # 11 步，任一步失败会 set -e 中止
```

`deploy.sh` 会做（顺序有意义，别跳）：预检磁盘/依赖 → 备份 nginx 配置与打 git tag → 拉代码 →
装 Python 依赖 → `alembic upgrade head` → **`scripts/check_schema_integrity.py` 校验 CHECK 约束** →
检查 `frontend/dist` 存在 → 建日志目录 → 停旧服务 → 装新 systemd unit → 装 nginx 配置并 `nginx -t`（失败自动回滚配置）→
启动服务 → 健康检查（`127.0.0.1:8003/health` + `$SITE_URL/` + `$SITE_URL/api/exchange/rates`）。

**最小手动等价路径**（不想用脚本时）：

```bash
git pull && ./venv/bin/pip install -r requirements.txt
./venv/bin/alembic upgrade head && ./venv/bin/python scripts/check_schema_integrity.py
sudo cp deploy/fastapi-app.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl restart fastapi-app
curl -fsS http://127.0.0.1:8003/health
```

---

## 5. 验证

```bash
systemctl status fastapi-app --no-pager
curl -fsS http://127.0.0.1:8003/health          # 200；db 挂会返回 503（这是设计）
sudo nginx -t && sudo systemctl reload nginx
curl -fsS https://your-domain.com/              # 前端 index.html
curl -fsS https://your-domain.com/api/exchange/rates
journalctl -u fastapi-app -n 50 --no-pager      # 出错先看这里
tail -50 /var/log/your-app/error.log
```

> 生产通过凭证 URL 访问时，裸访问 `/` 返回 **401 是正常的**。

---

## 6. 回滚

```bash
bash deploy/rollback.sh                          # 回滚到最新 pre-deploy-* tag（DB schema 不动）
bash deploy/rollback.sh <tag>                    # 指定 tag
bash deploy/rollback.sh <tag> --auto-schema-rollback        # 同时 alembic downgrade 到该 tag 的 head
bash deploy/rollback.sh <tag> --restore-db-snapshot=/path/dump.sql --yes   # 从 pg_dump 恢复（危险）
```

`deploy.sh` 每次部署前会打 `pre-deploy-<时间戳>` tag，并把旧 nginx 配置备份到 `$NGINX_BACKUP_DIR`。

---

## 7. 定时任务（试用/溢出窗口）

```bash
sudo cp deploy/trial-check.service deploy/trial-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trial-check.timer
systemctl list-timers trial-check.timer
```

用 `oneshot + timer` 而不是在应用里起后台线程，是为了避免 gunicorn 多 worker **重复触发**同一批任务。

---

## 8. 已知坑（都是踩过的）

1. **nginx 备份不能放在 `sites-enabled/` 里**：`*.bak.*` 会被 nginx 当活跃站点加载 → `limit_req_zone` 重复定义 → emergency 模式起不来。脚本默认把备份放 `/var/backups/`。
2. **`alembic check` 不要直接用**：历史库有 SQLite→PG 的类型残留，会产生大量假阳性。CHECK 约束的唯一守卫是 `scripts/check_schema_integrity.py` —— **改 CHECK 约束时，迁移 DDL 与该脚本的 `EXPECTED_CHECK_VALUES` 必须同步**。
3. **`get_db()` 在 `yield` 后自动 commit**：路由里用 `try/except` 吞掉 service 的异常会把脏状态写库。
4. **`frontend/dist` 是纳入版本管理的**：改了前端源码必须重新 `npm run build` 并提交，否则线上跑的是旧产物（`deploy.sh` 只检查产物存在，不会替你构建）。
5. **微信回调路径要三处对齐**：`.env` 的 `WECHAT_NOTIFY_URL`、nginx 的 location、代码里的默认值。历史上存在 `/wechat/notify`、`/api/payments/notify`、`/api/payment/wechat/notify` 三种写法；**回调 location 不要加 `limit_req`**（微信重试会被限流）。
6. **gunicorn 多 worker 跑迁移会竞争**：应用启动时用 `pg_try_advisory_lock` 串行化，保留这段逻辑。
7. **前端测试需要 Node ≥ 20**（`frontend/package.json` 的 `engines`）。Node 22+ 在 vitest 的 jsdom 下拿不到 Web Storage，`src/setupTests.js` 里有兜底 polyfill。

---

## 9. 关于原实例

- `cbprice.cn` 已停止运营；本仓库以「**代码存档 + 可复用部署脚手架**」的形式公开。
- 根目录的 `start_production*.bat`、`install_*.bat`、`rollback_production.sh` 是 Windows 时代/早期运维脚本，**已不适用于新部署**，仅作历史参考；请以本目录的 `deploy.sh` + `rollback.sh` 为准。
- 仓库是 public：`.env`、`cert/`、`wxpaycertificate/`、`xlsx/` 都在 `.gitignore` 里，**不要提交你自己的密钥/证书/供应商数据**。
