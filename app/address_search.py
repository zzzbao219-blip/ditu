"""高德 Web API 地址搜索模块

通过高德 Web 服务 API 实现地址搜索建议和地理编码。
使用独立线程发起请求，避免阻塞 Kivy 主线程。
返回 GCJ-02 坐标（高德原生坐标系），由调用方按需转换。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

import requests

# 高德 Web API 端点
_INPUTTIPS_URL = "https://restapi.amap.com/v3/assistant/inputtips"
_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"


@dataclass
class AddressSuggestion:
    """地址搜索建议项"""

    name: str           # 地点名称
    address: str        # 详细地址
    latitude: float     # 纬度（GCJ-02）
    longitude: float    # 经度（GCJ-02）
    poi_id: str = ""    # POI ID


class AddressSearcher:
    """地址搜索器

    异步调用高德 Web API，通过回调返回结果。
    返回 GCJ-02 坐标，调用方负责按需转换。
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session = requests.Session()
        self._session.timeout = (3, 5)

    def search_suggestions(
        self,
        keyword: str,
        callback: Callable[[list[AddressSuggestion]], None],
        city: str = "",
    ) -> None:
        if not keyword.strip():
            callback([])
            return

        def _worker() -> None:
            try:
                resp = self._session.get(
                    _INPUTTIPS_URL,
                    params={
                        "key": self._api_key,
                        "keywords": keyword,
                        "city": city,
                        "citylimit": "false",
                        "datatype": "all",
                    },
                    timeout=(3, 5),
                )
                suggestions = self._parse_suggestions(resp.json())
                callback(suggestions)
            except (requests.RequestException, ValueError):
                callback([])

        threading.Thread(target=_worker, daemon=True).start()

    def _parse_suggestions(self, data: dict) -> list[AddressSuggestion]:
        if data.get("status") != "1":
            return []

        tips = data.get("tips", [])
        result: list[AddressSuggestion] = []
        for tip in tips:
            name = tip.get("name", "")
            if not name:
                continue

            location = tip.get("location", "")
            lat, lng = 0.0, 0.0
            if location and "," in location:
                parts = location.split(",")
                if len(parts) == 2:
                    try:
                        # 高德返回 "lng,lat" (GCJ-02)
                        lng = float(parts[0])
                        lat = float(parts[1])
                    except ValueError:
                        continue

            result.append(
                AddressSuggestion(
                    name=name,
                    address=tip.get("district", ""),
                    latitude=lat,
                    longitude=lng,
                    poi_id=tip.get("id", ""),
                )
            )
        return result

    def geocode(
        self,
        address: str,
        callback: Callable[[float, float, str], None],
        error_callback: Callable[[str], None] | None = None,
    ) -> None:
        if not address.strip():
            if error_callback:
                error_callback("地址不能为空")
            return

        def _worker() -> None:
            try:
                resp = self._session.get(
                    _GEOCODE_URL,
                    params={
                        "key": self._api_key,
                        "address": address,
                    },
                    timeout=(3, 5),
                )
                data = resp.json()
                geocodes = data.get("geocodes", [])
                if data.get("status") == "1" and geocodes:
                    geo = geocodes[0]
                    location = geo.get("location", "")
                    if "," in location:
                        parts = location.split(",")
                        # 高德返回 "lng,lat" (GCJ-02)
                        lng = float(parts[0])
                        lat = float(parts[1])
                        callback(lat, lng, geo.get("formatted_address", address))
                        return
                if error_callback:
                    error_callback("无法获取该地址的坐标")
            except (requests.RequestException, ValueError):
                if error_callback:
                    error_callback("网络请求失败")

        threading.Thread(target=_worker, daemon=True).start()
