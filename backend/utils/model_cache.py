"""模型缓存路径统一管理。

把所有第三方库（ModelScope / HuggingFace）的模型缓存重定向到项目内
``<项目根>/models-offline/``，避免污染用户主目录（C 盘 ``~/.cache``）。

设计要点
--------
- 路径基于 ``__file__`` 动态解析，**不硬编码绝对路径**，整个项目可整体搬迁。
- 仅在 ``import mineru / paddleocr / funasr`` **之前**调用 ``configure_model_cache_env``
  才能生效（这些库在 import / 首次调用时读取缓存环境变量）。
- 使用 ``os.environ.setdefault``：若用户在 ``.env`` 显式设置了同名变量，则尊重用户值。
"""

from __future__ import annotations

import os
from pathlib import Path


def get_models_offline_root(project_root: Path | None = None) -> Path:
    """返回项目内 ``models-offline`` 的绝对路径。

    Args:
        project_root: 项目根目录。为 ``None`` 时基于本文件位置推断
            （``backend/utils/model_cache.py`` 上溯三级即项目根）。
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent.parent
    return Path(project_root) / "models-offline"


def configure_model_cache_env(project_root: Path | None = None) -> dict[str, str]:
    """把 ModelScope / HuggingFace 的缓存根重定向到项目内 ``models-offline``。

    必须在 ``import mineru`` / ``import funasr`` 等第三方库之前调用。
    会自动创建目标目录。

    Returns:
        ``{env_key: 实际路径}`` 映射，方便调用方记录日志或回显。
    """
    base = get_models_offline_root(project_root)
    mappings = {
        # ModelScope：根目录，其下自动生成 hub/
        "MODELSCOPE_CACHE": base / "modelscope",
        # HuggingFace：HF_HOME 是根，HUGGINGFACE_HUB_CACHE 是 hub 缓存
        "HF_HOME": base / "huggingface",
        "HUGGINGFACE_HUB_CACHE": base / "huggingface" / "hub",
    }
    applied: dict[str, str] = {}
    for key, path in mappings.items():
        Path(path).mkdir(parents=True, exist_ok=True)
        # setdefault：不覆盖用户在 .env 里显式设置的值
        applied[key] = os.environ.setdefault(key, str(path))
    return applied


def get_active_cache_dirs() -> dict[str, Path]:
    """返回当前生效的各引擎缓存目录（供模型状态展示使用）。

    优先读环境变量（反映 ``configure_model_cache_env`` 或用户自定义的实际效果），
    回退到项目内默认路径。
    """
    base = get_models_offline_root()
    return {
        # MinerU 主模型：ModelScope（当前默认源）或 HuggingFace
        "modelscope_hub": Path(os.environ.get("MODELSCOPE_CACHE", base / "modelscope")) / "hub",
        "hf_hub": Path(os.environ.get("HUGGINGFACE_HUB_CACHE", base / "huggingface" / "hub")),
        # PaddleOCR-VL：SDK 自管理，本次不迁移，保持用户主目录
        "paddleocr_models": Path.home() / ".paddleocr" / "models",
        # SenseVoice：项目内 models/sensevoice（保持原有约定）
        "sensevoice_local": base.parent / "models" / "sensevoice",
    }
