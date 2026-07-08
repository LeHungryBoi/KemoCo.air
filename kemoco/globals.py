# -*- encoding=utf8 -*-
"""
KemoCo 全局运行时状态 (globals)
================================
和 config.py 的区别:
- config.py  -> 不会变的常量 (constants)
- globals.py -> 运行时会被修改的状态 (mutable state)

这里只做「集中初始化为默认值」，方便所有模块引用同一个实例。
真正的赋值发生在 main() / 各业务流程里
(例如 esp = ESPOverlay() 启动后 g.esp = esp)。

用法 (任意模块):
    from .globals import g
    if g.in_match:
        g.esp.add_box(...)
    g.in_match = True
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # 仅用于类型提示，避免运行时循环导入
    from .overlay import ESPOverlay


class State:
    """运行时全局状态容器。所有模块共享同一个实例 `g`。"""

    # ─── 游戏窗口 ───────────────────────────────────────────────────────────────
    # remove_titlebar() 返回的窗口句柄 (main 启动后赋值)
    hwnd: Optional[int] = None

    # ─── Overlay ────────────────────────────────────────────────────────────────
    # ESP overlay 实例 (ESPOverlay() start 之后赋值)
    esp: "Optional[ESPOverlay]" = None

    # ─── Match 状态机 ───────────────────────────────────────────────────────────
    # 当前是否处于一场 match 中
    in_match: bool = False
    # 主循环是否在运行
    running: bool = False

    def reset(self) -> None:
        """把所有运行时状态重置回初始默认值。"""
        self.hwnd = None
        self.esp = None
        self.in_match = False
        self.running = False


# 全局单例 —— 整个项目共享这一个 g
g = State()
