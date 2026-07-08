# -*- encoding=utf8 -*-
__author__ = "fatty"

from airtest.core.api import *
from airtest.cli.parser import cli_setup
import time
import cv2
import logging

logging.getLogger("airtest").setLevel(logging.ERROR)

# 网格配置 (from llm.txt)
absolute_corners = [
    [420, 116], [860, 116],
    [420, 556], [860, 556],
]
relative_corners = [
    [0.3281, 0.1611], [0.6719, 0.1611],
    [0.3281, 0.7722], [0.6719, 0.7722],
]

def main():
    if not cli_setup():
        auto_setup(__file__, logdir=True,
                   devices=["Windows:///?title_re=^KemoColiseum$",],
                   project_root="D:/Documents/Desktop/KemoCo.air")

    from .remove_titlebar import remove_titlebar
    from .overlay import ESPOverlay, ESPColor

    hwnd = remove_titlebar()
    

    # 启动 ESP overlay
    esp = ESPOverlay()
    esp.start()
    print("[log] overlay started")

    in_match = False
    try:
        while True:
            if exists(Template(r"tpl1783316818562.png", record_pos=(0.091, -0.236), resolution=(1104, 720))) and exists(Template(r"tpl1783316830805.png", record_pos=(0.083, 0.205), resolution=(1104, 720))):
                if not in_match:
                    in_match = True
                    print("[log] enter match")
                    esp.set_title("MATCH ACTIVE")
                    # 标记四个角 (你当前 touch 的位置)
                    for i, pos in enumerate(relative_corners):
                        col = i % 2 * 7   # 左列=0, 右列=7
                        row = i // 2 * 7   # 上行=0, 下行=7
                        esp.add_box(col, row, color=ESPColor.CYAN,
                                    label=f"CORNER {i}", line_thickness=2.0)
                for pos in relative_corners:
                    touch(pos)
                    time.sleep(0.01)
            else:
                if in_match:
                    in_match = False
                    print("[log] exit match")
                    esp.clear()  # 清空 overlay
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[log] shutting down")
    finally:
        esp.shutdown()


if __name__ == "__main__":
    main()

