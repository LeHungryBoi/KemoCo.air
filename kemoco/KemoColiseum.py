# -*- encoding=utf8 -*-
__author__ = "fatty"

from airtest.core.api import *
from airtest.cli.parser import cli_setup
import time
import cv2
import logging

logging.getLogger("airtest").setLevel(logging.ERROR)

def main():
    if not cli_setup():
        auto_setup(__file__, logdir=True,
                   devices=["Windows:///?title_re=^KemoColiseum$",],
                   project_root="D:/Documents/Desktop/KemoCo.air")

    from .remove_titlebar import remove_titlebar

    hwnd = remove_titlebar()

    in_match = False
    while True:
        if exists(Template(r"tpl1783316818562.png", record_pos=(0.091, -0.236), resolution=(1104, 720))) and exists(Template(r"tpl1783316830805.png", record_pos=(0.083, 0.205), resolution=(1104, 720))):
            if not in_match:
                in_match = True
                print("[log] enter match")
            for pos in relative_corners:
                touch(pos)
                time.sleep(0.01)
            
        else:
            if in_match:
                in_match = False
                print("[log] exit match")
        time.sleep(1.0)


if __name__ == "__main__":
    main()

