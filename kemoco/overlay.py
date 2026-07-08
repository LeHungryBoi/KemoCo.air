# -*- encoding=utf8 -*-
"""
ESP-style overlay for KemoCo match-3 game.
Renders transparent always-on-top boxes, arrows, and text over the game grid.
Uses raylib-py (overdev/raylib-py) for that crisp ESP/cheat HUD look.
"""

import threading
import time
import math
from typing import Optional, Tuple, List

from raylibpy import *


# ─── Grid config (from llm.txt) ───────────────────────────────────────────────
GRID_TOP_LEFT = (420, 116)
GRID_BOTTOM_RIGHT = (860, 556)
GRID_COLS = 8
GRID_ROWS = 8
GRID_W = GRID_BOTTOM_RIGHT[0] - GRID_TOP_LEFT[0]  # 440
GRID_H = GRID_BOTTOM_RIGHT[1] - GRID_TOP_LEFT[1]  # 440
CELL_W = GRID_W // GRID_COLS   # 55
CELL_H = GRID_H // GRID_ROWS   # 55

OFS_X = 10
OFS_Y = 20


# ─── ESP Color palette ─────────────────────────────────────────────────────────
class ESPColor:
    """ESP / cheat-HUD colors as raylib Color objects."""
    RED       = Color(255, 50, 50, 200)
    GREEN     = Color(50, 255, 100, 200)
    CYAN      = Color(0, 220, 255, 220)
    YELLOW    = Color(255, 220, 30, 220)
    MAGENTA   = Color(255, 50, 255, 200)
    WHITE     = Color(255, 255, 255, 230)
    BLACK_BG  = Color(0, 0, 0, 160)
    FILL_RED  = Color(255, 50, 50, 35)
    FILL_GREEN= Color(50, 255, 100, 35)
    FILL_CYAN = Color(0, 220, 255, 25)


# ─── Data classes ──────────────────────────────────────────────────────────────

class ESPBox:
    def __init__(self, col: int, row: int,
                 color=ESPColor.CYAN,
                 label: str = "",
                 fill_color=None,
                 line_thickness: float = 2.0):
        self.col = col
        self.row = row
        self.color = color
        self.label = label
        self.fill_color = fill_color
        self.line_thickness = line_thickness


class ESPArrow:
    def __init__(self, from_col: int, from_row: int,
                 to_col: int, to_row: int,
                 color=ESPColor.YELLOW,
                 label: str = ""):
        self.from_col = from_col
        self.from_row = from_row
        self.to_col = to_col
        self.to_row = to_row
        self.color = color
        self.label = label


class ESPLabel:
    def __init__(self, x: int, y: int, text: str,
                 color=ESPColor.WHITE,
                 size: int = 18):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.size = size


# ─── Overlay engine ────────────────────────────────────────────────────────────

class ESPOverlay:
    """
    Transparent always-on-top ESP overlay window via raylib-py.

    Usage:
        esp = ESPOverlay()
        esp.start()
        esp.add_box(3, 2, label="MOVE")
        esp.add_arrow(3, 2, 3, 3, label="SWAP")
        esp.set_title("AUTO-SOLVE")
        ...
        esp.shutdown()
    """

    def __init__(self,
                 window_x: int = GRID_TOP_LEFT[0],
                 window_y: int = GRID_TOP_LEFT[1],
                 window_w: int = GRID_W + OFS_X * 2,
                 window_h: int = GRID_H + OFS_Y + 10,
                 fps: int = 30):

        self.window_x = window_x
        self.window_y = window_y
        self.window_w = window_w
        self.window_h = window_h
        self.fps = fps

        self._boxes: List[ESPBox] = []
        self._arrows: List[ESPArrow] = []
        self._labels: List[ESPLabel] = []
        self._title_text: str = ""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ─── Public API ───────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def shutdown(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def clear(self):
        with self._lock:
            self._boxes.clear()
            self._arrows.clear()
            self._labels.clear()
            self._title_text = ""

    def add_box(self, col: int, row: int, **kwargs) -> ESPBox:
        box = ESPBox(col, row, **kwargs)
        with self._lock:
            self._boxes.append(box)
        return box

    def add_arrow(self, fc: int, fr: int, tc: int, tr: int, **kwargs) -> ESPArrow:
        arrow = ESPArrow(fc, fr, tc, tr, **kwargs)
        with self._lock:
            self._arrows.append(arrow)
        return arrow

    def add_label(self, x: int, y: int, text: str, **kwargs) -> ESPLabel:
        label = ESPLabel(x, y, text, **kwargs)
        with self._lock:
            self._labels.append(label)
        return label

    def set_title(self, text: str):
        with self._lock:
            self._title_text = text

    # ─── Coordinate helpers ──────────────────────────────────────────────

    @staticmethod
    def cell_center(col: int, row: int) -> Tuple[int, int]:
        cx = OFS_X + col * CELL_W + CELL_W // 2
        cy = OFS_Y + row * CELL_H + CELL_H // 2
        return (cx, cy)

    @staticmethod
    def cell_rect(col: int, row: int):
        return Rectangle(
            OFS_X + col * CELL_W,
            OFS_Y + row * CELL_H,
            CELL_W - 2,
            CELL_H - 2
        )

    # ─── Render loop (dedicated thread) ──────────────────────────────────

    def _render_loop(self):
        set_config_flags(
            FLAG_WINDOW_UNDECORATED |
            FLAG_WINDOW_TRANSPARENT |
            FLAG_WINDOW_MOUSE_PASSTHROUGH |
            FLAG_WINDOW_TOPMOST
        )
        init_window(self.window_w, self.window_h, b"KemoCo ESP")
        set_window_position(max(0, self.window_x - OFS_X),
                            max(0, self.window_y - OFS_Y))
        set_target_fps(self.fps)

        try:
            while self._running and not window_should_close():
                self._draw_frame()
        finally:
            close_window()

    # ─── Frame rendering ─────────────────────────────────────────────────

    def _draw_frame(self):
        with self._lock:
            boxes = list(self._boxes)
            arrows = list(self._arrows)
            labels = list(self._labels)
            title = self._title_text

        begin_drawing()
        clear_background(BLANK)

        if title:
            self._draw_title(title)

        for box in boxes:
            self._draw_esp_box(box)

        for arrow in arrows:
            self._draw_esp_arrow(arrow)

        for lbl in labels:
            self._draw_label(lbl)

        end_drawing()

    # ─── Drawing primitives (the ESP look) ────────────────────────────────

    def _draw_title(self, text: str):
        font_size = 22
        tw = measure_text(text, font_size)
        x = (self.window_w - tw) // 2
        y = 4

        # Background pill
        draw_rectangle_rounded(Rectangle(x - 10, y - 2, tw + 20, 28),
                               0.15, 8, ESPColor.BLACK_BG)

        # Shadow + main text
        draw_text(text, x + 1, y + 1, font_size, Color(0, 0, 0, 180))
        draw_text(text, x, y, font_size, ESPColor.CYAN)

    def _draw_esp_box(self, box: ESPBox):
        rect = self.cell_rect(box.col, box.row)
        thickness = max(1, int(box.line_thickness))

        # Fill tint
        if box.fill_color:
            draw_rectangle_rec(rect, box.fill_color)

        # Border
        draw_rectangle_lines_ex(rect, thickness, box.color)

        # Corner accents (thick L-brackets like real ESP cheats)
        cl = min(12, int(rect.width) // 3, int(rect.height) // 3)
        cw = max(2, thickness + 1)
        x, y, w, h = rect.x, rect.y, rect.width, rect.height
        c = box.color

        # TL
        draw_line_ex(Vector2(x, y), Vector2(x + cl, y), cw, c)
        draw_line_ex(Vector2(x, y), Vector2(x, y + cl), cw, c)
        # TR
        draw_line_ex(Vector2(x + w, y), Vector2(x + w - cl, y), cw, c)
        draw_line_ex(Vector2(x + w, y), Vector2(x + w, y + cl), cw, c)
        # BL
        draw_line_ex(Vector2(x, y + h), Vector2(x + cl, y + h), cw, c)
        draw_line_ex(Vector2(x, y + h), Vector2(x, y + h - cl), cw, c)
        # BR
        draw_line_ex(Vector2(x + w, y + h), Vector2(x + w - cl, y + h), cw, c)
        draw_line_ex(Vector2(x + w, y + h), Vector2(x + w, y + h - cl), cw, c)

        # Label below box
        if box.label:
            cx = int(rect.x + rect.width / 2)
            cy = int(rect.y + rect.height + 4)
            self._draw_text_with_bg(box.label, cx, cy, 15, box.color, ESPColor.BLACK_BG)

    def _draw_esp_arrow(self, arrow: ESPArrow):
        fx, fy = self.cell_center(arrow.from_col, arrow.from_row)
        tx, ty = self.cell_center(arrow.to_col, arrow.to_row)

        # Shaft
        draw_line_ex(Vector2(fx, fy), Vector2(tx, ty),
                     max(2, int(arrow.color.a // 80)), arrow.color)

        # Arrowhead
        angle = math.atan2(ty - fy, tx - fx)
        ah_len = 12
        ah_spread = math.pi / 6
        draw_triangle(
            Vector2(tx, ty),
            Vector2(tx - ah_len * math.cos(angle - ah_spread),
                    ty - ah_len * math.sin(angle - ah_spread)),
            Vector2(tx - ah_len * math.cos(angle + ah_spread),
                    ty - ah_len * math.sin(angle + ah_spread)),
            arrow.color
        )

        # Mid-point label
        if arrow.label:
            mx = (fx + tx) // 2
            my = (fy + ty) // 2 - 10
            self._draw_text_with_bg(arrow.label, mx, my, 14, arrow.color, ESPColor.BLACK_BG)

    def _draw_label(self, lbl: ESPLabel):
        self._draw_text_with_bg(lbl.text, lbl.x, lbl.y, lbl.size, lbl.color, ESPColor.BLACK_BG)

    def _draw_text_with_bg(self, text: str, cx: int, cy: int,
                           size: int, fg, bg):
        tw = measure_text(text, size)
        px, py = 6, 2
        bg_rect = Rectangle(cx - tw // 2 - px, cy - py, tw + px * 2, size + py * 2)
        draw_rectangle_rounded(bg_rect, 0.12, 4, bg)
        draw_text(text, cx - tw // 2, cy, size, fg)


# ─── Demo ───────────────────────────────────────────────────────────────────────

def demo():
    print("[ESP Overlay] Demo mode launching... Ctrl+C or close to exit")

    esp = ESPOverlay(fps=30)
    esp.set_title("MATCH-3 ESP DEMO")

    esp.add_box(3, 2, color=ESPColor.RED, label="MOVE",
                fill_color=ESPColor.FILL_RED, line_thickness=2.5)
    esp.add_box(3, 3, color=ESPColor.GREEN, label="TARGET",
                fill_color=ESPColor.FILL_GREEN, line_thickness=2.5)
    esp.add_arrow(3, 2, 3, 3, color=ESPColor.YELLOW, label="SWAP")

    esp.add_box(5, 4, color=ESPColor.CYAN, label="ALT", fill_color=ESPColor.FILL_CYAN)
    esp.add_arrow(5, 4, 6, 4, color=ESPColor.CYAN, label="OR")

    esp.add_box(7, 6, color=ESPColor.MAGENTA, label="SPECIAL", line_thickness=3.0)

    esp.add_label(GRID_W // 2 + OFS_X, GRID_H + OFS_Y + 15,
                  "Auto-solve: ON", color=ESPColor.GREEN, size=16)

    esp.start()

    try:
        time.sleep(8)
    except KeyboardInterrupt:
        pass
    finally:
        esp.shutdown()
        print("[ESP Overlay] Done.")


if __name__ == "__main__":
    demo()
