# task-list-batch-download Debug 记录

## 元信息
- 模块名称: task-list-batch-download
- 创建时间: 2026-02-14
- 最后更新: 2026-02-14
- 相关文件: frontend/src/views/TaskList.vue, frontend/src/locales/zh-CN.ts, frontend/src/locales/en-US.ts, start_dev.py
- 依赖模块: frontend taskStore/taskApi, backend start_all.py
- 用户说明书路径（涉及前端功能时）: README.md
- 开发/部署文档路径（涉及后端或环境时）: docs/WINDOWS_DEPLOYMENT.md, README.md

## 运行上下文与测试规则
- 运行环境: 本机 Windows
- SSH 方式（若远程）: 不适用
- 远程项目路径（若远程）: 不适用
- 验证/Checkfix 执行方式: 在本地 PowerShell 中执行前端构建与 Python 语法检查

## 上下文关系网络
- 文件结构:
  - `frontend/src/views/TaskList.vue`: 历史任务列表 UI、筛选、分页、勾选、批量操作
  - `frontend/src/api/taskApi.ts`: `getTaskStatus` 返回任务结果内容
  - `backend/start_all.py`: 后端统一启动入口
  - `start_dev.py`: 根目录一键同时启动前后端脚本
- 函数调用链:
  - `TaskList.vue -> taskStore.fetchTasks -> taskApi.listTasks`
  - `TaskList.vue -> taskApi.getTaskStatus -> /api/v1/tasks/{task_id}`
  - `start_dev.py -> backend/start_all.py + frontend npm run dev`
- 变量依赖图:
  - `selectedTasks` -> `selectedCompletedTasks` -> 批量下载按钮可见性与执行列表
  - `paginatedTasks` -> `selectableTaskIdsOnPage` -> 全选逻辑
- 数据流向:
  - 前端先拉取任务列表，再针对勾选的 completed 任务逐个拉取详情并本地生成下载文件

## Debug 历史
### [2026-02-14 01:xx] 历史任务成功项批量勾选与下载 + 一键启动脚本
- 问题描述:
  - 需要在历史任务列表中支持“成功任务批量勾选与下载”
  - 需要新增一个 Python 一键脚本同时启动前后端
- 根因定位:
  - 任务列表虽有勾选框，但未限定成功任务，也没有批量下载逻辑
  - 根目录缺少统一的一键启动 Python 脚本
- 解决方案:
  - 前端将勾选限制为 `completed`，新增“批量下载成功任务”按钮
  - 批量下载时逐个调用 `taskApi.getTaskStatus(task_id, false, 'both')`，下载 Markdown，若有 JSON 一并下载
  - 新增根目录 `start_dev.py`，并发启动 `backend/start_all.py` 与 `frontend npm run dev`，支持 Ctrl+C 联动停止
  - 同步更新 `README.md` 与 `docs/WINDOWS_DEPLOYMENT.md` 一键启动说明
- 代码变更（文件/函数）:
  - `frontend/src/views/TaskList.vue`
  - `frontend/src/locales/zh-CN.ts`
  - `frontend/src/locales/en-US.ts`
  - `start_dev.py`
  - `README.md`
  - `docs/WINDOWS_DEPLOYMENT.md`
- 验证结果:
  - `python -m py_compile start_dev.py` 通过
  - `npm run build` 在受限沙箱下初次因 `spawn EPERM` 失败；提权后重跑通过（仅有既有 chunk size 警告）
- 影响评估:
  - 批量操作行为从“批量取消”切换为“成功任务批量下载”
  - 保留单任务取消按钮，不影响 pending 任务的取消入口
- 文档更新（新增/修改的 docs 文件与更新点）:
  - `README.md`: 本地开发部署的一键启动命令改为 `python start_dev.py`
  - `docs/WINDOWS_DEPLOYMENT.md`: 方式三一键启动与输出目录说明改为 `start_dev.py`

## 待追踪问题
- 浏览器可能限制一次用户点击触发的多文件下载数量（取决于浏览器策略）

## 技术债务记录
- 当前批量下载采用“逐任务多文件下载”策略；若后续需要更好的体验，可增加后端打包 ZIP 接口

## 架构决策记录（可选）
- 为最小改动，优先复用已有 `/api/v1/tasks/{task_id}` 接口，不新增后端批量下载 API
