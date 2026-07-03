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
import winreg
# 确保 DPI 感知，获取虚拟屏幕坐标而非逻辑坐标
ctypes.windll.user32.SetProcessDPIAware()

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

        # 方案 3: Progman 子树递归搜索 (Win11 24H2+ 图标在 DesktopWindowXamlSource 下)
        if progman:
            result = self._find_listview_recursive(progman, class_name, user32)
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
        lparam = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
        ctypes.windll.user32.SendMessageW(
            self.listview, LVM_SETITEMPOSITION, idx, lparam
        )

    def get_icon_spacing(self) -> tuple[int, int]:
        """获取图标间距 (宽, 高)，含图标+标签的实际占用"""
        spacing = ctypes.windll.user32.SendMessageW(
            self.listview, LVM_GETITEMSPACING, 0, 0  # 0 = 大图标模式
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
            try:
                self.set_icon_position(i, x, y)
            except Exception:
                pass  # 单个图标移动失败不中断整体排列
        rows = math.ceil(count / cols)
        grid_w = cols * spacing_w
        grid_h = rows * spacing_h
        return (grid_w, grid_h)


    def redraw(self):
        """强制桌面重绘图标"""
        user32 = ctypes.windll.user32
        user32.InvalidateRect(self.listview, None, True)
        user32.UpdateWindow(self.listview)
# ── WindowController ──
class WindowController:
    """管理窗口置顶、反最小化、拖动完成后图标的跟随"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self._icon_mgr = None  # IconManager 引用，enable_drag_follow 时设置
        self._debounce_id: str | None = None
        self._topmost_timer: str | None = None
        self._border_x = 0   # 窗口左边框宽度
        self._border_y = 0   # 标题栏+上边框高度
        self._border_r = 0   # 右边框宽度
        self._border_b = 0   # 下边框高度
        self._measure_borders()

    def _measure_borders(self):
        """测量窗口边框和标题栏尺寸（窗口 realize 后调用）"""
        self.root.update_idletasks()
        hwnd = int(self.root.frame(), 16)
        user32 = ctypes.windll.user32

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))

        client_rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client_rect))

        self._border_x = pt.x - rect.left
        self._border_y = pt.y - rect.top
        self._border_r = (rect.right - rect.left) - client_rect.right - self._border_x
        self._border_b = (rect.bottom - rect.top) - client_rect.bottom - self._border_y

    def pin_top(self):
        """置顶窗口并定时刷新"""
        self.root.wm_attributes('-topmost', True)
        self.root.lift()
        self._topmost_timer = self.root.after(500, self._refresh_topmost)

    def _refresh_topmost(self):
        self.root.wm_attributes('-topmost', True)
        self.root.lift()
        self._topmost_timer = self.root.after(500, self._refresh_topmost)

    def unpin_top(self):
        """取消置顶"""
        if self._topmost_timer:
            self.root.after_cancel(self._topmost_timer)
            self._topmost_timer = None

    def block_minimize(self):
        """阻止最小化"""
        self.root.bind('<Unmap>', self._on_unmap)

    def _on_unmap(self, event):
        if event.widget is self.root and self.root.state() == 'iconic':
            self.root.after(1, self.root.deiconify)
            self.root.after(2, self.root.lift)
            # 恢复后重新绑定 Configure（最大化/最小化可能导致绑定丢失）
            if self._icon_mgr is not None:
                self.root.after(50, lambda: self.root.bind('<Configure>', self._on_configure))


    def _get_window_pos(self) -> tuple[int, int]:
        """通过 Win32 API 获取窗口实际屏幕坐标（比 winfo_x/y 更准确）"""
        hwnd = int(self.root.frame(), 16)
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top)

    def cancel_debounce(self):
        """取消防抖定时器（供 DesktopTidyApp 在 resize 前调用）"""
        if self._debounce_id:
            self.root.after_cancel(self._debounce_id)
            self._debounce_id = None
    def enable_drag_follow(self, icon_mgr):
        """启用拖动完成后图标跟随，icon_mgr 为 IconManager 实例"""
        self._icon_mgr = icon_mgr
        self.root.bind('<Configure>', self._on_configure)
        # 最大化/最小化恢复后重新绑定 Configure
        self.root.bind('<Map>', lambda e: self.root.bind('<Configure>', self._on_configure))
    def _on_configure(self, event):
        if self._icon_mgr is None:
            return
        if self._debounce_id:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(500, self._on_drag_end)

    def _on_drag_end(self):
        """拖动停止后触发：将图标排列到窗口客户区下方并强制重绘"""
        if self._icon_mgr is None:
            return
        wx, wy = self._get_window_pos()
        x = wx + self._border_x + self.MARGIN
        y = wy + self._border_y + self.MARGIN
        self._icon_mgr.arrange_grid(x, y)
        self._icon_mgr.redraw()


    # 安全边距：防止边框测量误差导致图标从窗口边缘漏出
    MARGIN = 8
    def resize_to_cover(self, grid_w: int, grid_h: int):
        """调整窗口大小以覆盖图标网格（含边框+安全边距），保持左上角不变"""
        wx, wy = self._get_window_pos()
        total_w = grid_w + self._border_x + self._border_r + self.MARGIN * 2
        total_h = grid_h + self._border_y + self._border_b + self.MARGIN * 2
        self.root.geometry(f'{total_w}x{total_h}+{wx}+{wy}')

# ── GUI 主应用 ──
class DesktopTidyApp:
    """主应用：状态机 + tkinter GUI"""

    STATE_IDLE = "idle"
    STATE_PROGRESS = "progress"
    STATE_DONE = "done"

    def __init__(self):
        self.state = self.STATE_IDLE
        self.lang = detect_system_language()
        self._progress_segments = 4
        self._progress_interval = 0
        self._progress_idx = 0
        self._progress_value = 0.0
        self._progress_after_id: str | None = None
        self._icon_count = 0

        # 窗口
        self.root = tk.Tk()
        self.root.title(self.t("window_title"))
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 窗口控制器
        self.win_ctrl = WindowController(self.root)

        # 图标管理器
        self.icon_mgr = IconManager()

        # 构建 UI
        self._build_menu()
        self._build_idle_view()
        self._center_window(500, 250)

    def t(self, key: str, **fmt) -> str:
        """获取当前语言的文本，缺失 key 时回退到 key 本身"""
        text = TEXTS[self.lang].get(key, TEXTS["en"].get(key, key))
        if fmt:
            text = text.format(**fmt)
        return text

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        lang_menu = tk.Menu(menubar, tearoff=0)
        lang_menu.add_command(label=self.t("menu_lang_zh"),
                              command=lambda: self._switch_lang("zh"))
        lang_menu.add_command(label=self.t("menu_lang_en"),
                              command=lambda: self._switch_lang("en"))
        menubar.add_cascade(label=self.t("menu_lang"), menu=lang_menu)
        self.root.config(menu=menubar)
        self._lang_menu = lang_menu

    def _switch_lang(self, lang: str):
        if lang == self.lang:
            return
        self.lang = lang
        self.root.title(self.t("window_title"))
        self._rebuild_ui()

    def _rebuild_ui(self):
        """语言切换后重建界面"""
        # 销毁旧菜单防止内存泄漏
        if hasattr(self, '_lang_menu'):
            self._lang_menu.destroy()
        for widget in list(self.root.winfo_children()):
            if isinstance(widget, tk.Menu):
                continue
            widget.destroy()
        self._build_menu()
        if self.state == self.STATE_IDLE:
            self._build_idle_view()
        elif self.state == self.STATE_PROGRESS:
            self._build_progress_view()
        elif self.state == self.STATE_DONE:
            self._build_done_view()
            # 等待窗口重建完成再重新覆盖图标
            self.root.update_idletasks()
            self._hide_icons()

    def _center_window(self, w: int, h: int):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    # ── IDLE 视图 ──
    def _build_idle_view(self):
        """彩虹标签 + 开始整理按钮"""
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        label_text = self.t("idle_label")
        canvas = tk.Canvas(frame, height=40, highlightthickness=0)
        canvas.pack(pady=(10, 20))
        self._idle_canvas = canvas

        x_offset = 10
        for i, ch in enumerate(label_text):
            color = RAINBOW_COLORS[i % len(RAINBOW_COLORS)]
            canvas.create_text(x_offset, 20, text=ch, fill=color,
                               font=("Microsoft YaHei", 14, "bold"), anchor="w")
            x_offset += 18

        btn = ttk.Button(frame, text=self.t("start_btn"),
                         command=self._on_start)
        btn.pack()
        self._idle_btn = btn

    def _on_start(self):
        """点击开始整理"""
        if self._check_auto_arrange():
            return
        if self.icon_mgr.find_listview() is None:
            messagebox.showerror(
                self.t("window_title"),
                self.t("no_desktop")
            )
            self.root.destroy()
            return

        self.state = self.STATE_PROGRESS
        self._rebuild_ui()
        self._start_progress()

    def _check_auto_arrange(self) -> bool:
        """检查桌面是否开启了自动排列/网格对齐，开启则弹窗返回 True"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Bags\1\Desktop"
            )
            fflags, _ = winreg.QueryValueEx(key, "FFlags")
            winreg.CloseKey(key)
            if fflags & 0x1 or fflags & 0x2:
                messagebox.showwarning(
                    self.t("window_title"),
                    self.t("auto_arrange_warn")
                )
                return True
        except (FileNotFoundError, OSError, TypeError):
            # 注册表键不存在、无法访问或值类型不匹配，忽略
            pass
        return False

    # ── PROGRESS 视图 ──
    def _build_progress_view(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        self._progress_label = ttk.Label(frame, text=self.t("progress_1"),
                                         font=("Microsoft YaHei", 12))
        self._progress_label.pack(pady=(10, 20))

        self._progress_bar = ttk.Progressbar(
            frame, mode='determinate', length=300
        )
        self._progress_bar.pack()
        self._progress_bar['value'] = 0

    def _start_progress(self):
        """开始进度条动画"""
        total_ms = int(random.uniform(4.0, 7.0) * 1000)
        self._progress_interval = total_ms / self._progress_segments
        self._progress_idx = 0
        self._progress_value = 0.0
        self._tick_progress()

    def _tick_progress(self):
        step = 100.0 / self._progress_segments
        labels = ["progress_1", "progress_2", "progress_3", "progress_4"]

        if self._progress_idx < self._progress_segments:
            self._progress_label.config(text=self.t(labels[self._progress_idx]))
            self._progress_value += step
            self._progress_bar['value'] = min(self._progress_value, 100)
            self._progress_idx += 1
            self._progress_after_id = self.root.after(
                int(self._progress_interval), self._tick_progress
            )
        else:
            self._on_progress_done()

    def _on_progress_done(self):
        """进度条完成 → 进入 DONE 状态"""
        self._icon_count = self.icon_mgr.get_icon_count()
        self.state = self.STATE_DONE
        self._rebuild_ui()
        self._hide_icons()

    # ── DONE 视图 ──
    def _build_done_view(self):
        """仅显示整理完成标签"""
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        label = ttk.Label(
            frame,
            text=self.t("done_label", count=self._icon_count),
            font=("Microsoft YaHei", 11),
            wraplength=380,
            justify=tk.CENTER,
        )
        label.pack(pady=5)
        self._done_label = label

    def _hide_icons(self):
        """将图标排列到窗口客户区下方并调整窗口大小"""
        # 重新测量边框（首次调用时窗口装饰可能尚未完全创建）
        self.win_ctrl._measure_borders()
        wx, wy = self.win_ctrl._get_window_pos()
        x = wx + self.win_ctrl._border_x + self.win_ctrl.MARGIN
        y = wy + self.win_ctrl._border_y + self.win_ctrl.MARGIN

        grid_w, grid_h = self.icon_mgr.arrange_grid(x, y)

        if grid_w > 0 and grid_h > 0:
            # 额外加一列图标间距作为宽度边距，确保长文件名也被遮住
            pad_w, _ = self.icon_mgr.get_icon_spacing()
            effective_w = grid_w + pad_w
            self.win_ctrl.cancel_debounce()
            self.win_ctrl.resize_to_cover(effective_w, grid_h)

        self.win_ctrl.pin_top()
        self.win_ctrl.block_minimize()
        self.win_ctrl.enable_drag_follow(self.icon_mgr)

    # ── 关闭 ──
    def _on_close(self):
        # 清理所有挂起的 after 定时器防止 TclError
        if self._progress_after_id:
            self.root.after_cancel(self._progress_after_id)
            self._progress_after_id = None
        self.win_ctrl.cancel_debounce()
        self.win_ctrl.unpin_top()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ── 入口 ──
if __name__ == "__main__":
    app = DesktopTidyApp()
    app.run()
