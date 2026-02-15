# model-preload Debug 记录

## 元信息
- 模块名称: model-preload
- 创建时间: 2026-02-15
- 最后更新: 2026-02-15
- 相关文件: backend/api_server.py, backend/download_models.py, frontend/src/api/systemApi.ts, frontend/src/views/Dashboard.vue, frontend/src/locales/zh-CN.ts, frontend/src/locales/en-US.ts, docs/WINDOWS_DEPLOYMENT.md, README.md
- 依赖模块: auth, dashboard, systemApi
- 用户说明书路径（涉及前端功能时）: README.md
- 开发/部署文档路径（涉及后端或环境时）: docs/WINDOWS_DEPLOYMENT.md

## 运行上下文与测试规则
- 运行环境: 本机 Windows
- SSH 方式（若远程）: 不适用
- 远程项目路径（若远程）: 不适用
- 验证/Checkfix 执行方式: 本地 PowerShell 运行 Python 语法检查与前端构建

## 上下文关系网络
- 文件结构:
  - `backend/download_models.py`: 实际模型预下载脚本（位于 backend）
  - `backend/api_server.py`: 模型状态与预下载 API
  - `frontend/src/views/Dashboard.vue`: 模型提示和一键预下载入口
  - `frontend/src/api/systemApi.ts`: 模型相关接口封装
- 函数调用链:
  - Dashboard -> `startModelPreload` -> `/api/v1/models/preload/start`
  - Dashboard -> `getModelPreloadStatus` -> `/api/v1/models/preload/status`
  - Dashboard -> `getModelsStatus` -> `/api/v1/models/status`
- 变量依赖图:
  - `preloadStatus.running` -> 按钮禁用态与轮询行为
  - `modelsStatus.catalog` -> 前端模型清单显示
- 数据流向:
  - 前端点击预下载 -> 后端后台线程执行 `download_models.py` -> 前端轮询状态并刷新模型就绪状态

## Debug 历史
### [2026-02-15 02:xx] 模型预下载命令修正与前端一键预下载
- 问题描述:
  - 前端提示写“python download_models.py ...”导致用户在根目录执行报错
  - 用户希望明确模型清单，并希望前端能一键做完整预下载
- 根因定位:
  - `download_models.py` 位于 `backend/`，提示文案未标注目录上下文
  - 前端仅展示模型状态，没有触发预下载的 API/按钮
- 解决方案:
  - 修正 `/api/v1/models/status` 的 `first_use_tip`，同时给出两种正确命令（根目录/backend目录）
  - 在后端新增：
    - `POST /api/v1/models/preload/start`（后台启动预下载，需 `queue:manage` 权限）
    - `GET /api/v1/models/preload/status`（查询运行状态与日志）
    - `catalog` 字段（返回模型清单）
  - 在前端 Dashboard 增加“预下载模型”按钮（manager/admin 可见），并轮询状态显示运行/完成/失败
  - 同步更新 `docs/WINDOWS_DEPLOYMENT.md` 与 `README.md`
- 代码变更（文件/函数）:
  - `backend/api_server.py`: `get_models_status` + preload start/status endpoints + 后台执行线程
  - `frontend/src/api/systemApi.ts`: 新增 preload start/status API
  - `frontend/src/views/Dashboard.vue`: 预下载按钮、状态展示、轮询
  - `frontend/src/locales/zh-CN.ts`, `frontend/src/locales/en-US.ts`: 新增文案键
  - `docs/WINDOWS_DEPLOYMENT.md`, `README.md`: 命令与功能说明更新
- 验证结果:
  - `python -m py_compile backend/api_server.py start_dev.py` 通过
  - `npm run build` 通过（在受限沙箱内首次 `spawn EPERM`，提权复跑成功）
- 影响评估:
  - 消除根目录执行脚本的误导
  - 增加后端长任务下载能力和前端可视化触发入口
- 文档更新（新增/修改的 docs 文件与更新点）:
  - `docs/WINDOWS_DEPLOYMENT.md`: 补充根目录与 backend 两种等价命令
  - `README.md`: 补充模型管理能力说明

## 待追踪问题
- 模型预下载是长任务，前端目前仅展示简要状态；若需要可进一步加实时日志面板

## 技术债务记录
- 后台预下载状态目前使用进程内内存维护，服务重启会丢失任务状态
