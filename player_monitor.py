"""Failure-aware player identity tracking for Palworld polling."""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_PLAYER_ID_KEYS = ("userId", "userid", "playerId", "playerid", "steamId", "steamid")
_PLAYER_NAME_KEYS = ("name",)


@dataclass(frozen=True, slots=True)
class PlayerSummary:
    player_id: str
    name: str
    level: Any = None


@dataclass(frozen=True, slots=True)
class PlayerChanges:
    joined: tuple[PlayerSummary, ...]
    left: tuple[PlayerSummary, ...]
    online_count: int

    @property
    def has_changes(self) -> bool:
        return bool(self.joined or self.left)


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _stable_id(player: Mapping[str, Any]) -> str | None:
    for key in _PLAYER_ID_KEYS:
        value = player.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if _finite_number(value):
            return str(value)
    return None


def _display_name(player: Mapping[str, Any], player_id: str) -> str:
    for key in _PLAYER_NAME_KEYS:
        value = player.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return f"{player_id}（名称未知）"


def _safe_level(value: Any) -> Any:
    return value if _finite_number(value) else None


class PlayerTracker:
    """Track stable player IDs without guessing across connection failures."""

    def __init__(self, warning_callback: Callable[[str], None] | None = None) -> None:
        self.last_players: dict[str, PlayerSummary] = {}
        self.has_baseline = False
        self.connection_healthy = False
        self._warning_callback = warning_callback
        self._warned_missing_id = False
        self._pending_names: dict[str, int] = {}
        self._notified_ids: set[str] = set()

    def observe(self, players: Sequence[Any]) -> PlayerChanges | None:
        """Record a successful poll and return changes after a healthy baseline."""
        current: dict[str, PlayerSummary] = {}
        has_game_name: dict[str, bool] = {}
        for player in players:
            if not isinstance(player, Mapping):
                continue
            player_id = _stable_id(player)
            if player_id is None:
                self._warn_missing_id_once()
                continue
            current[player_id] = PlayerSummary(
                player_id=player_id,
                name=_display_name(player, player_id),
                level=_safe_level(player.get("level")),
            )
            has_game_name[player_id] = isinstance(player.get("name"), str) and bool(
                player.get("name", "").strip()
            )

        online_count = len(players)
        if not self.has_baseline or not self.connection_healthy:
            self.last_players = current
            self._pending_names.clear()
            self._notified_ids.clear()
            self.has_baseline = True
            self.connection_healthy = True
            return None

        previous = self.last_players
        previous_ids = set(previous)
        current_ids = set(current)
        joined_ids = current_ids - previous_ids
        left_ids = previous_ids - current_ids

        joined: list[PlayerSummary] = []
        next_players: dict[str, PlayerSummary] = {}
        next_pending: dict[str, int] = {}

        for player_id in sorted(current_ids):
            incoming = current[player_id]
            previous_summary = previous.get(player_id)
            if player_id in joined_ids:
                if has_game_name[player_id]:
                    joined.append(incoming)
                    self._notified_ids.add(player_id)
                else:
                    next_pending[player_id] = 0
                next_players[player_id] = incoming
                continue

            if player_id in self._pending_names:
                if has_game_name[player_id]:
                    joined.append(incoming)
                    self._notified_ids.add(player_id)
                else:
                    attempts = self._pending_names[player_id] + 1
                    if attempts >= 2:
                        joined.append(incoming)
                        self._notified_ids.add(player_id)
                    else:
                        next_pending[player_id] = attempts
                next_players[player_id] = incoming
                continue

            if previous_summary is not None:
                next_players[player_id] = PlayerSummary(
                    player_id=player_id,
                    name=previous_summary.name,
                    level=incoming.level,
                )
            else:
                next_players[player_id] = incoming

        left: list[PlayerSummary] = []
        for player_id in sorted(left_ids):
            if player_id in self._pending_names:
                self._notified_ids.discard(player_id)
                continue
            left.append(previous[player_id])
            self._notified_ids.discard(player_id)

        self.last_players = next_players
        self._pending_names = next_pending
        self.connection_healthy = True

        return PlayerChanges(
            joined=tuple(joined),
            left=tuple(left),
            online_count=online_count,
        )

    def mark_failed(self) -> None:
        """Mark the connection unhealthy while preserving the last snapshot."""
        self.connection_healthy = False
        self._pending_names.clear()

    def _warn_missing_id_once(self) -> None:
        if self._warned_missing_id:
            return
        self._warned_missing_id = True
        if self._warning_callback is not None:
            try:
                self._warning_callback("忽略缺少稳定玩家 ID 的在线记录。")
            except Exception:
                pass
