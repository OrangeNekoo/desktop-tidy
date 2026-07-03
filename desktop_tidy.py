"""
桌面整理大师 (Desktop Tidy Master)
搞怪向桌面整理工具 — 把所有桌面图标藏到窗口下面。
"""
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
from ctypes import wintypes
import random
import math

# ── 国际化 ──
TEXTS = {
    "zh": {
        "window_title": "桌面整理大师",
        "idle_label": "点击按钮开始整理",
        "start_btn": "开始整理",
        "progress_1": "准备开始整理",
        "progress_2": "正在分析桌面",
        "progress_3": "调用homo银梦大模型",
        "progress_4": "整理完成",
        "done_label": "整理完成！桌面已清理，共计 {count} 个图标已被收容。",
        "auto_arrange_warn": (
            '请先关闭桌面的"自动排列图标"和"将图标与网格对齐"后再使用本软件。\n\n'
            '方法：桌面空白处右键 → 查看 → 取消勾选"自动排列图标"和"将图标与网格对齐"'
        ),
        "no_desktop": "无法访问桌面图标，程序即将退出。",
        "menu_lang": "语言",
        "menu_lang_zh": "简体中文",
        "menu_lang_en": "English",
    },
    "en": {
        "window_title": "Desktop Tidy Master",
        "idle_label": "Click the button to start tidying",
        "start_btn": "Start Tidying",
        "progress_1": "Preparing to tidy...",
        "progress_2": "Analyzing desktop...",
        "progress_3": "Invoking Homo Silver Dream LLM...",
        "progress_4": "Tidying complete!",
        "done_label": "Tidying complete! {count} icons have been contained.",
        "auto_arrange_warn": (
            'Please disable "Auto arrange icons" and "Align icons to grid" before using this software.\n\n'
            'How: Right-click desktop → View → Uncheck "Auto arrange icons" and "Align icons to grid"'
        ),
        "no_desktop": "Cannot access desktop icons. The program will exit.",
        "menu_lang": "Language",
        "menu_lang_zh": "简体中文",
        "menu_lang_en": "English",
    },
}

RAINBOW_COLORS = [
    "#FF0000", "#FF7F00", "#FFFF00", "#00FF00",
    "#00FFFF", "#0000FF", "#8B00FF",
]

def detect_system_language() -> str:
    """检测系统语言，中文返回 'zh'，否则返回 'en'"""
    try:
        # 使用 Win32 API 替代已弃用的 locale.getdefaultlocale()
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        # 0x0804 = 简体中文, 0x0404 = 繁体中文
        if lang_id in (0x0804, 0x0404):
            return "zh"
    except Exception:
        pass
    return "en"

# ── Windows API 常量 ──
LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMPOSITION = LVM_FIRST + 16
LVM_SETITEMPOSITION = LVM_FIRST + 15
LVM_GETITEMSPACING = LVM_FIRST + 51

# ── IconManager ──
class IconManager:
    """通过 ctypes 操作 Windows 桌面图标"""

    def __init__(self):
        self._listview: int | None = None

    def find_listview(self) -> int | None:
        """三层回退查找桌面 SysListView32 句柄"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        def class_name(hwnd: int) -> str:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf, 256)
            return buf.value

        def find_child(hwnd: int, cls: str) -> int | None:
            result = user32.FindWindowExW(hwnd, 0, cls, None)
            return result if result else None

        # 方案 1: Progman → SHELLDLL_DefView → SysListView32
        progman = user32.FindWindowW("Progman", None)
        if progman:
            defview = find_child(progman, "SHELLDLL_DefView")
            if defview:
                lv = find_child(defview, "SysListView32")
                if lv:
                    self._listview = lv
                    return lv

        # 方案 2: 枚举 WorkerW → SHELLDLL_DefView → SysListView32
        result = None
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_workerw(hwnd, _):
            nonlocal result
            if class_name(hwnd) == "WorkerW":
                defview = find_child(hwnd, "SHELLDLL_DefView")
                if defview:
                    lv = find_child(defview, "SysListView32")
                    if lv:
                        result = lv
                        return False
            return True

        user32.EnumWindows(WNDENUMPROC(enum_workerw), 0)
        if result:
            self._listview = result
            return result

        # 方案 3: Shell_TrayWnd → 递归找 SysListView32 (Win11 24H2+)
        shell = user32.FindWindowW("Shell_TrayWnd", None)
        if shell:
            result = self._find_listview_recursive(shell, class_name, user32)
        if result:
            self._listview = result
        return result

    def _find_listview_recursive(self, hwnd: int, class_name, user32) -> int | None:
        """递归搜索子树中的 SysListView32"""
        if class_name(hwnd) == "SysListView32":
            return hwnd
        child = user32.FindWindowExW(hwnd, 0, None, None)
        while child:
            found = self._find_listview_recursive(child, class_name, user32)
            if found:
                return found
            child = user32.FindWindowExW(hwnd, child, None, None)
        return None

    @property
    def listview(self) -> int:
        if self._listview is None:
            raise RuntimeError("Desktop listview not found")
        return self._listview

    def get_icon_count(self) -> int:
        return ctypes.windll.user32.SendMessageW(self.listview, LVM_GETITEMCOUNT, 0, 0)

    def get_icon_positions(self) -> list[tuple[int, int]]:
        """返回所有图标当前位置 (x, y) 列表"""
        count = self.get_icon_count()
        positions = []
        for i in range(count):
            pt = wintypes.POINT()
            ctypes.windll.user32.SendMessageW(
                self.listview, LVM_GETITEMPOSITION, i,
                ctypes.addressof(pt)
            )
            positions.append((pt.x, pt.y))
        return positions

    def set_icon_position(self, idx: int, x: int, y: int):
        """设置单个图标位置"""
        lparam = (y << 16) | (x & 0xFFFF)
        ctypes.windll.user32.SendMessageW(
            self.listview, LVM_SETITEMPOSITION, idx, lparam
        )

    def get_icon_spacing(self) -> tuple[int, int]:
        """获取图标间距 (宽, 高)，含图标+标签的实际占用"""
        spacing = ctypes.windll.user32.SendMessageW(
            self.listview, LVM_GETITEMSPACING, 1, 0
        )
        w = spacing & 0xFFFF
        h = (spacing >> 16) & 0xFFFF
        # 有些系统返回 0，回退到默认值
        if w == 0 or h == 0:
            return (75, 75)
        return (w, h)

    def arrange_grid(self, origin_x: int, origin_y: int) -> tuple[int, int]:
        """
        将所有图标排列成最小包围矩形网格，以 (origin_x, origin_y) 为左上角原点。
        返回 (grid_width, grid_height)。
        """
        count = self.get_icon_count()
        if count == 0:
            return (0, 0)

        spacing_w, spacing_h = self.get_icon_spacing()
        cols = math.ceil(math.sqrt(count))
        for i in range(count):
            col = i % cols
            row = i // cols
            x = origin_x + col * spacing_w
            y = origin_y + row * spacing_h
            self.set_icon_position(i, x, y)

        rows = math.ceil(count / cols)
        grid_w = cols * spacing_w
        grid_h = rows * spacing_h
        return (grid_w, grid_h)
