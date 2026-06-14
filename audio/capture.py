"""
双路音频采集模块
- 系统音频（WASAPI Loopback）：捕获腾讯会议扬声器输出
- 麦克风：捕获本地麦克风输入
"""
import threading
import queue
import time
import logging
from collections import deque

import numpy as np
import pyaudio

import config

logger = logging.getLogger(__name__)

# 音频数据标签
SOURCE_SYSTEM = "system"       # 系统音频 = 对方说话
SOURCE_MICROPHONE = "mic"      # 麦克风 = 自己说话


class AudioChunk:
    """带标签的音频数据块"""
    __slots__ = ("source", "data", "timestamp")

    def __init__(self, source: str, data: np.ndarray, timestamp: float):
        self.source = source
        self.data = data
        self.timestamp = timestamp


class SystemAudioCapture:
    """WASAPI Loopback 采集系统音频（腾讯会议对方的声音）"""

    def __init__(self, output_queue: queue.Queue):
        self.output_queue = output_queue
        self._running = False
        self._thread = None
        self._pa = None

    def _find_loopback_device(self) -> dict:
        """查找 WASAPI Loopback 设备"""
        try:
            import pyaudiowpatch as pyaudiowp
            pa = pyaudiowp.PyAudio()
            try:
                # 获取默认扬声器，然后用它的 loopback
                wasapi_info = pa.get_wasapi_loopback()
                logger.info(f"找到 WASAPI Loopback: {wasapi_info['name']}")
                return wasapi_info
            finally:
                pa.terminate()
        except ImportError:
            logger.warning("pyaudiowpatch 未安装，系统音频采集不可用")
        except Exception as e:
            logger.warning(f"WASAPI Loopback 查找失败: {e}")
        return None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("系统音频采集已启动")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("系统音频采集已停止")

    def _capture_loop(self):
        try:
            import pyaudiowpatch as pyaudiowp
        except ImportError:
            logger.error("pyaudiowpatch 未安装，无法采集系统音频")
            return

        loopback_info = self._find_loopback_device()
        if not loopback_info:
            logger.error("未找到 WASAPI Loopback 设备")
            return

        pa = pyaudiowp.PyAudio()
        try:
            # 使用设备的原始采样率，后续重采样到16kHz
            device_rate = int(loopback_info.get("defaultSampleRate", 44100))
            stream = pa.open(
                format=pyaudiowp.paInt16,
                channels=1,
                rate=device_rate,
                input=True,
                input_device_index=loopback_info["index"],
                frames_per_buffer=config.CHUNK_SIZE,
            )

            logger.info(f"系统音频流已打开，采样率: {device_rate}")
            buffer = bytearray()

            while self._running:
                try:
                    raw = stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                    buffer.extend(raw)

                    # 累积约0.5秒的数据后发送（减少队列压力）
                    chunk_samples = int(device_rate * 0.5)
                    chunk_bytes = chunk_samples * 2  # int16 = 2 bytes

                    if len(buffer) >= chunk_bytes:
                        audio_data = np.frombuffer(bytes(buffer[:chunk_bytes]), dtype=np.int16)
                        buffer = buffer[chunk_bytes:]

                        # 重采样到目标采样率
                        if device_rate != config.SAMPLE_RATE:
                            audio_data = self._resample(audio_data, device_rate, config.SAMPLE_RATE)

                        self.output_queue.put(AudioChunk(
                            source=SOURCE_SYSTEM,
                            data=audio_data,
                            timestamp=time.time(),
                        ))
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


class MicrophoneCapture:
    """麦克风采集（自己的声音）"""

    def __init__(self, output_queue: queue.Queue):
        self.output_queue = output_queue
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("麦克风采集已启动")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("麦克风采集已停止")

    def _capture_loop(self):
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=config.CHANNELS,
                rate=config.SAMPLE_RATE,
                input=True,
                frames_per_buffer=config.CHUNK_SIZE,
            )

            buffer = bytearray()

            while self._running:
                try:
                    raw = stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
                    buffer.extend(raw)

                    chunk_samples = int(config.SAMPLE_RATE * 0.5)
                    chunk_bytes = chunk_samples * 2

                    if len(buffer) >= chunk_bytes:
                        audio_data = np.frombuffer(bytes(buffer[:chunk_bytes]), dtype=np.int16)
                        buffer = buffer[chunk_bytes:]

                        self.output_queue.put(AudioChunk(
                            source=SOURCE_MICROPHONE,
                            data=audio_data,
                            timestamp=time.time(),
                        ))
                except Exception as e:
                    if self._running:
                        logger.warning(f"麦克风读取异常: {e}")
                    break
        finally:
            pa.terminate()


class DualAudioCapture:
    """双路音频采集管理器"""

    def __init__(self):
        self.audio_queue = queue.Queue()
        self._system_capture = SystemAudioCapture(self.audio_queue)
        self._mic_capture = MicrophoneCapture(self.audio_queue)
        self._running = False

    def start(self):
        self._running = True
        self._system_capture.start()
        self._mic_capture.start()
        logger.info("双路音频采集已启动")

    def stop(self):
        self._running = False
        self._system_capture.stop()
        self._mic_capture.stop()
        logger.info("双路音频采集已停止")

    def get_chunk(self, timeout: float = 0.1) -> AudioChunk | None:
        """获取一个音频块"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_running(self) -> bool:
        return self._running
