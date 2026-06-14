"""
faster-whisper 流式转写模块
- 将 VAD 检测到的语音段转为文字
- 带来源标签输出
"""
import logging
import threading
import queue
from dataclasses import dataclass

import numpy as np

import config
from audio.vad import SpeechSegment

logger = logging.getLogger(__name__)


@dataclass
class Transcript:
    """一条转写结果"""
    source: str       # system（对方）/ mic（自己）
    text: str         # 转写文字
    start_time: float  # 开始时间戳
    end_time: float    # 结束时间戳
    confidence: float = 0.0  # 置信度


class WhisperTranscriber:
    """faster-whisper 流式转写器"""

    def __init__(self, output_queue: queue.Queue):
        self.output_queue = output_queue
        self._model = None
        self._running = False
        self._thread = None
        self._input_queue = queue.Queue()

    def start(self):
        """初始化模型并启动转写线程"""
        self._load_model()
        self._running = True
        self._thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self._thread.start()
        logger.info("Whisper 转写器已启动")

    def stop(self):
        self._running = False
        # 放入 None 作为哨兵信号
        self._input_queue.put(None)
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Whisper 转写器已停止")

    def submit(self, segment: SpeechSegment):
        """提交一个语音段进行转写"""
        if self._running:
            self._input_queue.put(segment)

    def _load_model(self):
        """加载 faster-whisper 模型"""
        try:
            from faster_whisper import WhisperModel
            logger.info(f"正在加载 Whisper 模型: {config.WHISPER_MODEL}...")
            self._model = WhisperModel(
                config.WHISPER_MODEL,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
            logger.info("Whisper 模型加载完成")
        except Exception as e:
            logger.error(f"Whisper 模型加载失败: {e}")
            raise

    def _transcribe_loop(self):
        """转写主循环"""
        while self._running:
            try:
                segment = self._input_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if segment is None:
                break

            try:
                transcript = self._transcribe_segment(segment)
                if transcript and transcript.text.strip():
                    self.output_queue.put(transcript)
            except Exception as e:
                logger.error(f"转写失败: {e}")

    def _transcribe_segment(self, segment: SpeechSegment) -> Transcript | None:
        """转写单个语音段"""
        if self._model is None:
            return None

        # int16 → float32 归一化
        audio_float = segment.audio_data.astype(np.float32) / 32768.0

        try:
            segments_iter, info = self._model.transcribe(
                audio_float,
                language="zh",           # 中文
                beam_size=3,             # 减少beam size提升速度
                vad_filter=False,        # 已有VAD，不需要内置的
                condition_on_previous_text=False,
            )

            # 收集所有片段
            text_parts = []
            avg_confidence = 0.0
            count = 0

            for seg in segments_iter:
                if seg.text.strip():
                    text_parts.append(seg.text.strip())
                    avg_confidence += seg.avg_logprob
                    count += 1

            if not text_parts:
                return None

            text = "".join(text_parts)
            avg_confidence = avg_confidence / count if count > 0 else 0.0

            return Transcript(
                source=segment.source,
                text=text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                confidence=avg_confidence,
            )

        except Exception as e:
            logger.error(f"转写出错: {e}")
            return None
