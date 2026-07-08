# Language
- 当用户说英文的时候, 永远用中文说话.

# 这是单人游戏 match 3/chess, overlay assist tells me which piece to move.
- This project is a single-player match-3 game.

# Project Info
- This is a match 3 game.
- I'm using Airtest from github.com/AirtestProject/Airtest.
- raylib from https://github.com/overdev/raylib-py.
- The grid is the match 3 grid; when the game goes into a match, the grid shows up.
- It's an 8x8 grid.
- This project is managed by uv.
- Run with `uv run kemo`.
- Use `uv add` to add dependencies.

# Coordinate Notes
```python
# 絕對座標 (分辨率 1280x720 無標題欄 無黑邊 情況下得到的)
absolute_corners = [
    [420, 116], # 左上
    [860, 116], # 右上
    [420, 556], # 左下
    [860, 556]  # 右下
]
# 相對座標 (0.0~1.0)
relative_corners = [
    [0.3281, 0.1611], # 左上
    [0.6719, 0.1611], # 右上
    [0.3281, 0.7722], # 左下
    [0.6719, 0.7722]  # 右下
]
```
