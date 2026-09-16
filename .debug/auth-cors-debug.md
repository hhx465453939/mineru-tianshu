# Auth/CORS Debug 记录

## 元信息
- 模块名称: 前端登录与后端认证 API 连通性（CORS）
- 创建时间: 2026-02-18
- 最后更新: 2026-02-18
- 相关文件: `frontend/src/api/client.ts`, `frontend/.env.development`, `backend/api_server.py`, `start_dev.py`, `backend/start_all.py`
- 依赖模块: 认证路由 `backend/auth/routes.py`，前端认证状态 `frontend/src/stores/authStore.ts`
- 用户说明书路径（涉及前端功能时）: `docs/WINDOWS_DEPLOYMENT.md`
- 开发/部署文档路径（涉及后端或环境时）: `README.md`, `frontend/README.md`

## 运行上下文与测试规则
- 运行环境: 本机 Windows
- SSH 方式（若远程）: N/A
- 远程项目路径（若远程）: N/A
- 验证/Checkfix 执行方式: 本地 PowerShell

## 上下文关系网络
- 文件结构:
  - 前端 API 基址来自 `frontend/.env.development` 的 `VITE_API_BASE_URL`
  - 前端请求经 `frontend/src/api/client.ts` 发往 `http://127.0.0.1:8000`
  - 目标后端理论应为 `backend/api_server.py`（含 CORSMiddleware）
- 函数调用链:
  - `Login.vue` -> `authStore.login()` -> `authApi.login()` -> `apiClient.post('/api/v1/auth/login')`
  - `authStore.initialize()` -> `authApi.getCurrentUser()` -> `apiClient.get('/api/v1/auth/me')`
- 变量依赖图:
  - `VITE_API_BASE_URL` -> `API_BASE_URL` -> axios `baseURL`
- 数据流向:
  - 浏览器 `http://localhost:3000` -> `http://127.0.0.1:8000/api/v1/auth/*`

## Debug 历史
### [2026-02-18] 登录报“无法连接服务器”与 CORS 报错
- 问题描述:
  - 浏览器报 CORS preflight 失败（无 `Access-Control-Allow-Origin`）
  - 登录提示“无法连接到服务器，请检查网络连接”
- 根因定位:
  - 通过请求 `http://127.0.0.1:8000/openapi.json`，返回的 `info.title` 为 `Family Health Backend`，不是本项目 `MinerU Tianshu API`
  - 说明 8000 端口被其他项目占用，前端请求打错服务，导致 CORS 不匹配
  - 对 `OPTIONS /api/v1/auth/me` 实测返回 404 且无 CORS 头，进一步印证非本项目后端在响应
- 解决方案:
  - 停止占用 8000 的其他服务，或将本项目后端改到新端口并同步 `VITE_API_BASE_URL`
  - 以 `/openapi.json` 的标题校验目标服务是否正确
- 代码变更（文件/函数）:
  - 无代码变更（本次为环境与端口冲突定位）
- 验证结果:
  - `OPTIONS http://127.0.0.1:8000/api/v1/auth/me` 返回 404（无 CORS 头）
  - `GET http://127.0.0.1:8000/openapi.json` 返回 `Family Health Backend`
- 影响评估:
  - 仅影响本地开发联调，生产逻辑未变
- 文档更新（新增/修改的 docs 文件与更新点）:
  - 新增调试记录 `.debug/auth-cors-debug.md`

## 待追踪问题
- 若用户选择改端口运行，需要补充统一启动脚本端口透传能力（可选增强项）

## 技术债务记录
- 前端错误提示把跨域/端口冲突统一显示为“网络错误”，可考虑增强可观测性（例如输出响应 host 与 openapi 标识）

