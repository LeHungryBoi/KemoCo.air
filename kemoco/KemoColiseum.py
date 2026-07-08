# -*- encoding=utf8 -*-
__author__ = "fatty"

from airtest.core.api import *
from airtest.cli.parser import cli_setup
import time
import cv2
import logging

logging.getLogger("airtest").setLevel(logging.ERROR)

from .globals import g


def main():
    if not cli_setup():
        auto_setup(__file__, logdir=True,
                   devices=["Windows:///?title_re=^KemoColiseum$",],
                   project_root="D:/Documents/Desktop/KemoCo.air")

    from .remove_titlebar import remove_titlebar
    from .overlay import ESPOverlay, ESPColor

    g.reset()
    g.hwnd = remove_titlebar()

    # 启动 ESP overlay (传入游戏窗口句柄，overlay 会每帧对齐窗口真实屏幕位置)
    g.esp = ESPOverlay(game_hwnd=g.hwnd)
    g.esp.start()
    print("[log] overlay started")

    g.in_match = False
    g.running = True
    try:
        while g.running:
            if exists(Template(r"tpl1783316818562.png", record_pos=(0.091, -0.236), resolution=(1104, 720))) and exists(Template(r"tpl1783316830805.png", record_pos=(0.083, 0.205), resolution=(1104, 720))):
                if not g.in_match:
                    g.in_match = True
                    print("[log] enter match")
                    g.esp.set_title("MATCH ACTIVE")
                    # 画完整 8x8 网格用于肉眼对齐
                    g.esp.draw_grid(color=ESPColor.CYAN, show_labels=True)
            else:
                if g.in_match:
                    g.in_match = False
                    print("[log] exit match")
                    g.esp.clear()  # 清空 overlay
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[log] shutting down")
    finally:
        g.running = False
        if g.esp is not None:
            g.esp.shutdown()


if __name__ == "__main__":
    main()
