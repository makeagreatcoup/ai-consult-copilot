"""
语音活动检测（VAD）
- 能量阈值检测，简单高效
- 检测到语音开始 → 缓冲
- 检测到静音超过阈值 → 输出完整语音段
"""
import logging
import numpy as np
from dataclasses import dataclass, field

import config

logger = logging.getLogger(__name__)


@dataclass
class SpeechSegment:
    """一段完整的语音"""
    source: str                    # 来源标签：system / mic
    audio_data: np.ndarray         # PCM int16 音频数据
    start_time: float = 0.0        # 开始时间戳
    end_time: float = 0.0          # 结束时间戳


class VoiceActivityDetector:
    """基于能量阈值的 VAD"""

    def __init__(self):
        # 每个来源独立的缓冲区
        self._buffers: dict[str, list[np.ndarray]] = {}
        self._is_speaking: dict[str, bool] = {}
        self._silence_start: dict[str, float] = {}
        self._speech_start: dict[str, float] = {}
        self._silence_chunks: dict[str, int] = {}  # 连续静音块计数

        # 配置参数
        self.energy_threshold = config.VAD_ENERGY_THRESHOLD
        self.silence_duration = config.VAD_SILENCE_DURATION
        self.min_speech_duration = config.VAD_MIN_SPEECH_DURATION

    def process(self, chunk) -> list[SpeechSegment]:
        """
        处理一个音频块，返回检测到的完整语音段列表。
        通常返回空列表，只有在语音段结束时才返回。

        参数:
            chunk: AudioChunk 对象（来自 audio.capture）
        """
        source = chunk.source
        data = chunk.data
        timestamp = chunk.timestamp

        # 初始化该来源的状态
        if source not in self._buffers:
            self._buffers[source] = []
            self._is_speaking[source] = False
            self._silence_start[source] = 0.0
            self._speech_start[source] = 0.0
            self._silence_chunks[source] = 0

        # 计算能量（RMS）
        energy = self._compute_energy(data)
        is_voice = energy > self.energy_threshold

        segments = []

        if is_voice:
            # 有语音活动
            if not self._is_speaking[source]:
                # 语音开始
                self._is_speaking[source] = True
                self._speech_start[source] = timestamp
                self._buffers[source] = []
                logger.debug(f"[VAD] {source} 语音开始，能量={energy:.0f}")

            self._buffers[source].append(data)
            self._silence_chunks[source] = 0

        elif self._is_speaking[source]:
            # 正在说话中，但当前帧是静音
            self._buffers[source].append(data)
            self._silence_chunks[source] += 1

            # 计算累积静音时长（每个chunk约0.5秒）
            chunk_duration = len(data) / config.SAMPLE_RATE
            silence_time = self._silence_chunks[source] * chunk_duration

            if silence_time >= self.silence_duration:
                # 静音足够长，判定语音结束
                segment = self._finalize_segment(source, timestamp)
                if segment:
                    segments.append(segment)

        return segments

    def flush(self, source: str = None) -> list[SpeechSegment]:
        """强制结束所有未完成的语音段（咨询结束时调用）"""
        segments = []
        sources = [source] if source else list(self._buffers.keys())

        for src in sources:
            if self._is_speaking.get(src, False):
                segment = self._finalize_segment(src)
                if segment:
                    segments.append(segment)

        return segments

    def _finalize_segment(self, source: str, end_time: float = None) -> SpeechSegment | None:
        """将缓冲区的音频组装为完整语音段"""
        buffers = self._buffers.get(source, [])
        if not buffers:
            self._is_speaking[source] = False
            return None

        # 检查最短时长
        total_samples = sum(len(b) for b in buffers)
        duration = total_samples / config.SAMPLE_RATE

        # 重置状态
        self._is_speaking[source] = False
        self._silence_chunks[source] = 0
        self._buffers[source] = []

        if duration < self.min_speech_duration:
            logger.debug(f"[VAD] {source} 语音段太短 ({duration:.2f}s)，忽略")
            return None

        audio_data = np.concatenate(buffers)
        segment = SpeechSegment(
            source=source,
            audio_data=audio_data,
            start_time=self._speech_start.get(source, 0),
            end_time=end_time or 0,
        )

        logger.info(f"[VAD] {source} 语音段完成: {duration:.1f}s")
        return segment

    @staticmethod
    def _compute_energy(data: np.ndarray) -> float:
        """计算音频数据的 RMS 能量"""
        if len(data) == 0:
            return 0.0
        # 转为 float 避免溢出
        float_data = data.astype(np.float64)
        return float(np.sqrt(np.mean(float_data ** 2)))
