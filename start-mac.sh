#!/bin/bash
# ai-consult-copilot macOS 一键启动脚本
# 用法：bash start-mac.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "================================================"
echo "  咨询AI副驾 macOS 启动器"
echo "================================================"

# 1. 检查 venv
if [ ! -d ".venv" ]; then
    echo "[1/5] 创建虚拟环境..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# 2. 检查依赖
if ! python -c "import fastapi" 2>/dev/null; then
    echo "[2/5] 安装依赖..."
    # 检查 portaudio 是否已 brew 安装
    if ! brew list portaudio &>/dev/null; then
        echo "  正在安装 portaudio..."
        brew install portaudio
    fi
    pip install -r requirements-mac.txt
else
    echo "[2/5] 依赖已就绪"
fi

# 3. 检查 .env
if [ ! -f ".env" ]; then
    echo "[3/5] 创建 .env..."
    cp .env.example .env 2>/dev/null || echo "请先配置 .env（参考 .env.example）"
fi

# 4. 检查 ZHIPUAI_API_KEY
if grep -q "^ZHIPUAI_API_KEY=$" .env 2>/dev/null; then
    echo ""
    echo "⚠️  警告：ZHIPUAI_API_KEY 未配置！"
    echo "   请去 https://open.bigmodel.cn/ 申请，填入 .env"
    echo "   AI 建议功能在未配置 key 时不可用（Web 面板仍可打开）"
    echo ""
fi

# 5. 检查 BlackHole（系统音频采集需要）
if ! python -c "import pyaudio; pa=pyaudio.PyAudio(); [d for d in [pa.get_device_info_by_index(i) for i in range(pa.get_device_count())] if 'BlackHole' in d.get('name','')]; pa.terminate()" 2>/dev/null; then
    echo "[4/5] BlackHole 未检测到（系统音频采集不可用）"
    echo "   安装：brew install blackhole-2ch"
    echo "   麦克风采集不受影响，可继续"
else
    echo "[4/5] BlackHole 已就绪"
fi

# 6. 启动
echo "[5/5] 启动应用..."
echo ""
echo "面板地址: http://127.0.0.1:8765"
echo "Ctrl+C 退出（自动归档）"
echo "================================================"
echo ""

python main.py
