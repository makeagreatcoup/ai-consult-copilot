"""
咨询AI副驾系统 - 全局配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ==================== API 配置 ====================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# ==================== 音频配置 ====================
SAMPLE_RATE = 16000          # 目标采样率（Whisper要求）
CHANNELS = 1                 # 单声道
CHUNK_SIZE = 1024            # 每次读取的帧数
DTYPE = "int16"              # 采样位深

# ==================== VAD 配置 ====================
VAD_SILENCE_DURATION = 1.5   # 静音判定时长（秒）
VAD_ENERGY_THRESHOLD = 300   # 能量阈值（int16 范围）
VAD_MIN_SPEECH_DURATION = 0.3  # 最短有效语音时长（秒）

# ==================== Whisper 配置 ====================
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # tiny/base/small/medium
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")  # cuda / cpu
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # float16 / int8

# ==================== Web 服务配置 ====================
WEB_HOST = "127.0.0.1"
WEB_PORT = 8765

# ==================== 归档配置 ====================
OBSIDIAN_VAULT_PATH = Path(r"D:\ObsidianVaults\领航知识库")
ARCHIVE_BASE_PATH = OBSIDIAN_VAULT_PATH / "02.领域" / "0.内容创作系统" / "🔥我的产品" / "1.知识付费"

# 以用户为中心的归档结构
USER_DIR = ARCHIVE_BASE_PATH / "用户"     # 用户/张三/档案.md + 咨询记录
SOP_DIR = ARCHIVE_BASE_PATH / "SOP"       # SOP/免费咨询SOP.md
INBOX_DIR = ARCHIVE_BASE_PATH / "收件箱"  # 腾讯会议文档入站
AUDIO_DIR_NAME = "音频"                   # 用户目录下的音频子目录

# 音频保存配置
SAVE_AUDIO = True                         # 是否保存咨询音频
AUDIO_FORMAT = "wav"                      # 音频格式

# ==================== AI 建议配置 ====================
CONTEXT_WINDOW = 10          # 保留最近N轮对话作为上下文
API_COOLDOWN = 3.0           # 同一发言者两次API调用最小间隔（秒）
MAX_SUGGESTION_LENGTH = 200  # 单条建议最大字符数

# ==================== 咨询模式系统提示词 ====================
MODE_PROMPTS = {
    "free-consult": (
        "你是「小导」的AI咨询副驾。小导是一位AI实战教练，擅长帮助零基础小白用AI提升效率。\n"
        "当前模式：免费咨询（15-40分钟，目的是验证定位、建立信任）。\n\n"
        "你的任务：\n"
        "1. 用户发言后 → 给出简洁的回答建议（1-3条，每条不超过50字）\n"
        "2. 小导发言后 → 给出话术优化建议（让表达更有说服力或更自然）\n\n"
        "原则：\n"
        "- 快速识别痛点是「方向」「心力」还是「工具」问题\n"
        "- 建议要具体可执行，不要泛泛而谈\n"
        "- 自然引导到「要不要继续聊聊」，但不强行推销\n"
        "- 不要给深度方案（免费阶段目的是验证定位，不是解决问题）\n"
        "- 用中文回复，简洁有力\n"
    ),
    "paid-consult": (
        "你是「小导」的AI咨询副驾。小导是一位AI实战教练，擅长帮助零基础小白用AI提升效率。\n"
        "当前模式：付费咨询（深度诊断 + 方案设计）。\n\n"
        "你的任务：\n"
        "1. 用户发言后 → 给出深度回答建议，包含具体步骤\n"
        "2. 小导发言后 → 优化话术，确保方案表达清晰、可量化\n\n"
        "原则：\n"
        "- 给具体可执行的方案，不要泛泛建议\n"
        "- 帮助拆解为周计划和行动清单\n"
        "- 如果有上次咨询记录，追踪执行进度\n"
        "- 用中文回复，结构清晰\n"
    ),
    "coaching": (
        "你是「小导」的AI陪跑副驾。小导是一位AI实战教练，正在做30天陪跑课程。\n"
        "当前模式：陪跑复盘（检查进度 + 调整计划）。\n\n"
        "你的任务：\n"
        "1. 学员发言后 → 对照计划检查进度，给出调整建议\n"
        "2. 小导发言后 → 优化指导话术，确保学员能听懂\n\n"
        "原则：\n"
        "- 对照上周计划，逐项检查\n"
        "- 识别卡点是「工具」「方向」还是「心力」\n"
        "- 给出下周调整建议\n"
        "- 用中文回复，鼓励为主\n"
    ),
}
