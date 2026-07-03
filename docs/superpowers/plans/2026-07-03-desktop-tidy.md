# 桌面整理大师 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现一个搞怪向桌面整理软件，点击按钮后隐藏所有桌面图标到窗口下方，支持中英文切换。

**架构：** 单文件 `desktop_tidy.py`，三个类：`DesktopTidyApp`（状态机+UI）、`IconManager`（ctypes 桌面图标操作）、`WindowController`（置顶/反最小化/拖动跟随）。状态机 IDLE→PROGRESS→DONE，单向不可逆。

**技术栈：** Python 3 + tkinter + ctypes（全标准库）

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `desktop_tidy.py` | 全部代码：入口、状态机、GUI、图标操控、窗口控制、国际化 |

---

### 任务 1：项目骨架与国际化模块

**文件：**
- 创建：`desktop_tidy.py`

- [ ] **步骤 1：创建文件骨架，写入国际化字典和常量**

```python
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
import locale

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
        lang, _ = locale.getdefaultlocale()
        if lang and lang.startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"
```

- [ ] **步骤 2：运行语法检查验证**

运行：`python -m py_compile desktop_tidy.py`
预期：无输出，无报错。

- [ ] **步骤 3：Commit**

```bash
git add desktop_tidy.py
git commit -m "feat: add project skeleton and i18n module"
```

---

### 任务 2：IconManager — 桌面图标操控

**文件：**
- 修改：`desktop_tidy.py`（在任务 1 的代码后追加）

- [ ] **步骤 1：添加 Windows API 常量定义和 IconManager 类**

在 `desktop_tidy.py` 末尾追加：

```python
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
        user32 = ctypes.windll.user32
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
        # LVM_GETITEMSPACING: wParam=TRUE 获取含标签的间距
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
```

- [ ] **步骤 2：运行语法检查验证**

运行：`python -m py_compile desktop_tidy.py`
预期：无输出，无报错。

- [ ] **步骤 3：Commit**

```bash
git add desktop_tidy.py
git commit -m "feat: add IconManager for desktop icon manipulation"
```

---

### 任务 3：WindowController — 窗口控制

**文件：**
- 修改：`desktop_tidy.py`（在任务 2 的代码后追加）

- [ ] **步骤 1：追加 WindowController 类**

```python
# ── WindowController ──
class WindowController:
    """管理窗口置顶、反最小化、拖动完成后图标的跟随"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self._icon_mgr: IconManager | None = None
        self._debounce_id: str | None = None
        self._topmost_timer: str | None = None

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
        """取消置顶（仅在 PROGRESS 阶段不使用）"""
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

    def enable_drag_follow(self, icon_mgr: IconManager):
        """启用拖动完成后图标跟随"""
        self._icon_mgr = icon_mgr
        self.root.bind('<Configure>', self._on_configure)

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if self._debounce_id:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(300, self._on_drag_end)

    def _on_drag_end(self):
        """拖动停止 300ms 后触发：将图标排列到窗口下方"""
        if self._icon_mgr is None:
            return
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self._icon_mgr.arrange_grid(x, y)

    def resize_to_cover(self, w: int, h: int):
        """调整窗口大小以覆盖图标网格，保持左上角不变"""
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f'{w}x{h}+{x}+{y}')
```

- [ ] **步骤 2：运行语法检查**

运行：`python -m py_compile desktop_tidy.py`
预期：无输出。

- [ ] **步骤 3：Commit**

```bash
git add desktop_tidy.py
git commit -m "feat: add WindowController for topmost/anti-minimize/drag-follow"
```

---

### 任务 4：DesktopTidyApp — 状态机与 GUI

**文件：**
- 修改：`desktop_tidy.py`（在任务 3 的代码后追加）

- [ ] **步骤 1：追加 DesktopTidyApp 类**

```python
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
        self._center_window(400, 200)

    def t(self, key: str, **fmt) -> str:
        """获取当前语言的文本"""
        text = TEXTS[self.lang][key]
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
        for widget in self.root.winfo_children():
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

        # 彩虹标签：使用 Canvas 逐字绘制
        label_text = self.t("idle_label")
        canvas = tk.Canvas(frame, height=40, highlightthickness=0)
        canvas.pack(pady=(10, 20))
        self._idle_canvas = canvas

        x_offset = 10
        for i, ch in enumerate(label_text):
            color = RAINBOW_COLORS[i % len(RAINBOW_COLORS)]
            canvas.create_text(x_offset, 20, text=ch, fill=color,
                               font=("Microsoft YaHei", 14, "bold"), anchor="w")
            x_offset += 18  # 中文字符宽度估算

        # 按钮
        btn = ttk.Button(frame, text=self.t("start_btn"),
                         command=self._on_start)
        btn.pack()
        self._idle_btn = btn

    def _on_start(self):
        """点击开始整理"""
        # 检查自动排列
        if self._check_auto_arrange():
            return
        # 查找桌面图标列表
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
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Bags\1\Desktop"
            )
            # FFlags 包含排列相关标志位
            fflags, _ = winreg.QueryValueEx(key, "FFlags")
            winreg.CloseKey(key)
            # bit 2 (0x4) = 自动排列, bit 5 (0x20) = 网格对齐
            if fflags & 0x4 or fflags & 0x20:
                messagebox.showwarning(
                    self.t("window_title"),
                    self.t("auto_arrange_warn")
                )
                return True
        except Exception:
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
        """将图标排列到窗口下方并调整窗口大小"""
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        grid_w, grid_h = self.icon_mgr.arrange_grid(x, y)

        if grid_w > 0 and grid_h > 0:
            self.win_ctrl.resize_to_cover(grid_w, grid_h)
        elif grid_w == 0:
            # 无图标：窗口保持原样
            pass

        self.win_ctrl.pin_top()
        self.win_ctrl.block_minimize()
        self.win_ctrl.enable_drag_follow(self.icon_mgr)

    # ── 关闭 ──
    def _on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ── 入口 ──
if __name__ == "__main__":
    app = DesktopTidyApp()
    app.run()
```

- [ ] **步骤 2：运行语法检查**

运行：`python -m py_compile desktop_tidy.py`
预期：无输出。

- [ ] **步骤 3：Commit**

```bash
git add desktop_tidy.py
git commit -m "feat: add DesktopTidyApp with state machine and full GUI"
```

---

### 任务 5：集成测试 — 启动验证

**文件：**
- 无修改

- [ ] **步骤 1：运行启动测试（仅验证不崩溃）**

```bash
python -c "import desktop_tidy; print('Module loaded OK')"
```
预期输出：`Module loaded OK`

- [ ] **步骤 2：验证 tkinter 可初始化**

```bash
python -c "
import tkinter as tk
root = tk.Tk()
root.title('test')
print(f'Tk root created: {root.winfo_exists()}')
root.destroy()
print('Tk destroyed OK')
"
```
预期：输出两行，无异常。

- [ ] **步骤 3：Commit**

```bash
git commit --allow-empty -m "test: verify module import and tkinter init"
```

---

### 任务 6：README 文档

**文件：**
- 创建：`README.md`（中文）
- 创建：`README_en.md`（英文）
- 使用 humanizer-zh skill 润色中文 README

- [ ] **步骤 1：编写中文 README 原始内容后将调用 humanizer-zh 润色**

README.md 应包含：
- 项目名称与简介（搞怪向）
- 功能说明
- 使用方法
- 运行环境（Windows + Python 3）
- 警告：本软件会移动桌面图标且不恢复

- [ ] **步骤 2：翻译为英文 README**

README_en.md 为 README.md 的英文翻译版。

- [ ] **步骤 3：Commit**

```bash
git add README.md README_en.md
git commit -m "docs: add README in Chinese and English"
```
