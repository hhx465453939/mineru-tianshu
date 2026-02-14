# 部署（Windows 本地）Debug 记录

## 元信息
- 模块名称: deployment-windows
- 创建时间: 2025-02-14
- 最后更新: 2025-02-14
- 相关文件: docs/WINDOWS_DEPLOYMENT.md, backend/requirements.txt, backend/install.sh, scripts/docker-setup.bat
- 依赖模块: backend, frontend, docker-compose
- 用户说明书路径: docs/WINDOWS_DEPLOYMENT.md
- 开发/部署文档路径: docs/WINDOWS_DEPLOYMENT.md, README.md

## 运行上下文与测试规则
- 运行环境: 本机 Windows（用户需求：Windows 本地部署，显卡 RTX 3060）
- SSH 方式（若远程）: 不适用
- 远程项目路径（若远程）: 不适用
- 验证/Checkfix 执行方式: 在本地 Windows 终端（PowerShell/CMD）或 WSL2 内执行

## 上下文关系网络
- 项目特点：Python 3.12、MinerU、PaddleOCR-VL、PyTorch、PaddlePaddle GPU、FunASR、LitServe
- 后端安装：backend/install.sh 面向 Linux/WSL；requirements.txt 注明 PyTorch/PaddlePaddle 分步安装、CUDA 12.6
- PaddleOCR-VL：README 明确「Windows 用户请使用 WSL 或 Docker」
- Windows 部署可行路径：① Docker（推荐）② WSL2 按 Linux 流程 ③ **Windows 源码部署（uv + venv 后端，npm 前端）**，见 docs/WINDOWS_DEPLOYMENT.md 方式三

## Debug 历史
### 2025-02-14 Windows 本地部署文档
- 问题描述: 用户需要确认本机 Windows + RTX 3060 部署可行性，并得到一行一行写清的中文部署指导
- 根因定位: 项目主要面向 Linux/Docker，无独立 Windows 部署文档；PaddleOCR-VL 官方建议 Windows 用 WSL/Docker
- 解决方案: 新增 docs/WINDOWS_DEPLOYMENT.md，包含：环境要求、Docker 逐步部署、WSL2 逐步部署、验证与故障排查
- 代码变更: 新增 .debug/deployment-windows-debug.md、docs/WINDOWS_DEPLOYMENT.md
- 验证结果: 文档已编写，未在本机执行实际安装（由用户按文档执行）
- 影响评估: 仅新增文档，无代码变更
- 文档更新: 新增 docs/WINDOWS_DEPLOYMENT.md；README 中增加指向该文档的链接

### 2025-02-14 Windows 源码部署（非 WSL）— uv + venv + npm
- 问题描述: 用户希望有 Windows 非 WSL 的源码部署方案，后端用 uv 和 venv，前端用 npm
- 根因定位: 原文档仅有 Docker、WSL2 及简短「纯 Windows 尝试」；缺少完整的 uv/venv/npm 分步说明
- 解决方案: 在 docs/WINDOWS_DEPLOYMENT.md 中新增「方式三：Windows 源码部署（非 WSL）」：前置（Python 3.12、uv、Node、nvidia-smi）→ 环境与目录 → 后端 uv venv + 分步 pip（PyTorch cu126 → PaddlePaddle Windows cu121 → 关键依赖 → requirements.txt）→ 启动 start_all.py → 前端 npm install / npm run dev（端口 3000，代理 /api 到 8000）→ 验证与已知限制表
- 代码变更: 仅文档 — docs/WINDOWS_DEPLOYMENT.md 新增方式三、原「七、可选」改为「七、部署方式对照」、更新「一」中表格与文末版本说明；.debug 本段记录
- 验证结果: 未在本机执行；命令与路径与项目一致（backend/start_all.py、frontend vite port 3000、/api → 8000）
- 影响评估: 无代码改动，仅部署文档与 .debug 更新
- 文档更新: docs/WINDOWS_DEPLOYMENT.md 已更新；已检查与方式一、二、验证清单、常见问题无冲突

### 2025-02-14 飞桨 Windows 安装命令修正（方式三）
- 问题描述: 用户按方式三执行时，`uv pip install paddlepaddle-gpu` 报错：① uv 不支持 `--default-timeout`；② cu121 索引下找不到 paddlepaddle-gpu（no versions found）
- 根因: 飞桨官方 Windows 文档使用 **3.3.0** 和 **cu118/cu126/cu129** 索引（无 cu121）；且飞桨源可能与 uv 解析不兼容
- 解决方案: 更新 docs/WINDOWS_DEPLOYMENT.md 方式三第二步：改为官方版本 **3.3.0**、索引 **cu126**（RTX 3060），并改为 **python -m pip install** 安装 PaddlePaddle；补充 cu118/cu129 可选命令及官方文档链接
- 代码变更: 仅文档 — WINDOWS_DEPLOYMENT.md 第二步整段替换
- 验证结果: 未在本机执行；依据官方 Windows pip 安装页
- 文档更新: 已更新 WINDOWS_DEPLOYMENT.md

### 2025-02-14 uv venv 无 pip 导致 python -m pip 报错
- 问题描述: 用户执行 `python -m pip install paddlepaddle-gpu==3.3.0 ...` 报 “No module named pip”
- 根因: `uv venv` 创建的虚拟环境默认不包含 pip
- 解决方案: 在文档方式三第二步前增加「注意一」：先执行 `uv pip install pip`，再执行 `python -m pip install paddlepaddle-gpu==3.3.0 ...`
- 代码变更: docs/WINDOWS_DEPLOYMENT.md 第二步前增加注意一与命令
- 文档更新: 已更新 WINDOWS_DEPLOYMENT.md

### 2025-02-14 前端 build：CSS nesting 警告修复
- 问题描述: 用户执行 `npm run build` 时出现 “[postcss] Nested CSS was detected, but CSS nesting has not been configured correctly”，来自依赖（lucide-vue-next、@scalar/api-reference 等）中的嵌套 CSS（如 `& + .schema-properties`）
- 根因: PostCSS 中未在 Tailwind 之前启用 CSS nesting 插件，Tailwind 官方推荐使用自带的 `tailwindcss/nesting`
- 解决方案: 在 frontend/postcss.config.cjs 的 plugins 中、在 `tailwindcss` 之前添加 `'tailwindcss/nesting': {}`（无需额外安装，随 tailwindcss 包提供）
- 代码变更: frontend/postcss.config.cjs
- 验证结果: `npm run build` 通过，Nested CSS 警告消失；仍剩 baseline-browser-mapping 提示与 chunk 体积提示（可选优化）
- 文档更新: 无（属构建配置，非用户操作步骤）

### 2025-02-14 方式三第四步：uv 不支持 --use-deprecated=legacy-resolver
- 问题描述: 用户执行 `uv pip install -r requirements.txt ... --use-deprecated=legacy-resolver` 报 “unexpected argument '--use-deprecated' found”
- 根因: `--use-deprecated=legacy-resolver` 为 pip 专有选项，uv 不支持
- 解决方案: 文档方式三第四步改为仅用 `uv pip install -r requirements.txt -i ...`，去掉该参数；并说明若遇依赖冲突可改用 pip 执行此步
- 代码变更: docs/WINDOWS_DEPLOYMENT.md 第四步命令与说明
- 文档更新: 已更新 WINDOWS_DEPLOYMENT.md

### 2025-02-14 albumentations 与 doclayout-yolo 依赖冲突
- 问题描述: `uv pip install -r requirements.txt` 报 “mineru depends on albumentations>=1.4.11 (via doclayout-yolo==0.0.4), but you require albumentations>=1.3.1,<1.4.0” — 不可满足
- 根因: requirements.txt 中 albumentations 被固定为 <1.4.0（旧注释称 MinerU 2.6.2 需 1.3.x），而 mineru[core]==2.6.2 的依赖 doclayout-yolo==0.0.4 要求 albumentations>=1.4.11
- 解决方案: 将 albumentations 放宽为 >=1.4.11、albucore 放宽为 >=0.0.13（去掉 <1.4.0 与 <0.0.17 上限）；同步修改 backend/install.sh 与三个 Dockerfile 中的对应安装步骤
- 代码变更: backend/requirements.txt, backend/install.sh, backend/Dockerfile, backend/Dockerfile.offline, backend/Dockerfile.cpu
- 验证结果: 未在本机执行；依赖关系与 PyPI 一致
- 文档更新: 无（部署文档未写死 albumentations 版本）

### 2025-02-15 模型下载说明（方式三）
- 问题描述: 用户问安装命令是否已包含模型、模型下载到哪里
- 结论: 安装命令不包含模型；各引擎在**首次使用**时自动下载，缓存位置各异（MinerU: ~/.cache/huggingface 或 modelscope；PaddleOCR: ~/.paddleocr/models；SenseVoice: 项目 models/sensevoice；水印: ~/.cache/watermark_models）。可选预下载脚本 backend/download_models.py
- 代码变更: 无
- 文档更新: docs/WINDOWS_DEPLOYMENT.md 新增「8. 模型下载说明（方式三）」表格与可选预下载说明；原「8. 方式三的已知限制」改为「9.」

### 2025-02-15 .env 识别 + 前端模型检测与首次使用提示
- 问题描述: 用户要求 (1) 修复 .env 识别逻辑（支持根目录）；(2) 前端增加模型检测与下载说明，并在首次使用时提示模型下载
- 解决方案:
  - start_all.py：优先 backend/.env，不存在时使用 project_root/.env，错误信息改为「backend 或 project root」
  - 后端新增 GET /api/v1/models/status：检测 mineru/paddleocr/sensevoice 缓存目录是否就绪，返回 any_ready、any_missing、first_use_tip
  - 前端：systemApi 新增 getModelsStatus()；Dashboard 增加「模型状态」卡片（展示各模型 ready/message）、「首次使用提示」横幅（any_missing 时显示 first_use_tip，可关闭）；i18n 增加 dashboard.modelStatus、firstUseTip
- 代码变更: backend/start_all.py, backend/api_server.py, frontend/src/api/systemApi.ts, frontend/src/views/Dashboard.vue, frontend/src/locales/zh-CN.ts, frontend/src/locales/en-US.ts
- 文档更新: docs/WINDOWS_DEPLOYMENT.md 模型下载说明中补充「前端展示」一条

### 2025-02-15 将 hf_xet 加入 requirements
- 问题描述: 日志提示 "Xet Storage is enabled for this repo, but the 'hf_xet' package is not installed. Falling back to regular HTTP download"
- 解决方案: backend/requirements.txt 中将 huggingface-hub>=0.20.0 改为 huggingface-hub[hf_xet]>=0.20.0
- 代码变更: backend/requirements.txt

### 2025-02-15 根目录一键启动脚本
- 问题描述: 用户要求在根目录写一键启动脚本，同时启动前后端
- 解决方案: 新增 start.bat（Windows）、start.sh（Linux/Mac）。start.bat 用 start cmd /k 打开两个窗口分别运行 backend（激活 .venv 后 python start_all.py）与 frontend（npm run dev）；start.sh 后端后台、前端前台，Ctrl+C 时 trap 结束后端
- 代码变更: 新增 start.bat、start.sh
- 文档更新: docs/WINDOWS_DEPLOYMENT.md 方式三「访问与验证」下补充一键启动说明

## 待追踪问题
- 无

## 技术债务记录
- 无
