"""配置管理模块

负责 config.json 的读写，使用观察者模式通知配置变化。
配置文件位于 App 内部存储目录。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


# 选点模式常量
MODE_COORD = 2    # 经纬度输入
MODE_ADDRESS = 3  # 地址输入

# 坐标系常量
COORD_WGS84 = "wgs84"  # GPS 原始坐标（Google Maps、gps-coordinates.org）
COORD_GCJ02 = "gcj02"  # 火星坐标（高德地图、腾讯地图）
COORD_BD09 = "bd09"    # 百度坐标（百度地图）

# 可选坐标系列表（供 UI Spinner 使用）
COORD_CHOICES = (COORD_WGS84, COORD_GCJ02, COORD_BD09)


@dataclass
class AppConfig:
    """应用配置数据类"""

    # 选点模式：2=经纬度 3=地址
    mode: int = MODE_COORD
    # 纬度
    latitude: float = 39.908823
    # 经度
    longitude: float = 116.397470
    # 地址文本（模式3使用）
    address: str = ""
    # App 启动后是否自动开始模拟
    auto_start: bool = False
    # 位置注入间隔（秒）
    update_interval: float = 1.0
    # 高德 Web 服务 Key（地址搜索）
    amap_web_key: str = ""
    # 输出坐标系：wgs84 / gcj02 / bd09
    coord_system: str = COORD_GCJ02

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典构造配置，忽略未知字段"""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """转为字典"""
        return asdict(self)


class ConfigManager:
    """配置仓库

    单例模式，负责 config.json 的持久化和监听通知。
    修改配置后自动写入文件并通知所有监听者。
    """

    _instance: "ConfigManager | None" = None
    _config_path: Path | None = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._listeners: list[Callable[[AppConfig], None]] = []
            cls._instance._config: AppConfig = AppConfig()
        return cls._instance

    def init(self, config_path: Path | str) -> None:
        """初始化配置文件路径并加载"""
        self._config_path = Path(config_path)
        self._config = self._load()

    @property
    def config(self) -> AppConfig:
        """当前配置"""
        return self._config

    def _load(self) -> AppConfig:
        """从磁盘加载配置"""
        if self._config_path is None or not self._config_path.exists():
            return AppConfig()
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return AppConfig.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError):
            return AppConfig()

    def _save(self) -> None:
        """保存配置到磁盘"""
        if self._config_path is None:
            return
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def update(self, **kwargs) -> AppConfig:
        """更新配置字段并持久化，通知监听者"""
        current = self._config.to_dict()
        current.update(kwargs)
        self._config = AppConfig.from_dict(current)
        self._save()
        self._notify()
        return self._config

    def update_coordinate(self, lat: float, lng: float) -> None:
        """更新坐标"""
        self.update(latitude=lat, longitude=lng)

    def update_mode(self, mode: int) -> None:
        """更新模式"""
        self.update(mode=mode)

    def update_address(self, address: str) -> None:
        """更新地址"""
        self.update(address=address)

    def add_listener(self, callback: Callable[[AppConfig], None]) -> None:
        """添加配置变化监听者"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[AppConfig], None]) -> None:
        """移除配置变化监听者"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self) -> None:
        """通知所有监听者"""
        for callback in self._listeners:
            callback(self._config)
