## ADDED Requirements

### Requirement: 一键启动前后端开发服务
系统 SHALL 提供 PowerShell 脚本（`start_dev.ps1`）和 BAT 脚本（`start_dev.bat`），一键同时启动 FastAPI 后端（uvicorn port 8003）和 Vite 前端（port 3001）。

#### Scenario: PowerShell 脚本启动
- **WHEN** 用户在项目根目录运行 `.\start_dev.ps1`
- **THEN** 后端 uvicorn 和前端 vite dev server 同时启动，两个服务的日志输出可见

#### Scenario: BAT 脚本启动
- **WHEN** 用户在项目根目录运行 `start_dev.bat`
- **THEN** 后端 uvicorn 和前端 vite dev server 同时启动

#### Scenario: 终止脚本停止所有服务
- **WHEN** 用户在启动脚本的终端按 Ctrl+C
- **THEN** 前后端服务均被终止，端口被释放

### Requirement: 脚本包含环境检查
启动脚本 SHALL 在启动服务前检查必要条件（Python 虚拟环境、Node.js、npm 依赖），并在条件不满足时给出明确提示。

#### Scenario: 虚拟环境未激活
- **WHEN** 脚本检测到 Python 虚拟环境未激活
- **THEN** 脚本自动激活 `.venv` 或提示用户手动激活
