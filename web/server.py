"""
Web 服务模块
- FastAPI + WebSocket 实时推送
- 提供前端面板
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

import config

logger = logging.getLogger(__name__)

app = FastAPI(title="咨询AI副驾")

# 静态文件
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 连接: 当前 {len(self.active_connections)} 个")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket 断开: 当前 {len(self.active_connections)} 个")

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()

# 全局状态
class SessionState:
    """咨询会话状态"""
    def __init__(self):
        self.is_active = False
        self.mode = "free-consult"
        self.start_time: float | None = None
        self.transcripts: list[dict] = []       # 转写记录
        self.suggestions: list[dict] = []       # AI建议记录

    def reset(self):
        self.is_active = False
        self.start_time = None
        self.transcripts = []
        self.suggestions = []

    def add_transcript(self, source: str, text: str, timestamp: float):
        self.transcripts.append({
            "source": source,
            "speaker": "用户" if source == "system" else "我",
            "text": text,
            "time": timestamp,
            "time_str": datetime.fromtimestamp(timestamp).strftime("%H:%M:%S"),
        })

    def add_suggestion(self, suggestion):
        self.suggestions.append({
            "type": suggestion.suggestion_type,
            "trigger": suggestion.trigger_text[:50],
            "text": suggestion.suggestion,
            "time": suggestion.timestamp,
            "time_str": datetime.fromtimestamp(suggestion.timestamp).strftime("%H:%M:%S"),
        })


state = SessionState()


@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端面板"""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时通信"""
    await manager.connect(websocket)
    try:
        while True:
            # 接收前端控制命令
            data = await websocket.receive_json()
            await handle_command(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def handle_command(data: dict):
    """处理前端命令"""
    cmd = data.get("command")

    if cmd == "start":
        state.is_active = True
        state.start_time = time.time()
        state.mode = data.get("mode", "free-consult")
        state.reset()
        await manager.broadcast({
            "type": "status",
            "status": "active",
            "mode": state.mode,
            "start_time": state.start_time,
        })
        logger.info(f"咨询开始，模式: {state.mode}")

    elif cmd == "stop":
        state.is_active = False
        await manager.broadcast({
            "type": "status",
            "status": "ended",
            "duration": time.time() - state.start_time if state.start_time else 0,
        })
        logger.info("咨询结束")

    elif cmd == "switch_mode":
        state.mode = data.get("mode", "free-consult")
        await manager.broadcast({
            "type": "mode_changed",
            "mode": state.mode,
        })
        logger.info(f"模式切换: {state.mode}")


async def push_transcript(source: str, text: str, timestamp: float):
    """推送转写结果到前端"""
    state.add_transcript(source, text, timestamp)

    speaker = "用户" if source == "system" else "我"
    await manager.broadcast({
        "type": "transcript",
        "source": source,
        "speaker": speaker,
        "text": text,
        "time": datetime.fromtimestamp(timestamp).strftime("%H:%M:%S"),
    })


async def push_suggestion(suggestion):
    """推送AI建议到前端"""
    state.add_suggestion(suggestion)

    label = "回答建议" if suggestion.suggestion_type == "answer" else "话术优化"
    await manager.broadcast({
        "type": "suggestion",
        "suggestion_type": suggestion.suggestion_type,
        "label": label,
        "text": suggestion.suggestion,
        "trigger": suggestion.trigger_text[:50],
        "time": datetime.fromtimestamp(suggestion.timestamp).strftime("%H:%M:%S"),
    })


def get_session_data() -> dict:
    """获取当前会话完整数据（用于归档）"""
    duration = 0
    if state.start_time:
        duration = time.time() - state.start_time

    return {
        "mode": state.mode,
        "start_time": state.start_time,
        "duration": duration,
        "transcripts": state.transcripts,
        "suggestions": state.suggestions,
    }


def run_server():
    """启动 Web 服务"""
    uvicorn.run(
        app,
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        log_level="warning",
    )
