"""
MinerU Tianshu - SQLite Task Database Manager
天枢任务数据库管理器

负责任务的持久化存储、状态管理和原子性操作

架构说明 (Hybrid Queue):
    - SQLite: 任务元数据存储、历史记录、结果管理
    - Redis (可选): 高性能任务队列、优先级调度
    - 当 Redis 可用时，队列操作由 Redis 处理
    - 当 Redis 不可用时，自动回退到 SQLite
"""

import sqlite3
import json
import uuid
from contextlib import contextmanager
from typing import Optional, List, Dict
from pathlib import Path
from loguru import logger

# 导入 Redis 队列（可选）
try:
    from redis_queue import get_redis_queue

    REDIS_QUEUE_AVAILABLE = True
except ImportError:
    REDIS_QUEUE_AVAILABLE = False

    def get_redis_queue():
        return None


class TaskDB:
    """任务数据库管理类"""

    def __init__(self, db_path=None):
        # 导入所需模块
        import os
        from pathlib import Path

        # 优先使用传入的路径，其次使用环境变量，最后使用默认路径
        if db_path is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent
            default_db = project_root / "data" / "db" / "mineru_tianshu.db"
            db_path = os.getenv("DATABASE_PATH", str(default_db))
            # Windows 本地：.env 中 Docker 路径 /app/... 会解析为 E:\app\...，目录往往不存在
            if os.name == "nt" and db_path.replace("\\", "/").strip().startswith("/app/"):
                db_path = str(default_db)
            # 确保父目录存在
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            # 确保使用绝对路径
            db_path = str(Path(db_path).resolve())
        else:
            # 确保使用绝对路径
            db_path = str(Path(db_path).resolve())

        # 确保 db_path 是绝对路径字符串
        self.db_path = str(Path(db_path).resolve())
        self._init_db()

    def _get_conn(self):
        """获取数据库连接（每次创建新连接，避免 pickle 问题）

        并发安全说明：
            - 使用 check_same_thread=False 是安全的，因为：
              1. 每次调用都创建新连接，不跨线程共享
              2. 连接使用完立即关闭（在 get_cursor 上下文管理器中）
              3. 不使用连接池，避免线程间共享同一连接
            - timeout=30.0 防止死锁，如果锁等待超过30秒会抛出异常
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_cursor(self):
        """上下文管理器，自动提交和错误处理"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()  # 关闭连接

    def _init_db(self):
        """初始化数据库表"""
        with self.get_cursor() as cursor:
            # 创建表（如果不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    backend TEXT DEFAULT 'pipeline',
                    options TEXT,
                    result_path TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    worker_id TEXT,
                    retry_count INTEGER DEFAULT 0
                )
            """)

            # 创建基础索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON tasks(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_worker_id ON tasks(worker_id)")

            # 迁移：添加 parent_task_id 等字段（如果不存在）
            try:
                cursor.execute("SELECT parent_task_id FROM tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，添加新字段
                logger.info("📊 Migrating database schema: adding parent-child task support")
                cursor.execute("ALTER TABLE tasks ADD COLUMN parent_task_id TEXT")
                cursor.execute("ALTER TABLE tasks ADD COLUMN is_parent INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE tasks ADD COLUMN child_count INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE tasks ADD COLUMN child_completed INTEGER DEFAULT 0")
                logger.info("✅ Parent-child task fields added")

            # 创建主子任务索引（字段存在后才创建）
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_task ON tasks(parent_task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_parent ON tasks(is_parent)")

            # 迁移：添加 user_id 字段（如果不存在）
            try:
                cursor.execute("SELECT user_id FROM tasks LIMIT 1")
            except sqlite3.OperationalError:
                logger.info("📊 Migrating database schema: adding user_id field")
                cursor.execute("ALTER TABLE tasks ADD COLUMN user_id TEXT")
                logger.info("✅ user_id field added")

    def create_task(
        self,
        file_name: str,
        file_path: str,
        backend: str = "pipeline",
        options: dict = None,
        priority: int = 0,
        user_id: str = None,
    ) -> str:
        """
        创建新任务

        Args:
            file_name: 文件名
            file_path: 文件路径
            backend: 处理后端 (pipeline/vlm-transformers/vlm-vllm-engine)
            options: 处理选项 (dict)
            priority: 优先级，数字越大越优先
            user_id: 用户ID (可选,用于权限控制)

        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (task_id, file_name, file_path, backend, options, priority, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (task_id, file_name, file_path, backend, json.dumps(options or {}), priority, user_id),
            )

        # 入队到 Redis（如果可用）
        self._enqueue_to_redis(
            task_id,
            priority,
            {
                "file_name": file_name,
                "backend": backend,
            },
        )

        return task_id

    def _enqueue_to_redis(self, task_id: str, priority: int, task_data: dict = None) -> bool:
        """
        将任务加入 Redis 队列

        Args:
            task_id: 任务ID
            priority: 优先级
            task_data: 可选的任务快照数据

        Returns:
            bool: 是否成功入队到 Redis
        """
        if not REDIS_QUEUE_AVAILABLE:
            return False

        redis_queue = get_redis_queue()
        if redis_queue:
            try:
                return redis_queue.enqueue(task_id, priority, task_data)
            except Exception as e:
                logger.warning(f"⚠️  Failed to enqueue to Redis, SQLite fallback active: {e}")
        return False

    def get_next_task(self, worker_id: str, max_retries: int = 3) -> Optional[Dict]:
        """
        获取下一个待处理任务（原子操作，防止并发冲突）

        Args:
            worker_id: Worker ID
            max_retries: 当任务被其他 worker 抢走时的最大重试次数（默认3次）

        Returns:
            task: 任务字典，如果没有任务返回 None

        并发安全说明（SQLite 模式）：
            1. 使用 BEGIN IMMEDIATE 立即获取写锁
            2. UPDATE 时检查 status = 'pending' 防止重复拉取
            3. 检查 rowcount 确保更新成功
            4. 如果任务被抢走，立即重试而不是返回 None（避免不必要的等待）

        Redis 模式：
            1. 使用 BZPOPMIN 原子获取最高优先级任务
            2. 任务自动移入 processing set
            3. 从 SQLite 获取完整任务数据
        """
        from loguru import logger

        # 尝试使用 Redis 队列（如果可用）
        task = self._get_next_task_redis(worker_id)
        if task is not None:
            return task

        # Redis 不可用或出错，回退到 SQLite
        for attempt in range(max_retries):
            try:
                with self.get_cursor() as cursor:
                    # 使用事务确保原子性
                    cursor.execute("BEGIN IMMEDIATE")

                    # 按优先级和创建时间获取任务
                    cursor.execute("""
                        SELECT * FROM tasks
                        WHERE status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                    """)

                    task = cursor.fetchone()
                    if task:
                        task_id = task["task_id"]
                        # 立即标记为 processing，并确保状态仍是 pending
                        cursor.execute(
                            """
                            UPDATE tasks
                            SET status = 'processing',
                                started_at = CURRENT_TIMESTAMP,
                                worker_id = ?
                            WHERE task_id = ? AND status = 'pending'
                        """,
                            (worker_id, task_id),
                        )

                        # 检查是否更新成功（防止被其他 worker 抢走）
                        if cursor.rowcount == 0:
                            # 任务被其他进程抢走了，立即重试
                            # 因为队列中可能还有其他待处理任务
                            if attempt == 0:  # 只在第一次尝试时记录日志
                                logger.debug(f"Task {task_id} was grabbed by another worker, retrying...")
                            continue

                        return dict(task)
                    else:
                        # 队列中没有待处理任务，返回 None
                        # 只在第一次尝试时记录调试信息（避免日志过多）
                        if attempt == 0:
                            # 检查是否有 pending 任务（用于诊断）
                            cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'pending'")
                            pending_count = cursor.fetchone()["count"]
                            if pending_count > 0:
                                logger.warning(
                                    f"⚠️  Found {pending_count} pending tasks but failed to grab one "
                                    f"(attempt {attempt + 1}/{max_retries})"
                                )
                        return None

            except Exception as e:
                logger.error(f"❌ Error in get_next_task (attempt {attempt + 1}/{max_retries}): {e}")
                logger.exception(e)
                if attempt == max_retries - 1:
                    # 最后一次尝试失败，返回 None
                    return None
                # 等待一小段时间后重试
                import time

                time.sleep(0.1)

        # 重试次数用尽，仍未获取到任务（高并发场景）
        logger.warning(f"⚠️  Failed to get task after {max_retries} attempts")
        return None

    def _get_next_task_redis(self, worker_id: str) -> Optional[Dict]:
        """
        从 Redis 队列获取下一个任务

        Args:
            worker_id: Worker ID

        Returns:
            task: 任务字典，如果 Redis 不可用或无任务返回 None
        """
        if not REDIS_QUEUE_AVAILABLE:
            return None

        redis_queue = get_redis_queue()
        if not redis_queue:
            return None

        try:
            # 从 Redis 获取任务 ID（阻塞式，1秒超时）
            task_id = redis_queue.dequeue(worker_id, timeout=1.0)
            if not task_id:
                return None

            # 从 SQLite 获取完整任务数据
            with self.get_cursor() as cursor:
                cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
                task = cursor.fetchone()

                if not task:
                    # 任务在 Redis 中但不在 SQLite 中（异常情况）
                    logger.error(f"❌ Task {task_id} found in Redis but not in SQLite")
                    redis_queue.fail(task_id, worker_id, requeue=False)
                    return None

                # 更新 SQLite 中的任务状态
                cursor.execute(
                    """
                    UPDATE tasks
                    SET status = 'processing',
                        started_at = CURRENT_TIMESTAMP,
                        worker_id = ?
                    WHERE task_id = ? AND status = 'pending'
                    """,
                    (worker_id, task_id),
                )

                if cursor.rowcount == 0:
                    # 任务状态已经改变（可能被取消等）
                    logger.warning(f"⚠️  Task {task_id} status changed, skipping")
                    redis_queue.fail(task_id, worker_id, requeue=False)
                    return None

                logger.info(f"📤 [Redis] Task {task_id} claimed by worker {worker_id}")
                return dict(task)

        except Exception as e:
            logger.error(f"❌ Redis dequeue failed, falling back to SQLite: {e}")
            return None

    def update_task_status(
        self, task_id: str, status: str, result_path: str = None, error_message: str = None, worker_id: str = None
    ):
        """
        更新任务状态（使用预定义 SQL 模板，防止 SQL 注入）

        Args:
            task_id: 任务ID
            status: 新状态 (pending/processing/completed/failed/cancelled)
            result_path: 结果路径（可选）
            error_message: 错误信息（可选）
            worker_id: Worker ID（可选，用于并发检查）

        Returns:
            bool: 更新是否成功

        并发安全说明：
            1. 更新为 completed/failed 时会检查状态是 processing
            2. 如果提供 worker_id，会检查任务是否属于该 worker
            3. 返回 False 表示任务被其他进程修改了

        安全说明：
            使用预定义的 SQL 模板，完全避免 SQL 注入风险
        """
        with self.get_cursor() as cursor:
            success = False

            # 根据不同状态使用预定义的 SQL 模板
            if status == "completed":
                # 完成状态：更新状态、完成时间和结果路径
                if worker_id:
                    # 带 worker_id 验证
                    sql = """
                        UPDATE tasks
                        SET status = ?,
                            completed_at = CURRENT_TIMESTAMP,
                            result_path = ?
                        WHERE task_id = ?
                        AND status = 'processing'
                        AND worker_id = ?
                    """
                    cursor.execute(sql, (status, result_path, task_id, worker_id))
                else:
                    # 不验证 worker_id
                    sql = """
                        UPDATE tasks
                        SET status = ?,
                            completed_at = CURRENT_TIMESTAMP,
                            result_path = ?
                        WHERE task_id = ?
                        AND status = 'processing'
                    """
                    cursor.execute(sql, (status, result_path, task_id))

                success = cursor.rowcount > 0

            elif status == "failed":
                # 失败状态：更新状态、完成时间和错误信息
                if worker_id:
                    # 带 worker_id 验证
                    sql = """
                        UPDATE tasks
                        SET status = ?,
                            completed_at = CURRENT_TIMESTAMP,
                            error_message = ?
                        WHERE task_id = ?
                        AND status = 'processing'
                        AND worker_id = ?
                    """
                    cursor.execute(sql, (status, error_message, task_id, worker_id))
                else:
                    # 不验证 worker_id
                    sql = """
                        UPDATE tasks
                        SET status = ?,
                            completed_at = CURRENT_TIMESTAMP,
                            error_message = ?
                        WHERE task_id = ?
                        AND status = 'processing'
                    """
                    cursor.execute(sql, (status, error_message, task_id))

                success = cursor.rowcount > 0

            elif status == "cancelled":
                # 取消状态：直接更新状态
                sql = """
                    UPDATE tasks
                    SET status = ?,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                """
                cursor.execute(sql, (status, task_id))
                success = cursor.rowcount > 0

            elif status == "pending":
                # 重置为待处理状态
                sql = """
                    UPDATE tasks
                    SET status = ?,
                        worker_id = NULL,
                        started_at = NULL
                    WHERE task_id = ?
                """
                cursor.execute(sql, (status, task_id))
                success = cursor.rowcount > 0

            else:
                # 其他状态（如 processing）：简单更新状态
                sql = """
                    UPDATE tasks
                    SET status = ?
                    WHERE task_id = ?
                """
                cursor.execute(sql, (status, task_id))
                success = cursor.rowcount > 0

            # 调试日志（仅在失败时）
            if not success and status in ["completed", "failed"]:
                from loguru import logger

                logger.debug(f"Status update failed: task_id={task_id}, status={status}, worker_id={worker_id}")

            # 通知 Redis 任务完成/失败（清理 processing set）
            if success and status in ["completed", "failed"]:
                self._notify_redis_task_done(task_id, worker_id or "", status)

            return success

    def _notify_redis_task_done(self, task_id: str, worker_id: str, status: str):
        """
        通知 Redis 任务已完成/失败

        从 processing set 中移除任务

        Args:
            task_id: 任务ID
            worker_id: Worker ID
            status: 最终状态 (completed/failed)
        """
        if not REDIS_QUEUE_AVAILABLE:
            return

        redis_queue = get_redis_queue()
        if redis_queue:
            try:
                if status == "completed":
                    redis_queue.complete(task_id, worker_id)
                else:
                    redis_queue.fail(task_id, worker_id, requeue=False)
            except Exception as e:
                # Redis 清理失败不影响任务完成
                logger.warning(f"⚠️  Failed to notify Redis about task {task_id}: {e}")

    def get_task(self, task_id: str) -> Optional[Dict]:
        """
        查询任务详情

        Args:
            task_id: 任务ID

        Returns:
            task: 任务字典，如果不存在返回 None
        """
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            task = cursor.fetchone()
            return dict(task) if task else None

    def get_queue_stats(self) -> Dict[str, int]:
        """
        获取队列统计信息

        Returns:
            stats: 各状态的任务数量，包含 Redis 队列信息（如果可用）
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            """)
            stats = {row["status"]: row["count"] for row in cursor.fetchall()}

        # 添加 Redis 队列统计（如果可用）
        if REDIS_QUEUE_AVAILABLE:
            redis_queue = get_redis_queue()
            if redis_queue:
                try:
                    redis_stats = redis_queue.get_stats()
                    stats["_redis_enabled"] = True
                    stats["_redis_pending"] = redis_stats.get("pending", 0)
                    stats["_redis_processing"] = redis_stats.get("processing", 0)
                except Exception as e:
                    stats["_redis_enabled"] = False
                    stats["_redis_error"] = str(e)
            else:
                stats["_redis_enabled"] = False
        else:
            stats["_redis_enabled"] = False

        return stats

    def get_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """
        根据状态获取任务列表

        Args:
            status: 任务状态
            limit: 返回数量限制

        Returns:
            tasks: 任务列表
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (status, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_task_records(self, days: int = 30):
        """
        清理旧任务（同时删除所有相关文件和数据库记录）

        Args:
            days: 删除多少天前的任务

        Returns:
            int: 删除的任务记录数

        清理内容：
            - 上传的原始文件（file_path）
            - 结果文件夹及其所有内容（result_path，包括生成的文件和中间文件）
            - 数据库记录

        注意：
            - 操作不可恢复
            - 建议设置合理的保留期（如 7-30 天）
            - 由定时任务自动执行，也可通过管理接口手动触发
        """
        from pathlib import Path
        import shutil

        with self.get_cursor() as cursor:
            # 先查询要删除的任务及其文件路径（包括上传文件和结果文件）
            cursor.execute(
                """
                SELECT task_id, file_path, result_path FROM tasks
                WHERE completed_at < datetime('now', '-' || ? || ' days')
                AND status IN ('completed', 'failed')
            """,
                (days,),
            )

            old_tasks = cursor.fetchall()

            # 删除所有相关文件
            for task in old_tasks:
                task_id = task["task_id"]

                # 1. 删除上传的原始文件
                if task["file_path"]:
                    file_path = Path(task["file_path"])
                    if file_path.exists() and file_path.is_file():
                        try:
                            file_path.unlink()
                            logger.debug(f"Deleted upload file for task {task_id}: {file_path.name}")
                        except Exception as e:
                            logger.warning(f"Failed to delete upload file for task {task_id}: {e}")

                # 2. 删除结果文件夹（包含所有生成的文件和中间文件）
                if task["result_path"]:
                    result_path = Path(task["result_path"])
                    if result_path.exists() and result_path.is_dir():
                        try:
                            shutil.rmtree(result_path)
                            logger.debug(f"Deleted result directory for task {task_id}: {result_path.name}")
                        except Exception as e:
                            logger.warning(f"Failed to delete result files for task {task_id}: {e}")

            # 删除数据库记录
            cursor.execute(
                """
                DELETE FROM tasks
                WHERE completed_at < datetime('now', '-' || ? || ' days')
                AND status IN ('completed', 'failed')
            """,
                (days,),
            )

            deleted_count = cursor.rowcount
            return deleted_count

    def reset_stale_tasks(self, timeout_minutes: int = 60):
        """
        重置超时的 processing 任务为 pending

        Args:
            timeout_minutes: 超时时间（分钟）
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE tasks
                SET status = 'pending',
                    worker_id = NULL,
                    retry_count = retry_count + 1
                WHERE status = 'processing'
                AND started_at < datetime('now', '-' || ? || ' minutes')
            """,
                (timeout_minutes,),
            )
            reset_count = cursor.rowcount
            return reset_count

    # ============================================================================
    # 主子任务支持 (Parent-Child Task Support)
    # ============================================================================

    def create_parent_task(
        self,
        file_name: str,
        file_path: str,
        backend: str = "pipeline",
        options: dict = None,
        priority: int = 0,
        user_id: str = None,
    ) -> str:
        """
        创建主任务（用于大文件拆分）

        Args:
            file_name: 原始文件名
            file_path: 原始文件路径
            backend: 处理后端
            options: 处理选项
            priority: 优先级
            user_id: 用户ID

        Returns:
            task_id: 主任务ID
        """
        task_id = str(uuid.uuid4())
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (
                    task_id, file_name, file_path, backend, options,
                    status, priority, user_id, is_parent, child_count
                ) VALUES (?, ?, ?, ?, ?, 'processing', ?, ?, 1, 0)
            """,
                (task_id, file_name, file_path, backend, json.dumps(options or {}), priority, user_id),
            )
        logger.info(f"📋 Created parent task: {task_id}")
        return task_id

    def convert_to_parent_task(self, task_id: str, child_count: int = 0):
        """
        将普通任务转换为父任务

        Args:
            task_id: 任务ID
            child_count: 子任务数量
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE tasks
                SET is_parent = 1, child_count = ?, status = 'processing'
                WHERE task_id = ?
                """,
                (child_count, task_id),
            )
        logger.info(f"🔄 Converted task {task_id} to parent task with {child_count} children")

    def create_child_task(
        self,
        parent_task_id: str,
        file_name: str,
        file_path: str,
        backend: str = "pipeline",
        options: dict = None,
        priority: int = 0,
        user_id: str = None,
    ) -> str:
        """
        创建子任务

        Args:
            parent_task_id: 父任务ID
            file_name: 分片文件名
            file_path: 分片文件路径
            backend: 处理后端
            options: 处理选项（包含 chunk_info）
            priority: 优先级（继承父任务）
            user_id: 用户ID（继承父任务）

        Returns:
            task_id: 子任务ID
        """
        task_id = str(uuid.uuid4())
        with self.get_cursor() as cursor:
            # 创建子任务
            cursor.execute(
                """
                INSERT INTO tasks (
                    task_id, parent_task_id, file_name, file_path,
                    backend, options, status, priority, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
                (
                    task_id,
                    parent_task_id,
                    file_name,
                    file_path,
                    backend,
                    json.dumps(options or {}),
                    priority,
                    user_id,
                ),
            )

            # 更新父任务的子任务计数
            cursor.execute(
                """
                UPDATE tasks
                SET child_count = child_count + 1
                WHERE task_id = ?
            """,
                (parent_task_id,),
            )

        logger.debug(f"📄 Created child task: {task_id} (parent: {parent_task_id})")
        return task_id

    def on_child_task_completed(self, child_task_id: str) -> Optional[str]:
        """
        子任务完成回调

        当子任务完成时调用，更新父任务的完成计数
        如果所有子任务都完成，返回父任务ID用于触发合并

        Args:
            child_task_id: 子任务ID

        Returns:
            parent_task_id: 如果所有子任务完成，返回父任务ID；否则返回 None
        """
        with self.get_cursor() as cursor:
            # 获取父任务ID
            cursor.execute(
                """
                SELECT parent_task_id FROM tasks WHERE task_id = ?
            """,
                (child_task_id,),
            )
            row = cursor.fetchone()

            if not row or not row["parent_task_id"]:
                return None  # 不是子任务

            parent_task_id = row["parent_task_id"]

            # 更新父任务的完成计数
            cursor.execute(
                """
                UPDATE tasks
                SET child_completed = child_completed + 1
                WHERE task_id = ?
            """,
                (parent_task_id,),
            )

            # 检查是否所有子任务都完成了
            cursor.execute(
                """
                SELECT child_count, child_completed, file_name
                FROM tasks WHERE task_id = ?
            """,
                (parent_task_id,),
            )
            parent = cursor.fetchone()

            if parent and parent["child_completed"] >= parent["child_count"]:
                # 所有子任务完成
                logger.info(
                    f"🎉 All subtasks completed for parent task {parent_task_id} "
                    f"({parent['child_completed']}/{parent['child_count']}) - {parent['file_name']}"
                )
                return parent_task_id

            if parent:
                logger.info(
                    f"⏳ Subtask progress: {parent['child_completed']}/{parent['child_count']} "
                    f"for parent task {parent_task_id}"
                )

        return None

    def on_child_task_failed(self, child_task_id: str, error_message: str):
        """
        子任务失败回调

        当子任务失败时，标记父任务为失败状态

        Args:
            child_task_id: 子任务ID
            error_message: 错误信息
        """
        with self.get_cursor() as cursor:
            # 获取父任务ID
            cursor.execute(
                """
                SELECT parent_task_id FROM tasks WHERE task_id = ?
            """,
                (child_task_id,),
            )
            row = cursor.fetchone()

            if not row or not row["parent_task_id"]:
                return  # 不是子任务

            parent_task_id = row["parent_task_id"]

            # 标记父任务为失败
            cursor.execute(
                """
                UPDATE tasks
                SET status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    error_message = ?
                WHERE task_id = ?
                AND status = 'processing'
            """,
                (f"Subtask {child_task_id} failed: {error_message}", parent_task_id),
            )

            if cursor.rowcount > 0:
                logger.error(f"❌ Parent task {parent_task_id} marked as failed due to subtask failure")

    def get_task_with_children(self, task_id: str) -> Optional[Dict]:
        """
        获取任务及其所有子任务

        Args:
            task_id: 任务ID

        Returns:
            task: 包含 children 字段的任务字典
        """
        with self.get_cursor() as cursor:
            # 获取主任务
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            parent_row = cursor.fetchone()

            if not parent_row:
                return None

            parent = dict(parent_row)

            # 如果是主任务，获取所有子任务
            if parent.get("is_parent"):
                cursor.execute(
                    """
                    SELECT * FROM tasks
                    WHERE parent_task_id = ?
                    ORDER BY created_at
                """,
                    (task_id,),
                )
                children = [dict(row) for row in cursor.fetchall()]
                parent["children"] = children
            else:
                parent["children"] = []

            return parent

    def get_child_tasks(self, parent_task_id: str) -> List[Dict]:
        """
        获取父任务的所有子任务

        Args:
            parent_task_id: 父任务ID

        Returns:
            children: 子任务列表
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM tasks
                WHERE parent_task_id = ?
                ORDER BY created_at
            """,
                (parent_task_id,),
            )
            return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    # 测试代码
    db = TaskDB("test_tianshu.db")

    # 创建测试任务
    task_id = db.create_task(
        file_name="test.pdf",
        file_path="/tmp/test.pdf",
        backend="pipeline",
        options={"lang": "ch", "formula_enable": True},
        priority=1,
    )
    print(f"Created task: {task_id}")

    # 查询任务
    task = db.get_task(task_id)
    print(f"Task details: {task}")

    # 获取统计
    stats = db.get_queue_stats()
    print(f"Queue stats: {stats}")

    # 清理测试数据库
    Path("test_tianshu.db").unlink(missing_ok=True)
    print("Test completed!")
