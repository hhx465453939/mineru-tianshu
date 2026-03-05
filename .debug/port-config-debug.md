# 端口配置 Debug 记录

## 元信息
- 模块名称: port-config
- 创建时间: 2026-03-05 21:35
- 最后更新: 2026-03-05 21:35
- 相关文件: `.env`, `.env.example`, `backend/start_all.py`, `backend/api_server.py`, `backend/litserve_worker.py`, `backend/task_scheduler.py`, `backend/mcp_server.py`, `frontend/.env.development`, `frontend/.env.example`, `frontend/src/api/client.ts`, `frontend/vite.config.ts`, `frontend/src/views/ApiDocsScalar.vue`, `docs/WINDOWS_DEPLOYMENT.md`
- 依赖模块: backend, frontend, launcher
- 用户说明书路径（涉及前端功能时）: `docs/WINDOWS_DEPLOYMENT.md`
- 开发/部署文档路径（涉及后端或环境时）: `docs/WINDOWS_DEPLOYMENT.md`

## 运行上下文与测试规则
- 运行环境: 本机 Windows
- SSH 方式（若远程）: 不适用
- 远程项目路径（若远程）: 不适用
- 验证/Checkfix 执行方式: 本地 PowerShell 执行

## 上下文关系网络
- 文件结构: 启动端口由 `.env` + `backend/start_all.py` 默认值共同决定，前端请求端口由 `frontend/.env.development` 与 `frontend/src/api/client.ts` 决定，`vite.config.ts` 影响 `/api` 代理。
- 函数调用链: `start_dev.py` -> `backend/start_all.py` -> `api_server.py` / `litserve_worker.py` / `task_scheduler.py`。
- 变量依赖图: `API_PORT` 影响后端监听与前端 API 地址，`WORKER_PORT` 影响 worker 监听与 scheduler 调用地址。
- 数据流向: 浏览器 -> frontend axios/vite proxy -> backend API；backend scheduler -> worker `/predict`。

## Debug 历史
### [2026-03-05 21:35] 后端与中间层默认端口改为高位随机端口
- 问题描述: 用户要求将后端和中间层 API 端口改为更大的随机端口，规避本机 8000/8001 端口冲突。
- 根因定位: 默认值分散在后端启动脚本、worker、scheduler、前端环境变量与代理配置，多处仍硬编码 8000/8001。
- 解决方案: 统一默认端口为 `API_PORT=18657`、`WORKER_PORT=28657`，并同步前端默认 API 地址与开发代理。
- 代码变更（文件/函数）:
  - `backend/start_all.py`（`TianshuLauncher.__init__`，CLI 参数默认值）
  - `backend/api_server.py`（`API_PORT` 默认值）
  - `backend/litserve_worker.py`（`--port` 默认值、`WORKER_PORT` 回退值）
  - `backend/task_scheduler.py`（`litserve_url` 默认值）
  - `backend/mcp_server.py`（`API_BASE_URL` 默认值）
  - `frontend/src/api/client.ts`（默认 API 端口/URL）
  - `frontend/vite.config.ts`（dev proxy 目标）
  - `frontend/src/views/ApiDocsScalar.vue`（后端直连地址展示）
  - `.env`（本地实际运行值）
  - `.env.example`、`frontend/.env.development`、`frontend/.env.example`（模板与开发默认值）
  - `docs/WINDOWS_DEPLOYMENT.md`（部署/验证端口说明）
- 验证结果:
  - `npm run build`（frontend）通过
  - `python -m py_compile api_server.py litserve_worker.py mcp_server.py start_all.py task_scheduler.py`（backend）通过
- 影响评估: 仅更改默认端口与文档；不改变业务逻辑。若外部脚本仍写死 8000/8001，需要同步更新。
- 文档更新: 已更新 `docs/WINDOWS_DEPLOYMENT.md` 端口说明与验证步骤。

## 待追踪问题
- 若用户使用 Docker Compose 开发/生产模式，仍可能看到容器内部文档示例使用 8000/8001，需要按实际部署策略继续统一。

## 技术债务记录
- 文档与部分 README 仍存在历史端口示例（8000/8001），尚未全仓库统一。
