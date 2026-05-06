## ADDED Requirements

### Requirement: 测试用户完整清理
测试套件在运行结束后 SHALL 完整清理所有由测试创建的用户数据，不得在数据库中残留任何测试用户。

#### Scenario: 测试套件结束后无残留
- **WHEN** 完整的pytest测试套件运行结束（无论成功或失败）
- **THEN** 数据库中不存在任何is_test_user标记的用户记录

#### Scenario: 单个测试失败后仍清理
- **WHEN** 某个测试用例执行失败或抛出异常
- **THEN** 该测试创建的用户数据仍 SHALL 被清理（通过fixture的finalizer/teardown机制）

#### Scenario: 所有测试文件使用统一fixture
- **WHEN** 任何测试文件需要创建测试用户
- **THEN** SHALL 通过conftest.py中的共享fixture创建，确保清理逻辑统一管理
