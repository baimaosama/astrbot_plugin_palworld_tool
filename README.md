# astrbot_plugin_palworld

Palworld/幻兽帕鲁 服务器助手是一个面向群聊和私聊使用的 AstrBot 插件，用来查询 Palworld/幻兽帕鲁 服务器信息、在线玩家、性能指标和中文参数表，并支持玩家进退服通知与发送消息重启服务器（需在服务端运行进程守护）。

## 功能介绍

- `/pal info` 使用图片卡片展示服务器名称、版本、描述、游戏地址、在线人数、运行时间、游戏天数、基地数量和在线玩家等级。
- `/pal settings` 将 48 个常用安全参数翻译成中文，并以两列四排的单张完整 PNG 展示。
- `/pal players` 查询当前在线人数、玩家游戏内名称和等级。
- `/pal metrics` 查询服务器 FPS、帧时间、在线人数、运行时间、基地数量和游戏天数。
- 玩家进服、退服通知使用稳定玩家 ID 判断变化，显示游戏内名称、等级、当前在线人数和当地时间。
- 通知订阅保存在 AstrBot KV 存储中，插件重载后仍然保留。
- `/pal shutdown` 调用 Palworld 官方关服接口，并在关服前向游戏内发送提示消息。
- 关服命令必须明确配置 sender UID 白名单；AstrBot 管理员身份不会绕过该白名单。

## 示例图

### 服务器信息

![Palworld 服务器信息示例](https://raw.githubusercontent.com/moeneri/astrbot_plugin_palworld/master/assets/readme/palworld_info_example.png)

### 中文参数表

参数表固定为 8 个分类、每类 6 项，共 48 项；API 缺失字段显示“未知”。

![Palworld 中文参数表示例](https://raw.githubusercontent.com/moeneri/astrbot_plugin_palworld/master/assets/readme/palworld_settings_example.png)

## 常用命令

```text
/pal info
/pal players
/pal settings
/pal metrics
/pal notify on
/pal notify off
/pal shutdown
```

## 命令列表

| 命令 | 说明 | 权限 |
| --- | --- | --- |
| `/pal info` | 生成服务器信息图片 | 所有人 |
| `/pal status` | `/pal info` 的兼容别名 | 所有人 |
| `/pal players` | 查询在线玩家游戏内名称和等级 | 所有人 |
| `/pal settings` | 生成 48 项中文参数长图 | 所有人 |
| `/pal metrics` | 查询 FPS、帧时间、人数、运行时间、基地数和游戏天数 | 所有人 |
| `/pal notify on` | 为当前群聊或私聊开启玩家进退服通知 | AstrBot 管理员 |
| `/pal notify off` | 关闭当前会话的玩家进退服通知 | AstrBot 管理员 |
| `/pal shutdown` | 发送游戏内提示并调用官方关服接口 | `shutdown_whitelist` 中的 UID |

## 配置项

### 安装与 REST API 配置

1. 在 AstrBot 插件管理页面安装市场插件或上传 `astrbot_plugin_palworld.zip`。
2. 在 Palworld 的 `PalWorldSettings.ini` 现有 `OptionSettings` 中启用 REST API：

   ```ini
   RESTAPIEnabled=True,RESTAPIPort=8212
   ```

3. 在 AstrBot 插件配置中填写 REST API 地址和 HTTP Basic Auth 用户名、密码。
4. 重载插件后发送 `/pal info` 测试连接。

不要用示例配置覆盖完整的 `OptionSettings`。Palworld 官方不建议把 REST API 直接暴露到公网，请使用本机、局域网、VPN 或防火墙限制访问来源。

### 插件配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `api_base_url` | `http://127.0.0.1:8212/v1/api` | Palworld REST API 基址 |
| `api_username` | `admin` | Basic Auth 用户名 |
| `api_password` | 空 | Basic Auth 密码；为空时查询不可用且监控不会启动 |
| `request_timeout_seconds` | `10.0` | API 请求和主动消息发送超时秒数 |
| `monitor_enabled` | `true` | 是否启用玩家进退服轮询 |
| `monitor_interval_seconds` | `30` | 轮询间隔秒数；运行时最小为 10 秒 |
| `notify_join` | `true` | 是否发送玩家进服通知 |
| `notify_leave` | `true` | 是否发送玩家退服通知 |
| `max_players_per_message` | `50` | `/pal players` 最多展示人数 |
| `notification_timezone` | `Asia/Shanghai` | 图片和通知使用的 IANA 时区 |
| `game_server_host` | 空 | API 未返回 PublicIP 时使用的游戏服务器主机地址 |
| `game_server_password` | 空 | 可选的游戏进入密码；不是 REST API 管理密码 |
| `show_server_password` | `false` | 是否在参数图片右下角显示游戏进入密码区域 |
| `mask_server_password` | `true` | 显示进入密码时是否脱敏；关闭后会展示完整密码 |
| `shutdown_whitelist` | 空列表 | 允许执行 `/pal shutdown` 的 sender UID 列表 |
| `shutdown_wait_seconds` | `10` | 官方 shutdown 请求关服前等待秒数 |
| `shutdown_message` | `服务器即将重启，请稍后重新连接。` | 关服前发送到游戏内的提示消息 |

使用 AstrBot `/sid` 获取 sender UID，并把需要关服权限的 UID 明确加入 `shutdown_whitelist`。默认空名单下无人可以执行关服。

## 使用示例

### 查询服务器

```text
/pal info
/pal players
/pal settings
/pal metrics
```

### 开启和关闭通知

通知订阅命令仅限 AstrBot 管理员执行：

```text
/pal notify on
/pal notify off
```

单人进服通知示例：

```text
🟢 玩家进入服务器
玩家：Alice（Lv. 41）
当前在线：1 人
时间：2026-07-14 12:30:45
```

### 关闭并由进程守护重启服务器

```text
/pal shutdown
```

命令会把 `shutdown_wait_seconds` 和 `shutdown_message` 发送给 Palworld 官方 `/shutdown` 接口。插件只负责关服；服务器能否重新启动取决于你配置的外部进程守护服务。

## 注意事项

- Palworld REST API 不应直接暴露到公网。推荐限制在本机、局域网、VPN 或受防火墙保护的网络中。
- `api_password` 通常与服务器管理认证有关，请保护 AstrBot 配置文件，不要在群聊、Issue 或日志中发送密码。
- `/pal settings` 不展示 `AdminPassword`、API 返回的 `ServerPassword`、认证令牌、玩家 IP、坐标、REST API 端口、RCON 字段或未知字段，也不会直接返回原始 JSON。
- `game_server_password` 是手动填写的游戏进入密码。开启 `show_server_password` 且关闭 `mask_server_password` 会把完整密码发送到聊天中，请谨慎使用。
- `/pal shutdown` 必须通过 UID 白名单授权。AstrBot 管理员、群管理员或其他身份不会绕过 `shutdown_whitelist`。
- 第一次成功轮询只建立基线，不会把已经在线的所有玩家报告为刚进服。
- API 请求失败时会保留上一份玩家快照；API 恢复后的第一次成功查询重新建立基线，不补发故障期间的变化。
- 玩家改名但稳定 ID 不变时不会产生退出再进入；同名但不同 ID 的玩家会分别处理。
- 单个订阅会话发送失败不会影响其他会话，也不会中断后续监控。
- 图片需要系统存在可用中文字体。Windows 通常可直接使用微软雅黑；Linux/Docker 请安装 Noto Sans CJK、文泉驿或其他中文字体。
- 本插件只实现查询、玩家通知和 UID 白名单关服，不提供 RCON、启动、强停、踢人、封禁、备份、更新或 Mod 管理。

## 数据来源

- [Palworld REST API](https://docs.palworldgame.com/category/rest-api)
- [Palworld 服务器配置参数](https://docs.palworldgame.com/settings-and-operation/configuration/)

## 许可

AstrBot 兼容范围：`>=4.9.2,<5`  
项目仓库：[moeneri/astrbot_plugin_palworld](https://github.com/moeneri/astrbot_plugin_palworld)  
许可证：MIT
