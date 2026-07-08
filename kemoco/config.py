# -*- encoding=utf8 -*-
"""
KemoCo 全局配置 / 常量
=======================
所有「不太会变」的设定集中放在这里。
逻辑代码 (overlay, KemoColiseum, remove_titlebar ...) 只引用，不修改。

需要新增全局常量时，请加到本文件对应区块，而不是散落在各业务模块里。
"""

# ─── 游戏窗口 ───────────────────────────────────────────────────────────────────
# 目标窗口标题 (与 Airtest device title_re 对应)
WINDOW_TITLE = "KemoColiseum"
# 无标题栏 / 无黑边情况下的渲染分辨率
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720


# ─── Match-3 网格 ───────────────────────────────────────────────────────────────
GRID_COLS = 8
GRID_ROWS = 8

# 絕對座標 (分辨率 1280x720 無標題欄 無黑邊 情况下得到的)
# 顺序: [左上, 右上, 左下, 右下]
ABSOLUTE_CORNERS = [
    [420, 116],  # 左上
    [860, 116],  # 右上
    [420, 556],  # 左下
    [860, 556],  # 右下
]

# 相對座標 (0.0~1.0)，顺序同上
RELATIVE_CORNERS = [
    [0.3281, 0.1611],  # 左上
    [0.6719, 0.1611],  # 右上
    [0.3281, 0.7722],  # 左下
    [0.6719, 0.7722],  # 右下
]

# ─── 派生值 (由上面的角点算出，避免到处重复计算) ───────────────────────────────
GRID_TOP_LEFT     = (ABSOLUTE_CORNERS[0][0], ABSOLUTE_CORNERS[0][1])
GRID_TOP_RIGHT    = (ABSOLUTE_CORNERS[1][0], ABSOLUTE_CORNERS[1][1])
GRID_BOTTOM_LEFT  = (ABSOLUTE_CORNERS[2][0], ABSOLUTE_CORNERS[2][1])
GRID_BOTTOM_RIGHT = (ABSOLUTE_CORNERS[3][0], ABSOLUTE_CORNERS[3][1])

GRID_W = GRID_BOTTOM_RIGHT[0] - GRID_TOP_LEFT[0]  # 440
GRID_H = GRID_BOTTOM_RIGHT[1] - GRID_TOP_LEFT[1]  # 440
CELL_W = GRID_W // GRID_COLS   # 55
CELL_H = GRID_H // GRID_ROWS   # 55


# ─── Overlay 视觉偏移 ───────────────────────────────────────────────────────────
# overlay 窗口相对于网格左上角的像素偏移 (留出边框/标签空间)
OFS_X = 10
OFS_Y = 20
