"""模拟位置核心模块

Android：通过前台服务（独立进程）注入模拟位置，避免后台被杀。
PC 调试环境下提供完整的模拟实现，附带 HTTP 验证服务。
"""

from __future__ import annotations

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Callable

try:
    from jnius import autoclass
    _ANDROID = True
except ImportError:
    _ANDROID = False


# p4a 自动生成的 Service 类名：org.<domain>.<package.name>.Service<ServiceName>
_PACKAGE_NAME = "org.example.positionsetting"
_SERVICE_CLASS = f"{_PACKAGE_NAME}.ServiceMockLocationService"

# 运行时权限请求码
_PERMISSION_REQUEST_CODE = 1001


class _VerifyHandler(BaseHTTPRequestHandler):
    """PC 端验证 HTTP 服务"""

    manager: "MockLocationManager | None" = None

    def log_message(self, *args) -> None:
        pass  # 静默日志

    def do_GET(self):
        if self.manager is None:
            return

        if self.path == "/" or self.path == "/status":
            from app.coord_transform import wgs84_to_gcj02, wgs84_to_bd09
            from app.config_manager import ConfigManager

            wgs_lng, wgs_lat = self.manager.current_coordinate
            gcj_lng, gcj_lat = wgs84_to_gcj02(wgs_lng, wgs_lat)
            bd_lng, bd_lat = wgs84_to_bd09(wgs_lng, wgs_lat)

            cfg = ConfigManager().config

            self._json({
                "running": self.manager.is_running,
                "uptime_seconds": self.manager.uptime_seconds,
                "coord_system": cfg.coord_system,
                "wgs84": {"latitude": round(wgs_lat, 8), "longitude": round(wgs_lng, 8)},
                "gcj02": {"latitude": round(gcj_lat, 8), "longitude": round(gcj_lng, 8)},
                "bd09": {"latitude": round(bd_lat, 8), "longitude": round(bd_lng, 8)},
            })
        elif self.path == "/location":
            wgs_lng, wgs_lat = self.manager.current_coordinate
            self._text(f"{wgs_lat},{wgs_lng}")
        else:
            self.send_error(404)

    def _json(self, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MockLocationManager:
    """模拟位置管理器（单例）

    Android：启动前台服务（独立进程）注入位置，避免后台被杀。
    PC：完整模拟运行流程 + HTTP 验证服务（端口 58080）。
    """

    _instance: "MockLocationManager | None" = None

    def __new__(cls) -> "MockLocationManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._is_running = False
        self._inject_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._status_listeners: list[Callable[[bool], None]] = []
        self._current_lat: float = 0.0
        self._current_lng: float = 0.0
        self._start_time: float = 0.0

        # PC 验证 HTTP 服务
        self._http_server: HTTPServer | None = None
        self._http_thread: threading.Thread | None = None

        if _ANDROID:
            self._setup_android()

    # ==================== Android 初始化 ====================

    def _setup_android(self) -> None:
        """初始化 Android 上下文"""
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self._context = PythonActivity.mActivity
            Context = autoclass("android.content.Context")
            self._location_manager = self._context.getSystemService(Context.LOCATION_SERVICE)
            self._app_ops_manager = self._context.getSystemService(Context.APP_OPS_SERVICE)
            self._build = autoclass("android.os.Build")
            self._api_level = self._build.VERSION.SDK_INT
            print(f"[Mock] Android API level: {self._api_level}")
        except Exception as e:
            print(f"[Mock] Android 初始化失败: {e}")

    # ==================== P2: 运行时权限请求 ====================

    def request_runtime_permissions(self) -> None:
        """请求运行时权限（Android 6+ 必须动态申请）

        包括：ACCESS_FINE_LOCATION、ACCESS_COARSE_LOCATION、POST_NOTIFICATIONS
        """
        if not _ANDROID:
            return
        try:
            # 优先用 androidx 的 ActivityCompat（兼容性更好）
            try:
                ActivityCompat = autoclass("androidx.core.app.ActivityCompat")
            except Exception:
                # 回退到原生 Activity.requestPermissions
                ActivityCompat = None

            Manifest = autoclass("android.Manifest$permission")
            permissions = [
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            ]
            # Android 13+ 需要请求通知权限
            if self._api_level >= 33:
                permissions.append(Manifest.permission.POST_NOTIFICATIONS)

            if ActivityCompat:
                ActivityCompat.requestPermissions(
                    self._context, permissions, _PERMISSION_REQUEST_CODE
                )
            else:
                self._context.requestPermissions(permissions, _PERMISSION_REQUEST_CODE)
            print(f"[Mock] 已请求权限: {permissions}")
        except Exception as e:
            print(f"[Mock] 请求权限失败: {e}")

    # ==================== P3: 位置服务检测 ====================

    def is_location_service_enabled(self) -> bool:
        """检查系统位置服务是否开启

        Android 模拟位置必须开启系统位置服务才能生效。
        """
        if not _ANDROID:
            return True
        try:
            LocationManager = autoclass("android.location.LocationManager")
            gps_ok = self._location_manager.isProviderEnabled(LocationManager.GPS_PROVIDER)
            net_ok = self._location_manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
            return gps_ok or net_ok
        except Exception as e:
            print(f"[Mock] 检查位置服务失败: {e}")
            return True  # 检查失败时不阻塞启动

    def open_location_settings(self) -> None:
        """跳转到系统位置设置页面"""
        if not _ANDROID:
            return
        try:
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            intent = Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._context.startActivity(intent)
        except Exception as e:
            print(f"[Mock] 跳转位置设置失败: {e}")

    # ==================== 模拟位置权限检测 ====================

    def is_mock_location_enabled(self) -> bool:
        """检查本应用是否被设为模拟位置应用（开发者选项）"""
        if not _ANDROID:
            return True
        try:
            AppOpsManager = autoclass("android.app.AppOpsManager")
            Process = autoclass("android.os.Process")
            # unsafeCheckOpNoThrow 在 API 29+ 标记为 deprecated，但仍可用
            mode = self._app_ops_manager.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_MOCK_LOCATION,
                Process.myUid(),
                self._context.getPackageName(),
            )
            return mode == AppOpsManager.MODE_ALLOWED
        except Exception as e:
            print(f"[Mock] 检查模拟位置权限失败: {e}")
            return False

    # ==================== PC 验证 HTTP 服务 ====================

    def _start_http_server(self) -> None:
        """启动 PC 端验证 HTTP 服务"""
        if _ANDROID or self._http_server:
            return

        _VerifyHandler.manager = self

        port = 58080
        for _attempt in range(10):
            try:
                self._http_server = HTTPServer(("127.0.0.1", port), _VerifyHandler)
                break
            except OSError:
                port += 1

        def _serve():
            if self._http_server:
                try:
                    self._http_server.serve_forever()
                except Exception:
                    pass

        self._http_thread = threading.Thread(target=_serve, daemon=True)
        self._http_thread.start()

        print(f"\n[模拟位置] 验证服务已启动 → http://127.0.0.1:{port}/")
        print(f"[模拟位置] 验证命令: curl http://127.0.0.1:{port}/")

    def _stop_http_server(self) -> None:
        """停止 HTTP 验证服务（后台线程，不阻塞 UI）"""
        server = self._http_server
        self._http_server = None
        self._http_thread = None

        if server:
            def _do_shutdown():
                try:
                    server.shutdown()
                except Exception:
                    pass
            threading.Thread(target=_do_shutdown, daemon=True).start()
            print("[模拟位置] 验证服务已停止")

    # ==================== P4: 前台服务（Android） ====================

    def _start_service(self) -> bool:
        """启动前台服务（独立进程注入位置）"""
        try:
            Intent = autoclass("android.content.Intent")
            ComponentName = autoclass("android.content.ComponentName")

            intent = Intent()
            intent.setComponent(ComponentName(_PACKAGE_NAME, _SERVICE_CLASS))

            # Android 8+ 必须用 startForegroundService
            if self._api_level >= 26:
                self._context.startForegroundService(intent)
            else:
                self._context.startService(intent)

            print(f"[Mock] 前台服务已启动: {_SERVICE_CLASS}")
            return True
        except Exception as e:
            print(f"[Mock] 启动前台服务失败: {e}")
            return False

    def _stop_service(self) -> None:
        """停止前台服务"""
        try:
            Intent = autoclass("android.content.Intent")
            ComponentName = autoclass("android.content.ComponentName")

            intent = Intent()
            intent.setComponent(ComponentName(_PACKAGE_NAME, _SERVICE_CLASS))
            self._context.stopService(intent)
            print("[Mock] 前台服务已停止")
        except Exception as e:
            print(f"[Mock] 停止前台服务失败: {e}")

    # ==================== 公共接口 ====================

    def start(self, lat: float, lng: float, interval: float = 1.0) -> bool:
        """开始模拟位置

        Android：启动前台服务，由服务进程读取 config.json 注入位置。
        PC：启动 HTTP 验证服务。
        """
        if self._is_running:
            self.stop()

        self._current_lat = lat
        self._current_lng = lng
        self._start_time = time.time()

        if _ANDROID:
            # Android：启动前台服务
            success = self._start_service()
            if success:
                self._is_running = True
                self._notify_status(True)
            return success

        # PC：启动注入循环 + HTTP 验证服务
        self._is_running = True
        self._stop_event.clear()
        self._inject_thread = threading.Thread(
            target=self._inject_loop,
            args=(lat, lng, interval),
            daemon=True,
        )
        self._inject_thread.start()
        self._start_http_server()
        self._notify_status(True)
        return True

    def _inject_loop(self, lat: float, lng: float, interval: float) -> None:
        """PC 端注入循环（仅用于保持状态，不实际注入）"""
        while not self._stop_event.is_set():
            self._stop_event.wait(interval)

    def stop(self) -> None:
        """停止模拟位置"""
        if not self._is_running:
            return

        if _ANDROID:
            self._stop_service()
        else:
            self._stop_http_server()
            self._stop_event.set()
            self._inject_thread = None

        self._is_running = False
        self._start_time = 0.0
        self._notify_status(False)

    def is_injecting_alive(self) -> bool:
        """检查注入是否仍在运行（用于 on_resume 检测）"""
        if _ANDROID:
            return self._is_running
        return self._inject_thread is not None and self._inject_thread.is_alive()

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def current_coordinate(self) -> tuple[float, float]:
        return (self._current_lat, self._current_lng)

    @property
    def uptime_seconds(self) -> int:
        """模拟位置已运行的秒数"""
        if not self._is_running or not self._start_time:
            return 0
        return int(time.time() - self._start_time)

    def add_status_listener(self, callback: Callable[[bool], None]) -> None:
        """添加模拟状态变化监听者"""
        self._status_listeners.append(callback)

    def remove_status_listener(self, callback: Callable[[bool], None]) -> None:
        """移除模拟状态变化监听者"""
        if callback in self._status_listeners:
            self._status_listeners.remove(callback)

    def _notify_status(self, running: bool) -> None:
        for callback in self._status_listeners:
            callback(running)
