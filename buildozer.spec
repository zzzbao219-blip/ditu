[app]

# 应用信息
title = Position Setting
package.name = positionsetting
package.domain = org.example

# 源码配置
source.dir = .
source.include_exts = py,json,png,jpg,kv,ttf

# 版本
version = 1.0

# 依赖
requirements = python3,kivy,pyjnius,requests

# Android 配置
# 权限说明：
#   ACCESS_MOCK_LOCATION      - 注入模拟位置（核心）
#   ACCESS_FINE_LOCATION      - 运行时权限，Android 6+ 必须动态申请
#   ACCESS_COARSE_LOCATION    - 同上
#   FOREGROUND_SERVICE        - Android 9+ 前台服务
#   FOREGROUND_SERVICE_LOCATION - Android 14+ 前台位置服务类型
#   POST_NOTIFICATIONS        - Android 13+ 前台服务通知
#   INTERNET                  - 高德地址搜索
#   ACCESS_NETWORK_STATE      - 网络状态
android.permissions = ACCESS_MOCK_LOCATION,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,POST_NOTIFICATIONS,INTERNET,ACCESS_NETWORK_STATE
android.api = 34
android.minapi = 31
android.archs = arm64-v8a,armeabi-v7a

# 前台服务：保持后台位置注入持续运行
# 格式：services = ServiceDisplayName:path/to/service_entry.py
# p4a 会自动生成 org.example.positionsetting.ServiceMockLocationService Java 类
services = MockLocationService:app/mock_location_service.py

# p4a 配置
p4a.branch = develop
android.accept_sdk_license = True

# 构建配置
fullscreen = 0
orientation = portrait

# 日志
log_level = 2

[buildozer]

log_level = 2
warn_on_root = 1
