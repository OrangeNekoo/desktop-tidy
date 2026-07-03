# 桌面整理大师 — 设计规格

> 2026-07-03 | 单文件方案 | Python + tkinter + ctypes

## 概述

搞怪向桌面软件。点击按钮后假装"整理桌面"，进度条走完后把所有桌面图标藏到窗口下面。窗口置顶、反最小化、关闭不恢复图标。支持中英文切换。

---

## 一、架构与状态机

```
                 ┌─────────────────────────────────┐
                 │         DesktopTidyApp           │
                 │                                  │
   用户点击      │  ┌──────┐    ┌──────────┐    ┌──────┐  │
  ─────────────►│  │ IDLE  │───►│ PROGRESS │───►│ DONE  │  │
                 │  └──────┘    └──────────┘    └──────┘  │
                 │       ▲                           │    │
                 │       └─ 无返回路径（单向）────────┘    │
                 │                                  │
                 │  IconManager ◄── ctypes ◄── Windows   │
                 │  WindowController ◄── hwnd 操作       │
                 │  I18n ◄── dict[lang][key]             │
                 └─────────────────────────────────┘
```

| 状态 | 进入条件 | UI 内容 | 窗口行为 |
|------|----------|---------|----------|
| `IDLE` | 启动 | 彩虹标签 + "开始整理"按钮 | 默认大小，居中屏幕 |
| `PROGRESS` | 点击按钮 | 进度条 + 状态标签（4段文案轮流） | 维持原大小 |
| `DONE` | 进度条走完 | 仅"整理完成！..."标签（含图标统计数） | 缩至盖住图标的最小尺寸，置顶，拦截最小化 |

**不可逆：** IDLE → PROGRESS → DONE，无返回路径。关闭窗口 = 退出程序，图标留在被盖住的位置不恢复。

---

## 二、桌面图标操控（IconManager）

### 2.1 Windows 桌面窗口层级

不同 Windows 版本路径不同，三层回退查找 `SysListView32`：

| 优先级 | 路径 | 适用版本 |
|--------|------|----------|
| 1 | `Progman` → `SHELLDLL_DefView` → `SysListView32` | Win10 / Win11 23H2 及更早 |
| 2 | `WorkerW` → `SHELLDLL_DefView` → `SysListView32` | Win10 / 早期 Win11 备选 |
| 3 | `Shell_TrayWnd` → 递归找 `SysListView32` | Win11 24H2+ (DesktopWindowXamlSource 路径) |

### 2.2 接口

```python
class IconManager:
    def find_listview() -> int | None       # 三层回退查找
    def get_icon_count() -> int             # LVM_GETITEMCOUNT
    def get_icon_positions() -> list[tuple] # LVM_GETITEMPOSITION × N
    def set_icon_position(idx, x, y)        # LVM_SETITEMPOSITION
    def get_bounding_rect() -> tuple        # 所有图标包围盒 (l,t,r,b)
    def arrange_grid(win_x, win_y, win_w, win_h) -> tuple[int,int]
        # 排列图标到窗口下方网格，返回网格宽高
```

### 2.3 排列算法

+- 图标间距通过 `LVM_GETITEMSPACING` 消息动态获取（含图标+标签的实际占用尺寸），不使用硬编码值
+- N 个图标 → `cols = ceil(sqrt(N))` → `rows = ceil(N / cols)`
+- 图标 `i` → 网格位置 `(col * spacing_w, row * spacing_h)`，以窗口左上角为原点
+- 窗口左上角 = 图标网格左上角，窗口尺寸 = 网格尺寸（刚好盖住）

### 2.4 DPI 处理

调用 `SetProcessDPIAware()` 确保获取虚拟屏幕坐标而非逻辑坐标。图标尺寸基于系统 DPI 缩放因子动态计算。

### 2.5 自动排列检测

启动时检查桌面是否开启了"自动排列图标"或"将图标与网格对齐"（通过注册表 `HKCU\Software\Microsoft\Windows\Shell\Bags\1\Desktop`）。若开启则 `messagebox` 弹窗提示用户关闭后再使用。

---

## 三、窗口控制器（WindowController）

```python
class WindowController:
    def __init__(self, tk_root: Tk)
    def pin_top()              # 置顶 + 500ms 定时刷新 lift()
    def block_minimize()       # <Unmap> → deiconify() + lift()
    def enable_drag_follow(icon_mgr)  # <Configure> + 300ms 防抖 → 拖动结束后重排图标
    def resize_to_cover(w, h)  # geometry() 设置窗口大小覆盖图标网格
```

### 3.1 置顶

`wm_attributes('-topmost', True)` 配合 `after(500, ...)` 定时 `lift()`，防止其他 `-topmost` 窗口抢占。

### 3.2 反最小化

绑定 `<Unmap>`，检测 `state() == 'iconic'` → `after(1, deiconify)` + `after(2, lift)`。延迟避免与窗口管理器冲突。

### 3.3 拖动跟随

`<Configure>` 事件 → 每次重置 300ms 防抖定时器。拖动中持续重置，松手后 300ms 到期 → **一次性**执行 `IconManager.arrange_grid()` 将图标移到窗口下方。拖动过程中不移动图标。

### 3.4 自动调整大小

`DONE` 状态时，根据排列算法返回的网格宽高调用 `geometry(f'{w}x{h}+{x}+{y}')`，保持窗口左上角不变。

---

## 四、国际化（I18n）

单层字典 `TEXTS["zh"|"en"][key]`，不引入外部文件。

- 默认语言：系统语言为中文 → `zh`，否则 `en`
- 运行时切换：菜单栏点击 → 更新 `current_lang` → 遍历控件 `config(text=...)`
- `done_label` 含 `{count}` 占位符，显示前 `.format(count=N)`

### 文案表

| key | zh | en |
|-----|----|----|
| window_title | 桌面整理大师 | Desktop Tidy Master |
| idle_label | 点击按钮开始整理 | Click the button to start tidying |
| start_btn | 开始整理 | Start Tidying |
| progress_1 | 准备开始整理 | Preparing to tidy... |
| progress_2 | 正在分析桌面 | Analyzing desktop... |
| progress_3 | 调用homo银梦大模型 | Invoking Homo Silver Dream LLM... |
| progress_4 | 整理完成 | Tidying complete! |
| done_label | 整理完成！桌面已清理，共计 {count} 个图标已被收容。 | Tidying complete! {count} icons have been contained. |
| auto_arrange_warn | 请先关闭桌面的"自动排列图标"和"将图标与网格对齐"后再使用本软件。 | Please disable "Auto arrange icons" and "Align icons to grid" before using this software. |
| menu_lang | 语言 | Language |
| menu_lang_zh | 简体中文 | 简体中文 |
| menu_lang_en | English | English |

---

## 五、错误处理

| 场景 | 处理 |
|------|------|
| 找不到桌面 SysListView32 | 弹窗提示"无法访问桌面图标"，退出 |
| 桌面图标数为 0 | 正常完成流程，done_label 显示 count=0 |
| `SetProcessDPIAware` 失败 | 忽略，继续使用逻辑坐标 |
| 窗口被其他程序强制关闭 | 无需处理，程序正常退出 |
| 图标排列时某个图标移动失败 | 跳过该图标，继续排列其余 |

---

## 六、文件结构

```
desktop-tidy/
├── desktop_tidy.py          # 唯一源文件（~400 行）
├── README.md                # 中文
├── README_en.md             # 英文
├── docs/superpowers/specs/
│   └── 2026-07-03-desktop-tidy-design.md   # 本设计文档
└── LICENSE
```

---

## 七、进度条时序

1. 随机时长 `random.uniform(4.0, 7.0)` 秒
2. 等分为 4 段，每段占 25% 进度
3. 使用 `root.after(interval, callback)` 更新进度条值和状态标签
4. 状态标签依次显示：progress_1 → progress_2 → progress_3 → progress_4

---

## 八、彩虹标签实现

IDLE 状态的标签文字逐字设置前景色，从赤到紫：

```
colors = ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF", "#8B00FF"]
```

中文文字通常 7 个字（"点击按钮开始整理" 8 个字），颜色循环映射。
使用 tkinter `Text` 控件逐字插入并设置 tag 前景色，或使用多个 `Label` 拼接。

---

## 九、依赖

全部 Python 标准库：

| 模块 | 用途 |
|------|------|
| `tkinter` + `tkinter.ttk` | GUI |
| `ctypes` | Windows API |
| `threading` | （不使用——改用 after 回调） |
| `random` | 进度条时长 |
| `math` | ceil/sqrt 排列计算 |
| `locale` | 检测系统语言 |
| `winreg` | 读取注册表（自动排列检测） |

---

## 十、关键决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 图标恢复 | 永不恢复 | 用户选 B |
| 窗口置顶 | 始终置顶 | 用户选 A |
| 完成后界面 | 整蛊模式（仅标签） | 用户选 B，无按钮 |
| 最小化 | 自动弹回 | 用户选 B |
| 关闭按钮 | 真关闭 | 用户选 A |
| 自动排列检测 | 弹窗提示 | 用户选 A |
| 拖动行为 | 松手后一次性对齐 | 用户要求 |
| 文件结构 | 单文件 | 推荐，项目规模小 |
