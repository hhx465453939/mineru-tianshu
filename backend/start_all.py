#!/usr/bin/env python3
"""
MinerU Tianshu - 启动所有服务

1. API Server (FastAPI) - 端口 18657
2. LitServe Worker Pool - 端口 28657
3. Task Scheduler (可选) - 后台任务调度
4. MCP Server (可选) - 端口 8002

自动检查并下载 OCR 模型（PaddleOCR-VL）
支持 GPU 加速、任务队列、优先级管理
"""

import subprocess
import signal
import sys
import time
import os
from loguru import logger
from pathlib import Path
import argparse
from utils import parse_list_arg
from dotenv import load_dotenv


class TianshuLauncher:
    """天枢服务启动器"""

    def __init__(
        self,
        output_dir="/tmp/mineru_tianshu_output",
        api_port=18657,
        worker_port=28657,
        workers_per_device=1,
        devices="auto",
        accelerator="auto",
        enable_mcp=False,
        mcp_port=8002,
        paddleocr_vl_vllm_engine_enabled=False,  # 新增paddle ocr vllm engine 配置
        paddleocr_vl_vllm_api_list=[],  # 新增paddle ocr vllm engine 配置
    ):
        self.output_dir = output_dir
        self.api_port = api_port
        self.worker_port = worker_port
        self.workers_per_device = workers_per_device
        self.devices = devices
        self.accelerator = accelerator
        self.enable_mcp = enable_mcp
        self.mcp_port = mcp_port
        self.processes = []
        self.paddleocr_vl_vllm_engine_enabled = paddleocr_vl_vllm_engine_enabled
        self.paddleocr_vl_vllm_api_list = paddleocr_vl_vllm_api_list

    def check_ocr_models(self):
        """检查并下载所有 OCR 模型（异步，不阻塞启动）"""
        import threading

        # 1. 检查 PaddleOCR-VL 模型
        def check_paddleocr_vl():
            try:
                from paddleocr_vl import PaddleOCRVLEngine

                logger.info("🔍 Checking PaddleOCR-VL...")
                logger.info("   Note: PaddleOCR-VL models are auto-managed by PaddleOCR")
                logger.info("   Cache location: ~/.paddleocr/models/")
                logger.info("   Model will be auto-downloaded on first use (~2GB)")

                # 检查 home 目录的模型缓存
                home_dir = Path.home()
                model_cache_dir = home_dir / ".paddleocr" / "models"

                if model_cache_dir.exists():
                    logger.info(f"✅ PaddleOCR model cache found at: {model_cache_dir}")
                else:
                    logger.info("ℹ️  PaddleOCR model cache not found, will be created on first use")

                # 简单初始化引擎（不触发下载）
                try:
                    PaddleOCRVLEngine()
                    logger.info("✅ PaddleOCR-VL engine initialized successfully")
                except Exception as e:
                    logger.warning(f"⚠️  PaddleOCR-VL initialization failed: {e}")
                    logger.info("   This is normal if GPU is not available or dependencies are missing")

            except ImportError:
                logger.debug("PaddleOCR-VL not installed, skipping check")
            except Exception as e:
                logger.debug(f"PaddleOCR-VL check skipped: {e}")

        # 在后台线程中下载模型
        thread_paddleocr = threading.Thread(target=check_paddleocr_vl, daemon=True)
        thread_paddleocr.start()

    def start_services(self):
        """启动所有服务"""
        logger.info("=" * 70)
        logger.info("🚀 MinerU Tianshu - AI Data Preprocessing Platform")
        logger.info("=" * 70)
        logger.info("天枢 - 企业级 AI 数据预处理平台")
        logger.info("支持文档、图片、音频、视频等多模态数据处理")
        logger.info("")

        try:
            total_services = 4 if self.enable_mcp else 3

            # 1. 启动 API Server
            logger.info(f"📡 [1/{total_services}] Starting API Server...")
            env = os.environ.copy()
            env["API_PORT"] = str(self.api_port)
            env["OUTPUT_PATH"] = self.output_dir  # 设置输出目录（与 Worker 保持一致）
            api_proc = subprocess.Popen([sys.executable, "api_server.py"], cwd=Path(__file__).parent, env=env)
            self.processes.append(("API Server", api_proc))
            time.sleep(3)

            if api_proc.poll() is not None:
                logger.error("❌ API Server failed to start!")
                return False

            logger.info(f"   ✅ API Server started (PID: {api_proc.pid})")
            logger.info(f"   📖 API Docs: http://localhost:{self.api_port}/docs")
            logger.info("")

            # 2. 启动 LitServe Worker Pool
            logger.info(f"⚙️  [2/{total_services}] Starting LitServe Worker Pool...")
            worker_env = os.environ.copy()
            worker_env["WORKER_PORT"] = str(self.worker_port)
            worker_env["OUTPUT_PATH"] = self.output_dir

            worker_cmd = [
                sys.executable,
                "litserve_worker.py",
                "--output-dir",
                self.output_dir,
                "--accelerator",
                self.accelerator,
                "--workers-per-device",
                str(self.workers_per_device),
                "--port",
                str(self.worker_port),
                "--devices",
                str(self.devices) if isinstance(self.devices, str) else ",".join(map(str, self.devices)),
            ]

            # 只在启用时才添加 paddleocr-vl-vllm-engine-enabled 参数
            if self.paddleocr_vl_vllm_engine_enabled:
                worker_cmd.extend(["--paddleocr-vl-vllm-engine-enabled"])
            # 添加 paddleocr-vl-vllm-api-list 参数
            worker_cmd.extend(["--paddleocr-vl-vllm-api-list", str(self.paddleocr_vl_vllm_api_list)])

            worker_proc = subprocess.Popen(worker_cmd, cwd=Path(__file__).parent, env=worker_env)
            self.processes.append(("LitServe Workers", worker_proc))
            time.sleep(5)

            if worker_proc.poll() is not None:
                logger.error("❌ LitServe Workers failed to start!")
                return False

            logger.info(f"   ✅ LitServe Workers started (PID: {worker_proc.pid})")
            logger.info(f"   🔌 Worker Port: {self.worker_port}")
            logger.info(f"   👷 Workers per Device: {self.workers_per_device}")
            logger.info("")

            # 3. 启动 Task Scheduler
            logger.info(f"🔄 [3/{total_services}] Starting Task Scheduler...")
            scheduler_cmd = [
                sys.executable,
                "task_scheduler.py",
                "--litserve-url",
                f"http://localhost:{self.worker_port}/predict",
                "--wait-for-workers",
            ]

            scheduler_proc = subprocess.Popen(scheduler_cmd, cwd=Path(__file__).parent)
            self.processes.append(("Task Scheduler", scheduler_proc))
            time.sleep(3)

            if scheduler_proc.poll() is not None:
                logger.error("❌ Task Scheduler failed to start!")
                return False

            logger.info(f"   ✅ Task Scheduler started (PID: {scheduler_proc.pid})")
            logger.info("")

            # 4. 启动 MCP Server（可选）
            if self.enable_mcp:
                logger.info(f"🔌 [4/{total_services}] Starting MCP Server...")
                mcp_env = os.environ.copy()
                mcp_env["API_BASE_URL"] = f"http://localhost:{self.api_port}"
                mcp_env["MCP_PORT"] = str(self.mcp_port)
                mcp_env["MCP_HOST"] = "0.0.0.0"

                mcp_proc = subprocess.Popen([sys.executable, "mcp_server.py"], cwd=Path(__file__).parent, env=mcp_env)
                self.processes.append(("MCP Server", mcp_proc))
                time.sleep(3)

                if mcp_proc.poll() is not None:
                    logger.error("❌ MCP Server failed to start!")
                    return False

                logger.info(f"   ✅ MCP Server started (PID: {mcp_proc.pid})")
                logger.info(f"   🌐 MCP Endpoint: http://localhost:{self.mcp_port}/mcp")
                logger.info("")

            # 启动成功
            logger.info("=" * 70)
            logger.info("✅ All Services Started Successfully!")
            logger.info("=" * 70)
            logger.info("")
            logger.info("📚 Quick Start:")
            logger.info(f"   • API Documentation: http://localhost:{self.api_port}/docs")
            logger.info(f"   • Submit Task:       POST http://localhost:{self.api_port}/api/v1/tasks/submit")
            logger.info(f"   • Query Status:      GET  http://localhost:{self.api_port}/api/v1/tasks/{{task_id}}")
            logger.info(f"   • Queue Stats:       GET  http://localhost:{self.api_port}/api/v1/queue/stats")
            if self.enable_mcp:
                logger.info(f"   • MCP Endpoint:      http://localhost:{self.mcp_port}/mcp/sse")
            logger.info("")
            logger.info("🔧 Service Details:")
            for name, proc in self.processes:
                logger.info(f"   • {name:20s} PID: {proc.pid}")
            logger.info("")
            logger.info("⚠️  Press Ctrl+C to stop all services")
            logger.info("=" * 70)
            logger.info("")
            logger.info("💖 If you find this project helpful, please consider:")
            logger.info("   ⭐ Star us on GitHub: https://github.com/magicyuan876/mineru-tianshu")
            logger.info("   🐛 Report issues or contribute: https://github.com/magicyuan876/mineru-tianshu/issues")
            logger.info("")
            logger.info("=" * 70)
            logger.info("")

            # 所有服务启动完成后，检查并下载所有 OCR 模型
            self.check_ocr_models()

            return True

        except Exception as e:
            logger.error(f"❌ Failed to start services: {e}")
            self.stop_services()
            return False

    def stop_services(self, signum=None, frame=None):
        """停止所有服务"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("⏹️  Stopping All Services...")
        logger.info("=" * 70)

        for name, proc in self.processes:
            if proc.poll() is None:  # 进程仍在运行
                logger.info(f"   Stopping {name} (PID: {proc.pid})...")
                proc.terminate()

        # 等待所有进程结束
        for name, proc in self.processes:
            try:
                proc.wait(timeout=10)
                logger.info(f"   ✅ {name} stopped")
            except subprocess.TimeoutExpired:
                logger.warning(f"   ⚠️  {name} did not stop gracefully, forcing...")
                proc.kill()
                proc.wait()

        logger.info("=" * 70)
        logger.info("✅ All Services Stopped")
        logger.info("=" * 70)
        sys.exit(0)

    def wait(self):
        """等待所有服务"""
        try:
            while True:
                time.sleep(1)

                # 检查进程状态
                for name, proc in self.processes:
                    if proc.poll() is not None:
                        logger.error(f"❌ {name} unexpectedly stopped!")
                        self.stop_services()
                        return

        except KeyboardInterrupt:
            self.stop_services()


def main():
    """主函数"""
    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent
    # 优先 backend 目录，其次项目根目录（与部署文档中 copy .env 到根目录一致）
    env_path = backend_dir / ".env"
    if not env_path.exists():
        env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info(f"✅ Loaded .env from: {env_path}")
    else:
        logger.error("❌ .env file not found.")
        logger.error("Please create a .env file in the backend directory or project root (copy from .env.example).")
        sys.exit(1)
    parser = argparse.ArgumentParser(
        description="MinerU Tianshu - 统一启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置启动（自动检测GPU）
  python start_all.py

  # 使用CPU模式
  python start_all.py --accelerator cpu

  # 指定输出目录和端口
  python start_all.py --output-dir /data/output --api-port 8080

  # 每个GPU启动2个worker
  python start_all.py --accelerator cuda --workers-per-device 2

  # 只使用指定的GPU
  python start_all.py --accelerator cuda --devices 0,1

  # 启用 MCP Server 支持（用于 AI 助手调用）
  python start_all.py --enable-mcp --mcp-port 8002
        """,
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="/tmp/mineru_tianshu_output",
        help="输出目录 (默认: /tmp/mineru_tianshu_output)",
    )
    parser.add_argument("--api-port", type=int, default=18657, help="API服务器端口 (默认: 18657)")
    parser.add_argument("--worker-port", type=int, default=28657, help="Worker服务器端口 (默认: 28657)")
    parser.add_argument(
        "--accelerator",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="加速器类型 (默认: auto，自动检测)",
    )
    parser.add_argument("--workers-per-device", type=int, default=1, help="每个GPU的worker数量 (默认: 1)")
    parser.add_argument("--devices", type=str, default="auto", help="使用的GPU设备，逗号分隔 (默认: auto，使用所有GPU)")
    parser.add_argument(
        "--enable-mcp", action="store_true", help="启用 MCP Server（支持 Model Context Protocol 远程调用）"
    )
    parser.add_argument("--mcp-port", type=int, default=8002, help="MCP Server 端口 (默认: 8002)")
    # 配置 paddleocr-vl-vllm engine
    parser.add_argument(
        "--paddleocr-vl-vllm-engine-enabled",
        action="store_true",
        default=False,
        help="是否启用 PaddleOCR VL VLLM 引擎 (默认: False)",
    )
    parser.add_argument(
        "--paddleocr-vl-vllm-api-list",
        type=parse_list_arg,
        default=[],
        help='PaddleOCR VL VLLM API 列表（Python list 字面量格式，如: \'["http://0.0.0.0:17300/v1", "http://0.0.0.0:17301/v1"]\'）',
    )

    args = parser.parse_args()

    # 处理 devices 参数
    devices = args.devices
    if devices != "auto":
        try:
            devices = [int(d) for d in devices.split(",")]
        except ValueError:
            logger.warning(f"Invalid devices format: {devices}, using 'auto'")
            devices = "auto"
    if args.paddleocr_vl_vllm_engine_enabled:
        logger.success("start_all 脚本中 PaddleOCR VL VLLM 引擎已设置启用")
        if not args.paddleocr_vl_vllm_api_list:
            logger.error(
                "请配置 --paddleocr-vl-vllm-api-list 参数, 或者移除 --paddleocr-vl-vllm-engine-enabled 来关闭 PaddleOCR VL VLLM 引擎"
            )
            sys.exit(1)
        else:
            logger.success(f"PaddleOCR VL VLLM 引擎，API 列表为: {args.paddleocr_vl_vllm_api_list}")
    else:
        logger.info("start_all 脚本中PaddleOCR VL VLLM 引擎已设置不启用")
    # 创建启动器
    launcher = TianshuLauncher(
        output_dir=args.output_dir,
        api_port=args.api_port,
        worker_port=args.worker_port,
        workers_per_device=args.workers_per_device,
        devices=devices,
        accelerator=args.accelerator,
        enable_mcp=args.enable_mcp,
        mcp_port=args.mcp_port,
        paddleocr_vl_vllm_engine_enabled=args.paddleocr_vl_vllm_engine_enabled,
        paddleocr_vl_vllm_api_list=args.paddleocr_vl_vllm_api_list,
    )

    # 设置信号处理
    signal.signal(signal.SIGINT, launcher.stop_services)
    signal.signal(signal.SIGTERM, launcher.stop_services)

    # 启动服务
    if launcher.start_services():
        launcher.wait()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
