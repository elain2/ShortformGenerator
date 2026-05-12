#!/bin/bash
# ShortVideoGenerator 실행 스크립트

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 가상환경 활성화
source venv/bin/activate

# Python 스크립트 실행
python "$@"
