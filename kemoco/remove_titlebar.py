# -*- encoding=utf8 -*-
__author__ = "fatty"

import win32gui
import win32con

from .config import WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT


def remove_titlebar(title=WINDOW_TITLE, width=WINDOW_WIDTH, height=WINDOW_HEIGHT):
    """Remove title bar / border from a window by its title."""
    hwnd = win32gui.FindWindow(None, title)
    # 強制移除標題欄和邊框
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_SYSMENU |
               win32con.WS_MAXIMIZEBOX | win32con.WS_MINIMIZEBOX)
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
    # 移除擴展樣式
    exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    exstyle &= ~(win32con.WS_EX_CLIENTEDGE | win32con.WS_EX_WINDOWEDGE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exstyle)
    # 強制刷新並設定大小
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, width, height,
                          win32con.SWP_FRAMECHANGED | win32con.SWP_NOMOVE | win32con.SWP_SHOWWINDOW)
    return hwnd
