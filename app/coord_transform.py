"""坐标系转换模块

中国常用坐标系：
- WGS-84：GPS 原始坐标，国际标准（Google Maps、gps-coordinates.org）
- GCJ-02：火星坐标，国测局标准（高德地图、腾讯地图、谷歌中国）
- BD-09：百度坐标（百度地图）

高德 API 返回 GCJ-02，百度 API 返回 BD-09。
"""

from __future__ import annotations

import math

_PI = math.pi
_A = 6378245.0  # 长半轴
_EE = 0.00669342162296594323  # 偏心率平方
_X_PI = _PI * 3000.0 / 180.0


def _out_of_china(lng: float, lat: float) -> bool:
    """判断坐标是否在中国境外（境外无偏移）"""
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * _PI) + 20.0 * math.sin(2.0 * x * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * _PI) + 40.0 * math.sin(y / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * _PI) + 320.0 * math.sin(y * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * _PI) + 20.0 * math.sin(2.0 * x * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * _PI) + 40.0 * math.sin(x / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * _PI) + 300.0 * math.sin(x / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """GCJ-02 → WGS-84"""
    if _out_of_china(lng, lat):
        return lng, lat
    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * _PI
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * _PI)
    d_lng = (d_lng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * _PI)
    return lng - d_lng, lat - d_lat


def wgs84_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    """WGS-84 → GCJ-02"""
    if _out_of_china(lng, lat):
        return lng, lat
    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * _PI
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * _PI)
    d_lng = (d_lng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * _PI)
    return lng + d_lng, lat + d_lat


def gcj02_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    """GCJ-02 → BD-09"""
    if _out_of_china(lng, lat):
        return lng, lat
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * _X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * _X_PI)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lng, bd_lat


def bd09_to_gcj02(bd_lng: float, bd_lat: float) -> tuple[float, float]:
    """BD-09 → GCJ-02"""
    if _out_of_china(bd_lng, bd_lat):
        return bd_lng, bd_lat
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def wgs84_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    """WGS-84 → BD-09"""
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)


def bd09_to_wgs84(bd_lng: float, bd_lat: float) -> tuple[float, float]:
    """BD-09 → WGS-84"""
    gcj_lng, gcj_lat = bd09_to_gcj02(bd_lng, bd_lat)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def convert_from_gcj02(
    lng: float, lat: float, target: str
) -> tuple[float, float]:
    """从 GCJ-02 转换到目标坐标系

    Args:
        lng, lat: GCJ-02 坐标
        target: "wgs84" / "gcj02" / "bd09"

    Returns:
        目标坐标系下的 (lng, lat)
    """
    if target == "wgs84":
        return gcj02_to_wgs84(lng, lat)
    if target == "bd09":
        return gcj02_to_bd09(lng, lat)
    return lng, lat  # gcj02 原样返回


def convert_to_wgs84(
    lng: float, lat: float, source: str
) -> tuple[float, float]:
    """从源坐标系转换到 WGS-84（用于模拟位置注入）

    Args:
        lng, lat: 源坐标
        source: "wgs84" / "gcj02" / "bd09"

    Returns:
        WGS-84 坐标 (lng, lat)
    """
    if source == "gcj02":
        return gcj02_to_wgs84(lng, lat)
    if source == "bd09":
        return bd09_to_wgs84(lng, lat)
    return lng, lat  # wgs84 原样返回
