"""Local Pillow renderers for Palworld information cards."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CARD_WIDTH = 1200
_SETTINGS_ROWS_PER_SECTION = 6
_SETTINGS_ROW_HEIGHT = 68
_SETTINGS_SECTION_HEADER_HEIGHT = 76
_SETTINGS_SECTION_GAP = 18
_SETTINGS_FOOTER_HEIGHT = 80
_SETTINGS_COLUMN_X = (58, 607)
_SETTINGS_COLUMN_WIDTH = 535
_BACKGROUND = "#0b1220"
_PANEL = "#151f32"
_PANEL_ALT = "#1b2940"
_PRIMARY = "#f5f7fb"
_SECONDARY = "#aab7ca"
_ACCENT = "#63d7c8"
_SETTINGS_SECTION_COLORS = (
    "#8fd9ff",
    "#f5c879",
    "#c8a6ff",
    "#ff9e9e",
    "#76e0b2",
    "#7ec8ff",
    "#77d7c5",
    "#d6b37c",
)
_FONT_CANDIDATES = (
    Path("/AstrBot/data/fonts/MiSans-Normal.ttf"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/custom/MiSans-Normal.ttf"),
)


class ChineseFontUnavailableError(RuntimeError):
    """Raised when no local Chinese-capable font can be found."""


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = list(_FONT_CANDIDATES)
    if bold:
        candidates.insert(0, Path("/AstrBot/data/fonts/MiSans-Normal.ttf"))
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    raise ChineseFontUnavailableError("未找到可用的本地中文字体。")


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int
) -> list[str]:
    source = text if isinstance(text, str) and text else "未知"
    lines: list[str] = []
    for paragraph in source.splitlines() or [source]:
        current = ""
        for character in paragraph:
            candidate = current + character
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current)
                current = character
            else:
                current = candidate
        lines.append(current or " ")
    return lines


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _fit_text(
    draw: ImageDraw.ImageDraw,
    value: Any,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    text = str(value)
    if draw.textlength(text, font=font) <= max_width:
        return text
    suffix = "…"
    while text and draw.textlength(text + suffix, font=font) > max_width:
        text = text[:-1]
    return text + suffix


def _settings_section_height(row_count: int) -> int:
    return (
        _SETTINGS_SECTION_HEADER_HEIGHT
        + max(_SETTINGS_ROWS_PER_SECTION, row_count) * _SETTINGS_ROW_HEIGHT
    )


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    value: Any,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    lines = _wrap(draw, str(value), font, max_width)
    if len(lines) <= max_lines:
        return lines
    fitted = lines[:max_lines]
    fitted[-1] = _fit_text(draw, fitted[-1] + "…", font, max_width)
    return fitted


def _draw_settings_chip(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    *,
    fill: str,
    outline: str,
    max_width: int,
) -> int:
    text_width = int(draw.textlength(text, font=font) * 1.1)
    padding = 30
    width = min(text_width + padding, max_width)
    display_text = _fit_text(draw, text, font, max(1, width - padding))
    draw.rounded_rectangle((x, y, x + width, y + 38), 19, fill=fill, outline=outline)
    draw.text((x + 15, y + 9), display_text, font=font, fill=_PRIMARY)
    return x + width + 9


def _draw_settings_section(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    title: str,
    rows: Sequence[Mapping[str, str]],
    accent: str,
    section_font: ImageFont.FreeTypeFont,
    label_font: ImageFont.FreeTypeFont,
    field_font: ImageFont.FreeTypeFont,
    body_font: ImageFont.FreeTypeFont,
) -> None:
    height = _settings_section_height(len(rows))
    draw.rounded_rectangle(
        (x, y, x + width, y + height), 17, fill="#19263a", outline="#30445f"
    )
    draw.rounded_rectangle((x, y, x + width, y + 46), 17, fill="#22344d")
    draw.rectangle((x, y + 29, x + width, y + 46), fill="#22344d")
    draw.text((x + 17, y + 13), title, font=section_font, fill=accent)

    header_y = y + 52
    draw.text(
        (x + 16, header_y), "中文参数 / 原始字段", font=field_font, fill="#8095ae"
    )
    draw.text((x + 228, header_y), "当前值", font=field_font, fill="#8095ae")
    draw.text((x + 330, header_y), "中文说明", font=field_font, fill="#8095ae")

    row_y = y + 76
    for index, row in enumerate(rows):
        if index % 2 == 0:
            draw.rectangle((x + 1, row_y, x + width - 1, row_y + 68), fill="#162236")
        label = _fit_text(draw, row.get("label", "未知"), label_font, 190)
        key = _fit_text(draw, row.get("key", ""), field_font, 190)
        value = _fit_text(draw, row.get("value", "未知"), label_font, 92)
        description = _fit_lines(
            draw, row.get("description", ""), body_font, 180, max_lines=2
        )
        draw.text((x + 16, row_y + 10), label, font=label_font, fill=_PRIMARY)
        draw.text((x + 16, row_y + 38), key, font=field_font, fill="#66809d")
        value_fill = (
            "#65d79f" if value == "是" else "#ef8d8d" if value == "否" else accent
        )
        draw.text((x + 228, row_y + 10), value, font=label_font, fill=value_fill)
        for line_index, line in enumerate(description):
            draw.text(
                (x + 330, row_y + 10 + line_index * 22),
                line,
                font=body_font,
                fill="#91a5bd",
            )
        row_y += _SETTINGS_ROW_HEIGHT


def render_info_card(data: Mapping[str, Any]) -> bytes:
    """Render one adaptive 1200-pixel-wide server information PNG."""
    title_font = _font(46, bold=True)
    heading_font = _font(28, bold=True)
    body_font = _font(25)
    small_font = _font(20)
    probe = Image.new("RGB", (CARD_WIDTH, 100), _BACKGROUND)
    probe_draw = ImageDraw.Draw(probe)
    description_lines = _wrap(
        probe_draw, str(data.get("description", "未知")), body_font, 1040
    )
    players = data.get("players")
    safe_players = (
        tuple(str(player) for player in players)
        if isinstance(players, Sequence) and not isinstance(players, (str, bytes))
        else ()
    )
    players_known = data.get("players_known", True) is True
    player_lines = safe_players or (("当前无人在线",) if players_known else ("未知",))
    height = 684 + len(description_lines) * 36 + len(player_lines) * 38
    image = Image.new("RGB", (CARD_WIDTH, height), _BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((48, 42, 1152, 154), 28, fill=_PANEL)
    draw.text(
        (82, 70), str(data.get("server_name", "未知")), font=title_font, fill=_PRIMARY
    )
    version = str(data.get("version", "未知"))
    version_width = draw.textlength(version, font=small_font)
    draw.text((1110 - version_width, 89), version, font=small_font, fill=_SECONDARY)

    draw.rounded_rectangle((48, 178, 1152, 306), 22, fill=_PANEL_ALT)
    draw.text((78, 199), "服务器地址", font=small_font, fill=_SECONDARY)
    draw.text(
        (244, 196),
        str(data.get("server_address", "未知")),
        font=heading_font,
        fill=_ACCENT,
    )
    draw.text((78, 255), "在线", font=small_font, fill=_SECONDARY)
    draw.text(
        (155, 249), str(data.get("online", "未知")), font=heading_font, fill=_PRIMARY
    )
    draw.text((350, 255), "游戏天数", font=small_font, fill=_SECONDARY)
    draw.text(
        (462, 249),
        str(data.get("game_days", "未知")),
        font=heading_font,
        fill=_PRIMARY,
    )
    draw.text((670, 255), "基地数量", font=small_font, fill=_SECONDARY)
    draw.text(
        (782, 249),
        str(data.get("base_camps", "未知")),
        font=heading_font,
        fill=_PRIMARY,
    )

    y = 330
    description_height = 74 + len(description_lines) * 36
    draw.rounded_rectangle((48, y, 1152, y + description_height), 22, fill=_PANEL)
    draw.text((78, y + 22), "服务器描述", font=heading_font, fill=_PRIMARY)
    for line in description_lines:
        y += 36
        draw.text((78, y + 28), line, font=body_font, fill=_SECONDARY)
    y = 330 + description_height + 24

    players_height = 96 + len(player_lines) * 38
    draw.rounded_rectangle((48, y, 1152, y + players_height), 22, fill=_PANEL)
    draw.text((78, y + 22), "在线玩家", font=heading_font, fill=_PRIMARY)
    for index, player in enumerate(player_lines, start=1):
        draw.text(
            (82, y + 64 + index * 34),
            f"{index}. {player}" if safe_players else player,
            font=body_font,
            fill=_SECONDARY,
        )
    y += players_height + 24

    draw.text(
        (58, y),
        f"服务器运行：{data.get('uptime', '未知')}",
        font=small_font,
        fill=_SECONDARY,
    )
    query = str(data.get("query_time", "未知"))
    query_width = draw.textlength(query, font=small_font)
    draw.text((1142 - query_width, y), query, font=small_font, fill=_SECONDARY)
    return _png(image)


def render_settings_cards(
    rows: Sequence[Mapping[str, str]],
    *,
    server_address: str,
    query_time: str,
    server_password: str | None = None,
) -> tuple[bytes, ...]:
    """Render all settings as one v6-style two-column local PNG."""
    title_font = _font(38, bold=True)
    eyebrow_font = _font(14)
    time_font = _font(16, bold=True)
    chip_font = _font(14)
    section_font = _font(19, bold=True)
    label_font = _font(16, bold=True)
    field_font = _font(11)
    body_font = _font(14)

    grouped: dict[str, list[Mapping[str, str]]] = {}
    for row in rows:
        section = str(row.get("section", "其他常用参数"))
        grouped.setdefault(section, []).append(row)
    sections = tuple(grouped.items())
    paired_sections = tuple(
        sections[index : index + 2] for index in range(0, len(sections), 2)
    )
    grid_height = (
        sum(
            max(_settings_section_height(len(section_rows)) for _, section_rows in pair)
            for pair in paired_sections
        )
        + max(0, len(paired_sections) - 1) * _SETTINGS_SECTION_GAP
    )
    hero_height = 240
    height = 30 + hero_height + 26 + grid_height + _SETTINGS_FOOTER_HEIGHT
    image = Image.new("RGB", (CARD_WIDTH, height), _BACKGROUND)
    draw = ImageDraw.Draw(image)

    card_left = 40
    card_right = 1160
    draw.rounded_rectangle(
        (card_left, 30, card_right, height - 30),
        24,
        fill="#101827",
        outline="#334766",
    )
    hero_bottom = 30 + hero_height
    for offset in range(card_right - card_left):
        ratio = offset / max(1, card_right - card_left - 1)
        start = (29, 53, 87)
        end = (23, 76, 75)
        color = tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3))
        draw.line((card_left + offset, 30, card_left + offset, hero_bottom), fill=color)
    draw.rounded_rectangle(
        (card_left, 30, card_right, hero_bottom), 24, outline="#334766", width=1
    )

    draw.text((74, 64), "PALWORLD SERVER SETTINGS", font=eyebrow_font, fill="#83e3d4")
    draw.text((74, 92), "服务器参数设置", font=title_font, fill=_PRIMARY)
    time_left = 805
    draw.rounded_rectangle(
        (time_left, 58, 1126, 126),
        13,
        fill="#10243a",
        outline="#486078",
    )
    draw.text((time_left + 18, 72), "生成时间", font=eyebrow_font, fill="#8ea4bf")
    draw.text((time_left + 18, 94), query_time, font=time_font, fill=_PRIMARY)

    value_by_key = {
        str(row.get("key", "")): str(row.get("value", "未知")) for row in rows
    }
    chip_left = 74
    chip_y = 166
    chip_right = 1126
    chips = (
        (f"地址  {server_address}", "#102f47", "#2f688e"),
        (
            f"最多玩家 {value_by_key.get('ServerPlayerMaxNum', '未知')}",
            "#1e644f",
            "#3e8a70",
        ),
        (f"PvP {value_by_key.get('bIsPvP', '未知')}", "#314f7c", "#5d79a1"),
        (
            f"难度 {value_by_key.get('Difficulty', '未知')}",
            "#674d2b",
            "#9b7544",
        ),
        (
            str(value_by_key.get("CrossplayPlatforms", "跨平台未知")),
            "#453f72",
            "#6f68a3",
        ),
    )
    for line_index, line_chips in enumerate((chips[:3], chips[3:])):
        chip_x = chip_left
        slot_width = (chip_right - chip_left - 9 * (len(line_chips) - 1)) // len(
            line_chips
        )
        for chip_text, fill, outline in line_chips:
            chip_x = _draw_settings_chip(
                draw,
                chip_x,
                chip_y + line_index * 46,
                chip_text,
                chip_font,
                fill=fill,
                outline=outline,
                max_width=slot_width,
            )

    grid_y = hero_bottom + 26
    for pair_index, pair in enumerate(paired_sections):
        row_height = max(
            _settings_section_height(len(section_rows)) for _, section_rows in pair
        )
        for column_index, (section, section_rows) in enumerate(pair):
            _draw_settings_section(
                draw,
                x=_SETTINGS_COLUMN_X[column_index],
                y=grid_y,
                width=_SETTINGS_COLUMN_WIDTH,
                title=section,
                rows=section_rows,
                accent=_SETTINGS_SECTION_COLORS[
                    (pair_index * 2 + column_index) % len(_SETTINGS_SECTION_COLORS)
                ],
                section_font=section_font,
                label_font=label_font,
                field_font=field_font,
                body_font=body_font,
            )
        grid_y += row_height + _SETTINGS_SECTION_GAP

    if server_password is not None:
        badge_text = f"进入密码  {server_password}"
        padding = 34
        text_width = int(draw.textlength(badge_text, font=body_font) * 1.1)
        badge_width = text_width + padding
        left = max(680, 1146 - badge_width)
        available_width = 1146 - left - padding
        display_text = _fit_text(draw, badge_text, body_font, max(1, available_width))
        draw.rounded_rectangle(
            (left, height - 68, 1146, height - 30),
            14,
            fill="#123d35",
            outline="#286653",
        )
        draw.text((left + 17, height - 60), display_text, font=body_font, fill="#87b8a9")
    return (_png(image),)
