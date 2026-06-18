"""模式3：地址搜索 Tab

输入地址关键词，调用高德 Web API 实时搜索建议，
点击建议项获取坐标。
"""

from __future__ import annotations

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from app.address_search import AddressSearcher, AddressSuggestion
from app.config_manager import ConfigManager
from app.coord_transform import convert_from_gcj02


class AddressTab(BoxLayout):
    """地址搜索页面"""

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=20, spacing=12, **kwargs)
        self._config = ConfigManager()
        self._searcher = AddressSearcher(self._config.config.amap_web_key)
        self._suggestions: list[AddressSuggestion] = []

        self._build_ui()
        self._restore_address()

    def _build_ui(self) -> None:
        """构建界面"""
        # 标题
        self.add_widget(
            Label(
                text="输入地址搜索位置",
                size_hint_y=None,
                height=40,
                halign="left",
                valign="middle",
                color=(0.1, 0.1, 0.1, 1),
                font_size="16sp",
            )
        )

        # 搜索框
        self._search_input = TextInput(
            size_hint_y=None,
            height=48,
            font_size="15sp",
            multiline=False,
            hint_text="输入地址关键词",
        )
        self._search_input.bind(text=self._on_text_changed)
        self.add_widget(self._search_input)

        # 状态提示
        self._status_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            halign="left",
            valign="middle",
            color=(0.5, 0.5, 0.5, 1),
            font_size="12sp",
        )
        self.add_widget(self._status_label)

        # 建议列表（ScrollView）
        scroll = ScrollView(size_hint_y=1)
        self._list_container = BoxLayout(orientation="vertical", size_hint_y=None, spacing=4)
        self._list_container.bind(minimum_height=self._list_container.setter("height"))
        scroll.add_widget(self._list_container)
        self.add_widget(scroll)

    def _restore_address(self) -> None:
        """恢复上次地址"""
        addr = self._config.config.address
        if addr:
            self._search_input.text = addr

    def _on_text_changed(self, _instance: TextInput, value: str) -> None:
        """输入框文本变化"""
        keyword = value.strip()
        if len(keyword) < 2:
            self._suggestions = []
            self._refresh_list()
            return

        self._status_label.text = "搜索中..."
        # 异步搜索，回调在子线程，需调度到主线程更新 UI
        self._searcher.search_suggestions(keyword, self._on_search_result)

    def _on_search_result(self, suggestions: list[AddressSuggestion]) -> None:
        """搜索结果回调（子线程）"""
        # 调度到 Kivy 主线程
        Clock.schedule_once(lambda _dt: self._update_suggestions(suggestions), 0)

    def _update_suggestions(self, suggestions: list[AddressSuggestion]) -> None:
        """更新建议列表（主线程）"""
        self._suggestions = suggestions
        self._status_label.text = f"找到 {len(suggestions)} 条结果"
        self._refresh_list()

    def _refresh_list(self) -> None:
        """刷新建议列表 UI"""
        self._list_container.clear_widgets()

        for suggestion in self._suggestions:
            item = Button(
                text=f"[b]{suggestion.name}[/b]\n{suggestion.address}",
                size_hint_y=None,
                height=64,
                markup=True,
                halign="left",
                valign="middle",
                font_size="13sp",
                background_color=(0.95, 0.95, 0.95, 1),
                color=(0.1, 0.1, 0.1, 1),
            )
            item.bind(on_press=lambda _btn, s=suggestion: self._on_suggestion_click(s))
            self._list_container.add_widget(item)

    def _on_suggestion_click(self, suggestion: AddressSuggestion) -> None:
        """点击建议项"""
        if suggestion.latitude and suggestion.longitude:
            self._apply_coordinate(suggestion.latitude, suggestion.longitude, suggestion.name)
        else:
            # 没有坐标，使用地理编码
            self._status_label.text = "正在获取坐标..."
            self._searcher.geocode(
                suggestion.name,
                callback=self._on_geocode_success,
                error_callback=self._on_geocode_error,
            )

    def _apply_coordinate(self, gcj_lat: float, gcj_lng: float, name: str) -> None:
        """应用坐标：GCJ-02 → 配置的目标坐标系"""
        target = self._config.config.coord_system
        lng, lat = convert_from_gcj02(gcj_lng, gcj_lat, target)
        self._config.update_coordinate(lat, lng)
        self._config.update_address(name)
        self._status_label.text = f"已定位到：{name} [{target}]"
        self._status_label.color = (0.2, 0.7, 0.3, 1)

    def _on_geocode_success(self, lat: float, lng: float, address: str) -> None:
        """地理编码成功（子线程，GCJ-02 坐标）"""
        Clock.schedule_once(lambda _dt: self._apply_coordinate(lat, lng, address), 0)

    def _on_geocode_error(self, msg: str) -> None:
        """地理编码失败（子线程）"""
        Clock.schedule_once(lambda _dt: self._do_geocode_error(msg), 0)

    def _do_geocode_error(self, msg: str) -> None:
        """主线程更新错误"""
        self._status_label.text = msg
        self._status_label.color = (0.8, 0.2, 0.2, 1)
