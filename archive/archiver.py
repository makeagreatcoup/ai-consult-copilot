"""
归档模块（以用户为中心）
- 咨询结束后归档到 Obsidian
- 结构：用户/{姓名}/档案.md + 咨询记录.md + 行动方案.md + 音频/
- 档案持续更新，跨免费/付费/陪跑阶段
"""
import json
import logging
import re
from pathlib import Path
from datetime import datetime

import config
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# ─── 模式标签映射 ───

MODE_LABELS = {
    "free-consult": "免费咨询",
    "paid-consult": "付费咨询",
    "coaching": "陪跑复盘",
}


def format_duration(seconds: float) -> str:
    """格式化时长"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}小时{m}分钟{s}秒"
    return f"{m}分钟{s}秒"


class Archiver:
    """以用户为中心的咨询归档器"""

    def __init__(self):
        self._client = None
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保顶层目录存在（用户子目录在归档时按需创建）"""
        config.USER_DIR.mkdir(parents=True, exist_ok=True)
        config.SOP_DIR.mkdir(parents=True, exist_ok=True)
        config.INBOX_DIR.mkdir(parents=True, exist_ok=True)

    def _get_client(self) -> Anthropic:
        if self._client is None:
            self._client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        return self._client

    # ─── 主入口 ───

    def archive_session(self, session_data: dict, user_name: str = "未知用户"):
        """
        归档一次咨询会话。

        参数:
            session_data: {mode, start_time, duration, transcripts, suggestions, audio_data}
            user_name: 用户昵称（从对话中提取，或手动指定）
        """
        mode = session_data.get("mode", "free-consult")
        transcripts = session_data.get("transcripts", [])
        suggestions = session_data.get("suggestions", [])
        duration = session_data.get("duration", 0)
        audio_data = session_data.get("audio_data")  # 音频数据（bytes）

        if not transcripts:
            logger.warning("没有转写记录，跳过归档")
            return

        # 尝试从对话中提取用户称呼
        user_name = self._extract_user_name(transcripts) or user_name
        user_dir = config.USER_DIR / user_name
        user_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        date_str_cn = now.strftime("%Y年%-m月%-d日")
        mode_label = MODE_LABELS.get(mode, mode)
        duration_str = format_duration(duration)

        # 构建对话文本
        conversation = self._build_conversation(transcripts)
        suggestions_text = self._build_suggestions(suggestions)

        # AI 生成总结 + 档案数据
        logger.info("正在生成咨询总结和用户档案更新...")
        summary, profile_data = self._generate_summary_and_profile(
            mode, conversation, suggestions_text
        )

        # 1. 保存咨询记录
        keyword = self._extract_keyword(transcripts)
        record_filename = f"{date_str}-{mode_label}-{keyword}.md"
        record_path = user_dir / record_filename
        record_content = self._render_record(
            date_str_cn, mode, mode_label, duration_str,
            conversation, suggestions_text, summary,
        )
        record_path.write_text(record_content, encoding="utf-8")
        logger.info(f"咨询记录已保存: {record_path}")

        # 2. 更新用户档案（追加/创建）
        profile_path = user_dir / "档案.md"
        self._update_profile(
            profile_path, user_name, date_str, date_str_cn,
            mode_label, keyword, profile_data, record_filename,
        )
        logger.info(f"用户档案已更新: {profile_path}")

        # 3. 保存音频文件（如果有）
        audio_path = None
        if audio_data and config.SAVE_AUDIO:
            audio_path = self._save_audio(
                user_dir, audio_data, mode_label, date_str
            )

        # 4. 生成行动方案（付费咨询和陪跑模式）
        plan_path = None
        if mode in ("paid-consult", "coaching"):
            plan_path = self._generate_action_plan(
                user_dir, user_name, date_str, date_str_cn,
                mode_label, conversation, suggestions_text, summary
            )

        return {
            "record": record_path,
            "profile": profile_path,
            "audio": audio_path,
            "plan": plan_path,
        }

    # ─── 咨询记录渲染 ───

    @staticmethod
    def _render_record(date, mode, mode_label, duration_str,
                       conversation, suggestions, summary):
        return f"""---
type: 咨询记录
mode: {mode}
date: {date}
tags: [咨询, {mode_label}]
---

# {mode_label} - {date}

**时长**: {duration_str}

---

## 完整对话

{conversation}

---

## AI 辅助建议

{suggestions}

---

## 咨询总结

{summary}
"""

    # ─── 用户档案（持续更新型） ───

    def _update_profile(self, profile_path: Path, user_name: str,
                        date_str: str, date_str_cn: str,
                        mode_label: str, keyword: str,
                        profile_data: dict, record_filename: str):
        """创建或追加更新用户档案"""
        wiki_link = f"[[{record_filename}]]"

        if profile_path.exists():
            # 档案已存在 → 追加痛点行 + 咨询历程 + 更新状态
            self._append_to_profile(
                profile_path, date_str, date_str_cn,
                mode_label, keyword, profile_data, wiki_link,
            )
        else:
            # 首次创建档案
            content = self._render_new_profile(
                user_name, date_str, date_str_cn, mode_label,
                keyword, profile_data, wiki_link,
            )
            profile_path.write_text(content, encoding="utf-8")

    def _render_new_profile(self, user_name, date_str, date_str_cn,
                            mode_label, keyword, profile_data, wiki_link):
        """渲染新用户档案"""
        basic_info = profile_data.get("basic_info", "（待补充）")
        pain_point = profile_data.get("pain_points", "（待提取）")
        direction = profile_data.get("direction", "（待提取）")
        follow_up = profile_data.get("follow_up", "（待补充）")

        return f"""---
type: 用户档案
name: {user_name}
first_contact: {date_str}
status: {"付费用户" if mode_label == "付费咨询" else "免费用户"}
tags: [用户档案]
---

# {user_name}

## 基本信息

{basic_info}

## 痛点追踪

| 日期 | 阶段 | 卡点类型 | 具体问题 | 状态 |
|------|------|---------|---------|------|
| {date_str_cn} | {mode_label} | （待分类） | {keyword} | 进行中 |

## 咨询历程

- {date_str_cn} {mode_label} {wiki_link}

## 当前建议方向

{direction}

## 后续跟进

{follow_up}
"""

    def _append_to_profile(self, profile_path: Path, date_str: str,
                           date_str_cn: str, mode_label: str, keyword: str,
                           profile_data: dict, wiki_link: str):
        """追加到已有用户档案"""
        existing = profile_path.read_text(encoding="utf-8")

        # 更新 frontmatter 中的 status
        if mode_label == "付费咨询" and "status: 免费用户" in existing:
            existing = existing.replace("status: 免费用户", "status: 付费用户")
        elif mode_label == "陪跑复盘":
            existing = existing.replace("status: 付费用户", "status: 陪跑学员")

        # 追加痛点行
        pain_point = profile_data.get("pain_points", keyword)
        pain_row = f"| {date_str_cn} | {mode_label} | （待分类） | {pain_point} | 进行中 |"
        existing = self._insert_after(existing, "## 痛点追踪", pain_row, is_table=True)

        # 追加咨询历程
        history_line = f"- {date_str_cn} {mode_label} {wiki_link}"
        existing = self._insert_after(existing, "## 咨询历程", history_line)

        # 更新建议方向（覆盖旧内容）
        direction = profile_data.get("direction")
        if direction:
            existing = self._replace_section(
                existing, "## 当前建议方向", "## 咨询历程", direction,
            )

        # 追加后续跟进
        follow_up = profile_data.get("follow_up")
        if follow_up:
            follow_block = f"\n**{date_str_cn} 更新**：{follow_up}"
            existing = self._insert_after(existing, "## 后续跟进", follow_block)

        profile_path.write_text(existing, encoding="utf-8")

    # ─── 文本操作工具 ───

    @staticmethod
    def _insert_after(text: str, heading: str, line: str,
                      is_table: bool = False) -> str:
        """在指定标题后插入一行"""
        idx = text.find(heading)
        if idx < 0:
            return text

        # 找到标题行的末尾
        line_end = text.find("\n", idx)
        # 跳过空行和表头（如果是表格插入）
        insert_at = line_end + 1

        if is_table:
            # 跳过表头行和分隔行（|---|---|）
            for _ in range(2):
                next_newline = text.find("\n", insert_at)
                if next_newline >= 0:
                    insert_at = next_newline + 1

        return text[:insert_at] + line + "\n" + text[insert_at:]

    @staticmethod
    def _replace_section(text: str, section_start: str,
                         next_section: str, new_content: str) -> str:
        """替换两个标题之间的内容"""
        start_idx = text.find(section_start)
        if start_idx < 0:
            return text

        end_idx = text.find(next_section, start_idx + len(section_start))
        if end_idx < 0:
            # 没有下一个标题，替换到文件末尾
            return text[:start_idx] + section_start + "\n\n" + new_content + "\n"

        return text[:start_idx] + section_start + "\n\n" + new_content + "\n\n" + text[end_idx:]

    # ─── AI 总结生成 ───

    def _generate_summary_and_profile(self, mode: str,
                                       conversation: str, suggestions: str) -> tuple:
        """调用 Claude 生成咨询总结和用户档案数据"""
        client = self._get_client()

        prompt = f"""请根据以下咨询对话记录，生成两部分内容：

**第一部分：咨询总结**
- 核心问题（1-2句话概括）
- 建议方向（列出2-3个要点）
- 关键转折点（如果有的话）

**第二部分：用户档案数据**
请用 JSON 格式输出，包含以下字段：
- basic_info: 用户基本信息（背景、职业、现状等，从对话中推断）
- pain_points: 核心痛点（简洁描述，用于填入表格）
- direction: 建议方向（具体可执行的）
- follow_up: 后续跟进建议

对话记录：
{conversation}

AI辅助建议：
{suggestions}

请先用「## 咨询总结」输出总结，然后用 ```json ``` 输出用户档案JSON。"""

        try:
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            summary = text
            profile_data = {}

            json_start = text.find("```json")
            if json_start >= 0:
                summary = text[:json_start].strip()
                json_text = text[json_start + 7:]
                json_end = json_text.find("```")
                if json_end >= 0:
                    json_text = json_text[:json_end].strip()
                    profile_data = json.loads(json_text)

            return summary, profile_data

        except Exception as e:
            logger.error(f"总结生成失败: {e}")
            return "（自动生成失败，请手动补充）", {}

    # ─── 文本构建工具 ───

    @staticmethod
    def _build_conversation(transcripts: list) -> str:
        lines = []
        for t in transcripts:
            time_str = t.get("time_str", "")
            speaker = t.get("speaker", "")
            text = t.get("text", "")
            lines.append(f"**{time_str}** {speaker}：{text}")
        return "\n\n".join(lines)

    @staticmethod
    def _build_suggestions(suggestions: list) -> str:
        if not suggestions:
            return "无"
        lines = []
        for s in suggestions:
            time_str = s.get("time_str", "")
            label = s.get("label", "")
            text = s.get("text", "")
            lines.append(f"- **{time_str}** [{label}] {text}")
        return "\n".join(lines)

    @staticmethod
    def _extract_keyword(transcripts: list) -> str:
        """从对话中提取关键词作为文件名"""
        for t in transcripts:
            if t.get("source") == "system":
                text = t.get("text", "")
                clean = re.sub(r'[\\/:*?"<>|]', '', text[:15]).strip()
                return clean or "咨询"
        return "咨询"

    @staticmethod
    def _extract_user_name(transcripts: list) -> str:
        """尝试从对话中提取用户称呼"""
        for t in transcripts:
            text = t.get("text", "")
            # 匹配"我是XXX""我叫XXX""我叫XXX"等模式
            match = re.search(r'(?:我是|我叫|名字叫|叫我)\s*([\u4e00-\u9fa5]{2,4})', text)
            if match:
                return match.group(1)
        return ""

    # ─── 音频归档 ───

    def _save_audio(self, user_dir: Path, audio_data: bytes,
                    mode_label: str, date_str: str) -> Path:
        """保存咨询音频到用户目录"""
        audio_dir = user_dir / config.AUDIO_DIR_NAME
        audio_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{date_str}-{mode_label}.{config.AUDIO_FORMAT}"
        audio_path = audio_dir / filename
        audio_path.write_bytes(audio_data)
        logger.info(f"音频已保存: {audio_path}")
        return audio_path

    # ─── 行动方案生成 ───

    def _generate_action_plan(self, user_dir: Path, user_name: str,
                              date_str: str, date_str_cn: str,
                              mode_label: str, conversation: str,
                              suggestions: str, summary: str) -> Path:
        """生成并保存行动方案"""
        plan_content = self._call_claude_for_plan(
            mode_label, conversation, suggestions, summary
        )

        plan_filename = f"{date_str}-{mode_label}-行动方案.md"
        plan_path = user_dir / plan_filename

        plan_yaml = f"""---
type: 行动方案
mode: {mode_label}
date: {date_str}
tags: [行动方案, {mode_label}]
---

# 行动方案 - {user_name} - {date_str_cn}

"""
        plan_path.write_text(plan_yaml + plan_content, encoding="utf-8")
        logger.info(f"行动方案已保存: {plan_path}")
        return plan_path

    def _call_claude_for_plan(self, mode_label: str, conversation: str,
                              suggestions: str, summary: str) -> str:
        """调用 Claude 生成行动方案内容"""
        client = self._get_client()

        prompt = f"""请根据以下咨询对话，生成一份可执行的行动方案。

要求：
1. 本次咨询摘要：用表格列出咨询时间、核心卡点、关键转折
2. 当前状态诊断：基于对话内容评估用户的职业现状、能力缺口、心力状态
3. 30天行动路径：分3个阶段，每阶段有具体可执行的行动项（用 checkbox 格式 - [ ]）
4. 复盘检查点：每周一个检查项，方便后续复盘时对照
5. 资源清单：推荐具体的工具、教程、资料（如果对话中提到了）
6. 下次复盘重点：基于本次对话，下次应该关注什么

注意：
- 行动项要具体可执行，不要泛泛建议
- 时间节点要明确（如：6.18-6.28）
- 保持简洁，总长度控制在1500字以内

对话记录：
{conversation}

AI辅助建议：
{suggestions}

咨询总结：
{summary}

请直接输出 Markdown 格式的行动方案内容（不要包含 YAML frontmatter）。"""

        try:
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"行动方案生成失败: {e}")
            return "（自动生成失败，请根据咨询记录手动补充）"
