"""前台服务入口（Android 独立进程）

由 p4a 生成的 ServiceMockLocationService 调用，运行在独立进程。
职责：
1. 启动前台通知（保活，避免后台被杀）
2. 读取 config.json 获取目标坐标
3. 通过 LocationManager 持续注入模拟位置（P6: 补全 Location 字段）

通信方式：主 app 通过 config.json 传递坐标，通过 startService/stopService 控制。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from jnius import autoclass


# ==================== 主入口 ====================

def main() -> None:
    """服务主入口（由 p4a Service.onStartCommand 调用）"""
    print("[Service] 模拟位置服务启动")

    try:
        PythonService = autoclass("org.kivy.android.PythonService")
        service = PythonService.mService
        context = service.getApplicationContext()
    except Exception as e:
        print(f"[Service] 获取 Service 上下文失败: {e}")
        return

    # 1. 启动前台通知（保活）
    _start_foreground(service, context)

    # 2. 初始化 Android API
    try:
        Context = autoclass("android.content.Context")
        LocationManager = autoclass("android.location.LocationManager")
        Location = autoclass("android.location.Location")
        Criteria = autoclass("android.location.Criteria")
        SystemClock = autoclass("android.os.SystemClock")
        Build = autoclass("android.os.Build")
        api_level = Build.VERSION.SDK_INT

        lm = context.getSystemService(Context.LOCATION_SERVICE)
        gps_provider = LocationManager.GPS_PROVIDER
        network_provider = LocationManager.NETWORK_PROVIDER
    except Exception as e:
        print(f"[Service] 初始化 Android API 失败: {e}")
        return

    # 3. 注册 test provider
    _register_provider(lm, Criteria, gps_provider)
    _register_provider(lm, Criteria, network_provider)

    # 4. 配置文件路径
    config_path = Path(context.getFilesDir().getAbsolutePath()) / "config.json"
    print(f"[Service] 配置文件: {config_path}")

    # 5. 注入循环
    print("[Service] 开始注入位置循环")
    while True:
        try:
            cfg = _read_config(config_path)
            if not cfg:
                time.sleep(1.0)
                continue

            lat = cfg.get("latitude", 0.0)
            lng = cfg.get("longitude", 0.0)
            interval = cfg.get("update_interval", 1.0)

            _inject_location(lm, Location, SystemClock, api_level, gps_provider, lat, lng)
            _inject_location(lm, Location, SystemClock, api_level, network_provider, lat, lng)
        except Exception as e:
            print(f"[Service] 注入循环异常: {e}")

        time.sleep(max(0.5, interval))


# ==================== 前台通知 ====================

def _start_foreground(service, context) -> None:
    """启动前台通知（Android 8+ 必需，Android 14+ 需指定 location 类型）"""
    try:
        Context = autoclass("android.content.Context")
        Notification = autoclass("android.app.Notification")
        NotificationChannel = autoclass("android.app.NotificationChannel")
        NotificationManager = autoclass("android.app.NotificationManager")
        PendingIntent = autoclass("android.app.PendingIntent")
        Intent = autoclass("android.content.Intent")
        ServiceInfo = autoclass("android.content.pm.ServiceInfo")
        R = autoclass("android.R")

        channel_id = "mock_location_service"
        channel_name = "模拟位置服务"

        # 创建通知渠道（Android 8+）
        nm = context.getSystemService(Context.NOTIFICATION_SERVICE)
        channel = NotificationChannel(
            channel_id,
            channel_name,
            NotificationManager.IMPORTANCE_LOW,
        )
        nm.createNotificationChannel(channel)

        # 构建通知
        builder = Notification.Builder(context, channel_id)
        builder.setContentTitle("位置模拟运行中")
        builder.setContentText("正在注入模拟位置")
        builder.setSmallIcon(R.drawable.ic_menu_mylocation)
        builder.setOngoing(True)

        # 点击通知回到 app
        intent = Intent(context, autoclass("org.kivy.android.PythonActivity"))
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        pi = PendingIntent.getActivity(
            context, 0, intent, PendingIntent.FLAG_IMMUTABLE
        )
        builder.setContentIntent(pi)

        notification = builder.build()

        # 启动前台（Android 14+ 必须指定 foregroundServiceType）
        # 使用 startForeground(int, Notification, int) 重载（API 29+）
        service.startForeground(
            1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
        )
        print("[Service] 前台通知已启动")
    except Exception as e:
        print(f"[Service] 启动前台通知失败: {e}")
        # 降级：用无类型 startForeground
        try:
            service.startForeground(1, notification)
        except Exception:
            pass


# ==================== Provider 注册 ====================

def _register_provider(lm, Criteria, provider_name: str) -> None:
    """注册 test provider"""
    try:
        criteria = Criteria()
        criteria.setPowerRequirement(Criteria.POWER_LOW)
        criteria.setAccuracy(Criteria.ACCURACY_FINE)
        lm.addTestProvider(
            provider_name,
            False, False, False, False, True, True, True,
            Criteria.POWER_LOW,
            Criteria.ACCURACY_FINE,
        )
        lm.setTestProviderEnabled(provider_name, True)
        print(f"[Service] 注册 provider 成功: {provider_name}")
    except Exception as e:
        print(f"[Service] 注册 provider 失败 {provider_name}: {e}")


# ==================== 位置注入（P6: 补全字段） ====================

def _inject_location(lm, Location, SystemClock, api_level: int,
                     provider: str, lat: float, lng: float) -> None:
    """注入位置

    P6: 补全 Location 对象的所有字段，对抗反检测 app 的真实性校验。
    """
    try:
        location = Location(provider)
        location.setLatitude(lat)
        location.setLongitude(lng)
        location.setAltitude(0.0)
        location.setAccuracy(1.0)
        location.setBearing(0.0)
        location.setSpeed(0.0)
        location.setTime(int(time.time() * 1000))
        location.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos())

        # API 26+ 字段（对抗反检测）
        if api_level >= 26:
            try:
                location.setVerticalAccuracyMeters(1.0)
                location.setBearingAccuracyDegrees(1.0)
                location.setSpeedAccuracyMetersPerSecond(0.5)
            except Exception as e:
                print(f"[Service] 设置精度字段失败: {e}")

        lm.setTestProviderLocation(provider, location)
    except Exception as e:
        print(f"[Service] 注入位置失败 {provider}: {e}")


# ==================== 配置读取 ====================

def _read_config(config_path: Path) -> dict:
    """读取配置文件"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[Service] 读取配置失败: {e}")
        return {}


if __name__ == "__main__":
    main()
