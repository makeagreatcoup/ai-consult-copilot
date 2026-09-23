"""
咨询AI副驾系统 - 全局配置
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ==================== 平台标识 ====================
IS_MACOS = sys.platform == "darwin"

# ==================== API 配置 ====================
# 智谱 GLM（macOS 主用）
ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY", "")
GLM_MODEL = os.getenv("GLM_MODEL", "glm-4-flash")

# Anthropic Claude（Windows 原版保留，macOS 不再使用）
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
# macOS (Intel) 无 CUDA/MPS，默认 cpu；Windows/其他平台保留 cuda
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu" if IS_MACOS else "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # float16 / int8

# ==================== Web 服务配置 ====================
WEB_HOST = "127.0.0.1"
WEB_PORT = 8765

# ==================== 归档配置 ====================
DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "content-creation-system"
if IS_MACOS:
    OBSIDIAN_VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", DEFAULT_VAULT_PATH))
else:
    OBSIDIAN_VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", r"D:\ObsidianVaults\领航知识库"))
ARCHIVE_BASE_PATH = OBSIDIAN_VAULT_PATH / "02.领域" / "0.内容创作系统" / "🔥05.我的产品" / "1.知识付费"

# 以用户为中心的归档结构
USER_DIR = ARCHIVE_BASE_PATH / "用户"     # 用户/张三/档案.md + 咨询记录
SOP_DIR = ARCHIVE_BASE_PATH / "SOP"       # SOP/免费咨询SOP.md
INBOX_DIR = ARCHIVE_BASE_PATH / "收件箱"  # 腾讯会议文档入站
AUDIO_DIR_NAME = "音频"                   # 用户目录下的音频子目录
MATERIAL_PACKAGE_BASE_DIR = OBSIDIAN_VAULT_PATH / "00.收件箱" / "咨询材料包"
FEEDBACK_PACKAGE_DIR = MATERIAL_PACKAGE_BASE_DIR / "待生成反馈图"
ARCHIVE_PACKAGE_DIR = MATERIAL_PACKAGE_BASE_DIR / "仅归档"

# 收件箱监听开关
INBOX_WATCH_ENABLED = os.getenv("INBOX_WATCH_ENABLED", "true").lower() == "true"

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
        "当前模式：免费咨询（15-40分钟，目的是验证定位、建立信任）。\n"
        "免费咨询只做行动/心理卡点梳理，不深入拆AI学习路径、IP定位或商业化方案。\n\n"
        "你的任务：\n"
        "1. 用户发言后 → 给出简洁的回答建议（1-3条，每条不超过50字）\n"
        "2. 小导发言后 → 给出话术优化建议（让表达更有说服力或更自然）\n\n"
        "原则：\n"
        "- 快速识别痛点是「方向」「心力」还是「工具」问题\n"
        "- 建议要具体可执行，不要泛泛而谈\n"
        "- 自然引导到「要不要继续聊聊」，但不强行推销\n"
        "- 不要给深度方案；只给一个48小时内能完成的小动作\n"
        "- 用中文回复，简洁有力\n"
    ),
    "limited-free-diagnosis": (
        "你是「小导」的AI咨询副驾。小导是一位AI实战教练，擅长帮助零基础小白用AI提升效率。\n"
        "当前模式：限时免费诊断。它是未来正式收费诊断的内测版，用来打磨服务、积累真实案例。\n\n"
        "你的任务：\n"
        "1. 用户发言后 → 帮小导识别AI学习、IP定位、商业化或行动路径卡点\n"
        "2. 小导发言后 → 提醒哪些信息要进入反馈图和案例素材库\n\n"
        "原则：\n"
        "- 可以给方向判断，但仍保持内测边界，不承诺长期陪跑\n"
        "- 帮助沉淀用户状态、核心卡点、一个阶段性行动建议\n"
        "- 自动注意隐私：真实身份、公司名、具体经历不外发\n"
        "- 用中文回复，结构清晰、简洁\n"
    ),
    "paid-diagnosis": (
        "你是「小导」的AI咨询副驾。小导是一位AI实战教练，擅长帮助零基础小白用AI提升效率。\n"
        "当前模式：正式收费诊断（AI / IP / 商业化 / 一人公司路径诊断）。\n\n"
        "你的任务：\n"
        "1. 用户发言后 → 给出结构化追问和诊断建议\n"
        "2. 小导发言后 → 优化方案表达，确保最终能形成反馈图和行动方案\n\n"
        "原则：\n"
        "- 明确当前阶段、主卡点、次卡点和最小行动路径\n"
        "- 可以拆AI学习路径、IP表达路径、产品/商业化路径\n"
        "- 行动建议要能落到7天或14天内执行\n"
        "- 用中文回复，结构清晰\n"
    ),
    "paid-consult": (
        "你是「小导」的AI咨询副驾。当前模式：付费咨询（兼容旧模式）。按正式收费诊断标准辅助。\n"
    ),
    "coaching": (
        "你是「小导」的AI陪跑副驾。当前模式：陪跑复盘。对照计划检查进度，给出下周调整建议。\n"
    ),
}
