"""
AI 实时建议模块
- 维护对话上下文
- 用户发言 → 回答建议
- 自己发言 → 话术优化
"""
import time
import logging
import threading
import queue
from dataclasses import dataclass

import anthropic

import config
from transcriber.whisper_stream import Transcript

logger = logging.getLogger(__name__)

# 发言者映射
SPEAKER_MAP = {
    "system": "用户",    # 系统音频 = 对方
    "mic": "我",         # 麦克风 = 自己
}


@dataclass
class AISuggestion:
    """AI 建议结果"""
    trigger_source: str   # 触发来源
    trigger_text: str     # 触发文本
    suggestion: str       # 建议内容
    suggestion_type: str  # answer / refine
    timestamp: float = 0.0


class AIAdvisor:
    """Claude API 实时建议器"""

    def __init__(self, mode: str = "free-consult"):
        self.mode = mode
        self._client = None
        self._context: list[dict] = []  # 对话上下文 [{role, content}]
        self._last_api_time = 0.0
        self._running = False
        self._thread = None
        self._input_queue = queue.Queue()
        self.output_queue = queue.Queue()

    def start(self):
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._running = True
        self._thread = threading.Thread(target=self._advise_loop, daemon=True)
        self._thread.start()
        logger.info(f"AI 建议器已启动，模式: {self.mode}")

    def stop(self):
        self._running = False
        self._input_queue.put(None)
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("AI 建议器已停止")

    def set_mode(self, mode: str):
        """切换咨询模式"""
        self.mode = mode
        self._context.clear()
        logger.info(f"AI 模式切换为: {mode}")

    def submit_transcript(self, transcript: Transcript):
        """提交一条转写结果"""
        if self._running:
            self._input_queue.put(transcript)

    def get_context_text(self) -> str:
        """获取当前对话上下文（用于归档）"""
        lines = []
        for entry in self._context:
            lines.append(f"{entry['speaker']}：{entry['text']}")
        return "\n".join(lines)

    def _advise_loop(self):
        """建议生成主循环"""
        while self._running:
            try:
                item = self._input_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if item is None:
                break

            if isinstance(item, Transcript):
                self._process_transcript(item)

    def _process_transcript(self, transcript: Transcript):
        """处理一条转写，生成建议"""
        speaker = SPEAKER_MAP.get(transcript.source, "未知")
        text = transcript.text.strip()

        if not text:
            return

        # 加入上下文
        self._context.append({
            "speaker": speaker,
            "text": text,
            "timestamp": transcript.start_time,
        })

        # 维护上下文窗口
        if len(self._context) > config.CONTEXT_WINDOW:
            self._context = self._context[-config.CONTEXT_WINDOW:]

        # 冷却检查
        now = time.time()
        if now - self._last_api_time < config.API_COOLDOWN:
            return

        # 构建对话历史
        conversation = self._build_conversation()

        # 判断建议类型
        if transcript.source == "system":
            suggestion_type = "answer"
            task = "用户刚说了这段话，请给出简洁的回答建议（1-3条）。"
        else:
            suggestion_type = "refine"
            task = "我刚说了这段话，请给出话术优化建议（让表达更有说服力或更自然）。"

        try:
            suggestion_text = self._call_claude(task, conversation)
            self._last_api_time = time.time()

            suggestion = AISuggestion(
                trigger_source=transcript.source,
                trigger_text=text,
                suggestion=suggestion_text,
                suggestion_type=suggestion_type,
                timestamp=time.time(),
            )
            self.output_queue.put(suggestion)

        except Exception as e:
            logger.error(f"AI 建议生成失败: {e}")

    def _build_conversation(self) -> str:
        """构建对话历史文本"""
        lines = []
        for entry in self._context:
            lines.append(f"{entry['speaker']}：{entry['text']}")
        return "\n".join(lines)

    def _call_claude(self, task: str, conversation: str) -> str:
        """调用 Claude API"""
        system_prompt = config.MODE_PROMPTS.get(self.mode, config.MODE_PROMPTS["free-consult"])

        message = self._client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=300,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"当前对话：\n{conversation}\n\n任务：{task}\n\n请直接给出建议，不要多余的解释。"
                }
            ],
        )

        return message.content[0].text.strip()
