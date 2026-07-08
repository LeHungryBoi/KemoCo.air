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
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # 仅用于类型提示，避免运行时循环导入
    from .overlay import ESPOverlay


# ─── 宝石类型 / 棋盘数据结构 ───────────────────────────────────────────────────
# 7 种宝石 (对应 GemAndIcon_Assets/GemAndIcon-*.png)，另加 EMPTY / UNKNOWN

class GemType(Enum):
    EMPTY = 0              # 空格 (无宝石)
    ATTACK_A = 1           # GemAndIcon-Attack_A
    ATTACK_B = 2           # GemAndIcon-Attack_B
    HEAL = 3               # GemAndIcon-Heal
    MAGIC_RESOURCE = 4     # GemAndIcon-MagicResource
    PHYSICAL_RESOURCE = 5  # GemAndIcon-PhysicalResource
    RAGE = 6               # GemAndIcon-Rage
    SHIELD = 7             # GemAndIcon-Shield
    UNKNOWN = 8            # 检测失败 / 未识别


@dataclass
class CellGem:
    """单个格子上的宝石状态。variant=True 表示特殊变体 (素材里的 _0 后缀版本)。"""
    gem_type: GemType = GemType.UNKNOWN
    variant: bool = False


class Board:
    """
    8x8 棋盘状态容器。

    索引约定: cells[row][col]，row=0 在顶部，col=0 在左侧。
    检测算法写入、overlay / 求解器读取。
    """

    def __init__(self, rows: int = 8, cols: int = 8):
        self.rows = rows
        self.cols = cols
        self.cells: List[List[CellGem]] = [
            [CellGem() for _ in range(cols)] for _ in range(rows)
        ]

    def get(self, row: int, col: int) -> CellGem:
        return self.cells[row][col]

    def set(self, row: int, col: int, gem: CellGem) -> None:
        self.cells[row][col] = gem

    def fill(self, gem_type: GemType = GemType.UNKNOWN, variant: bool = False) -> None:
        """把整盘重置为同一个值。"""
        for r in range(self.rows):
            for c in range(self.cols):
                self.cells[r][c] = CellGem(gem_type=gem_type, variant=variant)

    def to_grid_str(self) -> str:
        """调试用：每格取宝石名首字母缩写，variant 加 '*'。"""
        names = {
            GemType.EMPTY: ".", GemType.ATTACK_A: "A", GemType.ATTACK_B: "B",
            GemType.HEAL: "H", GemType.MAGIC_RESOURCE: "M",
            GemType.PHYSICAL_RESOURCE: "P", GemType.RAGE: "R",
            GemType.SHIELD: "S", GemType.UNKNOWN: "?",
        }
        lines = []
        for r in range(self.rows):
            line = " ".join(
                (names[self.cells[r][c].gem_type] or "?")
                + ("*" if self.cells[r][c].variant else "")
                for c in range(self.cols)
            )
            lines.append(line)
        return "\n".join(lines)


# ─── 运行时全局状态容器 ─────────────────────────────────────────────────────────

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

    # ─── 棋盘状态 ───────────────────────────────────────────────────────────────
    # 当前 8x8 棋盘的宝石分布 (检测算法写入，overlay / 求解器读取)
    grid: Optional[Board] = None

    def reset(self) -> None:
        """把所有运行时状态重置回初始默认值。"""
        self.hwnd = None
        self.esp = None
        self.in_match = False
        self.running = False
        self.grid = None


# 全局单例 —— 整个项目共享这一个 g
g = State()
