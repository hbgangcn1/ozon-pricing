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
