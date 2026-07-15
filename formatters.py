"""Pure text formatters for Palworld REST API responses."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit


if TYPE_CHECKING:
    from .player_monitor import PlayerChanges, PlayerSummary


_SENSITIVE_KEY_PARTS = ("password", "token", "secret", "authorization")
_SETTING_KEYS = (
    "ServerName",
    "ServerDescription",
    "Difficulty",
    "ServerPlayerMaxNum",
    "ExpRate",
    "PalCaptureRate",
    "PalSpawnNumRate",
    "DayTimeSpeedRate",
    "NightTimeSpeedRate",
    "DeathPenalty",
    "bIsPvP",
    "bEnableFriendlyFire",
    "CrossplayPlatforms",
)
_PLAYER_NAME_KEYS = ("name", "accountName", "account_name")
_PLAYER_ID_KEYS = ("userId", "userid", "playerId", "playerid", "steamId", "steamid")
_PLAYER_LABEL_MAX_LENGTH = 80

_SETTINGS_REGISTRY: tuple[tuple[str, str, str, str], ...] = (
    (
        "ServerPlayerMaxNum",
        "服务器与容量",
        "最大玩家数",
        "服务器允许的最大在线玩家数。",
    ),
    ("GuildPlayerMaxNum", "服务器与容量", "公会人数上限", "单个公会允许的最大玩家数。"),
    (
        "CoopPlayerMaxNum",
        "服务器与容量",
        "合作人数上限",
        "合作游戏队伍允许的最大玩家数。",
    ),
    ("CrossplayPlatforms", "服务器与容量", "跨平台范围", "允许连接服务器的平台列表。"),
    ("bIsMultiplay", "服务器与容量", "多人游戏", "是否启用多人游戏模式。"),
    ("Region", "服务器与容量", "服务器区域", "服务器所属的区域设置。"),
    ("ExpRate", "游戏平衡", "经验倍率", "玩家与帕鲁获得经验的倍率。"),
    ("PalCaptureRate", "游戏平衡", "帕鲁捕获倍率", "捕获帕鲁的成功率倍率。"),
    ("PalSpawnNumRate", "游戏平衡", "帕鲁生成倍率", "地图中帕鲁生成数量的倍率。"),
    ("DayTimeSpeedRate", "游戏平衡", "白天速度倍率", "游戏内白天流逝速度倍率。"),
    ("NightTimeSpeedRate", "游戏平衡", "夜晚速度倍率", "游戏内夜晚流逝速度倍率。"),
    ("Difficulty", "游戏平衡", "难度", "服务器采用的整体难度预设。"),
    ("DeathPenalty", "生存规则", "死亡惩罚", "玩家死亡时应用的物品与帕鲁惩罚规则。"),
    (
        "PalEggDefaultHatchingTime",
        "生存规则",
        "帕鲁蛋孵化时间",
        "大型帕鲁蛋的默认孵化小时数。",
    ),
    ("DropItemAliveMaxHours", "生存规则", "掉落物保留时间", "地面掉落物保留的小时数。"),
    (
        "PlayerStomachDecreaceRate",
        "生存规则",
        "玩家饱食度消耗倍率",
        "玩家饱食度下降速度倍率。",
    ),
    (
        "PlayerStaminaDecreaceRate",
        "生存规则",
        "玩家体力消耗倍率",
        "玩家体力消耗速度倍率。",
    ),
    ("bHardcore", "生存规则", "硬核模式", "是否启用硬核模式规则。"),
    ("PlayerDamageRateAttack", "战斗", "玩家攻击伤害倍率", "玩家造成伤害的倍率。"),
    ("PlayerDamageRateDefense", "战斗", "玩家承受伤害倍率", "玩家受到伤害的倍率。"),
    ("PalDamageRateAttack", "战斗", "帕鲁攻击伤害倍率", "帕鲁造成伤害的倍率。"),
    ("PalDamageRateDefense", "战斗", "帕鲁承受伤害倍率", "帕鲁受到伤害的倍率。"),
    ("bIsPvP", "战斗", "玩家对战", "是否启用玩家之间的对战规则。"),
    ("bEnableFriendlyFire", "战斗", "友军伤害", "是否允许对友方造成伤害。"),
    ("BaseCampMaxNum", "基地与建筑", "世界基地上限", "世界中允许存在的基地总数。"),
    (
        "BaseCampMaxNumInGuild",
        "基地与建筑",
        "公会基地上限",
        "每个公会允许拥有的基地数。",
    ),
    (
        "BaseCampWorkerMaxNum",
        "基地与建筑",
        "基地工作帕鲁上限",
        "单个基地可工作的帕鲁数量上限。",
    ),
    ("BuildObjectHpRate", "基地与建筑", "建筑生命倍率", "建筑物耐久度倍率。"),
    (
        "BuildObjectDamageRate",
        "基地与建筑",
        "建筑承受伤害倍率",
        "建筑物受到攻击时的伤害倍率。",
    ),
    (
        "BuildObjectDeteriorationDamageRate",
        "基地与建筑",
        "建筑劣化倍率",
        "建筑随时间自然损耗的倍率。",
    ),
    ("CollectionDropRate", "资源与掉落", "采集掉落倍率", "采集资源时的掉落数量倍率。"),
    ("EnemyDropItemRate", "资源与掉落", "敌人掉落倍率", "击败敌人时的物品掉落倍率。"),
    ("WorkSpeedRate", "资源与掉落", "工作速度倍率", "基地工作速度倍率。"),
    (
        "CollectionObjectHpRate",
        "资源与掉落",
        "采集物生命倍率",
        "可采集物体的耐久度倍率。",
    ),
    (
        "CollectionObjectRespawnSpeedRate",
        "资源与掉落",
        "采集物重生速度倍率",
        "可采集物体的重生速度倍率。",
    ),
    ("ItemWeightRate", "资源与掉落", "物品重量倍率", "物品重量的倍率。"),
    ("bEnableFastTravel", "常用功能", "快速传送", "是否允许玩家使用快速传送。"),
    (
        "bEnableFastTravelOnlyBaseCamp",
        "常用功能",
        "仅基地快速传送",
        "是否仅允许从基地进行快速传送。",
    ),
    ("bShowPlayerList", "常用功能", "玩家列表", "是否允许显示服务器玩家列表。"),
    (
        "bExistPlayerAfterLogout",
        "常用功能",
        "离线保留角色",
        "玩家退出后是否在世界中保留角色。",
    ),
    ("bEnableInvaderEnemy", "常用功能", "入侵事件", "是否启用敌人入侵事件。"),
    ("EnablePredatorBossPal", "常用功能", "掠食者首领", "是否生成掠食者首领帕鲁。"),
    (
        "bAllowClientMod",
        "其他常用参数",
        "允许客户端 Mod",
        "是否允许使用客户端 Mod 的玩家连接。",
    ),
    ("bEnableVoiceChat", "其他常用参数", "语音聊天", "是否启用游戏内语音聊天。"),
    (
        "AutoSaveSpan",
        "其他常用参数",
        "自动保存间隔",
        "服务器自动保存世界数据的秒数间隔。",
    ),
    ("SupplyDropSpan", "其他常用参数", "补给投放间隔", "补给投放事件的秒数间隔。"),
    (
        "ChatPostLimitPerMinute",
        "其他常用参数",
        "每分钟聊天上限",
        "单名玩家每分钟允许发送的聊天消息数。",
    ),
    (
        "bIsShowJoinLeftMessage",
        "其他常用参数",
        "加入离开消息",
        "是否显示玩家加入与离开服务器的消息。",
    ),
)


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _text(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return "未知"


def _safe_player_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    replaced = "".join(
        character if character.isprintable() else " " for character in value
    )
    collapsed = " ".join(replaced.split())
    if not collapsed:
        return None
    if len(collapsed) > _PLAYER_LABEL_MAX_LENGTH:
        return collapsed[: _PLAYER_LABEL_MAX_LENGTH - 1].rstrip() + "…"
    return collapsed


def _player_identity(player: Mapping[str, Any]) -> str:
    for key in (*_PLAYER_NAME_KEYS, *_PLAYER_ID_KEYS):
        value = player.get(key)
        label = _safe_player_label(value)
        if label is not None:
            return label
        if key in _PLAYER_ID_KEYS and _is_finite_number(value):
            return _safe_player_label(str(value)) or "未知玩家"
    return "未知玩家"


def _setting_value(value: Any) -> str:
    if value is None:
        return "未知"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        safe_values = [
            str(item) for item in value if isinstance(item, (str, int, float, bool))
        ]
        return ", ".join(safe_values) if safe_values else "未知"
    return "未知"


def _number(value: Any) -> str:
    if not _is_finite_number(value):
        return "未知"
    return str(value)


def format_server_info(data: Mapping[str, Any]) -> str:
    """Format the public server identity fields."""
    return "\n".join(
        (
            "Palworld 服务器状态",
            f"名称：{_text(data.get('servername'))}",
            f"版本：{_text(data.get('version'))}",
            f"描述：{_text(data.get('description'))}",
            f"世界 GUID：{_text(data.get('worldguid'))}",
        )
    )


def _server_address(
    settings: Mapping[str, Any], api_base_url: str, game_server_host: str = ""
) -> str:
    public_ip = _safe_player_label(settings.get("PublicIP"))
    configured_host = _safe_player_label(game_server_host)
    parsed_host: str | None = None
    if isinstance(api_base_url, str):
        try:
            parsed_host = urlsplit(api_base_url).hostname
        except ValueError:
            parsed_host = None
    host = public_ip or configured_host or _safe_player_label(parsed_host)
    port = settings.get("PublicPort")
    safe_port = (
        str(port)
        if isinstance(port, int) and not isinstance(port, bool) and 0 < port <= 65535
        else None
    )
    if host is None or safe_port is None:
        return "未知"
    return f"{host}:{safe_port}"


def build_info_card_data(
    *,
    info: Mapping[str, Any],
    players: Sequence[Mapping[str, Any]] | None,
    settings: Mapping[str, Any],
    metrics: Mapping[str, Any],
    api_base_url: str,
    query_time: str,
    game_server_host: str = "",
) -> dict[str, Any]:
    """Combine only the public REST fields needed by the info image."""
    player_labels: list[str] = []
    for raw_player in players or ():
        player = raw_player if isinstance(raw_player, Mapping) else {}
        name = _safe_player_label(player.get("name")) or "名称未知"
        level = player.get("level")
        if _is_finite_number(level):
            name += f"（Lv. {level}）"
        player_labels.append(name)

    return {
        "server_name": _text(info.get("servername")),
        "version": _text(info.get("version")),
        "description": _text(info.get("description")),
        "server_address": _server_address(
            settings, api_base_url, game_server_host=game_server_host
        ),
        "online": (
            f"{_number(metrics.get('currentplayernum'))} / "
            f"{_number(metrics.get('maxplayernum'))}"
        ),
        "uptime": format_uptime(metrics.get("uptime")),
        "game_days": _number(metrics.get("days")),
        "base_camps": _number(metrics.get("basecampnum")),
        "players": tuple(player_labels),
        "players_known": players is not None,
        "query_time": _safe_player_label(query_time) or "未知",
    }


def build_settings_rows(data: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    """Return detailed Chinese rows from the exact safe settings registry."""
    rows: list[dict[str, str]] = []
    for key, section, label, description in _SETTINGS_REGISTRY:
        lowered_key = key.casefold()
        if any(part in lowered_key for part in _SENSITIVE_KEY_PARTS):
            continue
        rows.append(
            {
                "section": section,
                "label": label,
                "key": key,
                "value": _setting_value(data.get(key)),
                "description": description,
            }
        )
    return tuple(rows)


def format_players(players: Sequence[Mapping[str, Any]], limit: int) -> str:
    """Format a privacy-preserving, bounded online player list."""
    total = len(players)
    if total == 0:
        return "当前无人在线"

    safe_limit = max(1, limit)
    lines = [f"当前在线：{total} 人"]
    for index, player in enumerate(players[:safe_limit], start=1):
        safe_player = player if isinstance(player, Mapping) else {}
        line = f"{index}. {_player_identity(safe_player)}"
        level = safe_player.get("level")
        if _is_finite_number(level):
            line += f"（Lv. {level}）"
        lines.append(line)

    hidden = total - safe_limit
    if hidden > 0:
        lines.append(f"另有 {hidden} 人未展示")
    return "\n".join(lines)


def format_settings(data: Mapping[str, Any]) -> str:
    """Format only explicitly allowlisted, non-sensitive server settings."""
    lines = ["Palworld 服务器设置"]
    for key in _SETTING_KEYS:
        lowered_key = key.lower()
        if key not in data or any(part in lowered_key for part in _SENSITIVE_KEY_PARTS):
            continue
        lines.append(f"{key}：{_setting_value(data[key])}")
    return "\n".join(lines)


def format_uptime(value: Any) -> str:
    """Format a finite non-negative numeric duration in seconds."""
    if not _is_finite_number(value) or value < 0:
        return "未知"

    total_seconds = int(value)
    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)
    clock = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{days}天 {clock}" if days else clock


def format_metrics(data: Mapping[str, Any]) -> str:
    """Format numeric server performance metrics without raising on bad values."""
    return "\n".join(
        (
            "Palworld 性能指标",
            f"服务器 FPS：{_number(data.get('serverfps'))}",
            f"帧时间：{_number(data.get('serverframetime'))} ms",
            (
                f"在线人数：{_number(data.get('currentplayernum'))} / "
                f"{_number(data.get('maxplayernum'))}"
            ),
            f"运行时间：{format_uptime(data.get('uptime'))}",
            f"基地数量：{_number(data.get('basecampnum'))}",
            f"游戏天数：{_number(data.get('days'))}",
        )
    )


def _change_name(player: PlayerSummary) -> str:
    name = _safe_player_label(player.name)
    if name is None:
        name = _safe_player_label(player.player_id) or "未知玩家"
    if _is_finite_number(player.level):
        name += f"（Lv. {player.level}）"
    return name


def _online_count(value: Any) -> str:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return str(value)
    return "未知"


def _change_block(
    players: tuple[PlayerSummary, ...], symbol: str, action: str, compact: bool
) -> list[str]:
    if compact:
        return [f"{symbol} 玩家{action}服务器", f"玩家：{_change_name(players[0])}"]
    return [
        f"{symbol} {len(players)} 名玩家{action}服务器",
        *(f"- {_change_name(player)}" for player in players),
    ]


def format_player_changes(
    changes: PlayerChanges,
    notify_join: bool,
    notify_leave: bool,
    *,
    timestamp: str | None = None,
) -> str | None:
    """Format enabled player changes as one privacy-preserving message."""
    joined = changes.joined if notify_join else ()
    left = changes.left if notify_leave else ()
    if not joined and not left:
        return None

    mixed = bool(joined and left)
    lines: list[str] = []
    if joined:
        lines.extend(
            _change_block(joined, "🟢", "进入", len(joined) == 1 and not mixed)
        )
    if left:
        lines.extend(_change_block(left, "🔴", "离开", len(left) == 1 and not mixed))
    lines.append(f"当前在线：{_online_count(changes.online_count)} 人")
    if timestamp is not None:
        lines.append(f"时间：{_setting_value(timestamp)}")
    return "\n".join(lines)
