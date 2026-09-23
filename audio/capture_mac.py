"""
macOS 版系统音频采集模块
- 通过 BlackHole 虚拟音频设备采集系统输出（腾讯会议/Zoom 对方声音）
- 接口与 Windows 版 SystemAudioCapture 完全一致，可互换

前置条件：
1. brew install blackhole-2ch
2. 在"音频 MIDI 设置"中创建 Multi-Output Device（扬声器 + BlackHole）
3. 系统输出设为 Multi-Output Device
"""
from __future__ import annotations
import threading
import queue
import time
import logging

import numpy as np
import pyaudio

import config
from audio.capture import AudioChunk, SOURCE_SYSTEM

logger = logging.getLogger(__name__)


class SystemAudioCaptureMac:
    """macOS 版系统音频采集（BlackHole 设备）"""

    def __init__(self, output_queue: queue.Queue):
        self.output_queue = output_queue
        self._running = False
        self._thread = None

    def _find_blackhole_device(self, pa: pyaudio.PyAudio) -> dict | None:
        """遍历设备列表，查找 BlackHole 输入设备"""
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            name = info.get("name", "")
            # 匹配 BlackHole 2ch / 16ch / 64ch 等变体
            if "blackhole" in name.lower() and info.get("maxInputChannels", 0) > 0:
                logger.info(f"找到 BlackHole 设备: {name} (index={i})")
                return info
        return None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("系统音频采集已启动（macOS/BlackHole）")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("系统音频采集已停止")

    def _capture_loop(self):
        pa = pyaudio.PyAudio()
        try:
            device_info = self._find_blackhole_device(pa)
            if not device_info:
                logger.error(
                    "未找到 BlackHole 设备。请先安装：brew install blackhole-2ch"
                )
                return

            # 使用设备的原始采样率，后续重采样到 16kHz
            device_rate = int(device_info.get("defaultSampleRate", 44100))
            channels = min(int(device_info.get("maxInputChannels", 2)), 2)

            stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=device_rate,
                input=True,
                input_device_index=device_info["index"],
                frames_per_buffer=config.CHUNK_SIZE,
            )

            logger.info(
                f"系统音频流已打开，采样率: {device_rate}, 声道: {channels}"
            )
            buffer = bytearray()

            while self._running:
                try:
                    raw = stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                    buffer.extend(raw)

                    # 累积约 0.5 秒数据后发送
                    chunk_samples = int(device_rate * 0.5)
                    chunk_bytes = chunk_samples * 2 * channels

                    if len(buffer) >= chunk_bytes:
                        audio_data = np.frombuffer(
                            bytes(buffer[:chunk_bytes]), dtype=np.int16
                        )
                        buffer = buffer[chunk_bytes:]

                        # 多声道 → 单声道（取平均）
                        if channels > 1:
                            audio_data = audio_data.reshape(-1, channels).mean(axis=1).astype(np.int16)

                        # 重采样到目标采样率
                        if device_rate != config.SAMPLE_RATE:
                            audio_data = self._resample(
                                audio_data, device_rate, config.SAMPLE_RATE
                            )

                        self.output_queue.put(
                            AudioChunk(
                                source=SOURCE_SYSTEM,
                                data=audio_data,
                                timestamp=time.time(),
                            )
                        )
                except Exception as e:
                    if self._running:
                        logger.warning(f"系统音频读取异常: {e}")
                    break
        finally:
            pa.terminate()

    @staticmethod
    def _resample(data: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
        """简单线性插值重采样"""
        if orig_rate == target_rate:
            return data
        ratio = target_rate / orig_rate
        new_length = int(len(data) * ratio)
        indices = np.linspace(0, len(data) - 1, new_length)
        return np.interp(indices, np.arange(len(data)), data).astype(np.int16)
