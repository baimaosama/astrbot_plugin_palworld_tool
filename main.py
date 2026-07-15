from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star

try:
    from astrbot.api.message_components import Image
except ImportError:
    from astrbot.api.event import Image

from .api_client import (
    PalworldApiClient,
    PalworldAuthError,
    PalworldResponseError,
    PalworldUnavailableError,
)
from .formatters import (
    build_info_card_data,
    build_settings_rows,
    format_metrics,
    format_player_changes,
    format_players,
)
from .image_renderers import (
    ChineseFontUnavailableError,
    render_info_card,
    render_settings_cards,
)
from .player_monitor import PlayerTracker
from .subscriptions import normalize_subscriptions, subscriptions_for_storage


_SUBSCRIPTIONS_KEY = "notification_subscriptions"
_NO_AUTH_MESSAGE = "Palworld 插件尚未配置 API 认证信息。"
_AUTH_ERROR_MESSAGE = "Palworld API 认证失败，请检查用户名和密码。"
_UNAVAILABLE_MESSAGE = "暂时无法连接 Palworld 服务器。"
_INVALID_RESPONSE_MESSAGE = "Palworld API 返回了无法识别的数据。"
_REQUEST_FAILED_MESSAGE = "Palworld API 请求失败，请稍后重试。"
_SUBSCRIPTION_SAVE_FAILED_MESSAGE = "保存 Palworld 玩家通知订阅失败，请稍后重试。"
_SHUTDOWN_DENIED_MESSAGE = "你没有权限执行 Palworld 服务器关闭命令。"
_DEFAULT_SHUTDOWN_MESSAGE = "服务器即将重启，请稍后重新连接。"
_DEFAULT_TIMEZONE = "Asia/Shanghai"


def _positive_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(result) or result <= 0:
        return default
    return result


def _minimum_integer(value: Any, default: int, minimum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, result)


def _monitor_interval(value: Any) -> tuple[int, bool]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 30, True
    try:
        numeric = float(value)
    except OverflowError:
        return 30, True
    if not math.isfinite(numeric):
        return 30, True
    if numeric < 10:
        return 10, True
    return int(numeric), False


def _shutdown_whitelist(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def _shutdown_wait_seconds(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 10
    return value


def _timezone(value: Any) -> tuple[tzinfo, str]:
    name = value if isinstance(value, str) and value.strip() else _DEFAULT_TIMEZONE
    try:
        zone = ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == _DEFAULT_TIMEZONE:
            return timezone(timedelta(hours=8)), _DEFAULT_TIMEZONE
        logger.warning("Palworld 时区配置无效，已回退到 Asia/Shanghai。")
        try:
            return ZoneInfo(_DEFAULT_TIMEZONE), _DEFAULT_TIMEZONE
        except ZoneInfoNotFoundError:
            return timezone(timedelta(hours=8)), _DEFAULT_TIMEZONE
    return zone, name


def _time_label(value: datetime, timezone_name: str) -> str:
    label = "北京时间" if timezone_name == _DEFAULT_TIMEZONE else timezone_name
    return f"{value.strftime('%Y-%m-%d %H:%M:%S')}（{label}）"


class PalworldPlugin(Star):
    """Query a Palworld server and deliver opt-in player notifications."""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config

        base_url = config.get("api_base_url", "http://127.0.0.1:8212/v1/api")
        username = config.get("api_username", "admin")
        password = config.get("api_password", "")
        self.request_timeout_seconds = _positive_float(
            config.get("request_timeout_seconds", 10.0), 10.0
        )

        interval_value = config.get("monitor_interval_seconds", 30)
        self.monitor_interval_seconds, interval_adjusted = _monitor_interval(
            interval_value
        )
        if interval_adjusted:
            logger.warning("Palworld 玩家监控轮询间隔无效，已使用至少 10 秒的安全值。")

        self.max_players_per_message = _minimum_integer(
            config.get("max_players_per_message", 50), 1, 1
        )
        self.api_password = password if isinstance(password, str) else ""
        self.monitor_enabled = bool(config.get("monitor_enabled", True))
        self.notify_join = bool(config.get("notify_join", True))
        self.notify_leave = bool(config.get("notify_leave", True))
        self.shutdown_whitelist = _shutdown_whitelist(
            config.get("shutdown_whitelist", [])
        )
        self.shutdown_wait_seconds = _shutdown_wait_seconds(
            config.get("shutdown_wait_seconds", 10)
        )
        shutdown_message = config.get("shutdown_message", _DEFAULT_SHUTDOWN_MESSAGE)
        self.shutdown_message = (
            shutdown_message
            if isinstance(shutdown_message, str)
            else _DEFAULT_SHUTDOWN_MESSAGE
        )
        self.notification_timezone, self.notification_timezone_name = _timezone(
            config.get("notification_timezone", _DEFAULT_TIMEZONE)
        )
        self.game_server_host = (
            config.get("game_server_host", "")
            if isinstance(config.get("game_server_host", ""), str)
            else ""
        )
        self.game_server_password = (
            config.get("game_server_password", "")
            if isinstance(config.get("game_server_password", ""), str)
            else ""
        )
        self.show_server_password = bool(config.get("show_server_password", False))
        self.mask_server_password = bool(config.get("mask_server_password", True))

        self.client = PalworldApiClient(
            str(base_url),
            str(username),
            self.api_password,
            timeout=self.request_timeout_seconds,
        )
        self.tracker = PlayerTracker(logger.warning)
        self.subscriptions: set[str] = set()
        self.monitor_task: asyncio.Task[None] | None = None
        self.stop_event = asyncio.Event()
        self._subscription_lock = asyncio.Lock()
        self._termination_lock = asyncio.Lock()
        self._monitor_failure_logged = False
        self._client_closed = False

    async def initialize(self) -> None:
        """Load subscriptions and start the single configured monitor task."""
        stored = await self.get_kv_data(_SUBSCRIPTIONS_KEY, [])
        self.subscriptions = normalize_subscriptions(stored)
        if not isinstance(stored, list) or any(
            not isinstance(item, str) or not item for item in stored
        ):
            logger.warning("Palworld 通知订阅存储包含无效数据，已忽略非法项。")

        if (
            self.monitor_task is None
            and self.monitor_enabled
            and bool(self.api_password)
        ):
            self.monitor_task = asyncio.create_task(self._monitor_loop())

    @filter.command_group("pal")
    def pal(self) -> None:
        """Palworld 服务器查询与通知指令组。"""

    @pal.command("info")
    async def info(self, event: AstrMessageEvent) -> None:
        """以图片查询 Palworld 服务器基本信息。"""
        await self._send_info_card(event)

    @pal.command("status")
    async def status(self, event: AstrMessageEvent) -> None:
        """兼容别名：以图片查询 Palworld 服务器基本信息。"""
        await self._send_info_card(event)

    @pal.command("players")
    async def players(self, event: AstrMessageEvent) -> str:
        """查询当前在线的 Palworld 玩家。"""
        text = await self._query(
            self.client.get_players,
            lambda value: format_players(value, self.max_players_per_message),
        )
        return await self._send_text(event, text)

    @pal.command("settings")
    async def settings(self, event: AstrMessageEvent) -> None:
        """查询经过安全过滤的 Palworld 服务器设置。"""
        if not self.api_password:
            await self._send_text(event, _NO_AUTH_MESSAGE)
            return
        try:
            settings = await self.client.get_settings()
            rows = build_settings_rows(settings)
            display_password: str | None = None
            if self.show_server_password and self.game_server_password:
                display_password = (
                    self.game_server_password
                    if not self.mask_server_password
                    else "••••••"
                )
            now = _time_label(
                datetime.now(self.notification_timezone),
                self.notification_timezone_name,
            )
            cards = render_settings_cards(
                rows,
                server_address=self._configured_display_address(settings),
                query_time=now,
                server_password=display_password,
            )
            await self._send_images(event, cards)
            return
        except (
            PalworldAuthError,
            PalworldUnavailableError,
            PalworldResponseError,
        ) as error:
            await self._send_text(event, self._public_error(error))
        except ChineseFontUnavailableError:
            await self._send_text(
                event, "未找到可用的本地中文字体，暂时无法生成参数图片。"
            )
        except Exception as error:
            logger.error(
                "处理 Palworld 设置图片时发生未预期异常（异常类型=%s）。",
                type(error).__name__,
            )
            await self._send_text(event, _REQUEST_FAILED_MESSAGE)

    @pal.command("metrics")
    async def metrics(self, event: AstrMessageEvent) -> str:
        """查询 Palworld 服务器性能指标。"""
        text = await self._query(self.client.get_metrics, format_metrics)
        return await self._send_text(event, text)

    @pal.command("shutdown")
    async def shutdown(self, event: AstrMessageEvent) -> str:
        """向 Palworld REST API 发送服务器关闭指令。"""
        sender_id = event.get_sender_id()
        if not isinstance(sender_id, str) or not sender_id:
            return await self._send_text(event, _SHUTDOWN_DENIED_MESSAGE)
        if sender_id not in self.shutdown_whitelist:
            return await self._send_text(event, _SHUTDOWN_DENIED_MESSAGE)
        if not self.api_password:
            return await self._send_text(event, _NO_AUTH_MESSAGE)

        try:
            await self.client.shutdown(
                self.shutdown_wait_seconds, self.shutdown_message
            )
            text = (
                "Palworld API 关服指令已发送，服务器将在 "
                f"{self.shutdown_wait_seconds} 秒后关闭。"
            )
        except PalworldAuthError:
            text = _AUTH_ERROR_MESSAGE
        except PalworldUnavailableError:
            text = _UNAVAILABLE_MESSAGE
        except PalworldResponseError as error:
            if error.status_code is None or 200 <= error.status_code < 300:
                text = _INVALID_RESPONSE_MESSAGE
            else:
                text = _REQUEST_FAILED_MESSAGE
        except Exception as error:
            logger.error(
                "处理 Palworld API 关服请求时发生未预期异常（异常类型=%s）。",
                type(error).__name__,
            )
            text = _REQUEST_FAILED_MESSAGE
        return await self._send_text(event, text)

    @pal.group("notify")
    def notify(self) -> None:
        """管理当前会话的 Palworld 玩家通知订阅。"""

    @filter.permission_type(filter.PermissionType.ADMIN)
    @notify.command("on")
    async def notify_on(self, event: AstrMessageEvent) -> str:
        """为当前管理员会话开启 Palworld 玩家通知。"""
        origin = event.unified_msg_origin
        async with self._subscription_lock:
            if origin in self.subscriptions:
                text = "当前会话已经订阅 Palworld 玩家通知。"
            else:
                candidate = set(self.subscriptions)
                candidate.add(origin)
                if not await self._save_subscriptions(candidate):
                    text = _SUBSCRIPTION_SAVE_FAILED_MESSAGE
                else:
                    self.subscriptions = candidate
                    if not self.api_password:
                        text = (
                            "当前会话的 Palworld 玩家通知订阅已保存；"
                            "API 认证未配置，玩家监控未启动。"
                        )
                    elif not self.monitor_enabled:
                        text = (
                            "已保存当前会话的 Palworld 玩家通知订阅；"
                            "玩家监控当前已关闭，请在配置中启用监控。"
                        )
                    else:
                        text = "已为当前会话开启 Palworld 玩家通知。"
        return await self._send_text(event, text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @notify.command("off")
    async def notify_off(self, event: AstrMessageEvent) -> str:
        """取消当前管理员会话的 Palworld 玩家通知。"""
        origin = event.unified_msg_origin
        async with self._subscription_lock:
            if origin not in self.subscriptions:
                text = "当前会话尚未订阅 Palworld 玩家通知。"
            else:
                candidate = set(self.subscriptions)
                candidate.remove(origin)
                if not await self._save_subscriptions(candidate):
                    text = _SUBSCRIPTION_SAVE_FAILED_MESSAGE
                else:
                    self.subscriptions = candidate
                    text = "已取消当前会话的 Palworld 玩家通知订阅。"
        return await self._send_text(event, text)

    async def _send_text(self, event: AstrMessageEvent, text: str) -> str:
        """Send a plain MessageChain without AstrBot result decorators."""
        try:
            await event.send(MessageChain().message(text))
        except Exception as error:
            logger.error(
                "发送 Palworld 命令回复失败（异常类型=%s）。", type(error).__name__
            )
        return text

    async def _send_images(
        self, event: AstrMessageEvent, images: tuple[bytes, ...] | list[bytes]
    ) -> None:
        components = [Image.fromBytes(image) for image in images]
        try:
            chain = MessageChain(components)
        except TypeError:
            chain = MessageChain()
            for component in components:
                chain.chain(component)
        await event.send(chain)

    def _public_error(self, error: Exception) -> str:
        if isinstance(error, PalworldAuthError):
            return _AUTH_ERROR_MESSAGE
        if isinstance(error, PalworldUnavailableError):
            return _UNAVAILABLE_MESSAGE
        if isinstance(error, PalworldResponseError):
            if error.status_code is None or 200 <= error.status_code < 300:
                return _INVALID_RESPONSE_MESSAGE
            return _REQUEST_FAILED_MESSAGE
        return _REQUEST_FAILED_MESSAGE

    def _configured_display_address(self, settings: dict[str, Any]) -> str:
        return build_info_card_data(
            info={},
            players=[],
            settings=settings,
            metrics={},
            api_base_url=str(self.config.get("api_base_url", "")),
            query_time="",
            game_server_host=self.game_server_host,
        )["server_address"]

    async def _send_info_card(self, event: AstrMessageEvent) -> None:
        if not self.api_password:
            await self._send_text(event, _NO_AUTH_MESSAGE)
            return
        try:
            results = await asyncio.gather(
                self.client.get_info(),
                self.client.get_players(),
                self.client.get_settings(),
                self.client.get_metrics(),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, asyncio.CancelledError):
                    raise result
            failures = [result for result in results if isinstance(result, Exception)]
            if len(failures) == len(results):
                if not isinstance(
                    failures[0],
                    (
                        PalworldAuthError,
                        PalworldUnavailableError,
                        PalworldResponseError,
                    ),
                ):
                    logger.error(
                        "Palworld 信息图片请求全部失败（异常类型=%s）。",
                        type(failures[0]).__name__,
                    )
                await self._send_text(event, self._public_error(failures[0]))
                return
            for failure in failures:
                logger.warning(
                    "Palworld 信息图片的部分接口请求失败（异常类型=%s）。",
                    type(failure).__name__,
                )
            raw_info, raw_players, raw_settings, raw_metrics = results
            info = raw_info if isinstance(raw_info, dict) else {}
            players = raw_players if isinstance(raw_players, list) else None
            settings = raw_settings if isinstance(raw_settings, dict) else {}
            metrics = raw_metrics if isinstance(raw_metrics, dict) else {}
            query_time = _time_label(
                datetime.now(self.notification_timezone),
                self.notification_timezone_name,
            )
            card_data = build_info_card_data(
                info=info,
                players=players,
                settings=settings,
                metrics=metrics,
                api_base_url=str(self.config.get("api_base_url", "")),
                query_time=query_time,
                game_server_host=self.game_server_host,
            )
            await self._send_images(event, (render_info_card(card_data),))
        except (
            PalworldAuthError,
            PalworldUnavailableError,
            PalworldResponseError,
        ) as error:
            await self._send_text(event, self._public_error(error))
        except ChineseFontUnavailableError:
            await self._send_text(
                event, "未找到可用的本地中文字体，暂时无法生成信息图片。"
            )
        except Exception as error:
            logger.error(
                "处理 Palworld 信息图片时发生未预期异常（异常类型=%s）。",
                type(error).__name__,
            )
            await self._send_text(event, _REQUEST_FAILED_MESSAGE)

    async def _query(
        self,
        request: Callable[[], Awaitable[Any]],
        formatter: Callable[[Any], str],
    ) -> str:
        if not self.api_password:
            return _NO_AUTH_MESSAGE
        try:
            value = await request()
            return formatter(value)
        except PalworldAuthError:
            return _AUTH_ERROR_MESSAGE
        except PalworldUnavailableError:
            return _UNAVAILABLE_MESSAGE
        except PalworldResponseError as error:
            if error.status_code is None or 200 <= error.status_code < 300:
                return _INVALID_RESPONSE_MESSAGE
            return _REQUEST_FAILED_MESSAGE
        except Exception as error:
            logger.error(
                "处理 Palworld API 查询时发生未预期异常（异常类型=%s）。",
                type(error).__name__,
            )
            return _REQUEST_FAILED_MESSAGE

    async def _save_subscriptions(self, candidate: set[str]) -> bool:
        try:
            await self.put_kv_data(
                _SUBSCRIPTIONS_KEY, subscriptions_for_storage(candidate)
            )
        except Exception as error:
            logger.error(
                "保存 Palworld 玩家通知订阅时发生异常（异常类型=%s）。",
                type(error).__name__,
            )
            return False
        return True

    async def _poll_once(self) -> None:
        try:
            players = await self.client.get_players()
        except (PalworldAuthError, PalworldUnavailableError, PalworldResponseError):
            self.tracker.mark_failed()
            if not self._monitor_failure_logged:
                logger.warning("Palworld 玩家监控请求失败，将在后续轮询中重试。")
                self._monitor_failure_logged = True
            return
        except Exception as error:
            self.tracker.mark_failed()
            if not self._monitor_failure_logged:
                logger.error(
                    "Palworld 玩家监控发生未预期异常（异常类型=%s）。",
                    type(error).__name__,
                )
                self._monitor_failure_logged = True
            return

        changes = self.tracker.observe(players)
        if changes is None:
            self._monitor_failure_logged = False
            return
        timestamp = datetime.now(self.notification_timezone).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        text = format_player_changes(
            changes,
            self.notify_join,
            self.notify_leave,
            timestamp=timestamp,
        )
        if text is None:
            self._monitor_failure_logged = False
            return
        self._monitor_failure_logged = False

        for origin in tuple(self.subscriptions):
            chain = MessageChain().message(text)
            try:
                sent = await asyncio.wait_for(
                    self.context.send_message(origin, chain),
                    timeout=self.request_timeout_seconds,
                )
            except Exception as error:
                logger.error(
                    "发送 Palworld 玩家通知失败（会话=%s，异常类型=%s）。",
                    origin,
                    type(error).__name__,
                )
                continue
            if sent is False:
                logger.warning("发送 Palworld 玩家通知返回失败（会话=%s）。", origin)

    async def _monitor_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self._poll_once()
            except Exception as error:
                self.tracker.mark_failed()
                if not self._monitor_failure_logged:
                    logger.error(
                        "Palworld 玩家监控轮询未预期失败（异常类型=%s）。",
                        type(error).__name__,
                    )
                    self._monitor_failure_logged = True
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), timeout=self.monitor_interval_seconds
                )
            except asyncio.TimeoutError:
                continue

    async def terminate(self) -> None:
        """Stop background work and close the shared API client safely."""
        async with self._termination_lock:
            self.stop_event.set()
            task = self.monitor_task
            self.monitor_task = None
            try:
                if task is not None:
                    task.cancel()
                    await task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                logger.error(
                    "等待 Palworld 玩家监控任务结束时发生异常（异常类型=%s）。",
                    type(error).__name__,
                )
            finally:
                if not self._client_closed:
                    await self.client.close()
                    self._client_closed = True
