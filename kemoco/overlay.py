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


# ─── Grid config (see kemoco/config.py) ───────────────────────────────────────
from .config import (
    GRID_TOP_LEFT, GRID_BOTTOM_RIGHT,
    GRID_COLS, GRID_ROWS,
    GRID_W, GRID_H,
    CELL_W, CELL_H,
    OFS_X, OFS_Y,
)


# ─── WinEvent (SetWinEventHook) 常量 ───────────────────────────────────────────
# 事件驱动追踪游戏窗口前台/可见状态，替代每帧轮询。仅在状态变化时回调。
WINEVENT_OUTOFCONTEXT     = 0x0000
EVENT_SYSTEM_FOREGROUND   = 0x0003   # 某窗口进入前台 (hwnd = 新前台窗口)
EVENT_SYSTEM_MINIMIZESTART = 0x0016  # 窗口被最小化
EVENT_SYSTEM_MINIMIZEEND   = 0x0017  # 窗口从最小化恢复
EVENT_OBJECT_SHOW   = 0x8002        # 窗口/对象显示
EVENT_OBJECT_HIDE   = 0x8003        # 窗口/对象隐藏
EVENT_OBJECT_DESTROY = 0x8001       # 窗口/对象销毁 (游戏关闭)


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
                 fps: int = 30,
                 game_hwnd: Optional[int] = None):

        self.window_x = window_x
        self.window_y = window_y
        self.window_w = window_w
        self.window_h = window_h
        self.fps = fps

        # 游戏窗口句柄：提供后 overlay 每帧对齐到游戏窗口的真实屏幕位置
        self.game_hwnd = game_hwnd
        self._last_track_x: Optional[int] = None
        self._last_track_y: Optional[int] = None

        # 游戏窗口是否在前台/可见 (由 WinEvent 钩子线程事件驱动更新)
        self._game_visible: bool = True

        # WinEvent 钩子线程 (事件驱动，平时零 CPU)
        self._win_event_thread_obj: Optional[threading.Thread] = None
        self._win_event_cb = None  # 持有 ctypes 回调引用防 GC

        self._boxes: List[ESPBox] = []
        self._arrows: List[ESPArrow] = []
        self._labels: List[ESPLabel] = []
        self._title_text: str = ""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 网格可视化状态
        self._show_grid: bool = False
        self._grid_color = ESPColor.CYAN
        self._show_grid_labels: bool = True

    # ─── Public API ───────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def shutdown(self):
        self._running = False
        # 先停 WinEvent 钩子线程，再停渲染线程
        if self._win_event_thread_obj and self._win_event_thread_obj.is_alive():
            self._win_event_thread_obj.join(timeout=2)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def clear(self):
        with self._lock:
            self._boxes.clear()
            self._arrows.clear()
            self._labels.clear()
            self._title_text = ""
            self._show_grid = False

    def draw_grid(self, color=None, show_labels: bool = True):
        """开启完整 8x8 网格可视化 (外框 + 内部网格线 + 行列标签 A1~H8)。"""
        with self._lock:
            self._show_grid = True
            self._grid_color = color or ESPColor.CYAN
            self._show_grid_labels = show_labels

    def hide_grid(self):
        """关闭网格可视化。"""
        with self._lock:
            self._show_grid = False

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

        # 先把 overlay 设为「无焦点/无任务栏」的工具窗口并把前台还给游戏，
        # 之后再启动 WinEvent 钩子 —— 此时游戏在前台，初值 _game_visible=True，
        # 不会因为 init_window 抢焦点而误触发 hide。
        self._setup_overlay_window_style()
        self._start_win_event_hook()

        try:
            while self._running and not window_should_close():
                self._track_game_window()
                self._draw_frame()
        finally:
            close_window()

    # ─── Overlay 窗口样式 (无焦点 / 无任务栏图标) ───────────────────────

    def _setup_overlay_window_style(self):
        """把 overlay 变成「无焦点、无任务栏图标」的 HUD 工具窗口。

        raylib 的 init_window 把窗口当普通应用窗口创建: 出现在任务栏、且
        创建时抢前台。这会让游戏瞬间失去前台 -> WinEvent 钩子误判并隐藏
        overlay，用户得手动点回游戏才显示。

        修复: 创建后立即给 overlay 加 WS_EX_NOACTIVATE (永不抢焦点) +
        WS_EX_TOOLWINDOW (无任务栏图标)、去掉 WS_EX_APPWINDOW，再把被抢走
        的前台还给游戏窗口。
        """
        try:
            import win32gui
            import win32con
        except Exception:
            return

        # 取 overlay 窗口句柄: 优先用 raylib 的 get_window_handle，失败则 FindWindow
        overlay_hwnd = 0
        try:
            raw = get_window_handle()
            overlay_hwnd = int(raw) if raw else 0
        except Exception:
            overlay_hwnd = 0
        if not overlay_hwnd:
            try:
                overlay_hwnd = win32gui.FindWindow(None, "KemoCo ESP")
            except Exception:
                overlay_hwnd = 0
        if not overlay_hwnd:
            return

        WS_EX_NOACTIVATE = getattr(win32con, "WS_EX_NOACTIVATE", 0x08000000)
        try:
            ex = win32gui.GetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE)
            ex |= win32con.WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            ex &= ~win32con.WS_EX_APPWINDOW
            win32gui.SetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE, ex)
        except Exception:
            pass

        # 以「不激活」方式重显，刷新任务栏归属
        try:
            win32gui.ShowWindow(overlay_hwnd, win32con.SW_SHOWNOACTIVATE)
        except Exception:
            pass

        # 把 init_window 抢走的前台还给游戏 (此时本进程持有前台，允许跨进程设置)
        if self.game_hwnd:
            try:
                if win32gui.IsWindow(self.game_hwnd):
                    win32gui.SetForegroundWindow(self.game_hwnd)
            except Exception:
                try:
                    win32gui.BringWindowToTop(self.game_hwnd)
                except Exception:
                    pass

    # ─── 游戏窗口前台/可见性检测 (WinEvent 事件驱动) ─────────────────────

    def _poll_game_visible(self) -> bool:
        """一次性查询游戏窗口当前是否在前台且可见。

        只在启动时取初值、以及 WinEvent 回调里状态变化时复核用，
        不在渲染循环里调用。
        """
        if not self.game_hwnd:
            return True
        try:
            import win32gui
            if not win32gui.IsWindow(self.game_hwnd):
                return False
            return (win32gui.GetForegroundWindow() == self.game_hwnd
                    and not win32gui.IsIconic(self.game_hwnd)
                    and win32gui.IsWindowVisible(self.game_hwnd))
        except Exception:
            return self._game_visible  # 查询失败时保持原状

    def _start_win_event_hook(self):
        """启动 WinEvent 钩子线程。

        用 SetWinEventHook + WINEVENT_OUTOFCONTEXT 订阅系统窗口事件，
        仅在游戏窗口进入/离开前台、最小化/恢复、显示/隐藏、销毁时回调。
        相比每帧轮询 GetForegroundWindow，平时零 CPU 开销。
        """
        if not self.game_hwnd:
            return  # 无游戏窗口句柄时跳过 (如 demo 模式)
        # 初始状态：先轮询一次拿到准确初值 (事件只在未来变化时才来)
        self._game_visible = self._poll_game_visible()
        self._win_event_thread_obj = threading.Thread(
            target=self._win_event_pump, daemon=True)
        self._win_event_thread_obj.start()

    def _win_event_pump(self):
        """WinEvent 钩子线程主体：注册钩子 + 跑 message pump 分发回调。

        WINEVENT_OUTOFCONTEXT 的事件会投递到「调用 SetWinEventHook 的线程」
        的消息队列，必须由该线程自己 pump message 才能触发回调，所以
        SetWinEventHook 必须在本线程内调用。
        """
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        PM_REMOVE = 0x0001

        # WinEvent 回调签名
        WinEventProc = ctypes.WINFUNCTYPE(
            None,
            wintypes.HANDLE,  # hWinEventHook
            wintypes.DWORD,   # event
            wintypes.HWND,    # hwnd
            wintypes.LONG,    # idObject
            wintypes.LONG,    # idChild
            wintypes.DWORD,   # dwEventThread
            wintypes.DWORD,   # dwmsEventTime
        )

        def on_event(hWinEventHook, event, hwnd, idObject, idChild,
                     dwEventThread, dwmsEventTime):
            # 只关心窗口本身 (idObject==0 即 OBJID_WINDOW)，忽略子对象/控件
            if idObject != 0:
                return
            self._on_win_event(event, hwnd)

        callback = WinEventProc(on_event)
        self._win_event_cb = callback  # 防 GC，否则 ctypes 回收会崩溃

        # 订阅相关事件 (每个 SetWinEventHook 接受单个 event 范围)
        hooks = []
        for ev in (EVENT_SYSTEM_FOREGROUND,
                   EVENT_SYSTEM_MINIMIZESTART,
                   EVENT_SYSTEM_MINIMIZEEND,
                   EVENT_OBJECT_SHOW,
                   EVENT_OBJECT_HIDE,
                   EVENT_OBJECT_DESTROY):
            h = user32.SetWinEventHook(ev, ev, None, callback, 0, 0,
                                       WINEVENT_OUTOFCONTEXT)
            if h:
                hooks.append(h)

        msg = wintypes.MSG()
        try:
            while self._running:
                # PeekMessage 取走所有待处理消息；WinEvent 回调在此期间被
                # 系统调用。无消息时小睡 20ms 避免空转 (事件到达后下次循环
                # 立即处理，最大延迟 ~20ms，对人眼无感)。
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.02)
        finally:
            for h in hooks:
                user32.UnhookWinEvent(h)

    def _on_win_event(self, event: int, hwnd):
        """WinEvent 回调：根据事件类型更新 _game_visible。

        - EVENT_SYSTEM_FOREGROUND: 前台变了，重算 (hwnd 可能是任意窗口)
        - 其它事件: 仅当 hwnd == game_hwnd 时才重算
        重算统一走 _poll_game_visible()，保证状态完全一致。
        """
        if not self.game_hwnd:
            return
        if event == EVENT_SYSTEM_FOREGROUND:
            pass  # 前台变化总要重算
        elif hwnd == self.game_hwnd:
            pass  # 事件针对游戏窗口本身
        else:
            return  # 与游戏无关的事件，忽略

        new_visible = self._poll_game_visible()
        if new_visible != self._game_visible:
            self._game_visible = new_visible
            print(f"[log] game window "
                  f"{'foreground' if new_visible else 'background/hidden'} "
                  f"-> overlay {'shown' if new_visible else 'hidden'}")

    # ─── 跟随游戏窗口位置 ─────────────────────────────────────────────────

    def _track_game_window(self):
        """每帧把 overlay 对齐到游戏窗口的真实屏幕位置 (ESP 贴附效果)。

        GRID_TOP_LEFT 是「相对于游戏窗口客户区左上角」的像素偏移；
        overlay 内部网格画在 (OFS_X, OFS_Y) 处，所以 overlay 屏幕左上角应为：
            game_client_screen_topleft + GRID_TOP_LEFT - (OFS_X, OFS_Y)
        """
        if not self.game_hwnd:
            return
        # 游戏不在前台/不可见时不重定位 (最小化时 ClientToScreen 会返回垃圾坐标)
        if not self._game_visible:
            self._last_track_x = None
            self._last_track_y = None
            return
        try:
            import win32gui
            # ClientToScreen 返回客户区左上角的屏幕坐标
            pt = win32gui.ClientToScreen(self.game_hwnd, (0, 0))
            target_x = pt[0] + GRID_TOP_LEFT[0] - OFS_X
            target_y = pt[1] + GRID_TOP_LEFT[1] - OFS_Y
        except Exception:
            return
        # 只在位置变化时重定位，避免每帧无谓调用
        if (target_x, target_y) != (self._last_track_x, self._last_track_y):
            set_window_position(max(0, target_x), max(0, target_y))
            self._last_track_x = target_x
            self._last_track_y = target_y

    # ─── Frame rendering ─────────────────────────────────────────────────

    def _draw_frame(self):
        # 游戏不在前台/不可见时 overlay 保持全透明 (不绘制任何内容)，
        # 避免漂浮在其它窗口之上。仅 begin/clear(BLANK)/end 刷新帧缓冲。
        if not self._game_visible:
            begin_drawing()
            clear_background(BLANK)
            end_drawing()
            return

        with self._lock:
            boxes = list(self._boxes)
            arrows = list(self._arrows)
            labels = list(self._labels)
            title = self._title_text

        begin_drawing()
        clear_background(BLANK)

        if title:
            self._draw_title(title)

        # 先画网格底层，再画 boxes/arrows/labels 叠在上面
        with self._lock:
            show_grid = self._show_grid
            grid_color = self._grid_color
            show_labels = self._show_grid_labels
        if show_grid:
            self._draw_grid(grid_color, show_labels)

        for box in boxes:
            self._draw_esp_box(box)

        for arrow in arrows:
            self._draw_esp_arrow(arrow)

        for lbl in labels:
            self._draw_label(lbl)

        end_drawing()

    # ─── Drawing primitives (the ESP look) ────────────────────────────────

    def _draw_grid(self, color, show_labels: bool):
        """画完整 8x8 网格：外框 + 内部网格线 + 行列标签 (A-H 上, 1-8 左)。"""
        gx = OFS_X
        gy = OFS_Y
        thin = 1

        # 内部竖线 (cols-1 条)
        for c in range(1, GRID_COLS):
            x = gx + c * CELL_W
            draw_line_ex(Vector2(x, gy), Vector2(x, gy + GRID_H), thin, color)
        # 内部横线 (rows-1 条)
        for r in range(1, GRID_ROWS):
            y = gy + r * CELL_H
            draw_line_ex(Vector2(gx, y), Vector2(gx + GRID_W, y), thin, color)

        # 外框 (粗一点)
        outer = Rectangle(gx, gy, GRID_W, GRID_H)
        draw_rectangle_lines_ex(outer, 2, color)

        if show_labels:
            col_letters = "ABCDEFGH"
            # 列标签 A-H: 顶行每个格子中心上方
            for c in range(GRID_COLS):
                cx = gx + c * CELL_W + CELL_W // 2
                self._draw_text_with_bg(col_letters[c], cx, gy - 18, 14, color, ESPColor.BLACK_BG)
            # 行标签 1-8: 左列每个格子中心左侧
            for r in range(GRID_ROWS):
                cy = gy + r * CELL_H + CELL_H // 2
                self._draw_text_with_bg(str(r + 1), gx - 16, cy - 7, 14, color, ESPColor.BLACK_BG)

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
    esp.draw_grid(color=ESPColor.CYAN, show_labels=True)

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
