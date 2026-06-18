"""主应用模块

构建 Kivy UI：顶部 Tab 切换 + 底部控制卡片。
管理模拟位置服务的启动/停止。
"""

from __future__ import annotations

from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem

from app.config_manager import (
    ConfigManager,
    MODE_COORD,
    MODE_ADDRESS,
    COORD_CHOICES,
)
from app.mock_location import MockLocationManager
from app.widgets.coord_tab import CoordTab
from app.widgets.address_tab import AddressTab


def _get_config_path() -> Path:
    """获取配置文件路径

    Android 上使用 App 内部存储，PC 上使用项目目录。
    """
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity
        files_dir = context.getFilesDir().getAbsolutePath()
        return Path(files_dir) / "config.json"
    except ImportError:
        # PC 调试：项目根目录
        return Path(__file__).resolve().parent.parent / "config.json"


class MainPanel(TabbedPanel):
    """主面板：Tab 切换容器"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config = ConfigManager()
        self._tabs: dict[int, TabbedPanelItem] = {}

        self._build_tabs()
        # 选中配置中的模式
        self._select_tab(self._config.config.mode)

    def _build_tabs(self) -> None:
        """构建两个 Tab：经纬度 / 地址"""
        tab_configs = [
            (MODE_COORD, "经纬度", CoordTab),
            (MODE_ADDRESS, "地址", AddressTab),
        ]
        for mode, title, tab_class in tab_configs:
            item = TabbedPanelItem(text=title)
            item.add_widget(tab_class())
            self._tabs[mode] = item
            self.add_widget(item)

    def _select_tab(self, mode: int) -> None:
        """选中指定模式的 Tab"""
        if mode in self._tabs:
            self.switch_to(self._tabs[mode])
        else:
            # 兼容旧配置（mode=1 已删除），回退到经纬度
            if MODE_COORD in self._tabs:
                self.switch_to(self._tabs[MODE_COORD])


class ControlCard(BoxLayout):
    """底部控制卡片：坐标系选择 + 坐标显示 + 开始/停止按钮"""

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=16, spacing=8, **kwargs)
        self._config = ConfigManager()
        self._mock = MockLocationManager()

        self._build_ui()
        self._update_coord_display()
        self._update_mock_status(False)

        # 监听配置变化
        self._config.add_listener(self._on_config_changed)
        self._mock.add_status_listener(self._on_mock_status_changed)

    def _build_ui(self) -> None:
        """构建界面"""
        # 坐标系选择行
        coord_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=40, spacing=8)
        coord_label = Label(
            text="坐标系:",
            size_hint_x=None,
            width=70,
            halign="right",
            valign="middle",
            color=(0.2, 0.2, 0.2, 1),
            font_size="14sp",
        )
        coord_label.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        coord_row.add_widget(coord_label)

        current_coord = self._config.config.coord_system
        self._coord_spinner = Spinner(
            text=current_coord,
            values=list(COORD_CHOICES),
            size_hint_x=1,
            font_size="14sp",
            background_color=(0.9, 0.9, 0.9, 1),
        )
        self._coord_spinner.bind(text=self._on_coord_system_changed)
        coord_row.add_widget(self._coord_spinner)
        self.add_widget(coord_row)

        # 坐标显示
        self._coord_label = Label(
            text="",
            size_hint_y=None,
            height=30,
            halign="left",
            valign="middle",
            color=(0.1, 0.1, 0.1, 1),
            font_size="15sp",
        )
        self.add_widget(self._coord_label)

        # 状态显示
        self._status_label = Label(
            text="模拟位置已停止",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=(0.4, 0.4, 0.4, 1),
            font_size="13sp",
        )
        self.add_widget(self._status_label)

        # 按钮行
        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=56, spacing=8)
        self._btn_start = Button(
            text="开始模拟",
            font_size="16sp",
            background_color=(0.1, 0.46, 0.82, 1),
        )
        self._btn_start.bind(on_press=self._on_start)
        btn_row.add_widget(self._btn_start)

        self._btn_stop = Button(
            text="停止模拟",
            font_size="16sp",
            background_color=(0.83, 0.18, 0.18, 1),
            disabled=True,
        )
        self._btn_stop.bind(on_press=self._on_stop)
        btn_row.add_widget(self._btn_stop)

        self.add_widget(btn_row)

    def _update_coord_display(self) -> None:
        """更新坐标显示"""
        cfg = self._config.config
        self._coord_label.text = (
            f"当前坐标：{cfg.latitude:.6f}, {cfg.longitude:.6f} [{cfg.coord_system}]"
        )

    def _update_mock_status(self, running: bool) -> None:
        """更新模拟状态"""
        if running:
            self._status_label.text = "模拟位置运行中"
            self._status_label.color = (1.0, 0.43, 0.0, 1)
            self._btn_start.disabled = True
            self._btn_stop.disabled = False
        else:
            self._status_label.text = "模拟位置已停止"
            self._status_label.color = (0.4, 0.4, 0.4, 1)
            self._btn_start.disabled = False
            self._btn_stop.disabled = True

    def _on_config_changed(self, _config) -> None:
        """配置变化回调"""
        self._update_coord_display()
        # 同步坐标系 Spinner（避免循环触发）
        if self._coord_spinner.text != _config.coord_system:
            self._coord_spinner.text = _config.coord_system

    def _on_coord_system_changed(self, _spinner, coord_system: str) -> None:
        """坐标系切换回调"""
        self._config.update(coord_system=coord_system)

    def _on_mock_status_changed(self, running: bool) -> None:
        """模拟状态变化回调（子线程）"""
        from kivy.clock import Clock
        Clock.schedule_once(lambda _dt: self._update_mock_status(running), 0)

    def _set_status(self, text: str, color: tuple = (0.83, 0.18, 0.18, 1)) -> None:
        """更新状态文本（主线程安全）"""
        self._status_label.text = text
        self._status_label.color = color

    def _on_start(self, _instance: Button) -> None:
        """开始模拟"""
        cfg = self._config.config

        # 1. 检查模拟位置权限（开发者选项中设置本应用为模拟位置应用）
        if not self._mock.is_mock_location_enabled():
            self._set_status("请先在开发者选项中设置本应用为模拟位置应用")
            return

        # 2. 检查系统位置服务是否开启（Android 模拟位置必须开启位置服务）
        if not self._mock.is_location_service_enabled():
            self._set_status("请先开启手机位置服务（下拉状态栏打开定位）")
            # 尝试引导用户跳转位置设置
            self._mock.open_location_settings()
            return

        # 3. 注入位置前，把配置坐标转换为 WGS-84（Android 系统期望 WGS-84）
        from app.coord_transform import convert_to_wgs84
        wgs_lng, wgs_lat = convert_to_wgs84(cfg.longitude, cfg.latitude, cfg.coord_system)

        success = self._mock.start(
            lat=wgs_lat,
            lng=wgs_lng,
            interval=cfg.update_interval,
        )
        if not success:
            self._set_status("启动失败，请检查权限设置或日志")
        else:
            self._set_status("模拟位置已启动", color=(0.2, 0.7, 0.3, 1))

    def _on_stop(self, _instance: Button) -> None:
        """停止模拟"""
        self._mock.stop()


class PositionSettingApp(App):
    """位置模拟主应用"""

    def build(self):
        """构建应用界面"""
        # 初始化配置
        config_path = _get_config_path()
        ConfigManager().init(config_path)

        # Android 端：请求运行时权限（P2）
        from app.mock_location import MockLocationManager
        MockLocationManager().request_runtime_permissions()

        # 根布局
        root = BoxLayout(orientation="vertical")

        # 顶部 Tab 面板
        self._panel = MainPanel(size_hint_y=0.7)
        root.add_widget(self._panel)

        # 底部控制卡片
        self._control = ControlCard(size_hint_y=0.3)
        root.add_widget(self._control)

        return root

    def on_pause(self) -> bool:
        """切到后台时返回 True，保持 app 运行（配合前台服务）"""
        return True

    def on_resume(self) -> None:
        """切回前台时检查模拟状态"""
        from app.mock_location import MockLocationManager
        mock = MockLocationManager()
        if mock.is_running and not mock.is_injecting_alive():
            # 注入线程已死，重启
            mock.stop()
