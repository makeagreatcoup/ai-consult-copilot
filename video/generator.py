"""
视频生成器 - 逐字弹出动画
横排逐字跳出 → 竖排逐字跳出 → 横排 → 竖排 交替
"""
import logging
import math
import numpy as np
from pathlib import Path
from typing import List
from moviepy import VideoClip, AudioFileClip

from video.text_animator import (
    render_progressive, render_intro_frame, COLOR_SCHEMES
)

logger = logging.getLogger(__name__)


def generate_text_video(
    audio_path: str,
    segments: List[dict],
    output_path: str,
    title: str = "",
    width: int = 1080,
    height: int = 1920,
    fps: int = 24,
    char_interval: float = 0.18,
) -> str:
    """
    生成逐字弹出视频

    Args:
        audio_path: 音频文件路径
        segments: [{"text": "...", "start": 0.0, "end": 2.5}]
        output_path: 输出 MP4 路径
        title: 片头标题
        char_interval: 每个字弹出的间隔（秒）
    """
    logger.info(f"开始生成逐字弹出视频: {output_path}")

    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration
    logger.info(f"音频时长: {audio_duration:.1f}s, 片段数: {len(segments)}")

    # 构建时间线
    # 每个 segment 对应一段时间段，内部逐字弹出
    timeline = []
    cursor = 0.0

    intro_duration = 0.0
    if title:
        # 片头：每个字 char_interval 秒，加 0.5s 停留
        intro_chars = len(title)
        intro_duration = intro_chars * char_interval + 0.8
        timeline.append({
            "type": "intro",
            "title": title,
            "start": 0.0,
            "end": intro_duration,
        })
        cursor = intro_duration

    # 为每个 segment 分配配色和方向
    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if not text or len(text) < 2:
            continue

        n_chars = len(text)
        seg_duration = n_chars * char_interval + 0.6  # 弹完+停留

        start = max(seg.get("start", cursor), cursor)

        # 如果有间隙，黑帧填充
        if start > cursor + 0.1:
            timeline.append({
                "type": "black",
                "start": cursor,
                "end": start,
            })
            cursor = start

        orientation = "h" if i % 2 == 0 else "v"
        scheme = COLOR_SCHEMES[i % len(COLOR_SCHEMES)]

        timeline.append({
            "type": "text",
            "text": text,
            "orientation": orientation,
            "scheme": scheme,
            "n_chars": n_chars,
            "start": cursor,
            "end": cursor + seg_duration,
        })
        cursor += seg_duration

    # 尾部黑帧补齐
    if cursor < audio_duration:
        timeline.append({
            "type": "black",
            "start": cursor,
            "end": audio_duration,
        })

    logger.info(f"时间线: {len(timeline)} 段")

    def make_frame(t):
        """根据时间 t 渲染对应帧"""
        for seg in timeline:
            if seg["start"] <= t < seg["end"]:
                if seg["type"] == "black":
                    return np.zeros((height, width, 3), dtype=np.uint8)

                elif seg["type"] == "intro":
                    # 片头逐字
                    elapsed = t - seg["start"]
                    pop_duration = len(seg["title"]) * char_interval
                    if elapsed < pop_duration:
                        progress = elapsed / pop_duration
                    else:
                        progress = 1.0
                    return render_intro_frame(seg["title"], progress,
                                             width, height)

                elif seg["type"] == "text":
                    # 正文逐字
                    elapsed = t - seg["start"]
                    pop_duration = seg["n_chars"] * char_interval
                    if elapsed < pop_duration:
                        visible = int(elapsed / char_interval)
                    else:
                        visible = seg["n_chars"]
                    return render_progressive(
                        seg["text"], seg["orientation"], visible,
                        width, height, seg["scheme"]
                    )

        # fallback
        return np.zeros((height, width, 3), dtype=np.uint8)

    video = VideoClip(make_frame, duration=audio_duration)
    video = video.with_audio(audio)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    video.write_videofile(
        str(output),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        bitrate="2000k",
        preset="medium",
        ffmpeg_params=["-pix_fmt", "yuv420p"],
        logger=None,
    )

    video.close()
    audio.close()

    file_size = output.stat().st_size / 1024 / 1024
    logger.info(f"视频生成完成: {output} ({file_size:.1f}MB)")
    return str(output)


def generate_from_transcript(
    audio_path: str,
    transcript_text: str,
    output_path: str,
    title: str = "",
    char_interval: float = 0.18,
) -> str:
    """
    从纯文本生成逐字弹出视频
    按标点切分为句子，每句交替横竖
    """
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    audio.close()

    import re
    sentences = re.split(r'[。！？；，、\n]+', transcript_text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 1]

    # 时间戳：按字数比例分配
    total_chars = sum(len(s) for s in sentences)
    if total_chars == 0:
        return ""

    segments = []
    cursor = 0.0
    for sent in sentences:
        dur = (len(sent) / total_chars) * total_duration
        segments.append({
            "text": sent,
            "start": cursor,
            "end": cursor + dur,
        })
        cursor += dur

    return generate_text_video(
        audio_path=audio_path,
        segments=segments,
        output_path=output_path,
        title=title,
        char_interval=char_interval,
    )
