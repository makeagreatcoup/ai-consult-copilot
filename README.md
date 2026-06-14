# 咨询AI副驾系统 (Consult Copilot)

实时辅助咨询的 AI 副驾系统，帮助教练/咨询师在咨询过程中获得实时建议。

## 功能

- 实时双通道音频采集（系统音频 + 麦克风）
- VAD 语音活动检测，自动分割发言
- faster-whisper 中文流式转录
- Claude API 实时咨询建议（免费咨询 / 付费咨询 / 陪跑复盘 三种模式）
- Web 面板实时显示转录 + AI 建议
- 用户档案自动归档到 Obsidian
- 腾讯会议文档自动监听处理
- 逐字弹出式视频生成

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY

# 3. 启动
python main.py
```

打开浏览器访问 `http://127.0.0.1:8765`

## 配置

在 `config.py` 和 `.env` 中配置：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| ANTHROPIC_API_KEY | Claude API 密钥 | 必填 |
| WHISPER_MODEL | Whisper 模型大小 | small |
| WHISPER_DEVICE | 计算设备 | cuda |
| WEB_PORT | Web 面板端口 | 8765 |

## 架构

```
audio/capture.py     → 双通道音频采集（WASAPI + PyAudio）
audio/vad.py         → 语音活动检测
transcriber/         → Whisper 流式转录
ai/advisor.py        → Claude 实时建议
archive/archiver.py  → 用户档案归档（Obsidian）
archive/inbox_watcher.py → 腾讯会议文档监听
web/                 → FastAPI Web 面板
video/               → 逐字弹出视频生成
```

## 技术栈

- Python 3.10+
- faster-whisper (语音识别)
- Anthropic Claude API (AI 建议)
- FastAPI + WebSocket (实时面板)
- pyaudiowpatch (WASAPI 音频捕获)
- moviepy + Pillow (视频生成)
- watchdog (文件监听)

## License

MIT
