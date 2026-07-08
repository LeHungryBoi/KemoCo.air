# -*- encoding=utf8 -*-
"""
ESP-style overlay for KemoCo match-3 game.
Renders transparent always-on-top boxes, arrows, and text over the game grid.
Uses pygame for that crisp ESP/cheat HUD look — transparent click-through window.
"""

import threading
import time
import math
import os
from typing import Optional, Tuple, List

import pygame

# ─── Grid config (from llm.txt) ───────────────────────────────────────────────
# Absolute screen coordinates of the 8x8 match-3 grid
GRID_TOP_LEFT = (420, 116)
GRID_BOTTOM_RIGHT = (860, 556)
GRID_COLS = 8
GRID_ROWS = 8
GRID_W = GRID_BOTTOM_RIGHT[0] - GRID_TOP_LEFT[0]  # 440
GRID_H = GRID_BOTTOM_RIGHT[1] - GRID_TOP_LEFT[1]  # 440
CELL_W = GRID_W // GRID_COLS   # 55
CELL_H = GRID_H // GRID_ROWS   # 55

# Overlay padding inside the window
OFS_X = 10   # left offset for grid within overlay
OFS_Y = 20   # top offset (room for title bar)

# ─── ESP Color palette ─────────────────────────────────────────────────────────
class ESPColor:
    """Classic ESP / cheat-HUD color palette. All RGBA tuples."""
    RED       = (255, 50, 50, 200)
    GREEN     = (50, 255, 100, 200)
    CYAN      = (0, 220, 255, 220)
    YELLOW    = (255, 220, 30, 220)
    MAGENTA   = (255, 50, 255, 200)
    WHITE     = (255, 255, 255, 230)
    BLACK_BG  = (0, 0, 0, 160)
    FILL_RED  = (255, 50, 50, 35)
    FILL_GREEN= (50, 255, 100, 35)
    FILL_CYAN = (0, 220, 255, 25)


# ─── Data classes ──────────────────────────────────────────────────────────────

class ESPBox:
    """An ESP-style bounding box around a grid cell."""
    def __init__(self, col: int, row: int,
                 color: Tuple[int,int,int,int] = ESPColor.CYAN,
                 label: str = "",
                 fill_color: Optional[Tuple[int,int,int,int]] = None,
                 line_thickness: float = 2.0):
        self.col = col
        self.row = row
        self.color = color
        self.label = label
        self.fill_color = fill_color
        self.line_thickness = line_thickness


class ESPArrow:
    """Arrow / line connecting two cells (showing move direction)."""
    def __init__(self, from_col: int, from_row: int,
                 to_col: int, to_row: int,
                 color: Tuple[int,int,int,int] = ESPColor.YELLOW,
                 label: str = ""):
        self.from_col = from_col
        self.from_row = from_row
        self.to_col = to_col
        self.to_row = to_row
        self.color = color
        self.label = label


class ESPLabel:
    """Free-floating text label at arbitrary position."""
    def __init__(self, x: int, y: int, text: str,
                 color: Tuple[int,int,int,int] = ESPColor.WHITE,
                 size: int = 18):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.size = size


# ─── Overlay engine ────────────────────────────────────────────────────────────

class ESPOverlay:
    """
    Transparent always-on-top ESP overlay window (pygame-based).

    Usage:
        esp = ESPOverlay()
        esp.start()                     # launches render thread (non-blocking)
        esp.add_box(3, 2, label="GEM")
        esp.add_arrow(3, 2, 3, 3, label="SWAP")
        esp.set_title("AUTO-SOLVE")
        # ... later ...
        esp.clear()
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

        # pygame objects (created in render thread)
        _screen = None
        _font_small = None
        _font_title = None
        _font_label = None

    # ─── Public API ───────────────────────────────────────────────────────

    def start(self):
        """Start the overlay render thread (non-blocking)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def shutdown(self):
        """Stop the overlay and clean up."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def clear(self):
        """Clear all ESP elements."""
        with self._lock:
            self._boxes.clear()
            self._arrows.clear()
            self._labels.clear()
            self._title_text = ""

    def add_box(self, col: int, row: int, **kwargs) -> ESPBox:
        """Add an ESP box around cell (col, row). Returns the box object."""
        box = ESPBox(col, row, **kwargs)
        with self._lock:
            self._boxes.append(box)
        return box

    def add_arrow(self, fc: int, fr: int, tc: int, tr: int, **kwargs) -> ESPArrow:
        """Add an arrow from (fc,fr) to (tc,tr). Returns the arrow object."""
        arrow = ESPArrow(fc, fr, tc, tr, **kwargs)
        with self._lock:
            self._arrows.append(arrow)
        return arrow

    def add_label(self, x: int, y: int, text: str, **kwargs) -> ESPLabel:
        """Add a free-floating text label at pixel position (x,y)."""
        label = ESPLabel(x, y, text, **kwargs)
        with self._lock:
            self._labels.append(label)
        return label

    def set_title(self, text: str):
        """Set top-center title text."""
        with self._lock:
            self._title_text = text

    # ─── Coordinate helpers ──────────────────────────────────────────────

    @staticmethod
    def cell_center(col: int, row: int) -> Tuple[int, int]:
        """Pixel center of a grid cell relative to the overlay window."""
        cx = OFS_X + col * CELL_W + CELL_W // 2
        cy = OFS_Y + row * CELL_H + CELL_H // 2
        return (cx, cy)

    @staticmethod
    def cell_rect(col: int, row: int) -> pygame.Rect:
        """Bounding Rect for a grid cell (relative to overlay origin)."""
        return pygame.Rect(
            OFS_X + col * CELL_W,
            OFS_Y + row * CELL_H,
            CELL_W - 2, CELL_H - 2
        )

    # ─── Render loop (dedicated thread) ──────────────────────────────────

    def _render_loop(self):
        os.environ['SDL_WINDOW'] = 'position={},{}'.format(
            max(0, self.window_x - OFS_X), max(0, self.window_y - OFS_Y))
        os.environ['SDL_VIDEO_WINDOW_POS'] = '{},{}'.format(
            max(0, self.window_x - OFS_X), max(0, self.window_y - OFS_Y))

        pygame.init()
        pygame.display.set_caption("KemoCo ESP")

        # Create per-pixel-alpha surface for transparency support
        self._screen = pygame.display.set_mode(
            (self.window_w, self.window_h),
            pygame.NOFRAME | pygame.DOUBLEBUF | pygame.SRCALPHA
        )

        # Win32: set always-on-top & transparent via hwnd
        self._set_window_style()

        # Fonts — use monospace for that terminal/ESP feel
        self._font_title = pygame.font.SysFont('consolas', 20, bold=True)
        self._font_label = pygame.font.SysFont('consolas', 14)
        self._font_small = pygame.font.SysFont('consolas', 13)

        clock = pygame.time.Clock()

        try:
            while self._running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self._running = False
                self._draw_frame()
                clock.tick(self.fps)
        finally:
            pygame.quit()

    def _set_window_style(self):
        """Set win32 window attributes: topmost, transparent, click-through."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            WS_EX_TOOLWINDOW = 0x80
            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_SHOWWINDOW = 0x0040
            LWA_ALPHA = 0x02

            hwnd = pygame.display.get_wm_info()['window']

            # Layered window (for alpha blending)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

            # Set window alpha (whole window uses per-pixel alpha via SRCALPHA)
            user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)

            # Always on top
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

        except Exception:
            pass  # non-Windows or missing ctypes — degrade gracefully

    # ─── Frame rendering ─────────────────────────────────────────────────

    def _draw_frame(self):
        """Render one frame to the alpha surface."""
        surf = self._screen
        surf.fill((0, 0, 0, 0))  # fully transparent

        with self._lock:
            boxes = list(self._boxes)
            arrows = list(self._arrows)
            labels = list(self._labels)
            title = self._title_text

        if title:
            self._draw_title(surf, title)

        for box in boxes:
            self._draw_esp_box(surf, box)

        for arrow in arrows:
            self._draw_esp_arrow(surf, arrow)

        for lbl in labels:
            self._draw_label(surf, lbl)

        pygame.display.flip()

    # ─── Drawing primitives (the ESP look) ────────────────────────────────

    def _draw_title(self, surf, text: str):
        """Centered title pill at top with glow effect."""
        font = self._font_title
        text_surf = font.render(text, True, (*ESPColor.CYAN[:3],))
        tw, th = text_surf.get_size()
        x = (self.window_w - tw) // 2
        y = 4

        # Background pill (rounded rect approximation)
        pill_rect = pygame.Rect(x - 10, y - 2, tw + 20, th + 4)
        self._rounded_rect(surf, pill_rect, 6, ESPColor.BLACK_BG)

        # Text shadow
        shadow = font.render(text, True, (0, 0, 0))
        surf.blit(shadow, (x + 1, y + 1))

        # Main text
        surf.blit(text_surf, (x, y))

    def _draw_esp_box(self, surf, box: ESPBox):
        """ESP-style bounding box with corner accents and optional label."""
        rect = self.cell_rect(box.col, box.row)
        thickness = max(1, int(box.line_thickness))

        # Fill tint
        if box.fill_color:
            fill_s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            fill_s.fill(box.fill_color)
            surf.blit(fill_s, rect.topleft)

        color_rgb = box.color[:3]

        # Main border rectangle
        pygame.draw.rect(surf, color_rgb, rect, width=thickness)

        # Corner accents (thicker L-brackets like real ESP cheats)
        cl = min(12, rect.w // 3, rect.h // 3)  # corner length
        cw = max(2, thickness + 1)              # corner width (thicker)
        x, y, w, h = rect.topleft[0], rect.topleft[1], rect.w, rect.h

        corners = [
            ((x, y), (x + cl, y)),       # top-left horiz
            ((x, y), (x, y + cl)),       # top-left vert
            ((x + w, y), (x + w - cl, y)),  # top-right horiz
            ((x + w, y), (x + w, y + cl)),  # top-right vert
            ((x, y + h), (x + cl, y + h)),  # bottom-left horiz
            ((x, y + h), (x, y + h - cl)),  # bottom-left vert
            ((x + w, y + h), (x + w - cl, y + h)),  # bottom-right horiz
            ((x + w, y + h), (x + w, y + h - cl)),  # bottom-right vert
        ]
        for start, end in corners:
            pygame.draw.line(surf, color_rgb, start, end, width=cw)

        # Label below the box
        if box.label:
            cx = rect.centerx
            cy = rect.bottom + 4
            self._draw_text_with_bg(surf, box.label, cx, cy,
                                    self._font_small, box.color, ESPColor.BLACK_BG)

    def _draw_esp_arrow(self, surf, arrow: ESPArrow):
        """Draw arrow from source cell center to target cell center."""
        fx, fy = self.cell_center(arrow.from_col, arrow.from_row)
        tx, ty = self.cell_center(arrow.to_col, arrow.to_row)
        color_rgb = arrow.color[:3]
        color_rgba = arrow.color

        # Shaft
        pygame.draw.line(surf, color_rgb, (fx, fy), (tx, ty), width=max(2, int(arrow.color[3] // 80)))

        # Arrowhead
        angle = math.atan2(ty - fy, tx - fx)
        ah_len = 12
        ah_spread = math.pi / 6
        pts = [
            (tx, ty),
            (tx - ah_len * math.cos(angle - ah_spread),
             ty - ah_len * math.sin(angle - ah_spread)),
            (tx - ah_len * math.cos(angle + ah_spread),
             ty - ah_len * math.sin(angle + ah_spread)),
        ]
        pygame.draw.polygon(surf, color_rgb, pts)
        pygame.draw.polygon(surf, color_rgb, pts, width=1)  # crisp edge

        # Mid-point label
        if arrow.label:
            mx = (fx + tx) // 2
            my = (fy + ty) // 2 - 10
            self._draw_text_with_bg(surf, arrow.label, mx, my,
                                    self._font_small, arrow.color, ESPColor.BLACK_BG)

    def _draw_label(self, surf, lbl: ESPLabel):
        """Free-floating text label."""
        self._draw_text_with_bg(surf, lbl.text, lbl.x, lbl.y,
                                self._font_label, lbl.color, ESPColor.BLACK_BG)

    def _draw_text_with_bg(self, surf, text: str, cx: int, cy: int,
                           font, fg_color, bg_color):
        """Render centered text with dark rounded-bg pill."""
        text_surf = font.render(text, True, fg_color[:3])
        tw, th = text_surf.get_size()
        px, py = 6, 2

        bg_rect = pygame.Rect(cx - tw // 2 - px, cy - py, tw + px * 2, th + py * 2)
        self._rounded_rect(surf, bg_rect, 3, bg_color)

        surf.blit(text_surf, (cx - tw // 2, cy))

    def _rounded_rect(self, surf, rect: pygame.Rect, radius: int, color):
        """Draw a filled rounded rectangle."""
        if isinstance(color, (tuple, list)) and len(color) == 4:
            s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            s.fill((0, 0, 0, 0))
            pygame.draw.rect(s, color, s.get_rect(), border_radius=radius)
            surf.blit(s, rect.topleft)
        else:
            pygame.draw.rect(surf, color, rect, border_radius=radius)


# ─── Demo / test ───────────────────────────────────────────────────────────────

def demo():
    """
    Quick standalone demo. Shows sample ESP elements for ~8 seconds.

    Run:
        uv run python -c "from kemoco.overlay import demo; demo()"
    """
    print("[ESP Overlay] Demo mode launching...")
    print("[ESP Overlay] Close the overlay or Ctrl+C to exit")

    esp = ESPOverlay(fps=30)
    esp.set_title("MATCH-3 ESP DEMO")

    # Red box = piece to move
    esp.add_box(3, 2, color=ESPColor.RED, label="MOVE",
                fill_color=ESPColor.FILL_RED, line_thickness=2.5)

    # Green box = swap destination
    esp.add_box(3, 3, color=ESPColor.GREEN, label="TARGET",
                fill_color=ESPColor.FILL_GREEN, line_thickness=2.5)

    # Yellow arrow showing swap direction
    esp.add_arrow(3, 2, 3, 3, color=ESPColor.YELLOW, label="SWAP")

    # Cyan alternative move
    esp.add_box(5, 4, color=ESPColor.CYAN, label="ALT",
                fill_color=ESPColor.FILL_CYAN)
    esp.add_arrow(5, 4, 6, 4, color=ESPColor.CYAN, label="OR")

    # Magenta focus highlight
    esp.add_box(7, 6, color=ESPColor.MAGENTA, label="SPECIAL",
                line_thickness=3.0)

    # Status label
    esp.add_label(GRID_W // 2 + OFS_X, GRID_H + OFS_Y + 15,
                  "Auto-solve: ON", color=ESPColor.GREEN, size=16)

    esp.start()

    try:
        time.sleep(8)
    except KeyboardInterrupt:
        pass
    finally:
        esp.shutdown()
        print("[ESP Overlay] Demo ended.")


if __name__ == "__main__":
    demo()
