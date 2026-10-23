# 前端 pdfjs 报错 / Hybrid 引擎失败 / 批量删除无响应 —— 系统核查方案

> 记录时间：2026-10-23
> 触发场景：上传图片后任务跑不起来，页面弹出 Vite import-analysis 覆盖层；同一文件选「自动模式」可跑，「Hybrid High-Prec (Local)」失败；任务列表勾选失败任务后点「批量删除」无任何反应。
> 环境快照：node v24.22.1 / npm 11.18.0；前端 Vite dev :3000 → proxy → API :18657；api_server PID 53204；litserve worker :28657；mineru 2.6.2；Docker daemon **未运行**。

---

## 0. 结论速览（先看这个）

| # | 现象 | 层级 | 根因 | 严重度 |
|---|------|------|------|--------|
| 1 | `Failed to resolve import "pdfjs-dist" from VirtualPdfViewer.vue` | 前端依赖层 | `package.json` 已声明 `pdfjs-dist@3.11.174`，但 `frontend/node_modules/` 下**没有安装**该包（node_modules 与 lock 脱节） | P0（阻断任务详情页） |
| 2 | 选 `hybrid-auto-engine` 任务必失败：`ValueError: Unsupported backend: hybrid-auto-engine` | 后端引擎契约层 | 运行时 **mineru 2.6.2 不支持 hybrid / vlm-auto-engine 这两个名字**；`mineru_vl_utils` 只认 `transformers / http-client / vllm-engine / vllm-async-engine / lmdeploy-engine`。项目把 MinerU 3.x 的后端名直接透传给 2.6.2 | P0（功能不可用 + 报错不友好） |
| 3 | 勾选任务点「批量删除」完全没动静 | 前端状态层 | `TaskList.vue` 用**组件本地** `selectedTasks`，而 `taskStore.storeBatchDeleteTasks()` 读的是**store 内** `selectedTaskIds`（从未同步 → 恒为空）→ 函数首行 `if (ids.length === 0) return` **静默返回**。批量重启同病 | P0（功能完全失效） |
| 4 | 批量删除失败时也无提示 | 前端反馈层 | `TaskList.vue` 全文件零 toast；axios 拦截器 403 只 `console.error`；store 的 `error` 没人渲染 | P1（故障不可见） |
| 5 | —— | 前端模板层 | `TaskList.vue` 第 370-375 行残留一个 `ConfirmDialog`，引用了**根本不存在的** `showBatchDialog` / `batchDialogMessage` / `confirmBatchAction`（死代码 + Vue 未定义属性警告） | P1（噪声/隐患） |

---

## 1. 复现与证据链

### 1.1 现象 1：pdfjs-dist

```bash
$ ls -d frontend/node_modules/pdfjs-dist
ls: cannot access 'node_modules/pdfjs-dist': No such file or directory

$ grep -n '"pdfjs-dist"' frontend/package.json frontend/package-lock.json
frontend/package.json:20:        "pdfjs-dist": "3.11.174",
frontend/package-lock.json:20:        "pdfjs-dist": "3.11.174",
frontend/package-lock.json:6005:    "node_modules/pdfjs-dist": { ... }

$ git log --oneline -3 -- frontend/package.json
c6cb2cf feat: 跨平台模型预下载命令提示 + 前端依赖修复与验证脚本
```

→ 声明与 lock 一致，唯独物理安装缺失。属于「改完 package.json 没重装」或「上次 install 被镜像/网络中断」。

### 1.2 现象 2：Hybrid 引擎

数据库实证（`data/db/mineru_tianshu.db`）：

```
task_id 55b61a59  status=failed  backend=hybrid-auto-engine
  error_message = ValueError: Unsupported backend: hybrid-auto-engine
task_id 735a4e92  status=completed  backend=auto   ← 同文件，自动模式成功
```

调用链：

```
POST /api/v1/tasks/submit (backend=hybrid-auto-engine)
  → task_db 入队
  → litserve worker: _process_task
      elif "pipeline" in backend or "vlm-" in backend or "hybrid-" in backend:
          options["parse_mode"] = "hybrid-auto-engine"
          _process_with_mineru(...)
  → MinerUPipelineEngine.parse
      user_backend = "hybrid-auto-engine"
      # 只有 self.vlm_api_base 非空才会换成 hybrid-http-client
      # 实测启动参数没传 --mineru-vllm-api-list → vlm_api_base=None → 原样透传
      do_parse(backend="hybrid-auto-engine")
  → mineru 2.6.2 / cli/common.py
      if backend == "pipeline": ...
      else:
          if backend.startswith("vlm-"): backend = backend[4:]
          _process_vlm(..., backend="hybrid-auto-engine" ...)
  → mineru_vl_utils/vlm_client/base_client.py:276
      raise ValueError(f"Unsupported backend: {backend}")
```

**版本能力实测**：

```bash
$ cat backend/.venv/Lib/site-packages/mineru/version.py
__version__ = "2.6.2"

$ grep -n "click.Choice" backend/.venv/Lib/site-packages/mineru/cli/client.py
53:    type=click.Choice(['pipeline', 'vlm-transformers', 'vlm-vllm-engine', 'vlm-http-client']),

$ grep -rn "hybrid" backend/.venv/Lib/site-packages/mineru/ --include=*.py
（无匹配 —— 2.6.2 根本没有 hybrid 实现）
```

后端 `/api/v1/engines` 却**谎报**三件套全部可用（`pipeline` / `vlm-auto-engine` / `hybrid-auto-engine`），前端下拉因此全量展示。

同时注意：即便将来本地 vLLM 起来了，`hybrid-auto-engine → hybrid-http-client` 在 2.6.2 上依然走不通（不以 `vlm-` 开头 → 原样透传）。**唯一可用形态是 `vlm-http-client`（会 strip 成 `http-client`）**。

### 1.3 现象 3：批量删除无响应

```ts
// frontend/src/views/TaskList.vue（本地选择态）
const selectedTasks = ref<string[]>([])          // 第 424 行
checkbox v-model="selectedTasks" :value="task.task_id"

// 第 675 行
await taskStore.storeBatchDeleteTasks()          // ← 没有传参
```

```ts
// frontend/src/stores/taskStore.ts
const selectedTaskIds = ref<string[]>([])        // 第 221 行，TaskList 从未写入
async function storeBatchDeleteTasks() {
  const ids = [...selectedTaskIds.value]
  if (ids.length === 0) return                   // 第 253-254 行：静默 return，无日志无异常
  ...
}
```

`grep -n "taskStore.\(selected\|setSelected\|toggleSelect\)" TaskList.vue` → **零命中**，确认两套选择态从未打通。

后果链：确认框正常弹出 → `pendingAction` 执行 → store 提前 return → `selectedTasks=[]` + `refreshTasks(true)` → 列表无变化 → 用户感知「点了没用」。

`storeBatchRestartTasks()`（第 696 行调用）同病。

### 1.4 现象 4/5：失败不可见 + 死代码

```bash
$ grep -n "showBatchDialog\|confirmBatchAction\|batchDialogMessage" frontend/src/views/TaskList.vue
371:      v-model="showBatchDialog"
373:      :message="batchDialogMessage"
374:      @confirm="confirmBatchAction"
# 仅模板引用，<script setup> 内无任何定义
```

```bash
$ grep -n "toast" frontend/src/views/TaskList.vue
# 零命中
```

`frontend/src/api/client.ts` 对 403 只 `console.error`，401 才跳登录；其余错误交给调用方，调用方又吞掉。

---

## 2. 分层核查矩阵（可复用 checklist）

| 层 | 核查项 | 命令 / 位置 | 本次结果 |
|----|--------|-------------|----------|
| L0 运行时 | 哪些进程、什么解释器、什么端口 | `powershell Get-CimInstance Win32_Process -Filter "Name='python.exe'" \| Select ProcessId,CommandLine \| ConvertTo-Json` | api_server:18657 / litserve:28657 / scheduler 均在；解释器为 uv python + `.venv` 混合 |
| L0 运行时 | Docker 依赖是否就绪 | `docker ps` | **daemon 未运行**（vLLM/paddle 容器化路径全部不可用） |
| L1 依赖 | package.json ↔ node_modules ↔ lock 三方一致 | `npm ls --depth=0` / 逐包 `ls -d node_modules/<pkg>` | pdfjs-dist 缺失 |
| L1 依赖 | Python 侧引擎版本 | `python -c "import mineru; print(mineru.__version__)"`（必须在 **运行态解释器**） | 2.6.2 |
| L2 契约 | 前端可提交的 backend 枚举 | `frontend/src/views/TaskSubmit.vue` optgroup | 11 个值 |
| L2 契约 | 后端实际可路由的 backend | `backend/litserve_worker.py::_process_task` | 分支存在，但下游 mineru 不认 |
| L2 契约 | 引擎能力声明是否真实 | `curl /api/v1/engines` vs `mineru.cli.client:53` | **谎报**（hybrid 标为可用） |
| L3 数据 | 失败任务真实错误 | `sqlite3 data/db/mineru_tianshu.db "select backend,error_message from tasks"` | `Unsupported backend` |
| L4 状态 | 组件选择态 ↔ store 选择态 | `grep selectedTaskIds` 两侧 | 未打通 |
| L4 反馈 | 失败是否有 UI 反馈 | `grep toast` | 无 |
| L5 模板 | 模板引用变量是否都已定义 | `grep` 逐个回查 `<script setup>` | 3 个未定义 |

---

## 3. 修复方案（按层，禁止跨层打补丁）

### Fix-1 前端依赖（L1）
```bash
cd frontend && npm install
# 验证：node -e "console.log(require.resolve('pdfjs-dist/package.json'))"
```
`package.json` / lock 无需改动，仅补装物理包。装完重启 Vite（依赖预构建缓存需失效：`rm -rf node_modules/.vite`）。

### Fix-2 引擎能力契约（L2，后端为契约源头）
1. **`backend/mineru_pipeline/engine.py`**：新增 `_resolve_backend()` —— 用 `importlib.metadata.version("mineru")` 探测真实能力，把前端传来的 backend 映射为**当前环境可执行**的 backend，并产出 `notice`：
   - `hybrid-auto-engine` → 有 `vlm_api_base` 则 `vlm-http-client`，否则 `pipeline`（降级）
   - `vlm-auto-engine` → 有 `vlm_api_base` 则 `vlm-http-client`，否则 `pipeline`（降级）
   - `hybrid-http-client`（mineru<3.0）→ 降级 `vlm-http-client` 或 `pipeline`
   - 结果经 `parse()` 返回值向上带出 `effective_backend` / `backend_notice`
2. **`backend/litserve_worker.py`**：把 `effective_backend` / `backend_notice` 落库到 `data` JSON，供详情页展示。
3. **`backend/api_server.py::list_engines`**：为每个 document 引擎补 `available` / `unavailable_reason` / `effective_backend`，不再谎报。
4. **`frontend/src/views/TaskSubmit.vue`**：消费 `/api/v1/engines`，对不可用引擎追加「（当前环境不可用，将自动降级）」并禁用选择。

> 取舍说明：直接 422 拒绝会让用户「还是跑不起来」；静默降级会让用户误解精度。因此采用「**自动降级 + 显式告知（响应 notice + 详情页 badge）**」。

### Fix-3 批量操作状态打通（L4）
1. `taskStore.storeBatchDeleteTasks(ids?: string[])` / `storeBatchRestartTasks(ids?: string[])`：接受显式 ids（默认回落到 store 选择态，保持向后兼容）。
2. `TaskList.vue` 调用处传 `selectedTasks.value`。
3. 删除 TaskList 中残留的第二个 `ConfirmDialog`（引用未定义符号）。
4. `executeConfirmedAction` / 批量删除 / 批量重启：成功与失败均 `toast`，部分失败时列出 `failed[]` 的 `reason`。

### Fix-4 反馈兜底（L4/L5）
`frontend/src/api/client.ts`：对 403 补一条 `toast.error(detail)`（当前仅 console），避免再出现「静默 403」。

---

## 4. 验证清单（改完必须逐条跑）

```bash
# A. 前端依赖与构建
cd frontend
node -e "console.log(require.resolve('pdfjs-dist/package.json'))"
npx tsc --noEmit
npm run build            # 预期 0 error，VirtualPdfViewer 正常打进 chunk

# B. 引擎契约
curl -s localhost:18657/api/v1/engines | python -m json.tool | grep -A4 hybrid
#   预期：hybrid-auto-engine.available=false, effective_backend="pipeline"
# 提交 hybrid 任务 → 预期 completed，data.backend_notice 含降级说明
python -c "import sqlite3;c=sqlite3.connect('data/db/mineru_tianshu.db');print(c.execute('select backend,status,error_message from tasks order by created_at desc limit 5').fetchall())"

# C. 批量删除
# 前端勾选 1 个失败任务 → 批量删除 → 确认
#   预期：toast「已删除 1 个任务」；列表立即消失；刷新后仍不存在
# 直接验证接口（需 admin token）：
curl -X POST localhost:18657/api/v1/tasks/batch/delete \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"task_ids":["<task_id>"]}'
#   预期：{"success":true,"deleted":["..."],"failed":[]}

# D. 回归
# - auto / pipeline / vlm-http-client 三条路径仍可提交
# - 批量取消、批量重启、导出归档不受影响
# - 详情页 PDF 预览可加载（pdfjs worker 正常）
```

---

## 5. 风险与遗留

- 降级到 `pipeline` 后精度低于用户对「Hybrid」的预期 → 已通过 notice + 详情页提示显式告知，避免静默。
- 升级 mineru ≥ 3.0 时 `hybrid-*` 才真正可用；`_resolve_backend()` 已按版本分支，升级后自动恢复，无需再改代码。
- Docker 未运行：`paddleocr-vl-vllm` / 本地 vLLM 路径仍不可用，属环境问题非代码问题，已在 `/api/v1/engines` 的 `available` 中体现。
- `frontend/src/locales/en-US.ts` 大量词条仍是中文文案（i18n 未翻译），不影响功能，单独记 TODO。

---

## 6. 修复与验证结果（实测）

### 6.1 改动清单

| 文件 | 改动 |
|------|------|
| `backend/mineru_pipeline/engine.py` | 新增 `_mineru_version()` / `_resolve_backend()`，按 mineru 真实版本探测能力并安全降级；`parse()` 返回值新增 `requested_backend` / `effective_backend` / `backend_notice` |
| `backend/litserve_worker.py` | `_process_with_mineru()` 透传引擎信息；任务 `data` JSON 落库三者 |
| `backend/api_server.py` | `list_engines` 为 document 引擎补 `available` / `effective_backend` / `unavailable_reason`，不再谎报能力 |
| `frontend/src/views/TaskSubmit.vue` | 拉取 `/api/v1/engines`，不可用引擎下拉项追加「将降级」后缀、hint 展示原因、提交时 toast 告知 |
| `frontend/src/views/TaskDetail.vue` | 展示「引擎降级」提示条 |
| `frontend/src/stores/taskStore.ts` | `storeBatchDeleteTasks(ids?)` / `storeBatchRestartTasks(ids?)` 支持显式传入 ID |
| `frontend/src/views/TaskList.vue` | 批量删除/重启显式传 `selectedTasks`；删除未定义变量的死代码 `ConfirmDialog`；成功/部分失败全部 toast |
| `frontend/src/api/client.ts` | 403 权限不足补 toast 提示 |
| `frontend/src/api/types.ts` | `EngineItem` / `Task.data` 补能力与降级字段 |
| `frontend/src/locales/{zh-CN,en-US}.ts` | 批量操作与降级提示文案 |
| `frontend/src/utils/toast.ts` | 便捷方法支持自定义 duration |
| `frontend/node_modules/pdfjs-dist` | `npm install` 补装 3.11.174 |

### 6.2 实测记录

**A. 前端依赖 / 编译**
```
node -e require.resolve('pdfjs-dist/package.json')
→ E:\Development\mineru-tianshu\frontend\node_modules\pdfjs-dist\package.json

npx tsc --noEmit                      → 0 error
npx vite build                        → ✓ built，TaskDetail chunk 1.66 MB（pdfjs 已打入）
GET http://localhost:3000/src/components/VirtualPdfViewer.vue
→ http=200, 53543 bytes，import 正常解析为 /node_modules/.vite/deps/pdfjs-dist.js
```

**B. 引擎能力契约**
```
GET /api/v1/engines
→ pipeline            available=True   effective=pipeline
→ vlm-auto-engine     available=False  effective=pipeline
→ hybrid-auto-engine  available=False  effective=pipeline
   reason: Hybrid 模式需要 MinerU 3.x，当前为 2.6.2，提交后会自动降级为 Pipeline
```

**C. end-to-end 提交 hybrid 任务**
```
POST /api/v1/tasks/submit  backend=hybrid-auto-engine
→ task_id=138fa0be-..., status=pending
[60s] status=completed

DB data:
  requested_backend : hybrid-auto-engine
  effective_backend : pipeline
  backend_notice    : MinerU 2.6.2 不支持 hybrid-auto-engine 且未配置 VLM 服务，已自动降级为 Pipeline（可正常出结果，精度低于 Hybrid）
  markdown_len      : 731

worker log:
  WARNING | mineru_pipeline.engine:parse - ⚠️ Backend fallback: hybrid-auto-engine -> pipeline (...)
```

**D. 批量删除接口**
```
POST /api/v1/tasks/batch/delete {"task_ids":["55b61a59-..."]}
→ {"success":true,"deleted":["55b61a59-..."],"failed":[]}
GET /api/v1/tasks/55b61a59-...  → http=404
DB: exists=0
```
→ 后端链路本身健康，原「无反应」纯粹是前端选择态未打通导致的静默 return。

**E. 服务状态**
```
api_server   :18657  LISTENING  (PID 43264)
litserve     :28657  LISTENING  (PID 38128)
vite dev     :3000   LISTENING  (PID 34056)
docker       : 未运行（不影响 pipeline 路径）
```

### 6.3 回归确认

- `auto` / `pipeline` 路径未改变默认行为（`_resolve_backend` 对二者原样返回）。
- `vlm-http-client` 仍需 `server_url`，缺失时才降级（与原逻辑差异：原逻辑会直接抛 Unsupported backend）。
- 批量取消（TaskList 自行循环 `cancelTask`）未改动。
- 导出归档调用本就显式传参，未受影响。
- 升级 mineru ≥ 3.0 后 `_resolve_backend` 自动走 3.x 分支，`hybrid-*` 恢复原生可用，无需改代码。

