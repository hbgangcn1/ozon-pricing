import importlib.util
import sys
from pathlib import Path
from typing import Any

_app_module: Any = None


def get_app_module():
    """懒加载 app.py，避免测试重复导入耗时的 Streamlit 页面。"""
    global _app_module
    if _app_module is not None:
        return _app_module

    project_root = Path(__file__).resolve().parents[1]
    app_path = project_root / "app_main.py"
    spec = importlib.util.spec_from_file_location(
        "logistics_app_under_test", app_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 app.py 模块")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("logistics_app_under_test", module)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    _app_module = module
    return module

