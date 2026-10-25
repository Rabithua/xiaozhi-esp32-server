# 可选模型预设

`model-presets.sql` 从公开参数创建三项模型和一项音色，所有 API Key 均为空。它不是本机数据库导出，不包含账号、智能体、设备或聊天数据。预设不会自动导入，也不会切换现有角色或全局默认模型。

| 用途 | 模型 | 服务端 provider |
| --- | --- | --- |
| 流式识别 | `qwen-audio-3.1-asr-flash-streaming`，PCM 16 kHz | `aliyunbl_stream` |
| 对话 | `qwen-flash`，百炼 OpenAI 兼容接口 | `openai` |
| 流式合成 | `cosyvoice-v3-flash`，PCM 24 kHz | `alibl_stream` |
| 女声音色 | 龙安台（台湾女声），`longantai_v3` | 上述 CosyVoice 预设 |

先按 [README](README.md) 启动 `db redis web`，等待管理后台完成数据库初始化。需要这组模型时，在本目录手动执行：

```bash
./manage.sh exec -T db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql --default-character-set=utf8mb4 -u "$MYSQL_USER" "$MYSQL_DATABASE"' < model-presets.sql
```

导入使用固定的公开预设 ID；重复执行会保留已有模型内容及密钥。脚本仅在原有百炼 ASR 表单缺少 `ws_url` 时追加这个字段，不重置其他表单字段。若已有自建模型，可直接继续使用它们。

在后台“模型配置”中分别填写自己业务空间的 API Key。公共接口地址已提供默认值；业务空间专用密钥需要同时填写该空间和地域对应的 `ws_url` / LLM `base_url`。例如北京语音业务空间的地址形式为 `wss://<WorkspaceId>.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`。真实空间 ID 和密钥只填本机后台，勿写回此 SQL。

在智能体配置中选这三项模型，并将音色选为“龙安台（台湾女声）”。角色音色会覆盖 TTS 模型的默认 `voice`，因此两处需要匹配。VAD 可继续使用上游本地 Silero。全局默认模板也需配置可用模型，才能处理未绑定设备的激活流程；脚本不会替你更改模板。

ASR 必须使用此 fork 的 provider 文件；本目录 Compose 已将该文件只读挂载进固定版本的语音镜像。预设不附带服务额度，模型是否可调用取决于自己百炼账号的地域、权限和余额。

配置完成后按 README 启动语音服务。修改模型或角色后重新建立设备会话，使服务端重新读取配置。
