"""
MinerU Tianshu - API Server
天枢 API 服务器

企业级 AI 数据预处理平台
支持文档、图片、音频、视频等多模态数据处理
提供 RESTful API 接口用于任务提交、查询和管理
企业级认证授权: JWT Token + API Key + SSO
"""

import json
import os
import re
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from loguru import logger

# 导入认证模块
from auth import (
    User,
    Permission,
    get_current_active_user,
    require_permission,
)
from auth.auth_db import AuthDB
from auth.routes import router as auth_router
from task_db import TaskDB

# 初始化 FastAPI 应用
app = FastAPI(
    title="MinerU Tianshu API",
    description="天枢 - 企业级 AI 数据预处理平台 | 支持文档、图片、音频、视频等多模态数据处理 | 企业级认证授权",
    version="2.0.0",
    # 不设置 servers，让 FastAPI 自动根据请求的 Host 生成
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取项目根目录（backend 的父目录）
PROJECT_ROOT = Path(__file__).parent.parent

# 初始化数据库
# 确保使用环境变量中的数据库路径（与 Worker 保持一致）
db_path_env = os.getenv("DATABASE_PATH")
# Windows 本地：.env 中常见的 Docker 路径 /app/data/db/... 会解析为 E:\app\...，目录往往不存在
if db_path_env and os.name == "nt" and db_path_env.replace("\\", "/").strip().startswith("/app/"):
    db_path_env = None
if db_path_env:
    db_path = str(Path(db_path_env).resolve())
    logger.info(f"📊 API Server using DATABASE_PATH: {db_path_env} -> {db_path}")
    db = TaskDB(db_path)
else:
    logger.warning("⚠️  DATABASE_PATH not set in API Server, using default")
    # Docker 环境: /app/data/db/mineru_tianshu.db
    # 本地环境: ./data/db/mineru_tianshu.db
    default_db_path = PROJECT_ROOT / "data" / "db" / "mineru_tianshu.db"
    default_db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path = str(default_db_path.resolve())
    logger.info(f"📊 Using default database path: {db_path}")
    db = TaskDB(db_path)
auth_db = AuthDB()

# 注册认证路由
app.include_router(auth_router)

# 配置输出目录（使用共享目录，Docker 环境可访问）
output_path_env = os.getenv("OUTPUT_PATH")
if output_path_env:
    OUTPUT_DIR = Path(output_path_env)
else:
    # Docker 环境: /app/output
    # 本地环境: ./data/output
    OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"📁 Output directory: {OUTPUT_DIR.resolve()}")


# 注意：此函数已废弃，Worker 已自动上传图片到 RustFS 并替换 URL
# 保留此函数仅用于向后兼容（处理旧任务或 RustFS 失败的情况）
def process_markdown_images_legacy(md_content: str, image_dir: Path, result_path: str):
    """
    【已废弃】处理 Markdown 中的图片引用

    Worker 已自动上传图片到 RustFS 并替换 URL，此函数仅用于向后兼容。
    如果检测到图片路径不是 URL，则转换为本地静态文件服务 URL。

    Args:
        md_content: Markdown 内容
        image_dir: 图片所在目录
        result_path: 任务结果路径

    Returns:
        处理后的 Markdown 内容
    """
    # 检查是否已经包含 RustFS URL
    if "http://" in md_content or "https://" in md_content:
        logger.debug("✅ Markdown already contains URLs (RustFS uploaded)")
        return md_content

    # 如果没有图片目录，直接返回
    if not image_dir.exists():
        logger.debug("ℹ️  No images directory, skipping processing")
        return md_content

    # 兼容模式：转换相对路径为本地 URL
    logger.warning("⚠️  Images not uploaded to RustFS, using local URLs (legacy mode)")

    def replace_image_path(match):
        """替换图片路径为本地 URL"""
        full_match = match.group(0)
        # 提取图片路径（Markdown 或 HTML）
        if "![" in full_match:
            # Markdown: ![alt](path)
            image_path = match.group(2)
            alt_text = match.group(1)
        else:
            # HTML: <img src="path">
            image_path = match.group(2)
            alt_text = "Image"

        # 如果已经是 URL，跳过
        if image_path.startswith("http"):
            return full_match

        # 生成本地静态文件 URL
        try:
            image_filename = Path(image_path).name
            output_dir_str = str(OUTPUT_DIR).replace("\\", "/")
            result_path_str = result_path.replace("\\", "/")

            if result_path_str.startswith(output_dir_str):
                relative_path = result_path_str[len(output_dir_str) :].lstrip("/")
                encoded_relative_path = quote(relative_path, safe="/")
                encoded_filename = quote(image_filename, safe="/")
                static_url = f"/api/v1/files/output/{encoded_relative_path}/images/{encoded_filename}"

                # 返回替换后的内容
                if "![" in full_match:
                    return f"![{alt_text}]({static_url})"
                else:
                    return full_match.replace(image_path, static_url)
        except Exception as e:
            logger.error(f"❌ Failed to generate local URL: {e}")

        return full_match

    try:
        # 匹配 Markdown 和 HTML 图片
        md_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        html_pattern = r'<img\s+([^>]*\s+)?src="([^"]+)"([^>]*)>'

        new_content = re.sub(md_pattern, replace_image_path, md_content)
        new_content = re.sub(html_pattern, replace_image_path, new_content)
        return new_content
    except Exception as e:
        logger.error(f"❌ Failed to process images: {e}")
        return md_content


@app.get("/", tags=["系统信息"])
async def root():
    """API根路径"""
    return {
        "service": "MinerU Tianshu",
        "version": "1.0.0",
        "description": "天枢 - 企业级 AI 数据预处理平台",
        "features": "文档、图片、音频、视频等多模态数据处理",
        "docs": "/docs",
    }


@app.post("/api/v1/tasks/submit", tags=["任务管理"])
async def submit_task(
    file: UploadFile = File(..., description="文件: PDF/图片/Office/HTML/音频/视频等多种格式"),
    backend: str = Form(
        "auto",
        description="处理后端: auto (自动选择) | pipeline/paddleocr-vl (文档) | sensevoice (音频) | video (视频) | fasta/genbank (专业格式)",
    ),
    lang: str = Form("auto", description="语言: auto/ch/en/korean/japan等"),
    method: str = Form("auto", description="解析方法: auto/txt/ocr"),
    formula_enable: bool = Form(True, description="是否启用公式识别"),
    table_enable: bool = Form(True, description="是否启用表格识别"),
    priority: int = Form(0, description="优先级，数字越大越优先"),
    # 视频处理专用参数
    keep_audio: bool = Form(False, description="视频处理时是否保留提取的音频文件"),
    enable_keyframe_ocr: bool = Form(False, description="是否启用视频关键帧OCR识别（实验性功能）"),
    ocr_backend: str = Form("paddleocr-vl", description="关键帧OCR引擎: paddleocr-vl"),
    keep_keyframes: bool = Form(False, description="是否保留提取的关键帧图像"),
    # 音频处理专用参数
    enable_speaker_diarization: bool = Form(
        False, description="是否启用说话人分离（音频多说话人识别，需要额外下载 Paraformer 模型）"
    ),
    # 水印去除专用参数
    remove_watermark: bool = Form(False, description="是否启用水印去除（支持 PDF/图片）"),
    watermark_conf_threshold: float = Form(0.35, description="水印检测置信度阈值（0.0-1.0，推荐 0.35）"),
    watermark_dilation: int = Form(10, description="水印掩码膨胀大小（像素，推荐 10）"),
    # Office 文件转 PDF 参数
    convert_office_to_pdf: bool = Form(
        False, description="是否将 Office 文件转换为 PDF 后再处理（图片提取更完整，但速度较慢）"
    ),
    # 认证依赖
    current_user: User = Depends(require_permission(Permission.TASK_SUBMIT)),
):
    """
    提交文档解析任务

    需要认证和 TASK_SUBMIT 权限。
    立即返回 task_id，任务在后台异步处理。
    """
    try:
        # 创建共享的上传目录（Backend 和 Worker 都能访问）
        upload_path_env = os.getenv("UPLOAD_PATH")
        if upload_path_env:
            upload_dir = Path(upload_path_env)
        else:
            # Docker 环境: /app/uploads
            # 本地环境: ./data/uploads
            upload_dir = PROJECT_ROOT / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一的文件名（避免冲突）
        unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
        temp_file_path = upload_dir / unique_filename

        # 流式写入文件到磁盘，避免高内存使用
        with open(temp_file_path, "wb") as temp_file:
            while True:
                chunk = await file.read(1 << 23)  # 8MB chunks
                if not chunk:
                    break
                temp_file.write(chunk)

        # 构建处理选项
        options = {
            "lang": lang,
            "method": method,
            "formula_enable": formula_enable,
            "table_enable": table_enable,
            # 视频处理参数
            "keep_audio": keep_audio,
            "enable_keyframe_ocr": enable_keyframe_ocr,
            "ocr_backend": ocr_backend,
            "keep_keyframes": keep_keyframes,
            # 音频处理参数
            "enable_speaker_diarization": enable_speaker_diarization,
            # 水印去除参数
            "remove_watermark": remove_watermark,
            "watermark_conf_threshold": watermark_conf_threshold,
            "watermark_dilation": watermark_dilation,
            # Office 转 PDF 参数
            "convert_office_to_pdf": convert_office_to_pdf,
        }

        # 创建任务（PDF 拆分逻辑由 Worker 处理）
        task_id = db.create_task(
            file_name=file.filename,
            file_path=str(temp_file_path),
            backend=backend,
            options=options,
            priority=priority,
            user_id=current_user.user_id,
        )

        logger.info(f"✅ Task submitted: {task_id} - {file.filename}")
        logger.info(f"   User: {current_user.username} ({current_user.role.value})")
        logger.info(f"   Backend: {backend}")
        logger.info(f"   Priority: {priority}")

        return {
            "success": True,
            "task_id": task_id,
            "status": "pending",
            "message": "Task submitted successfully",
            "file_name": file.filename,
            "user_id": current_user.user_id,
            "created_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to submit task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tasks/{task_id}", tags=["任务管理"])
async def get_task_status(
    task_id: str,
    upload_images: bool = Query(False, description="【已废弃】图片已自动上传到 RustFS，此参数保留仅用于向后兼容"),
    format: str = Query("markdown", description="返回格式: markdown(默认)/json/both"),
    current_user: User = Depends(get_current_active_user),
):
    """
    查询任务状态和详情

    需要认证。用户只能查看自己的任务，管理员可以查看所有任务。
    当任务完成时，会自动返回解析后的内容（data 字段）
    - format=markdown: 只返回 Markdown 内容（默认）
    - format=json: 只返回 JSON 结构化数据（MinerU 和 PaddleOCR-VL 支持）
    - format=both: 同时返回 Markdown 和 JSON
    可选择是否上传图片到 MinIO 并替换为 URL
    """
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 权限检查: 用户只能查看自己的任务，管理员/经理可以查看所有任务
    if not current_user.has_permission(Permission.TASK_VIEW_ALL):
        if task.get("user_id") != current_user.user_id:
            raise HTTPException(status_code=403, detail="Permission denied: You can only view your own tasks")

    response = {
        "success": True,
        "task_id": task_id,
        "status": task["status"],
        "file_name": task["file_name"],
        "backend": task["backend"],
        "priority": task["priority"],
        "error_message": task["error_message"],
        "created_at": task["created_at"],
        "started_at": task["started_at"],
        "completed_at": task["completed_at"],
        "worker_id": task["worker_id"],
        "retry_count": task["retry_count"],
        "user_id": task.get("user_id"),
    }

    # 如果是主任务,添加子任务进度信息
    if task.get("is_parent"):
        child_count = task.get("child_count", 0)
        child_completed = task.get("child_completed", 0)

        response["is_parent"] = True
        response["subtask_progress"] = {
            "total": child_count,
            "completed": child_completed,
            "percentage": round(child_completed / child_count * 100, 1) if child_count > 0 else 0,
        }

        # 可选: 返回所有子任务状态
        try:
            children = db.get_child_tasks(task_id)
            response["subtasks"] = [
                {
                    "task_id": child["task_id"],
                    "status": child["status"],
                    "chunk_info": json.loads(child.get("options", "{}")).get("chunk_info"),
                    "error_message": child.get("error_message"),
                }
                for child in children
            ]
            logger.info(f"✅ Parent task status: {task['status']} - Progress: {child_completed}/{child_count} subtasks")
        except Exception as e:
            logger.warning(f"⚠️  Failed to load subtasks: {e}")

    else:
        logger.info(f"✅ Task status: {task['status']} - (result_path: {task.get('result_path')})")

    # 如果任务已完成，尝试返回解析内容
    if task["status"] == "completed":
        if not task["result_path"]:
            # 结果文件已被清理
            response["data"] = None
            response["message"] = "Task completed but result files have been cleaned up (older than retention period)"
            return response

        result_dir = Path(task["result_path"])
        logger.info(f"📂 Checking result directory: {result_dir}")

        if result_dir.exists():
            logger.info("✅ Result directory exists")
            # 递归查找 Markdown 文件（MinerU 输出结构：task_id/filename/auto/*.md）
            md_files = list(result_dir.rglob("*.md"))
            # 递归查找 JSON 文件
            # MinerU 输出格式: {filename}_content_list.json (主要的结构化内容)
            # 也支持其他引擎的: content.json, result.json
            json_files = [
                f
                for f in result_dir.rglob("*.json")
                if not f.parent.name.startswith("page_")
                and (f.name in ["content.json", "result.json"] or "_content_list.json" in f.name)
            ]
            logger.info(f"📄 Found {len(md_files)} markdown files and {len(json_files)} json files")

            if md_files:
                try:
                    # 初始化 data 字段
                    response["data"] = {}

                    # 标记 JSON 是否可用
                    response["data"]["json_available"] = len(json_files) > 0

                    # 根据 format 参数决定返回内容
                    if format in ["markdown", "both"]:
                        # 选择主 Markdown 文件（优先 result.md）
                        md_file = None
                        for f in md_files:
                            if f.name == "result.md":
                                md_file = f
                                break
                        if not md_file:
                            md_file = md_files[0]

                        # 查找图片目录（Worker 已规范化为 images/）
                        image_dir = md_file.parent / "images"

                        # 读取 Markdown 内容（Worker 已自动上传图片到 RustFS）
                        logger.info(f"📖 Reading markdown file: {md_file}")
                        with open(md_file, "r", encoding="utf-8") as f:
                            md_content = f.read()

                        logger.info(f"✅ Markdown content loaded, length: {len(md_content)} characters")

                        # Worker 已自动上传图片到 RustFS 并替换 URL
                        # 仅在兼容模式下处理（旧任务或 RustFS 失败）
                        if image_dir.exists() and ("http://" not in md_content and "https://" not in md_content):
                            logger.warning("⚠️  Images not uploaded to RustFS, using legacy mode")
                            md_content = process_markdown_images_legacy(md_content, image_dir, task["result_path"])
                        else:
                            logger.debug("✅ Images already processed by Worker (RustFS URLs)")

                        # 添加 Markdown 相关字段
                        response["data"]["markdown_file"] = md_file.name
                        response["data"]["content"] = md_content
                        response["data"]["has_images"] = image_dir.exists()

                    # 如果用户请求 JSON 格式
                    if format in ["json", "both"] and json_files:
                        import json as json_lib

                        json_file = json_files[0]
                        logger.info(f"📖 Reading JSON file: {json_file}")
                        try:
                            with open(json_file, "r", encoding="utf-8") as f:
                                json_content = json_lib.load(f)
                            response["data"]["json_file"] = json_file.name
                            response["data"]["json_content"] = json_content
                            logger.info("✅ JSON content loaded successfully")
                        except Exception as json_e:
                            logger.warning(f"⚠️  Failed to load JSON: {json_e}")
                    elif format == "json" and not json_files:
                        # 用户请求 JSON 但没有 JSON 文件
                        logger.warning("⚠️  JSON format requested but no JSON file available")
                        response["data"]["message"] = "JSON format not available for this backend"

                    # 如果没有返回任何内容，添加提示
                    if not response["data"]:
                        response["data"] = None
                        logger.warning(f"⚠️  No data returned for format: {format}")
                    else:
                        logger.info(f"✅ Response data field added successfully (format={format})")

                except Exception as e:
                    logger.error(f"❌ Failed to read content: {e}")
                    logger.exception(e)
                    # 读取失败不影响状态查询，只是不返回 data
                    response["data"] = None
            else:
                logger.warning(f"⚠️  No markdown files found in {result_dir}")
        else:
            logger.error(f"❌ Result directory does not exist: {result_dir}")
    else:
        logger.info(f"ℹ️  Task status is {task['status']}, skipping content loading")

    return response


@app.delete("/api/v1/tasks/{task_id}", tags=["任务管理"])
async def cancel_task(task_id: str, current_user: User = Depends(get_current_active_user)):
    """
    取消任务（仅限 pending 状态）

    需要认证。用户只能取消自己的任务，管理员可以取消任何任务。
    """
    task = db.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 权限检查: 用户只能取消自己的任务，管理员可以取消任何任务
    if not current_user.has_permission(Permission.TASK_DELETE_ALL):
        if task.get("user_id") != current_user.user_id:
            raise HTTPException(status_code=403, detail="Permission denied: You can only cancel your own tasks")

    if task["status"] == "pending":
        db.update_task_status(task_id, "cancelled")

        # 删除临时文件
        file_path = Path(task["file_path"])
        if file_path.exists():
            file_path.unlink()

        logger.info(f"⏹️  Task cancelled: {task_id} by user {current_user.username}")
        return {"success": True, "message": "Task cancelled successfully"}
    else:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task in {task['status']} status")


@app.get("/api/v1/queue/stats", tags=["队列管理"])
async def get_queue_stats(current_user: User = Depends(require_permission(Permission.QUEUE_VIEW))):
    """
    获取队列统计信息

    需要认证和 QUEUE_VIEW 权限。
    """
    stats = db.get_queue_stats()

    return {
        "success": True,
        "stats": stats,
        "total": sum(stats.values()),
        "timestamp": datetime.now().isoformat(),
        "user": current_user.username,
    }


@app.get("/api/v1/queue/tasks", tags=["队列管理"])
async def list_tasks(
    status: Optional[str] = Query(None, description="筛选状态: pending/processing/completed/failed"),
    limit: int = Query(100, description="返回数量限制", le=1000),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取任务列表

    需要认证。普通用户只能看到自己的任务，管理员/经理可以看到所有任务。
    """
    # 检查用户权限
    can_view_all = current_user.has_permission(Permission.TASK_VIEW_ALL)

    if can_view_all:
        # 管理员/经理查看所有任务
        if status:
            tasks = db.get_tasks_by_status(status, limit)
        else:
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )
                tasks = [dict(row) for row in cursor.fetchall()]
    else:
        # 普通用户只能看到自己的任务
        with db.get_cursor() as cursor:
            if status:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (current_user.user_id, status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (current_user.user_id, limit),
                )
            tasks = [dict(row) for row in cursor.fetchall()]

    return {"success": True, "count": len(tasks), "tasks": tasks, "can_view_all": can_view_all}


@app.post("/api/v1/admin/cleanup", tags=["系统管理"])
async def cleanup_old_tasks(
    days: int = Query(7, description="清理N天前的任务"),
    current_user: User = Depends(require_permission(Permission.QUEUE_MANAGE)),
):
    """
    清理旧任务（管理接口）

    同时删除任务的所有相关文件和数据库记录：
    - 上传的原始文件
    - 结果文件夹（包括生成的文件和所有中间文件）
    - 数据库记录

    需要管理员权限。
    """
    deleted_count = db.cleanup_old_task_records(days)

    logger.info(f"🧹 Cleaned up {deleted_count} old tasks (files and records) by {current_user.username}")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Cleaned up {deleted_count} tasks older than {days} days (files and records deleted)",
    }


@app.post("/api/v1/admin/reset-stale", tags=["系统管理"])
async def reset_stale_tasks(
    timeout_minutes: int = Query(60, description="超时时间（分钟）"),
    current_user: User = Depends(require_permission(Permission.QUEUE_MANAGE)),
):
    """
    重置超时的 processing 任务（管理接口）

    需要管理员权限。
    """
    reset_count = db.reset_stale_tasks(timeout_minutes)

    logger.info(f"🔄 Reset {reset_count} stale tasks by {current_user.username}")

    return {
        "success": True,
        "reset_count": reset_count,
        "message": f"Reset tasks processing for more than {timeout_minutes} minutes",
    }


@app.get("/api/v1/engines", tags=["系统信息"])
async def list_engines():
    """
    列出所有可用的处理引擎

    无需认证。返回系统中所有可用的处理引擎信息。
    """
    engines = {
        "document": [
            {
                "name": "pipeline",
                "display_name": "MinerU Pipeline",
                "description": "默认的 PDF/图片解析引擎，支持公式、表格等复杂结构",
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg"],
            },
        ],
        "ocr": [],
        "audio": [],
        "video": [],
        "format": [],
        "office": [
            {
                "name": "MarkItDown (快速)",
                "value": "auto",
                "description": "Office 文档和文本文件转换引擎（快速但图片提取可能不完整）",
                "supported_formats": [".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt", ".html", ".txt", ".csv"],
                "features": ["文本提取", "基础格式保留", "图片提取（DOCX）"],
                "note": "推荐启用 convert_office_to_pdf 参数以获得更好的图片提取效果",
            },
            {
                "name": "LibreOffice + MinerU (完整)",
                "value": "auto",
                "description": "将 Office 文件转为 PDF 后使用 MinerU 处理（慢但图片提取完整）",
                "supported_formats": [".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt"],
                "features": ["完整格式保留", "完整图片提取", "表格识别", "公式识别"],
                "requirement": "需要设置 convert_office_to_pdf=true",
            },
        ],
    }

    # 动态检测可用引擎
    import importlib.util

    if importlib.util.find_spec("paddleocr_vl") is not None:
        engines["ocr"].append(
            {
                "name": "paddleocr_vl",
                "display_name": "PaddleOCR-VL",
                "description": "PaddlePaddle 视觉语言 OCR 引擎",
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg"],
            }
        )

    if importlib.util.find_spec("paddleocr_vl_vllm") is not None:
        engines["ocr"].append(
            {
                "name": "paddleocr-vl-vllm",
                "display_name": "PaddleOCR-VL-VLLM",
                "description": "基于 vLLM 的高性能 PaddleOCR 引擎",
                "supported_formats": [".pdf", ".png", ".jpg", ".jpeg"],
            }
        )

    if importlib.util.find_spec("audio_engines") is not None:
        engines["audio"].append(
            {
                "name": "sensevoice",
                "display_name": "SenseVoice",
                "description": "语音识别引擎，支持多语言自动检测",
                "supported_formats": [".wav", ".mp3", ".flac", ".m4a", ".ogg"],
            }
        )

    if importlib.util.find_spec("video_engines") is not None:
        engines["video"].append(
            {
                "name": "video",
                "display_name": "Video Processing",
                "description": "视频处理引擎，支持关键帧提取和音频转录",
                "supported_formats": [".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv"],
            }
        )

    # 专业格式引擎
    try:
        from format_engines import FormatEngineRegistry

        for engine_info in FormatEngineRegistry.list_engines():
            engines["format"].append(
                {
                    "name": engine_info["name"],
                    "display_name": engine_info["name"].upper(),
                    "description": engine_info["description"],
                    "supported_formats": engine_info["extensions"],
                }
            )
    except ImportError:
        pass

    return {
        "success": True,
        "engines": engines,
        "timestamp": datetime.now().isoformat(),
    }


def _check_model_cache_dir(path: Path, has_any_file: bool = True) -> bool:
    """检查目录存在且（可选）非空。"""
    if not path.exists() or not path.is_dir():
        return False
    if not has_any_file:
        return True
    try:
        return any(path.iterdir())
    except OSError:
        return False


MODEL_PRELOAD_STATE = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "success": None,
    "return_code": None,
    "error": None,
    "output_dir": None,
    "logs": [],
}
_model_preload_lock = threading.Lock()


def _model_catalog():
    return [
        {
            "key": "mineru",
            "name": "MinerU PDF-Extract-Kit",
            "required": True,
            "auto_download": False,
            "description": "PDF OCR and layout analysis models",
        },
        {
            "key": "paddleocr",
            "name": "PaddleOCR Multi-language Models",
            "required": False,
            "auto_download": True,
            "description": "Will be downloaded automatically on first run (~2GB)",
        },
        {
            "key": "sensevoice",
            "name": "SenseVoice Audio Recognition",
            "required": True,
            "auto_download": False,
            "description": "Multi-language speech recognition model",
        },
        {
            "key": "paraformer",
            "name": "Paraformer Speaker Diarization",
            "required": False,
            "auto_download": False,
            "description": "Speaker diarization and VAD model",
        },
        {
            "key": "yolo11",
            "name": "YOLO11x Watermark Detection",
            "required": False,
            "auto_download": False,
            "description": "Watermark detection model for document processing",
        },
        {
            "key": "lama",
            "name": "LaMa Watermark Inpainting",
            "required": False,
            "auto_download": True,
            "description": "Will be downloaded by simple_lama_inpainting on first use",
        },
    ]


def _append_model_preload_log(line: str):
    with _model_preload_lock:
        MODEL_PRELOAD_STATE["logs"].append(line.rstrip())
        # Keep only recent lines to avoid memory growth.
        if len(MODEL_PRELOAD_STATE["logs"]) > 300:
            MODEL_PRELOAD_STATE["logs"] = MODEL_PRELOAD_STATE["logs"][-300:]


def _run_model_preload(output_dir: str, selected_models: Optional[str], force: bool):
    backend_dir = Path(__file__).parent
    script_path = backend_dir / "download_models.py"
    command = [os.sys.executable, str(script_path), "--output", output_dir]
    if selected_models:
        command.extend(["--models", selected_models])
    if force:
        command.append("--force")

    _append_model_preload_log(f"Command: {' '.join(command)}")

    process = subprocess.Popen(
        command,
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        if process.stdout:
            for line in process.stdout:
                _append_model_preload_log(line)
        process.wait()
    except Exception as e:
        with _model_preload_lock:
            MODEL_PRELOAD_STATE["running"] = False
            MODEL_PRELOAD_STATE["finished_at"] = datetime.now().isoformat()
            MODEL_PRELOAD_STATE["success"] = False
            MODEL_PRELOAD_STATE["return_code"] = None
            MODEL_PRELOAD_STATE["error"] = str(e)
        return

    with _model_preload_lock:
        MODEL_PRELOAD_STATE["running"] = False
        MODEL_PRELOAD_STATE["finished_at"] = datetime.now().isoformat()
        MODEL_PRELOAD_STATE["success"] = process.returncode == 0
        MODEL_PRELOAD_STATE["return_code"] = process.returncode
        if process.returncode != 0:
            MODEL_PRELOAD_STATE["error"] = f"download_models.py exited with code {process.returncode}"


@app.get("/api/v1/models/status", tags=["系统信息"])
async def get_models_status():
    """
    模型就绪状态（用于前端展示与首次使用提示）

    检测各引擎默认缓存目录是否有模型文件，便于用户了解是否需等待首次下载。
    """
    home = Path.home()
    project_root = Path(__file__).parent.parent
    status = {}

    # MinerU：HuggingFace 或 ModelScope 缓存
    hf_hub = home / ".cache" / "huggingface" / "hub"
    ms_hub = home / ".cache" / "modelscope" / "hub"
    mineru_ready = _check_model_cache_dir(hf_hub) or _check_model_cache_dir(ms_hub)
    status["mineru"] = {
        "ready": mineru_ready,
        "name": "MinerU（PDF 解析）",
        "cache_hint": "~/.cache/huggingface/hub 或 ~/.cache/modelscope/hub",
        "message": "已缓存" if mineru_ready else "首次解析 PDF 时将自动下载",
    }

    # PaddleOCR-VL
    paddle_models = home / ".paddleocr" / "models"
    status["paddleocr"] = {
        "ready": _check_model_cache_dir(paddle_models),
        "name": "PaddleOCR-VL",
        "cache_hint": "~/.paddleocr/models",
        "message": "已缓存" if _check_model_cache_dir(paddle_models) else "首次使用该引擎时将自动下载（约 2GB）",
    }

    # SenseVoice：项目 models/sensevoice 或 ModelScope 缓存
    sensevoice_local = project_root / "models" / "sensevoice"
    ms_cache = home / ".cache" / "modelscope"
    sensevoice_ready = _check_model_cache_dir(sensevoice_local) or _check_model_cache_dir(ms_cache)
    status["sensevoice"] = {
        "ready": sensevoice_ready,
        "name": "SenseVoice（音频）",
        "cache_hint": "项目 models/sensevoice 或 ~/.cache/modelscope",
        "message": "已缓存" if sensevoice_ready else "首次提交音频任务时将自动下载",
    }

    any_ready = any(s["ready"] for s in status.values())
    any_missing = not all(s["ready"] for s in status.values())

    return {
        "success": True,
        "models": status,
        "catalog": _model_catalog(),
        "any_ready": any_ready,
        "any_missing": any_missing,
        "first_use_tip": "部分模型将在首次使用时自动下载，请保持网络畅通。预下载命令：cd backend && python download_models.py --output ../models-offline；或在项目根目录执行 python backend/download_models.py --output ./models-offline。",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/v1/models/preload/start", tags=["系统信息"])
async def start_model_preload(
    output_dir: Optional[str] = Query(None, description="模型输出目录"),
    models: Optional[str] = Query(None, description="逗号分隔模型列表，如 mineru,sensevoice"),
    force: bool = Query(False, description="是否强制重新下载"),
    current_user: User = Depends(require_permission(Permission.QUEUE_MANAGE)),
):
    """启动模型预下载任务（后台执行）。"""
    with _model_preload_lock:
        if MODEL_PRELOAD_STATE["running"]:
            raise HTTPException(status_code=409, detail="Model preload is already running")

        project_root = Path(__file__).parent.parent
        target_dir = output_dir or str((project_root / "models-offline").resolve())
        MODEL_PRELOAD_STATE["running"] = True
        MODEL_PRELOAD_STATE["started_at"] = datetime.now().isoformat()
        MODEL_PRELOAD_STATE["finished_at"] = None
        MODEL_PRELOAD_STATE["success"] = None
        MODEL_PRELOAD_STATE["return_code"] = None
        MODEL_PRELOAD_STATE["error"] = None
        MODEL_PRELOAD_STATE["output_dir"] = target_dir
        MODEL_PRELOAD_STATE["logs"] = [f"Started by {current_user.username}"]

    thread = threading.Thread(target=_run_model_preload, args=(target_dir, models, force), daemon=True)
    thread.start()

    return {
        "success": True,
        "message": "Model preload started",
        "output_dir": target_dir,
        "models": models,
        "force": force,
        "started_at": MODEL_PRELOAD_STATE["started_at"],
    }


@app.get("/api/v1/models/preload/status", tags=["系统信息"])
async def get_model_preload_status(current_user: User = Depends(get_current_active_user)):
    """获取模型预下载任务状态。"""
    with _model_preload_lock:
        return {
            "success": True,
            "running": MODEL_PRELOAD_STATE["running"],
            "started_at": MODEL_PRELOAD_STATE["started_at"],
            "finished_at": MODEL_PRELOAD_STATE["finished_at"],
            "success_flag": MODEL_PRELOAD_STATE["success"],
            "return_code": MODEL_PRELOAD_STATE["return_code"],
            "error": MODEL_PRELOAD_STATE["error"],
            "output_dir": MODEL_PRELOAD_STATE["output_dir"],
            "logs": MODEL_PRELOAD_STATE["logs"],
        }


@app.get("/api/v1/health", tags=["系统信息"])
async def health_check():
    """
    健康检查接口
    """
    try:
        # 检查数据库连接
        stats = db.get_queue_stats()

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "queue_stats": stats,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})


# ============================================================================
# 自定义文件服务（支持 URL 编码的中文路径）
# ============================================================================
from urllib.parse import unquote


@app.get("/v1/files/output/{file_path:path}", tags=["文件服务"])
async def serve_output_file(file_path: str):
    """
    提供输出文件的访问服务

    支持 URL 编码的中文路径
    注意：Nginx 代理会去掉 /api/ 前缀，所以这里不需要 /api/
    """
    try:
        logger.debug(f"📥 Received file request: {file_path}")
        # URL 解码
        decoded_path = unquote(file_path)
        logger.debug(f"📝 Decoded path: {decoded_path}")
        # 构建完整路径
        full_path = OUTPUT_DIR / decoded_path
        logger.debug(f"📂 Full path: {full_path}")

        # 安全检查：确保路径在 OUTPUT_DIR 内
        try:
            full_path = full_path.resolve()
            OUTPUT_DIR.resolve()
            if not str(full_path).startswith(str(OUTPUT_DIR.resolve())):
                raise HTTPException(status_code=403, detail="Access denied")
        except Exception:
            raise HTTPException(status_code=403, detail="Invalid path")

        # 检查文件是否存在
        if not full_path.exists():
            logger.warning(f"⚠️  File not found: {full_path}")
            raise HTTPException(status_code=404, detail="File not found")

        if not full_path.is_file():
            raise HTTPException(status_code=404, detail="Not a file")

        # 返回文件
        return FileResponse(path=str(full_path), media_type="application/octet-stream", filename=full_path.name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error serving file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


logger.info(f"📁 File service mounted: /v1/files/output -> {OUTPUT_DIR}")
logger.info("   Frontend can access images via: /api/v1/files/output/{task_id}/images/xxx.jpg (Nginx will strip /api/)")

if __name__ == "__main__":
    # 从环境变量读取端口，默认为18657
    api_port = int(os.getenv("API_PORT", "18657"))

    logger.info("🚀 Starting MinerU Tianshu API Server...")
    logger.info(f"📖 API Documentation: http://localhost:{api_port}/docs")

    uvicorn.run(app, host="0.0.0.0", port=api_port, log_level="info")
