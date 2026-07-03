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
