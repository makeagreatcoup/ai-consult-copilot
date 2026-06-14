"""
咨询AI副驾 - 主入口
一键启动：音频采集 → VAD → 转写 → AI建议 → Web面板 → 归档
"""
import asyncio
import io
import logging
import signal
import sys
import threading
import time
import wave
import webbrowser

import numpy as np
import config
from audio.capture import DualAudioCapture
from audio.vad import VoiceActivityDetector
from transcriber.whisper_stream import WhisperTranscriber, Transcript
from ai.advisor import AIAdvisor
from web.server import app, push_transcript, push_suggestion, get_session_data, state
from archive.archiver import Archiver
from archive.inbox_watcher import inbox_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


class ConsultCopilot:
    """咨询AI副驾主控制器"""

    def __init__(self):
        self.audio_capture = DualAudioCapture()
        self.vad = VoiceActivityDetector()
        self._transcript_queue = __import__("queue").Queue()
        self.transcriber = WhisperTranscriber(output_queue=self._transcript_queue)
        self.advisor = AIAdvisor(mode="free-consult")
        self.archiver = Archiver()

        self._running = False
        self._ws_loop = None

        # 音频缓冲区（用于保存完整咨询音频）
        self._audio_buffer = []
        self._audio_lock = threading.Lock()

    def start(self):
        """启动所有组件"""
        logger.info("=" * 50)
        logger.info("  咨询AI副驾 启动中...")
        logger.info("=" * 50)

        # 1. 加载 Whisper 模型
        logger.info("[1/6] 加载 Whisper 模型...")
        self.transcriber.start()

        # 2. 初始化 AI 建议器
        logger.info("[2/6] 初始化 AI 建议器...")
        self.advisor.start()

        # 3. 启动音频采集
        logger.info("[3/6] 启动双路音频采集...")
        self.audio_capture.start()

        # 4. 启动收件箱监听
        logger.info("[4/6] 启动收件箱监听...")
        inbox_watcher.start()

        # 5. 启动处理线程（音频处理 + 消费者）
        self._running = True
        threading.Thread(target=self._audio_loop, daemon=True).start()
        threading.Thread(target=self._consume_transcripts, daemon=True).start()
        threading.Thread(target=self._consume_suggestions, daemon=True).start()
        logger.info("[5/6] 处理线程已启动")

        # 6. 启动 Web 服务（阻塞主线程）
        logger.info("[6/6] 启动 Web 面板...")
        url = f"http://{config.WEB_HOST}:{config.WEB_PORT}"
        logger.info(f"面板地址: {url}")

        # 延迟打开浏览器
        threading.Thread(
            target=lambda: (time.sleep(1.5), webbrowser.open(url)),
            daemon=True,
        ).start()

        # 异步事件循环用于 WebSocket 推送
        self._ws_loop = asyncio.new_event_loop()

        import uvicorn
        uvicorn.run(
            app,
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            log_level="warning",
        )

    def stop(self):
        """优雅停止"""
        logger.info("正在停止...")
        self._running = False

        # 归档活跃会话
        if state.is_active:
            self._archive_session()

        self.audio_capture.stop()
        self.transcriber.stop()
        self.advisor.stop()
        inbox_watcher.stop()

        if self._ws_loop and self._ws_loop.is_running():
            self._ws_loop.call_soon_threadsafe(self._ws_loop.stop)

        logger.info("咨询AI副驾已停止")

    # ─── 线程：音频 → VAD → 转写提交 ───

    def _audio_loop(self):
        """音频采集 + VAD 处理"""
        logger.info("音频处理循环已启动")
        while self._running:
            chunk = self.audio_capture.get_chunk(timeout=0.1)
            if chunk is None:
                continue
            if not state.is_active:
                continue

            # 保存音频到缓冲区（用于后续归档）
            if config.SAVE_AUDIO:
                with self._audio_lock:
                    self._audio_buffer.append(chunk)

            segments = self.vad.process(chunk)
            for seg in segments:
                self.transcriber.submit(seg)

        # 停止时 flush
        for source in ["system", "mic"]:
            for seg in self.vad.flush(source):
                self.transcriber.submit(seg)

    # ─── 线程：消费转写结果 → 推前端 + 提交AI ───

    def _consume_transcripts(self):
        """消费转写结果，推送到前端和AI建议器"""
        while self._running:
            try:
                t = self._transcript_queue.get(timeout=0.5)
            except Exception:
                continue
            if t is None:
                break

            # 推送到前端
            if self._ws_loop and self._ws_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    push_transcript(t.source, t.text, t.start_time),
                    self._ws_loop,
                )

            # 提交给 AI 建议器
            self.advisor.submit_transcript(t)

    # ─── 线程：消费AI建议 → 推前端 ───

    def _consume_suggestions(self):
        """消费AI建议，推送到前端"""
        while self._running:
            try:
                s = self.advisor.output_queue.get(timeout=0.5)
            except Exception:
                continue
            if s is None:
                break

            if self._ws_loop and self._ws_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    push_suggestion(s),
                    self._ws_loop,
                )

    # ─── 归档 ───

    def _archive_session(self):
        """归档当前会话到 Obsidian"""
        try:
            session_data = get_session_data()

            # 合并音频缓冲区
            if config.SAVE_AUDIO and self._audio_buffer:
                with self._audio_lock:
                    audio_data = self._merge_audio_buffer(self._audio_buffer)
                    session_data["audio_data"] = audio_data
                    self._audio_buffer.clear()

            result = self.archiver.archive_session(session_data)
            if result:
                logger.info(f"归档完成:")
                logger.info(f"  咨询记录: {result.get('record')}")
                logger.info(f"  用户档案: {result.get('profile')}")
                if result.get("audio"):
                    logger.info(f"  音频文件: {result.get('audio')}")
                if result.get("plan"):
                    logger.info(f"  行动方案: {result.get('plan')}")
        except Exception as e:
            logger.error(f"归档失败: {e}")

    def _merge_audio_buffer(self, buffer: list) -> bytes:
        """合并音频缓冲区为 WAV 文件"""
        if not buffer:
            return b""

        # 合并所有音频块
        merged = np.concatenate(buffer)

        # 转换为 WAV 格式
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(config.SAMPLE_RATE)
            wav_file.writeframes(merged.tobytes())

        return wav_buffer.getvalue()


def main():
    copilot = ConsultCopilot()

    def signal_handler(sig, frame):
        copilot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("\n" + "=" * 50)
    print("  咨询AI副驾 v1.0")
    print("  Ctrl+C 优雅退出并自动归档")
    print("=" * 50 + "\n")

    copilot.start()


if __name__ == "__main__":
    main()
