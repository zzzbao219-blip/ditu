"""Position Setting 应用入口

运行方式：
    python main.py

PC 调试：仅显示 UI，模拟位置功能不可用。
Android 运行：完整功能。
"""

import os
import sys
import platform

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Kivy 环境变量（必须在导入 Kivy 之前设置）
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_WINDOW", "sdl2")
os.environ.setdefault("KIVY_TEXT", "sdl2")

# ---------- 中文字体配置（必须在导入 Kivy App 之前） ----------
_CHINESE_FONT_PATHS = {
    "Windows": [
        "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
    ],
    "Darwin": [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ],
    "Android": [
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/DroidSansFallback.ttf",
    ],
}

# 检测平台
_platform_name = platform.system()
try:
    from jnius import autoclass  # noqa: F401
    _platform_name = "Android"
except ImportError:
    pass

# 查找可用中文字体并注入 Kivy 配置
_font_name = "chinese"
_candidates = _CHINESE_FONT_PATHS.get(_platform_name, [])

from kivy.config import Config

for _font_path in _candidates:
    if os.path.isfile(_font_path):
        Config.set("kivy", "default_font", [_font_name, _font_path])
        break
# ---------------------------------------------------------------

from app.main_app import PositionSettingApp


def main() -> None:
    """应用入口"""
    app = PositionSettingApp()
    app.run()


if __name__ == "__main__":
    main()
