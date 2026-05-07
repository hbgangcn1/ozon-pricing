# 测试说明

## 测试清理机制

本项目已经实现了自动测试清理机制，确保测试过程中创建的数据不会污染数据库。

### 自动清理功能

1. **函数级清理** (`clean_db` fixture)
   - 每个测试函数执行前记录现有用户
   - 测试执行后自动清理新创建的用户

2. **测试用户fixture** (`test_user`, `test_admin`)
   - 自动创建测试用户，测试后自动删除
   - 避免手动管理测试用户

3. **会话级清理** (`session_cleanup` fixture)
   - 所有测试结束后自动清理所有非admin用户
   - 确保测试套件运行后数据库保持干净

### 使用方法

```python
# 使用自动清理的测试用户
def test_something(test_user):
    user_id = test_user["id"]
    username = test_user["username"]
    # 测试代码...
    # 测试结束后自动清理

# 使用自动清理的管理员
def test_admin_function(test_admin):
    admin_id = test_admin["id"]
    # 测试代码...
    # 测试结束后自动清理

# 手动创建用户，自动清理
def test_manual_user(clean_db):
    # 手动创建用户
    user_id = create_user("test_user", "password")
    # 测试代码...
    # 测试结束后自动清理新创建的用户
```

### 数据库状态

- 测试前：只保留admin用户
- 测试中：可以创建临时用户
- 测试后：自动清理，只保留admin用户

### 注意事项

1. 不要手动删除admin用户
2. 测试用户会自动使用时间戳命名，避免冲突
3. 如果测试失败，清理机制仍会执行
4. 清理失败会在控制台输出警告信息
5. **保护机制**: 只清理以 `test_` 开头的用户名，手动创建的用户不会被清理
6. **命名规范**: 测试用户应使用 `test_` 前缀，手动用户避免使用此前缀

## Worker 隔离机制

为支持 `pytest-xdist` 并行执行 (`-n auto` / `-n 4` / `-n 2`)，本项目对每个 worker 使用**独立的 PostgreSQL schema** 进行物理隔离，避免并行 worker 之间的表行互相污染、cross-event-loop 错误以及测试数据互相覆盖。

### Schema 命名规则

每个 worker 进程在 `pytest_sessionstart` 阶段创建并接管一个专属 schema：

| 场景 | `PYTEST_XDIST_WORKER` 环境变量 | Schema 名称 |
|---|---|---|
| 单 worker (`pytest -n0`) | 未设置 | `test_master` |
| xdist worker 0 | `gw0` | `test_gw0` |
| xdist worker N | `gwN` | `test_gwN` |

实现位于 [`tests/_db_isolation.py`](_db_isolation.py) 的 `worker_schema_name()`。

### 触发逻辑

1. **master `pytest_sessionstart`** (root `conftest.py`)：清理上一次跑遗留的 `test_*` schema，并兜底创建 `test_master`。
2. **每 worker `pytest_sessionstart`** (`tests/conftest.py`)：调用 `create_worker_schema(...)` + `create_all_in_schema(...)` 在 worker schema 内重建全部 ORM 表，并 monkeypatch `database.AsyncSessionLocal` 为 worker-local sessionmaker（带 `search_path=<schema>, public`、`poolclass=NullPool`）。
3. **master `pytest_sessionfinish`**：兜底再次 DROP 所有 `test_*` schema CASCADE，回收资源。

### PostgreSQL 用户权限要求

跑测试的 PG 用户**必须**对 `logistics` 数据库具备 `CREATE` 权限（用于创建 worker schema）。如果权限不足，`tests/_db_isolation.py:create_worker_schema()` 会在 sessionstart 阶段 fail-fast，并打印修复命令：

```sql
GRANT CREATE ON DATABASE logistics TO <your_pg_user>;
```

默认账号 `logistics_user` 已在生产部署脚本中具备此权限。

### 调试技巧

- **单 worker 调试**：`pytest -n0 tests/test_xxx.py` — 仍走 `test_master` schema，便于打断点。
- **检查 schema 状态**：`psql -d logistics -c "\dn test_*"` — 跑测试中应见到 `test_master` 或 `test_gw*`；跑完后应为 0 行。
- **手工清理残留**：`psql -d logistics -c "DROP SCHEMA test_master CASCADE; DROP SCHEMA test_gw0 CASCADE; ..."`（master 进程 `pytest_sessionfinish` 已自动清理；仅在意外中断时需要手工清理）。
