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
- preview the ESP look with `uv run python -c "from kemoco.overlay import demo; demo()`

# Config / Globals
- Two separate concerns, two files:
  - `kemoco/config.py` — **constants** that never change at runtime
    (window size, grid coords, derived values, overlay offsets).
    Logic files only `from .config import ...` and never mutate these.
  - `kemoco/globals.py` — **mutable runtime state** (the `g` singleton).
    Initialized to defaults here for cleanliness, but DOES change during
    execution (e.g. `g.esp`, `g.in_match`, `g.hwnd`, `g.running`).
- For runtime state, do `from .globals import g` then read/write `g.<field>`.
  Never `from .globals import in_match` — you'd lose live updates (rebinding).

# Coordinate Notes
- Absolute & relative corner coordinates are defined in `kemoco/config.py`
  (`ABSOLUTE_CORNERS` / `RELATIVE_CORNERS`). See that file for exact values.
- Reference (分辨率 1280x720 無標題欄 無黑邊):
```python
absolute_corners = [
    [420, 116], # 左上
    [860, 116], # 右上
    [420, 556], # 左下
    [860, 556]  # 右下
]
relative_corners = [
    [0.3281, 0.1611], # 左上
    [0.6719, 0.1611], # 右上
    [0.3281, 0.7722], # 左下
    [0.6719, 0.7722]  # 右下
]
```
