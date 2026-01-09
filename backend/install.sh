#!/bin/bash

echo "📦 Installing MinerU Tianshu Backend Dependencies..."
echo ""
echo "📋 Installation Options:"
echo "  - Core Dependencies (Required)"
echo "  - PaddleOCR-VL"
echo "  - Audio Processing (SenseVoice)"
echo "  - Video Processing"
echo "  - Watermark Removal"
echo "  - Format Engines (FASTA/GenBank)"
echo ""
echo "Installation Strategy:"
echo "  1. Install PaddlePaddle first (CUDA 12.6)"
echo "  2. Install PyTorch with compatible version"
echo "  3. Install packages separately to avoid conflicts"
echo "  4. Use legacy resolver for final dependency resolution"
echo ""
echo "============================================================"

# Step 1: Check system
echo ""
echo "[Step 1/8] Checking system requirements..."
if [ "$(uname)" != "Linux" ]; then
    echo "Warning: This script is designed for Linux/WSL"
    echo "Windows users should use WSL2 or Docker"
fi

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    echo "✓ GPU detected:"
    nvidia-smi --query-gpu=name --format=csv,noheader | head -1
else
    echo "⚠ Warning: nvidia-smi not found. GPU may not be available."
fi

# Step 2: Install system library
echo ""
echo "[Step 2/8] Installing system libraries..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y libgomp1 ffmpeg
    echo "✓ System libraries installed (libgomp1, ffmpeg)"
else
    echo "⚠ Warning: apt-get not found. You may need to install libgomp1 and ffmpeg manually."
fi

# Step 3: Install PaddlePaddle
echo ""
echo "[Step 3/9] Installing PaddlePaddle GPU 3.2.0..."
echo "  This may take a few minutes..."
pip install paddlepaddle-gpu==3.2.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ \
    --default-timeout=600 \
    --retries 5
echo "✓ PaddlePaddle installed"

# Step 4: Install PyTorch (including torchaudio for SenseVoice)
echo ""
echo "[Step 4/9] Installing PyTorch 2.6.0+cu126 (with torchaudio)..."
echo "  This may take a few minutes..."
pip install torch==2.6.0+cu126 torchvision==0.21.0+cu126 torchaudio==2.6.0+cu126 \
    --index-url https://download.pytorch.org/whl/cu126 \
    --default-timeout=600 \
    --retries 5
echo "✓ PyTorch installed"

# Step 5: Install Python 3.12 critical dependencies
echo ""
echo "[Step 5/9] Installing Python 3.12 critical dependencies..."
pip install "kiwisolver>=1.4.5" "Pillow>=11.0.0" \
    "numpy>=1.26.0,<2.0.0" "setuptools>=75.0.0" "lxml>=5.3.0" \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=300 \
    --retries 5
echo "✓ Python 3.12 dependencies installed"

# Step 6: Install transformers core dependencies
echo ""
echo "[Step 6/9] Installing transformers core dependencies..."
pip install regex packaging filelock requests tqdm \
    "huggingface-hub>=0.23.2,<1.0" \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=300 \
    --retries 5
echo "✓ Transformers dependencies installed"

# Step 7: Install MinerU with dependencies (allow auto dependency resolution)
echo ""
echo "[Step 7/10] Installing MinerU with dependencies..."
cd "$(dirname "$0")" || exit
pip install "mineru[core]" \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=600 \
    --retries 5
echo "✓ MinerU installed"

# Step 7.5: Install other core packages
echo ""
echo "[Step 7.5/10] Installing other core packages..."
pip install "paddleocr[doc-parser]" \
    transformers==4.46.3 tokenizers==0.20.3 \
    fastapi uvicorn litserve aiohttp \
    PyMuPDF Pillow img2pdf einops easydict addict loguru modelscope \
    minio markitdown \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=300 \
    --retries 5
echo "✓ Other packages installed"

# Step 7.6: Ensure albumentations compatibility (MinerU 2.6.2 needs 1.3.x)
echo ""
echo "[Step 7.6/10] Ensuring albumentations compatibility..."
pip install 'albumentations>=1.3.1,<1.4.0' 'albucore>=0.0.13,<0.0.17' \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=300 \
    --retries 5
echo "✓ Albumentations compatibility ensured"

# Step 8: Install safetensors (PaddlePaddle dependency)
echo ""
echo "[Step 8/10] Installing safetensors (PaddlePaddle dependency)..."
pip install \
    --default-timeout=300 \
    --retries 5 \
    https://paddle-whl.bj.bcebos.com/nightly/cu126/safetensors/safetensors-0.6.2.dev0-cp38-abi3-linux_x86_64.whl
echo "✓ safetensors installed"

# Step 9: Resolve all remaining dependencies with legacy resolver
echo ""
echo "[Step 9/10] Resolving remaining dependencies..."
echo "  Using legacy resolver to avoid 'resolution-too-deep' errors..."
echo "  This may show some warnings, but should complete successfully..."
pip install -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --use-deprecated=legacy-resolver \
    --default-timeout=600 \
    --retries 5
echo "✓ All dependencies resolved"

# Verification
echo ""
echo "============================================================"
echo "Verifying installation..."
echo "============================================================"

python3 << 'EOF'
import sys

print("\nChecking frameworks...")
success = True

# Check PaddlePaddle
try:
    import paddle
    print(f"✓ PaddlePaddle: {paddle.__version__}")
    if paddle.device.is_compiled_with_cuda():
        print(f"  CUDA: Available ({paddle.device.cuda.device_count()} GPU)")
    else:
        print("  ⚠ CUDA: Not available")
        success = False
except Exception as e:
    print(f"✗ PaddlePaddle: {str(e)[:80]}")
    success = False

# Check PyTorch
try:
    import torch
    print(f"✓ PyTorch: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"  CUDA: Available ({torch.cuda.device_count()} GPU)")
    else:
        print("  ⚠ CUDA: Not available")
        success = False
except Exception as e:
    print(f"✗ PyTorch: {str(e)[:80]}")
    success = False

# Check Transformers
try:
    from transformers import AutoModel
    print("✓ Transformers: Ready")
except Exception as e:
    print(f"✗ Transformers: {str(e)[:80]}")
    success = False

# Check PaddleOCR-VL
try:
    from paddleocr import PaddleOCRVL
    print("✓ PaddleOCR-VL: Ready")
except Exception as e:
    print(f"⚠ PaddleOCR-VL: {str(e)[:80]}")
    # Not critical if this fails

# Check FunASR (Audio Processing with Speaker Diarization)
try:
    import funasr
    print("✓ FunASR: Ready (Audio Processing + Speaker Diarization)")
except Exception as e:
    print(f"⚠ FunASR: {str(e)[:80]}")
    # Not critical if this fails

print("")
if success:
    print("="*60)
    print("✓ Installation successful!")
    print("="*60)
    sys.exit(0)
else:
    print("="*60)
    print("✗ Installation completed with warnings")
    print("  Please check the errors above")
    print("="*60)
    sys.exit(1)
EOF

VERIFY_EXIT=$?

echo ""
if [ $VERIFY_EXIT -eq 0 ]; then
    echo "============================================================"
    echo "Installation complete! You can now start the server."
    echo "============================================================"
else
    echo "============================================================"
    echo "Installation completed with warnings."
    echo "See INSTALL.md for troubleshooting."
    echo "============================================================"
fi
