"""
测试脚本：生成一个简短的文字动画视频
"""
import sys
import wave
from pathlib import Path

# 确保项目根目录在 path 中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def generate_test_audio(path: str, duration: float = 15.0):
    """生成一段静音测试音频（只测试文字动画，不生成刺耳音频）"""
    sample_rate = 16000
    num_samples = int(duration * sample_rate)

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 全零 = 静音
        wf.writeframes(b'\x00' * (num_samples * 2))

    print(f"测试音频已生成（静音）: {path} ({duration}s)")


def test_video():
    """主测试函数"""
    print("=" * 50)
    print("文字动画视频生成测试")
    print("=" * 50)

    # 准备输出目录
    output_dir = Path("D:/workspace/consult-copilot/output")
    output_dir.mkdir(exist_ok=True)

    # 1. 生成测试音频
    audio_path = str(output_dir / "test_audio.wav")
    generate_test_audio(audio_path, duration=12.0)

    # 2. 准备测试文本（模拟咨询对话片段）
    test_segments = [
        {"text": "很多人学AI的第一步就错了", "start": 0.0, "end": 2.5},
        {"text": "他们去搜教程", "start": 2.8, "end": 4.0},
        {"text": "然后跟着教程一步步做", "start": 4.2, "end": 6.0},
        {"text": "做完之后发现", "start": 6.2, "end": 7.5},
        {"text": "自己根本不知道为什么这么做", "start": 7.8, "end": 10.0},
        {"text": "这就是问题所在", "start": 10.3, "end": 12.0},
    ]

    # 3. 生成视频
    from video.generator import generate_text_video

    output_path = str(output_dir / "test_text_video.mp4")
    print(f"\n开始生成视频...")
    result = generate_text_video(
        audio_path=audio_path,
        segments=test_segments,
        output_path=output_path,
        title="AI学习最大的误区",
    )

    print(f"\n[OK] 视频生成成功: {result}")
    size_mb = Path(result).stat().st_size / 1024 / 1024
    print(f"   文件大小: {size_mb:.1f} MB")

    # 4. 也测试一下纯文本模式
    print(f"\n测试纯文本模式...")
    transcript = """很多人学AI的第一步就错了。
他们去搜教程，然后跟着教程一步步做。
做完之后发现，自己根本不知道为什么这么做。
这就是问题所在。"""
    output_path2 = str(output_dir / "test_text_video_v2.mp4")
    from video.generator import generate_from_transcript
    result2 = generate_from_transcript(
        audio_path=audio_path,
        transcript_text=transcript,
        output_path=output_path2,
        title="AI学习最大的误区",
    )
    print(f"\n[OK] 纯文本模式视频生成成功: {result2}")
    size_mb2 = Path(result2).stat().st_size / 1024 / 1024
    print(f"   文件大小: {size_mb2:.1f} MB")


if __name__ == "__main__":
    test_video()
