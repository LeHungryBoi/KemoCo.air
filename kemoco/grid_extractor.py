# -*- encoding=utf8 -*-
"""
网格图像抽取器 (Grid Image Extractor)
=====================================
职责单一：截取游戏窗口 → 按 config.py 已知角点坐标裁剪出 64 个 cell 图像。

- 不落盘：capture() 只在内存里返回 numpy 数组，绝不写文件。
- 稳定 API：后续检测算法只依赖本模块的接口，不会因算法试验而被改动。

依赖：airtest.snapshot() 返回 BGR numpy 数组 (airtest 已带 numpy + opencv)。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

try:
    import numpy as np  # noqa: F401  (类型标注 + 运行时都用到)
except ImportError:  # pragma: no cover - airtest 已带 numpy
    np = None

from .config import (
    ABSOLUTE_CORNERS,        # [[x,y], ...] 左上/右上/左下/右下
    GRID_TOP_LEFT,           # (x, y) 左上角像素
    GRID_W, GRID_H,          # 棋盘宽高 (440x440)
    CELL_W, CELL_H,          # 单格宽高 (55x55)
    GRID_COLS, GRID_ROWS,    # 8x8
)


# ─── 返回结构 ───────────────────────────────────────────────────────────────────

@dataclass
class GridImage:
    """一次 capture 的结果。full 是整张截图，cells[row][col] 是 55x55 切片。"""
    full: object            # np.ndarray  (BGR, 1280x720x3)
    cells: List[List[object]]  # cells[row][col] -> np.ndarray (55x55x3)
    width: int = 0           # full 的宽
    height: int = 0          # full 的高


# ─── 抽取器 ─────────────────────────────────────────────────────────────────────

class GridImageExtractor:
    """
    从游戏窗口抓取 8x8 棋盘图像，切成 64 个 cell。

    用法：
        ext = GridImageExtractor()
        gi = ext.capture()
        cell_img = gi.cells[3][5]   # row=3, col=5 的格子图像
    """

    def __init__(self, hwnd: Optional[int] = None):
        # hwnd 保留以备后续直接 win32 截图 fallback；airtest snapshot 不需要它
        self.hwnd = hwnd

    def capture(self) -> GridImage:
        """截取当前游戏画面并切出 64 个 cell。全程在内存中，不写文件。"""
        if np is None:
            raise RuntimeError("numpy 不可用 (airtest 应已带 numpy)")

        # airtest.snapshot() 不传 filename 时不落盘，直接返回 BGR ndarray
        full = self._grab_full()

        x0, y0 = GRID_TOP_LEFT  # 左上角像素 (420, 116)
        cells: List[List[object]] = []
        for row in range(GRID_ROWS):
            row_cells: List[object] = []
            for col in range(GRID_COLS):
                x1 = x0 + col * CELL_W
                y1 = y0 + row * CELL_H
                x2 = x1 + CELL_W
                y2 = y1 + CELL_H
                row_cells.append(full[y1:y2, x1:x2])
            cells.append(row_cells)

        h, w = full.shape[:2]
        return GridImage(full=full, cells=cells, width=w, height=h)

    # ─── 内部 ────────────────────────────────────────────────────────────

    def _grab_full(self):
        """抓取整张游戏窗口截图 (BGR ndarray)。优先用 airtest snapshot。"""
        try:
            from airtest.core.api import snapshot
            # 不传 filename -> 返回 ndarray，不落盘
            img = snapshot()
            return img
        except Exception as e:
            raise RuntimeError(f"无法抓取游戏窗口截图: {e}") from e


# ─── 便捷函数 ───────────────────────────────────────────────────────────────────

def capture_grid(hwnd: Optional[int] = None) -> GridImage:
    """一次性快捷调用：直接返回当前棋盘的 GridImage。"""
    return GridImageExtractor(hwnd=hwnd).capture()
