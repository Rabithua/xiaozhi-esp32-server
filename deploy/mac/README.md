# Apple Silicon Mac 本地部署

使用 OrbStack 或支持 Docker Compose v2 的本机容器运行环境，部署真实管理前后端、Python 语音服务、MySQL 和 Redis。此目录面向 `linux/arm64`，默认只允许本机访问；不会修改硬件固件、配网或设备身份。

镜像按公开 digest 固定，见 [image-lock.json](image-lock.json)。其中源码提交是 provider 修改的参考版本；上游镜像未提供可核验的源码 revision，不能据此认定镜像恰好由该提交构建。Compose 将本 checkout 的 [百炼 ASR provider](../../main/xiaozhi-server/core/providers/asr/aliyunbl_stream.py) 只读挂载到固定镜像中。更新镜像前需要重新验证 provider 兼容性。

## 准备私有配置

在本目录操作：

```sh
umask 077
cp .env.example .env
chmod 600 .env
```

用编辑器填写 `.env` 的三个独立随机密码，以及 `STATE_DIR` 的绝对路径。`STATE_DIR` 应位于 checkout 外的持久磁盘，磁盘在服务运行时保持挂载。创建其 `uploads/`、`server-data/` 两个目录，父目录权限设为 `700`。空密码或空状态路径会使 Compose 拒绝启动。

默认读取本目录 `.env`；可设置 `XIAOZHI_MAC_ENV_FILE` 指向另一份私有环境文件。脚本通过 Compose 解析环境文件，不将它作为 shell 脚本执行。需要多个独立实例时使用不同的 `COMPOSE_PROJECT_NAME`、可用宿主端口及状态目录。

`.env`、`server-data/.config.yaml`、数据库卷、日志、录音、设备激活资料和访问令牌都属于私有运行数据，不应提交。数据库与 Redis 使用 Compose 项目独立命名卷，`STATE_DIR` 中的目录保存上传文件和语音服务配置。

## 第一阶段：管理后台

```sh
./manage.sh up -d db redis web
./open.command
```

在 `http://127.0.0.1:8002` 注册第一个账号，该账号为管理员。数据库结构由 Java API 的 Liquibase 初始化。后续账号按普通用户处理。

配置模型和默认模板，并在参数管理中确认：

| 参数 | 本机试用值 |
| --- | --- |
| `server.ota` | `http://127.0.0.1:8002/xiaozhi/ota/` |
| `server.websocket` | `ws://127.0.0.1:8002/xiaozhi/v1/` |
| `server.fronted_url` | `http://127.0.0.1:8002` |
| `server.mqtt_gateway` | 字符串 `null`，纯 WebSocket 无需 MQTT 网关 |
| `server.auth.enabled` | `true` |

可选的公开模型预设及手动初始化方式见 [model-presets.md](model-presets.md)。预设不包含 API 密钥，模型凭据需在本机后台填写。

语音服务启动时会初始化默认模板的 VAD 和 ASR。选择已配置好的 API ASR 可以避免下载大型本地识别模型；只修改某个智能体的 ASR 不会改变启动用的默认模板。使用本地 ASR 时，按对应 provider 文档准备模型文件。

## 第二阶段：语音服务

将 [server-config.example.yaml](server-config.example.yaml) 复制为 `<STATE_DIR>/server-data/.config.yaml`，权限设为 `600`。从本机后台参数 `server.secret` 复制随机值到该文件的 `manager-api.secret`；该值与具体数据库绑定，不包含在示例里。

`manager-api.url` 保持 `http://web:8002/xiaozhi`：这是容器之间的地址。不要将其改成本机浏览器使用的 `127.0.0.1`。

```sh
./manage.sh --profile voice up -d
./manage.sh --profile voice ps
```

Nginx 在 `8002` 同时代理管理 API、`/xiaozhi/v1/` WebSocket 和 `/mcp/vision/`。它在请求时解析语音容器，因此后台可以先于语音服务启动。默认 Python 调试端口 `8000/8003` 也只绑定宿主机 loopback；数据库和 Redis 不发布宿主端口。

## 接入局域网设备

先确保模型凭据、WebSocket 和后台“更新配置”功能正常，再在私有 `.env` 中设置 `WEB_BIND_IP=0.0.0.0`，仅重建 Web 服务：

```sh
./manage.sh up -d web
```

将上表前三项中的 `127.0.0.1` 换为设备能够访问的 `<MAC_LAN_IP>`，端口仍为 `8002`。如需视觉功能，也将私有 `.config.yaml` 的 `server.vision_explain` 改为 `http://<MAC_LAN_IP>:8002/mcp/vision/explain` 并重启语音服务。认证保持开启，MQTT 参数保持 `null`。

设备的 OTA 服务地址填写 `http://<MAC_LAN_IP>:8002/xiaozhi/ota/`。该接口同时负责激活、对话服务器发现和校时，并非直接的固件文件地址。设备首次请求后会显示或播报六位激活码，在选定智能体的“添加设备”中输入该码绑定。不要将本机 `127.0.0.1` 或 Docker 服务名填入设备。Mac LAN 地址变化后，需要同步更新这些地址；可在路由器固定 DHCP 租约。

当前上游绑定流程会将设备自动升级默认设为开启。需要保留定制固件时，绑定后立即在后台关闭该设备的自动升级，并保留固件自身的禁止服务器升级设置；这不会影响服务器发现和激活。纯 WebSocket 无需填写 MQTT 地址。上游 OTA GET 诊断页会错误地要求 MQTT，验证时应以设备真实 POST 返回的 WebSocket 配置为准。

## 日常操作与验证

双击 `open.command` 仅启动并打开管理后台，不会首次启动尚未配置好的语音服务，也不会停止已有语音容器。双击 `stop.command` 停止本项目全部服务并保留数据。命令行可执行：

```sh
./manage.sh --profile voice ps
./manage.sh --profile voice stop
```

离线检查可以使用 `bash -n manage.sh open.command stop.command`，以及 `./manage.sh --profile voice config -q`。后者只验证配置；不要将不带 `-q` 的完整渲染输出公开，因为其中会包含环境中的密码。

从本目录复现百炼 ASR provider 的离线回归：

```sh
python3 -m unittest discover \
  -s ../../main/xiaozhi-server/tests/core/providers/asr \
  -p test_aliyunbl_stream.py -v
```

这些测试使用隔离的依赖和模拟事件，不需要 API 密钥，也不调用云接口。

启动后需确认 `/xiaozhi/user/pub-config` 返回 `code=0`、正常登录后台、WebSocket 升级成功、后台“更新配置”成功。仅有静态首页 HTTP 200 不能证明 Java API 或语音服务可用。模型接口、真人麦克风／扬声器及设备长时运行应分别验证。

停止服务不会删除数据库。重建环境前应自行保存私有配置和卷数据；`down -v` 会删除本项目数据库与 Redis 命名卷。
