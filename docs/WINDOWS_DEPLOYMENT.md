# Windows 本地部署指南（天枢 MinerU Tianshu）

本文档面向**本机 Windows** 用户，在**一台装有 NVIDIA 显卡（如 RTX 3060）**的电脑上，从零开始一行一行完成天枢的本地部署。

---

## 一、部署可行性结论（RTX 3060）

| 项目 | 说明 |
|------|------|
| **是否可行** | 可行。推荐使用 **Docker** 或 **WSL2**，二者均可使用 RTX 3060 进行 GPU 加速。 |
| **显卡要求** | RTX 3060 算力 8.6，满足 PaddleOCR-VL 要求的 Compute Capability ≥ 8.5。 |
| **推荐方式** | 优先 **Docker 部署**；其次 **WSL2 部署**；**Windows 源码部署**（uv + venv + npm）见下方方式三。 |
| **Windows 源码（非 WSL）** | 可行。使用 **uv + venv** 配置后端、**npm** 配置前端即可；PaddleOCR-VL 在 Windows 上可能不可用，可仅用 MinerU pipeline 等引擎。 |

---

## 二、环境要求（部署前请逐项确认）

在开始前，请确认以下条件已满足：

1. **操作系统**：Windows 10 22H2 或更高 / Windows 11（64 位）。
2. **NVIDIA 显卡**：已安装显卡（如 RTX 3060）。
3. **NVIDIA 驱动**：已安装最新或较新的 Game Ready / Studio 驱动（建议 525+，使用 CUDA 12 时建议 550+）。  
   - 验证：打开 PowerShell 或 CMD，执行 `nvidia-smi`，能正常显示显卡信息即可。
4. **磁盘空间**：至少 30GB 可用（含镜像、模型、数据）。
5. **内存**：建议 16GB 及以上。

---

## 方式一：Docker 部署（推荐）

Docker 方式在 Windows 上通过 Docker Desktop（WSL2 后端）运行 Linux 容器，GPU 由 NVIDIA 驱动在 WSL2 下透传到容器内，无需在 Windows 上单独安装 Python/CUDA 等依赖。

### 1. 安装 Docker Desktop

1. 打开浏览器，访问：https://www.docker.com/products/docker-desktop  
2. 下载 **Docker Desktop for Windows** 并安装。  
3. 安装过程中若提示选择后端，请选择 **WSL 2**。  
4. 安装完成后重启电脑（若安装程序提示）。  
5. 启动 **Docker Desktop**，等待右下角图标显示 “Docker Desktop is running”。

### 2. 启用 WSL2 与 GPU 支持（若尚未启用）

1. 以**管理员身份**打开 PowerShell，执行：
   ```powershell
   wsl --install
   ```
   若已安装 WSL，可跳过；若提示需要更新 WSL，按提示执行 `wsl --update`。  
2. 在 Docker Desktop 中确认使用 WSL2：
   - 打开 Docker Desktop → **Settings** → **General**  
   - 勾选 **Use the WSL 2 based engine**  
   - 点击 **Apply & Restart**  
3. 本机已安装的 NVIDIA 驱动会自动在 WSL2 中生效，无需在 WSL 内再装驱动；容器内 GPU 由 Docker 通过 WSL2 透传。

### 3. 克隆或解压项目到本机

1. 打开 PowerShell 或 CMD。  
2. 进入你希望放置项目的目录，例如：
   ```powershell
   cd D:\development
   ```
3. 若使用 Git 克隆（已安装 Git 时）：
   ```powershell
   git clone https://github.com/magicyuan876/mineru-tianshu.git
   cd mineru-tianshu
   ```
   若为 ZIP 解压，则进入解压后的项目根目录，例如：
   ```powershell
   cd D:\development\mineru-tianshu
   ```

### 4. 准备环境变量文件

1. 在项目根目录下，复制示例配置为 `.env`：
   ```powershell
   copy .env.example .env
   ```
2. （可选）用记事本或 VS Code 打开 `.env`，按需修改：
   - `JWT_SECRET_KEY`：生产环境务必改为随机字符串（如用 `openssl rand -hex 32` 在 Git Bash 中生成）。  
   - `GPU_COUNT`、`CUDA_VISIBLE_DEVICES`：单卡 RTX 3060 可保持默认（GPU_COUNT=1，CUDA_VISIBLE_DEVICES=0）。  
3. 保存并关闭 `.env`。

### 5. 创建所需目录（若不存在）

在项目根目录下执行（PowerShell 中可逐行执行）：

```powershell
if (!(Test-Path models)) { New-Item -ItemType Directory -Path models }
if (!(Test-Path data\uploads)) { New-Item -ItemType Directory -Path data\uploads -Force }
if (!(Test-Path data\output)) { New-Item -ItemType Directory -Path data\output -Force }
if (!(Test-Path data\db)) { New-Item -ItemType Directory -Path data\db -Force }
if (!(Test-Path logs\backend)) { New-Item -ItemType Directory -Path logs\backend -Force }
if (!(Test-Path logs\worker)) { New-Item -ItemType Directory -Path logs\worker -Force }
if (!(Test-Path logs\mcp)) { New-Item -ItemType Directory -Path logs\mcp -Force }
```

若已存在，不会报错。

### 6. 构建并启动服务（一键脚本）

在项目根目录执行：

```powershell
scripts\docker-setup.bat
```

在菜单中选择 **1. Full Deployment (Setup + Build + Start)**，按回车。  
首次构建会下载镜像和依赖，可能需要 10～30 分钟，请耐心等待。构建完成后会自动启动服务。

**或** 不用脚本，在项目根目录手动执行：

```powershell
docker compose build --parallel
docker compose up -d
```

### 7. 等待服务就绪并验证

1. 等待约 10～30 秒（首次启动可能更久，需拉取镜像、下载模型等）。  
2. 在浏览器中访问：
   - 前端：http://localhost:80  
   - API 文档：http://localhost:8000/docs  
3. 若前端能打开、API 文档能打开，说明部署成功。  
4. （可选）在容器内检查 GPU 是否可见（PowerShell 中执行）：
   ```powershell
   docker compose exec worker nvidia-smi
   ```
   若能看到 RTX 3060 信息，说明 GPU 已透传。

### 8. 常用 Docker 命令（本机 Windows 上执行）

在项目根目录下：

- 查看服务状态：`docker compose ps`  
- 查看日志：`docker compose logs -f`  
- 停止服务：`docker compose down`  
- 再次启动：`docker compose up -d`  

---

## 方式二：WSL2 部署（与 Linux 流程一致）

若你希望不用 Docker，而在 WSL2 的 Linux 环境中直接安装 Python 依赖并运行，可按本方式操作。RTX 3060 在 WSL2 中可用（需 Windows 已装好 NVIDIA 驱动）。

### 1. 安装并进入 WSL2

1. 在 Windows 上以管理员身份打开 PowerShell，执行：
   ```powershell
   wsl --install
   ```
2. 重启后，打开 **Ubuntu**（或你选择的 WSL 发行版）。  
3. 首次会要求创建用户名和密码，按提示完成。  
4. 在 WSL 终端中确认 GPU 可见：
   ```bash
   nvidia-smi
   ```
   能看到显卡信息即可（驱动由 Windows 提供，无需在 WSL 内再装驱动）。

### 2. 在 WSL 中进入项目目录

若项目在 Windows 盘符下（例如 `D:\development\mineru-tianshu`），在 WSL 中一般对应：

```bash
cd /mnt/d/development/mineru-tianshu
```

若项目已在 WSL 家目录下，则按实际路径进入，例如：

```bash
cd ~/mineru-tianshu
```

### 3. 安装系统依赖（WSL 内为 Linux）

在 WSL 终端中执行：

```bash
sudo apt-get update
sudo apt-get install -y libgomp1 ffmpeg
```

### 4. 安装 Python 3.12 与 uv（推荐）或 pip

若使用 **uv**（推荐，与项目规范一致）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv python install 3.12
```

创建虚拟环境并进入项目后端目录（路径请按你实际项目位置修改）：

```bash
cd /mnt/d/development/mineru-tianshu
uv venv --python 3.12
source .venv/bin/activate
```

若使用系统 Python 与 pip，需确保为 3.12，并在 backend 目录下创建并激活虚拟环境：

```bash
python3 --version
cd /mnt/d/development/mineru-tianshu/backend
python3 -m venv .venv
source .venv/bin/activate
```

### 5. 安装后端依赖（分步安装，避免冲突）

以下在**已激活虚拟环境**的情况下执行。若你是用 uv 在项目根目录创建的 `.venv`，请先执行 `cd backend`（或 `cd /mnt/d/development/mineru-tianshu/backend`）再执行下列命令；若已在 backend 下创建并激活了 `.venv`，则直接执行即可。

**第一步：安装 PaddlePaddle GPU（CUDA 12.6）**

```bash
pip install paddlepaddle-gpu==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ --default-timeout=600 --retries 5
```

**第二步：安装 PyTorch（CUDA 12.6，含 torchaudio）**

```bash
pip install torch==2.6.0+cu126 torchvision==0.21.0+cu126 torchaudio==2.6.0+cu126 --index-url https://download.pytorch.org/whl/cu126 --default-timeout=600 --retries 5
```

**第三步：安装 Python 3.12 关键依赖**

```bash
pip install "kiwisolver>=1.4.5" "Pillow>=11.0.0" "numpy>=1.26.0,<2.0.0" "setuptools>=75.0.0" "lxml>=5.3.0" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**第四步：安装其余依赖（使用 legacy 解析器）**

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --use-deprecated=legacy-resolver --default-timeout=600 --retries 5
```

若项目提供一键脚本且你在 WSL 的 Linux 环境下，也可在 backend 目录执行：

```bash
bash install.sh
```

（仅限 WSL/Linux，不要在本机 Windows CMD 中执行 `install.sh`。）

### 6. 验证后端环境（WSL 内）

在 backend 目录下：

```bash
python -c "import paddle, torch; print('Paddle CUDA:', paddle.device.is_compiled_with_cuda()); print('PyTorch CUDA:', torch.cuda.is_available())"
```

若两行均为 True 或显示可用，说明 GPU 可用。再验证 PaddleOCR-VL（可选）：

```bash
python -c "from paddleocr import PaddleOCRVL; print('PaddleOCR-VL OK')"
```

### 7. 启动后端服务（WSL 内）

在项目根目录或 backend 目录下：

```bash
cd /mnt/d/development/mineru-tianshu/backend
python start_all.py
```

需要 MCP 时：

```bash
python start_all.py --enable-mcp
```

保持该终端不关闭。若需指定 GPU 或 worker 数，例如：

```bash
python start_all.py --workers-per-device 1 --devices 0
```

### 8. 启动前端（另开一个 WSL 或 Windows 终端）

在**项目根目录**下（若前端在 `frontend` 子目录）：

```bash
cd /mnt/d/development/mineru-tianshu/frontend
npm install
npm run dev
```

前端开发服务器通常会显示：`http://localhost:5173`。在 Windows 浏览器中访问该地址即可。

### 9. 访问与验证

- 前端：http://localhost:3000（开发模式，与 vite.config 一致）  
- API 文档：http://localhost:8000/docs  
- 健康检查：浏览器打开 http://localhost:8000/api/v1/health  

---

## 方式三：Windows 源码部署（非 WSL）— uv + venv 后端，npm 前端

本方式在**本机 Windows** 上直接使用源码运行：后端用 **uv** 管理虚拟环境（venv）和依赖，前端用 **npm** 安装与运行。不依赖 WSL 和 Docker。

**适用场景**：希望在本机 Windows 上开发或调试、能接受 PaddleOCR-VL 在 Windows 上可能不可用或需单独处理（见本节末尾「已知限制」）。

### 1. 安装前置软件（请按顺序执行）

**1.1 安装 Python 3.12**

1. 打开 https://www.python.org/downloads/ ，下载 **Python 3.12.x** Windows 安装包（64 位）。  
2. 运行安装程序，**勾选 “Add python.exe to PATH”**，然后安装。  
3. 打开**新的** PowerShell 窗口，验证：
   ```powershell
   python --version
   ```
   应显示 `Python 3.12.x`。

**1.2 安装 uv（推荐）**

在 PowerShell 中执行（若遇执行策略限制，先执行 `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`）：

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装完成后**关闭并重新打开 PowerShell**，验证：

```powershell
uv --version
```

**1.3 安装 Node.js 18+（前端用）**

1. 打开 https://nodejs.org/ ，下载并安装 **LTS 版本**（18 或 20）。  
2. 新开 PowerShell，验证：
   ```powershell
   node --version
   npm --version
   ```

**1.4 验证显卡驱动**

```powershell
nvidia-smi
```

能正常显示 RTX 3060 等信息即可。

### 2. 克隆或进入项目目录

在 PowerShell 中：

```powershell
cd D:\development
git clone https://github.com/magicyuan876/mineru-tianshu.git
cd mineru-tianshu
```

若项目已存在，直接 `cd` 到项目根目录即可。

### 3. 准备环境变量与目录

**3.1 复制环境变量文件**

```powershell
copy .env.example .env
```

（可选）用记事本或 VS Code 编辑 `.env`，修改 `JWT_SECRET_KEY` 等；单卡 3060 可保持默认 `GPU_COUNT=1`、`CUDA_VISIBLE_DEVICES=0`。

**3.2 创建所需目录**

```powershell
if (!(Test-Path models)) { New-Item -ItemType Directory -Path models }
if (!(Test-Path data\uploads)) { New-Item -ItemType Directory -Path data\uploads -Force }
if (!(Test-Path data\output)) { New-Item -ItemType Directory -Path data\output -Force }
if (!(Test-Path data\db)) { New-Item -ItemType Directory -Path data\db -Force }
if (!(Test-Path logs\backend)) { New-Item -ItemType Directory -Path logs\backend -Force }
if (!(Test-Path logs\worker)) { New-Item -ItemType Directory -Path logs\worker -Force }
if (!(Test-Path logs\mcp)) { New-Item -ItemType Directory -Path logs\mcp -Force }
```

### 4. 后端：使用 uv 创建 venv 并安装依赖

**4.1 进入 backend 目录并创建虚拟环境**

```powershell
cd D:\development\mineru-tianshu\backend
uv venv --python 3.12
```

**4.2 激活虚拟环境**

PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

若使用 CMD：

```cmd
.venv\Scripts\activate.bat
```

激活后，命令行前会出现 `(.venv)`。

**4.3 分步安装后端依赖（避免 PyTorch / PaddlePaddle 冲突）**

以下命令均在**已激活虚拟环境**且当前在 **backend** 目录下执行。

**第一步：安装 PyTorch（CUDA 12.6，适用于 RTX 3060）**

```powershell
uv pip install torch==2.6.0+cu126 torchvision==0.21.0+cu126 torchaudio==2.6.0+cu126 --index-url https://download.pytorch.org/whl/cu126
```

**第二步：安装 PaddlePaddle GPU（Windows 官方索引）**

飞桨官方 Windows GPU 安装说明见：<https://www.paddlepaddle.org.cn/documentation/docs/zh/install/pip/windows-pip.html>  
Windows 当前提供 **3.3.0**，按 CUDA 版本选择索引：**cu118** / **cu126** / **cu129**。RTX 3060 建议用 **cu126**。

**注意一**：用 **uv venv** 创建的虚拟环境**默认不含 pip**，若执行 `python -m pip` 报 “No module named pip”，请先在本环境中安装 pip：

```powershell
uv pip install pip
```

**注意二**：飞桨源格式可能与 uv 不兼容，故本步用 **pip** 安装（上面已确保 venv 内有 pip）：

```powershell
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

若本机为 CUDA 11.8 或 12.9，可改为：

```powershell
# CUDA 11.8
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# CUDA 12.9
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu129/
```

若仍失败，可**暂时跳过**本步，先完成其余依赖；届时 **pipeline（MinerU）** 仍可用，**PaddleOCR-VL 引擎**可能不可用。

**第三步：安装 Python 3.12 关键依赖**

```powershell
uv pip install "kiwisolver>=1.4.5" "Pillow>=11.0.0" "numpy>=1.26.0,<2.0.0" "setuptools>=75.0.0" "lxml>=5.3.0" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**第四步：安装 requirements.txt 中其余依赖**

```powershell
uv pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

说明：`--use-deprecated=legacy-resolver` 是 pip 的选项，**uv 不支持**，请勿添加。若此步报与 `paddleocr` 或依赖冲突相关错误，可暂时忽略（先完成 PaddlePaddle 第二步后再重试），或改用 `python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --use-deprecated=legacy-resolver` 仅在此步使用 pip。

**4.4 验证后端环境**

```powershell
python -c "import torch; print('PyTorch CUDA:', torch.cuda.is_available())"
python -c "import paddle; print('Paddle CUDA:', paddle.device.is_compiled_with_cuda())"
```

- 若两条均输出 **True**，即表示 PyTorch / Paddle 均已正确识别 GPU。
- 运行 Paddle 时若出现 **「信息: 用提供的模式无法找到文件。」** 或 **「No ccache found」** 等提示，可忽略，不影响使用；以最终 **Paddle CUDA: True** 为准。
- 若 Paddle 未安装，第二条会报错，可只确认 PyTorch 为 True。再验证 MinerU（必需）：

```powershell
python -c "import mineru; print('MinerU OK')"
```

### 5. 启动后端服务

仍在 **backend** 目录、虚拟环境已激活：

```powershell
python start_all.py
```

需要 MCP 时：

```powershell
python start_all.py --enable-mcp
```

单卡 3060 若显存紧张，可加：

```powershell
python start_all.py --workers-per-device 1
```

保持该终端不关闭。看到 API 与 Worker 启动成功的提示后，进行下一步。

### 6. 前端：使用 npm 安装并运行

**新开一个 PowerShell 窗口**，进入前端目录并安装依赖：

```powershell
cd D:\development\mineru-tianshu\frontend
npm install
```

**开发模式（推荐本地调试）：**

```powershell
npm run dev
```

默认前端地址：http://localhost:3000 ，且已配置将 `/api` 代理到 `http://localhost:8000`，无需改后端端口。

**生产模式（构建后提供静态资源）：**

```powershell
npm run build
```

构建产物在 `frontend/dist`。可用任意静态服务器托管该目录（如 `npx serve dist -p 3000`），或放到 Nginx 等；访问时需保证请求 `/api` 时被转发到本机 8000 端口。

### 7. 访问与验证

- 前端（开发）：http://localhost:3000  
- API 文档：http://localhost:8000/docs  
- 健康检查：http://localhost:8000/api/v1/health  

在前端提交一个小 PDF 任务，选择 **pipeline（MinerU）** 引擎测试；若未装 PaddlePaddle，不要选 **paddleocr-vl** 引擎。

**一键启动（方式三）**：在项目根目录双击 **start.bat**（或在该目录下执行 `start.bat`），会依次打开两个命令行窗口分别运行后端与前端，无需分别 cd 到 backend/frontend 再启动。

### 8. 转换完成后的文档输出到哪里？

解析完成后的 **Markdown / JSON / 图片** 会写在「输出目录」下，按任务分子目录存放。

| 启动方式 | 输出目录（根） | 说明 |
|----------|----------------|------|
| **start.bat**（一键启动） | 项目根目录下 **`data\output`** | start.bat 已传 `--output-dir` 到项目内 data/output |
| **手动 `python start_all.py`** | 默认 **`/tmp/mineru_tianshu_output`**（Windows 下多为 `C:\tmp\mineru_tianshu_output`） | 建议手动指定：`python start_all.py --output-dir ./data/output` |
| **环境变量 OUTPUT_PATH** | 你设置的路径 | 若在 .env 或系统环境里设置了 `OUTPUT_PATH`，以该路径为准 |

每个任务的结果在 **`{输出目录}/{文件名（无扩展名）}/`** 下，例如上传 `报告.pdf` 后会有：

- `data/output/报告/result.md`（或 `content.md`）— 主 Markdown
- `data/output/报告/result.json`（或 `content.json`）— 结构化 JSON
- `data/output/报告/images/` — 提取的图片

前端「任务详情」里的预览与下载，以及 API 返回的 `markdown_file` / 内容，都指向上述目录中的文件。

### 9. 模型下载说明（方式三）

**安装命令里不会下载模型**：`uv pip install` / `python -m pip install` 只安装 Python 包，**模型权重在首次使用对应功能时自动下载**。

| 功能 / 引擎 | 何时下载 | 默认缓存位置（本机） |
|-------------|----------|------------------------|
| **MinerU（PDF 解析）** | 首次用 pipeline 解析 PDF 时 | `%USERPROFILE%\.cache\huggingface\hub\` 或 `%USERPROFILE%\.cache\modelscope\`（由环境变量 `MODEL_DOWNLOAD_SOURCE` / `MINERU_MODEL_SOURCE` 决定） |
| **PaddleOCR-VL** | 首次用 paddleocr-vl 引擎时 | `%USERPROFILE%\.paddleocr\models\`（约 2GB，由 PaddleOCR 自动管理） |
| **SenseVoice（音频）** | 首次提交音频转写任务时 | 项目目录下 `models\sensevoice\`（如 `D:\development\mineru-tianshu\models\sensevoice`）或 ModelScope 缓存 |
| **水印检测（YOLO11）** | 首次使用水印去除时 | `%USERPROFILE%\.cache\watermark_models\` |

- 首次使用某功能时请保持网络畅通；国内建议在 `.env` 中设置 `MODEL_DOWNLOAD_SOURCE=modelscope` 或 `HF_ENDPOINT=https://hf-mirror.com` 以加速。
- **可选预下载**：在 backend 目录执行 `python download_models.py --output ../models-offline` 可提前下载 MinerU、SenseVoice 等模型到指定目录，供离线或加速首次使用；详见 `backend/download_models.py` 帮助。
- **前端展示**：登录后仪表盘会显示「模型状态」卡片与「首次使用提示」横幅（有模型未缓存时），提示首次使用将自动下载及预下载方式。

### 10. 方式三的已知限制与建议

| 项目 | 说明 |
|------|------|
| **PaddleOCR-VL** | 官方建议 Windows 用户使用 WSL 或 Docker。在纯 Windows 上可能安装失败或运行异常；若安装失败，可仅使用 **pipeline（MinerU）** 与 **markitdown** 等引擎。 |
| **FunASR / SenseVoice** | 部分依赖可能涉及 Linux 库，若报错可暂时跳过音频相关功能，或改用 Docker/WSL2。 |
| **首次运行** | MinerU、PaddleOCR 等会下载模型，可能较慢，请保持网络畅通。 |

若需 **109+ 语言 PaddleOCR-VL** 或 **音频转写** 等完整功能，建议使用 **方式一（Docker）** 或 **方式二（WSL2）**。

---

## 四、验证清单（部署完成后建议逐项检查）

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 本机执行 `nvidia-smi` | 能看到 RTX 3060 及驱动版本 |
| 2 | Docker 方式：`docker compose exec worker nvidia-smi` | 容器内能看到 GPU |
| 3 | 浏览器打开 http://localhost:80（Docker）或 http://localhost:5173（WSL2 本地） | 前端页面正常显示 |
| 4 | 浏览器打开 http://localhost:8000/docs | Swagger API 文档可打开 |
| 5 | 在前端提交一个小的 PDF 任务 | 任务能进入队列并完成（或至少 Worker 能拉取到任务） |

---

## 五、常见问题与排查

### 1. Docker 方式下提示 “NVIDIA GPU not detected”

- 确认本机已安装 NVIDIA 驱动并在 PowerShell 中能执行 `nvidia-smi`。  
- 确认 Docker Desktop 使用 WSL2 后端（Settings → General → Use the WSL 2 based engine）。  
- 重启 Docker Desktop 后重试。

### 2. 容器内 `nvidia-smi` 不可用

- 在 Docker Desktop 中确认已启用 GPU 支持（部分版本在 Settings → Resources → WSL Integration 或 GPU 相关项）。  
- 确认 WSL2 内能执行 `nvidia-smi`（在 Ubuntu 终端中运行一次）。

### 3. 任务一直处于 pending

- 查看 Worker 是否启动成功：`docker compose logs worker`（Docker）或查看运行 `start_all.py` 的终端（WSL2）。  
- 检查显存是否不足：单卡 3060 建议 `--workers-per-device 1`，或在 `.env` 中设置 `WORKER_GPUS=1` 后重启。

### 4. 端口被占用（80、8000、8001、8002）

- 修改 `.env` 中的 `API_PORT`、`WORKER_PORT`、`MCP_PORT`、`FRONTEND_PORT` 为未被占用的端口。  
- 或关闭占用端口的程序后重试。

### 5. WSL2 中 pip 安装 PaddlePaddle/PyTorch 很慢或失败

- 使用文档中给出的国内源（`-i https://...`）。  
- 若仍失败，可先只装 PyTorch CUDA 版，确认 GPU 可用后再装 PaddlePaddle。

### 6. 显存不足（OOM）

- 在 `.env` 中降低 `WORKER_GPUS` 或 `MAX_BATCH_SIZE`。  
- 启动时使用：`python start_all.py --workers-per-device 1`。

---

## 六、回滚与清理

### Docker 方式

在项目根目录执行：

```powershell
docker compose down
```

若需删除数据卷（数据库、上传文件等一并删除）：

```powershell
docker compose down -v
```

按需删除镜像以释放空间：

```powershell
docker compose down --rmi all
```

### WSL2 方式

在运行 `start_all.py` 的终端按 `Ctrl+C` 停止后端；在运行 `npm run dev` 的终端按 `Ctrl+C` 停止前端。  
若需完全卸载依赖，可删除 backend 下的虚拟环境目录（如 `.venv`）后按文档重新安装。

---

## 七、部署方式对照

| 方式 | 说明 | 推荐场景 |
|------|------|----------|
| **方式一** Docker | 容器化，GPU 透传，与官方脚本一致 | 生产或希望最少配置 |
| **方式二** WSL2 | 与 Linux 流程一致，bash/uv 在 WSL 内执行 | 习惯 Linux 命令行、需完整 PaddleOCR-VL |
| **方式三** Windows 源码（uv + venv + npm） | 本机 Windows 源码运行，后端 uv/venv，前端 npm | 本机开发调试、可接受 PaddleOCR-VL 可能不可用 |

完整功能（含 PaddleOCR-VL、音频等）建议 **方式一** 或 **方式二**；仅需 MinerU 文档解析时 **方式三** 即可。

---

## 八、文档与链接

- 项目主 README：[README.md](../README.md)  
- 后端说明与 API：[backend/README.md](../backend/README.md)  
- Docker 快速上手：`scripts/DOCKER_QUICK_START.txt`（若存在）  
- 主 README 中的生产/离线部署说明可作进阶参考。

---

*文档版本：2025-02-14；已含方式三 Windows 源码部署（uv + venv + npm），适用于本机 Windows + RTX 3060。*
