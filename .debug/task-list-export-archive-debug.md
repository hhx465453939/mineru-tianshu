# task-list-export-archive Debug 记录

## 元信息
- 模块名称: task-list-export-archive
- 创建时间: 2026-03-05 22:10
- 最后更新: 2026-03-05 22:10
- 相关文件: backend/api_server.py, frontend/src/api/taskApi.ts, frontend/src/views/TaskList.vue, frontend/src/locales/zh-CN.ts, frontend/src/locales/en-US.ts, docs/WINDOWS_DEPLOYMENT.md
- 依赖模块: task-db, task-api, task-list
- 用户说明书路径（涉及前端功能时）: docs/WINDOWS_DEPLOYMENT.md
- 开发/部署文档路径（涉及后端或环境时）: docs/WINDOWS_DEPLOYMENT.md

## 运行上下文与测试规则
- 运行环境: 本机 Windows
- SSH 方式（若远程）: 不适用
- 远程项目路径（若远程）: 不适用
- 验证/Checkfix 执行方式: 本地 PowerShell，前端构建 + 后端语法检查

## 上下文关系网络
- 文件结构:
  - `TaskList.vue` 负责批量勾选和下载触发
  - `taskApi.ts` 负责前端导出请求
  - `api_server.py` 负责读取任务结果目录并打包压缩
- 函数调用链:
  - `TaskList.batchDownloadResults -> taskApi.downloadTasksArchive -> POST /api/v1/tasks/export/archive`
- 变量依赖图:
  - `selectedTasks -> selectedCompletedTasks -> task_ids`
  - `task.result_path` 决定压缩包导出内容
- 数据流向:
  - 前端提交 task_ids -> 后端权限过滤 + 目录打包 -> 返回 zip blob 给浏览器下载

## Debug 历史
### [2026-03-05 22:10] 任务列表增加“完整结果压缩导出”能力
- 问题描述:
  - 用户需要在任务列表导出时增加勾选项，勾选后导出完整 MinerU 结果目录（含切分图片等全部文件）。
- 根因定位:
  - 现有批量下载仅导出 markdown/json 文本，不包含 `result_path` 目录中的所有资源文件。
- 解决方案:
  - 新增后端导出压缩接口 `POST /api/v1/tasks/export/archive`。
  - 前端任务列表增加勾选项，切换“文本批量下载”与“完整目录压缩下载”。
  - 压缩包内附带 `_export_report.json`，记录 included/skipped 任务。
- 代码变更（文件/函数）:
  - `backend/api_server.py`: `export_tasks_archive`, `sanitize_archive_name`
  - `frontend/src/api/taskApi.ts`: `downloadTasksArchive`
  - `frontend/src/views/TaskList.vue`: `downloadFullArchive`, `batchDownloadResults` 分支逻辑
  - `frontend/src/locales/zh-CN.ts`, `frontend/src/locales/en-US.ts`: 新增文案键
  - `docs/WINDOWS_DEPLOYMENT.md`: 增加用户操作说明
- 验证结果:
  - `python -m py_compile backend/api_server.py` 通过
  - `npm run build` 通过
- 影响评估:
  - 保留原有批量 md/json 下载；新功能通过勾选开关启用，兼容性风险低。
- 文档更新:
  - `docs/WINDOWS_DEPLOYMENT.md` 增加任务列表压缩导出说明

## 待追踪问题
- 超大任务集导出时 zip 生成耗时较长，可考虑后续改为异步任务导出。

## 技术债务记录
- 目前导出是即时打包，未做任务级缓存与重试机制。
