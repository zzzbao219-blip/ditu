"""模式2：经纬度输入 Tab

用户直接输入纬度和经度，带范围校验。
"""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

from app.config_manager import ConfigManager


class CoordTab(BoxLayout):
    """经纬度输入页面"""

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=20, spacing=12, **kwargs)
        self._config = ConfigManager()

        self._build_ui()
        self._restore_values()

    def _build_ui(self) -> None:
        """构建界面"""
        # 标题
        self.add_widget(
            Label(
                text="手动输入经纬度坐标",
                size_hint_y=None,
                height=40,
                halign="left",
                valign="middle",
                color=(0.1, 0.1, 0.1, 1),
                font_size="16sp",
            )
        )

        # 纬度输入
        self.add_widget(
            Label(
                text="纬度 (-90 ~ 90)",
                size_hint_y=None,
                height=30,
                halign="left",
                valign="middle",
                color=(0.3, 0.3, 0.3, 1),
                font_size="13sp",
            )
        )
        self._lat_input = TextInput(
            size_hint_y=None,
            height=48,
            font_size="16sp",
            multiline=False,
            input_filter="float",
        )
        self.add_widget(self._lat_input)

        # 经度输入
        self.add_widget(
            Label(
                text="经度 (-180 ~ 180)",
                size_hint_y=None,
                height=30,
                halign="left",
                valign="middle",
                color=(0.3, 0.3, 0.3, 1),
                font_size="13sp",
            )
        )
        self._lng_input = TextInput(
            size_hint_y=None,
            height=48,
            font_size="16sp",
            multiline=False,
            input_filter="float",
        )
        self.add_widget(self._lng_input)

        # 确定按钮
        btn_confirm = Button(
            text="确定",
            size_hint_y=None,
            height=56,
            font_size="16sp",
            background_color=(0.1, 0.46, 0.82, 1),
        )
        btn_confirm.bind(on_press=self._on_confirm)
        self.add_widget(btn_confirm)

        # 提示文本
        self._hint_label = Label(
            text="",
            size_hint_y=None,
            height=30,
            color=(0.8, 0.2, 0.2, 1),
            font_size="13sp",
        )
        self.add_widget(self._hint_label)

        # 常用坐标示例
        self.add_widget(
            Label(
                text="常用坐标示例：\n北京天安门  39.908823, 116.397470\n上海外滩    31.2397, 121.4905\n广州塔      23.1066, 113.3245",
                size_hint_y=None,
                height=100,
                halign="left",
                valign="top",
                color=(0.5, 0.5, 0.5, 1),
                font_size="12sp",
            )
        )

    def _restore_values(self) -> None:
        """恢复上次输入"""
        cfg = self._config.config
        self._lat_input.text = str(cfg.latitude)
        self._lng_input.text = str(cfg.longitude)

    def _on_confirm(self, _instance: Button) -> None:
        """确定按钮回调"""
        lat_str = self._lat_input.text.strip()
        lng_str = self._lng_input.text.strip()

        if not lat_str or not lng_str:
            self._hint_label.text = "请输入有效的经纬度"
            return

        try:
            lat = float(lat_str)
            lng = float(lng_str)

            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
                self._hint_label.text = "坐标超出范围"
                return

            self._config.update_coordinate(lat, lng)
            self._hint_label.text = "坐标已更新"
            self._hint_label.color = (0.2, 0.7, 0.3, 1)

        except ValueError:
            self._hint_label.text = "请输入有效数字"
