"""
收件箱监听器 - 自动处理腾讯会议文档
- 监听收件箱目录，有新文档进入时自动处理
- 解析文档内容，匹配用户，生成咨询记录
"""
import logging
from pathlib import Path
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config

logger = logging.getLogger(__name__)


class InboxHandler(FileSystemEventHandler):
    """收件箱文件处理器"""

    def __init__(self):
        self._supported_extensions = {".docx", ".doc", ".txt", ".md", ".pdf"}

    def on_created(self, event):
        """文件创建事件"""
        if event.is_directory:
            return

        filepath = Path(event.src_path)
        if filepath.suffix.lower() in self._supported_extensions:
            logger.info(f"检测到新文件: {filepath.name}")
            self._process_file(filepath)

    def on_moved(self, event):
        """文件移动事件（有些应用先创建临时文件再重命名）"""
        if event.is_directory:
            return

        dest_path = Path(event.dest_path)
        if dest_path.suffix.lower() in self._supported_extensions:
            logger.info(f"检测到文件移入: {dest_path.name}")
            self._process_file(dest_path)

    def _process_file(self, filepath: Path):
        """处理收件箱中的文件"""
        try:
            # 1. 解析文档内容
            content = self._read_document(filepath)
            if not content:
                logger.warning(f"无法读取文档内容: {filepath.name}")
                return

            # 2. 尝试匹配用户（基于文件名或内容）
            user_name = self._extract_user_from_document(filepath, content)
            if not user_name:
                user_name = "未匹配用户"
                logger.warning(f"无法匹配用户，文件暂存到: {user_name}")

            # 3. 创建用户目录（如果不存在）
            user_dir = config.USER_DIR / user_name
            user_dir.mkdir(parents=True, exist_ok=True)

            # 4. 复制文档到用户目录
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            new_filename = f"{date_str}-腾讯会议-{filepath.stem}{filepath.suffix}"
            dest_path = user_dir / new_filename

            # 复制文件内容
            dest_path.write_bytes(filepath.read_bytes())
            logger.info(f"文档已归档: {dest_path}")

            # 5. 移动原文件到已处理目录（或删除）
            self._archive_original(filepath)

        except Exception as e:
            logger.error(f"处理文件失败 {filepath.name}: {e}")

    def _read_document(self, filepath: Path) -> str:
        """读取文档内容"""
        suffix = filepath.suffix.lower()

        if suffix in {".txt", ".md"}:
            return filepath.read_text(encoding="utf-8")
        elif suffix == ".docx":
            return self._read_docx(filepath)
        elif suffix == ".pdf":
            return self._read_pdf(filepath)
        else:
            return ""

    def _read_docx(self, filepath: Path) -> str:
        """读取 Word 文档"""
        try:
            from docx import Document
            doc = Document(str(filepath))
            return "\n".join([para.text for para in doc.paragraphs])
        except ImportError:
            logger.warning("python-docx 未安装，无法读取 .docx 文件")
            return ""
        except Exception as e:
            logger.error(f"读取 docx 失败: {e}")
            return ""

    def _read_pdf(self, filepath: Path) -> str:
        """读取 PDF 文档"""
        try:
            import PyPDF2
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except ImportError:
            logger.warning("PyPDF2 未安装，无法读取 .pdf 文件")
            return ""
        except Exception as e:
            logger.error(f"读取 PDF 失败: {e}")
            return ""

    def _extract_user_from_document(self, filepath: Path, content: str) -> str:
        """从文档中提取用户名称"""
        import re

        # 尝试从文件名提取
        filename = filepath.stem
        # 匹配 "腾讯会议_2026-06-18_10-00-xxx_用户姓名" 格式
        match = re.search(r'[_-]([\u4e00-\u9fa5]{2,4})[_-]?', filename)
        if match:
            return match.group(1)

        # 尝试从内容提取（前500字）
        content_preview = content[:500]
        match = re.search(r'(?:咨询对象|用户|学员)[：:]\s*([\u4e00-\u9fa5]{2,4})', content_preview)
        if match:
            return match.group(1)

        return ""

    def _archive_original(self, filepath: Path):
        """归档原始文件"""
        # 创建已处理目录
        processed_dir = config.INBOX_DIR / "已处理"
        processed_dir.mkdir(parents=True, exist_ok=True)

        # 移动文件
        dest = processed_dir / filepath.name
        try:
            filepath.rename(dest)
            logger.info(f"原始文件已移动: {dest}")
        except Exception as e:
            logger.warning(f"移动原始文件失败: {e}")


class InboxWatcher:
    """收件箱监听器管理类"""

    def __init__(self):
        self._observer = None

    def start(self):
        """启动监听"""
        if not config.INBOX_WATCH_ENABLED:
            logger.info("收件箱监听已禁用")
            return

        # 确保目录存在
        config.INBOX_DIR.mkdir(parents=True, exist_ok=True)

        self._observer = Observer()
        handler = InboxHandler()
        self._observer.schedule(handler, str(config.INBOX_DIR), recursive=False)
        self._observer.start()
        logger.info(f"收件箱监听已启动: {config.INBOX_DIR}")

    def stop(self):
        """停止监听"""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join()
            logger.info("收件箱监听已停止")


# 全局实例
inbox_watcher = InboxWatcher()