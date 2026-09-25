# pyVideoTrans

pyVideoTrans 是一款开源的视频翻译、语音转录、字幕翻译和配音工具。当前产品提供 React Web 前端、FastAPI 后端和命令行入口；桌面 GUI 已退役。

## 功能

- 音视频语音识别并生成带时间轴的字幕
- 使用机器翻译或 LLM 翻译字幕
- 使用 TTS 生成配音并进行音画合成
- 说话人识别、OCR 字幕提取及媒体处理
- 通过浏览器查看任务进度、结果和输出文件
- 通过 CLI 运行共享处理工作流

具体可用渠道取决于当前配置和安装的 provider/model 依赖。

## 源码安装和启动

要求 Python 3.10、[uv](https://docs.astral.sh/uv/)、FFmpeg，以及用于构建前端的 Bun。

### 1. 开发模式（前后端热重载）

```powershell
uv sync
cd frontend && bun install && cd ..
bun run dev
```

- 前端界面：`http://localhost:3000`
- 后端 API（FastAPI + Uvicorn）：`http://127.0.0.1:7860`
- OpenAPI 文档：`http://127.0.0.1:7860/docs`

### 2. 单端口生产模式

```powershell
uv sync
bun run build
uv run python webui.py
```

默认在 `http://127.0.0.1:7860` 提供服务。可用 `--host` 和 `--port` 指定监听地址：

```powershell
uv run python webui.py --host 0.0.0.0 --port 7860
```

Docker 部署说明请参考仓库根目录的 `Dockerfile`。Web 工作流、上传文件及任务生命周期限制见[WebUI 使用说明](webui.md)。

## 命令行

CLI 与 Web 工作流共享处理逻辑：

```powershell
uv run cli.py --help
uv run cli.py --list providers
uv run cli.py --task stt --name "./audio.wav"
uv run cli.py --task sts --name "./subs.srt" --target_language_code en
```

更多参数见[CLI 文档](cli.md)。

## 架构与支持

- [当前架构](architecture.md)
- [WebUI 使用说明](webui.md)
- [常见问题](faq.md)
- [项目决策：Web-only runtime](decisions/0002-web-only-runtime.md)

遇到问题时，请提供操作系统、Python 版本、启动命令、任务阶段、provider 选择及脱敏后的错误日志。不要公开 API 密钥或访问令牌。

本项目使用的开源依赖和模型各自遵循其许可证；项目许可证见仓库根目录 [LICENSE](../LICENSE)。
