"""
文字动画渲染器 - 逐字弹出效果
横排：字符从左到右逐个弹出
竖排：字符从上到下逐个弹出
"""
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# 中文字体路径
FONT_PATHS = {
    "黑体": "C:/Windows/Fonts/simhei.ttf",
    "微软雅黑": "C:/Windows/Fonts/msyh.ttc",
}

# 配色方案（深色背景 + 高对比文字）
COLOR_SCHEMES = [
    {"bg": (18, 18, 24), "text": (255, 255, 255), "accent": (0, 200, 255)},
    {"bg": (24, 18, 30), "text": (255, 255, 255), "accent": (255, 100, 150)},
    {"bg": (18, 24, 20), "text": (255, 255, 255), "accent": (100, 255, 130)},
    {"bg": (28, 22, 18), "text": (255, 245, 230), "accent": (255, 200, 80)},
]


def _get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """获取字体对象"""
    for name in [font_name, "黑体", "微软雅黑"]:
        path = FONT_PATHS.get(name)
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)


def _calc_char_positions_h(text: str, draw: ImageDraw.ImageDraw,
                           font: ImageFont.FreeTypeFont, width: int,
                           height: int, font_size: int) -> list:
    """
    计算横排每个字的 (x, y) 位置
    基于完整文本居中布局，返回每个字的绝对坐标
    """
    margin = 80
    max_width = width - 2 * margin
    line_height = font_size + 20

    # 按完整文本换行
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)

    total_height = len(lines) * line_height
    start_y = (height - total_height) // 2

    # 计算每个字的坐标
    positions = []
    for line_idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x_cursor = (width - line_width) // 2
        y = start_y + line_idx * line_height
        for char in line:
            cbbox = draw.textbbox((0, 0), char, font=font)
            char_w = cbbox[2] - cbbox[0]
            positions.append((x_cursor, y))
            x_cursor += char_w

    return positions, total_height, start_y


def _calc_char_positions_v(text: str, draw: ImageDraw.ImageDraw,
                           font: ImageFont.FreeTypeFont, width: int,
                           height: int, font_size: int) -> list:
    """
    计算竖排每个字的 (x, y) 位置
    从右到左排列列，每列从上到下
    """
    max_chars = 7
    col_width = font_size + 30
    line_height = font_size + 16

    # 分列
    columns = []
    for i in range(0, len(text), max_chars):
        columns.append(text[i:i + max_chars])

    total_width = len(columns) * col_width
    start_x = (width - total_width) // 2 + col_width // 2
    total_col_height = max_chars * line_height
    start_y = (height - total_col_height) // 2

    positions = []
    for col_idx, column in enumerate(columns):
        x = start_x + (len(columns) - 1 - col_idx) * col_width
        for row_idx, char in enumerate(column):
            y = start_y + row_idx * line_height
            cbbox = draw.textbbox((0, 0), char, font=font)
            char_w = cbbox[2] - cbbox[0]
            positions.append((x - char_w // 2, y))

    return positions, total_width, start_x, total_col_height, start_y


def render_progressive(text: str, orientation: str, visible_chars: int,
                       width: int = 1080, height: int = 1920,
                       scheme: dict = None, font_name: str = "黑体") -> "np.ndarray":
    """
    渲染逐字弹出的文字帧

    Args:
        text: 完整文本
        orientation: "h" 横排 / "v" 竖排
        visible_chars: 显示前 N 个字（0 = 全黑背景）
        scheme: 配色方案
    """
    import numpy as np
    scheme = scheme or COLOR_SCHEMES[0]
    img = Image.new("RGB", (width, height), scheme["bg"])
    draw = ImageDraw.Draw(img)

    if visible_chars <= 0:
        return np.array(img)

    font_size = 72
    font = _get_font(font_name, font_size)
    visible = min(visible_chars, len(text))
    visible_text = text[:visible]

    if orientation == "v":
        # 竖排
        positions, total_w, start_x, total_h, start_y = \
            _calc_char_positions_v(text, draw, font, width, height, font_size)

        for i in range(visible):
            x, y = positions[i]
            # 最新弹出的字用 accent 色，其余用 text 色
            color = scheme["accent"] if i == visible - 1 else scheme["text"]
            draw.text((x, y), text[i], font=font, fill=color)

        # 装饰竖线
        accent_x = start_x + total_w + 10
        accent_y1 = start_y - 20
        accent_y2 = start_y + total_h // 2
        draw.line([(accent_x, accent_y1), (accent_x, accent_y2)],
                  fill=scheme["accent"], width=3)
    else:
        # 横排
        positions, total_h, start_y = \
            _calc_char_positions_h(text, draw, font, width, height, font_size)

        for i in range(visible):
            x, y = positions[i]
            color = scheme["accent"] if i == visible - 1 else scheme["text"]
            draw.text((x, y), text[i], font=font, fill=color)

        # 装饰横线
        accent_y = start_y + total_h + 30
        accent_x1 = (width - 200) // 2
        accent_x2 = accent_x1 + 200
        draw.line([(accent_x1, accent_y), (accent_x2, accent_y)],
                  fill=scheme["accent"], width=3)

    return np.array(img)


def render_intro_frame(title: str, progress: float,
                       width: int = 1080, height: int = 1920) -> "np.ndarray":
    """
    片头帧（逐字弹出）
    progress: 0.0-1.0
    """
    import numpy as np
    scheme = COLOR_SCHEMES[0]
    img = Image.new("RGB", (width, height), scheme["bg"])
    draw = ImageDraw.Draw(img)

    title_font = _get_font("黑体", 96)
    visible = math.ceil(progress * len(title))
    visible = min(visible, len(title))

    if visible > 0:
        # 基于完整标题居中
        full_bbox = draw.textbbox((0, 0), title, font=title_font)
        full_w = full_bbox[2] - full_bbox[0]
        x_cursor = (width - full_w) // 2
        y = height // 2 - 80

        for i in range(visible):
            char = title[i]
            color = scheme["accent"] if i == visible - 1 else scheme["text"]
            draw.text((x_cursor, y), char, font=title_font, fill=color)
            cbbox = draw.textbbox((0, 0), char, font=title_font)
            x_cursor += cbbox[2] - cbbox[0]

    return np.array(img)
