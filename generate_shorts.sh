#!/bin/bash
#
# ShortVideoGenerator 전체 파이프라인
# 사용법: ./generate_shorts.sh [옵션]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 기본 설정
INPUT_VIDEOS="input/videos"
INPUT_SCRIPT="input/script.txt"
OUTPUT_DIR="output"
HIGHLIGHTS_DIR="output/highlights"
HYPERFRAMES_DIR="hyperframes"
MAX_CLIPS=5
BGM_VOLUME=0.3
SKIP_HIGHLIGHTS=false
SKIP_SUBTITLES=false
SKIP_ORGANIZE=false

# 색상 출력
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "\n${BLUE}===================================================${NC}"
    echo -e "${GREEN}[$1]${NC} $2"
    echo -e "${BLUE}===================================================${NC}"
}

print_info() {
    echo -e "${YELLOW}→${NC} $1"
}

# 도움말
show_help() {
    cat << EOF
ShortVideoGenerator - 숏폼 영상 자동 생성 파이프라인

사용법:
    ./generate_shorts.sh [옵션]

옵션:
    -v, --videos PATH       입력 비디오 폴더 (기본: input/videos)
    -s, --script PATH       자막 스크립트 파일 (기본: input/script.txt)
    -o, --output PATH       출력 파일 경로 (기본: output/final.mp4)
    -n, --max-clips NUM     최대 클립 수 (기본: 5)
    --bgm-volume FLOAT      BGM 볼륨 0-1 (기본: 0.3)
    --skip-highlights       하이라이트 추출 건너뛰기
    --skip-subtitles        자막 생성 건너뛰기
    --skip-organize         영상 정리 건너뛰기
    -h, --help              도움말 출력

예시:
    ./generate_shorts.sh                           # 기본 설정으로 실행
    ./generate_shorts.sh -n 10                     # 10개 클립 사용
    ./generate_shorts.sh --skip-highlights         # 기존 클립 사용
    ./generate_shorts.sh -v ~/Movies -n 3          # 커스텀 비디오 폴더

EOF
    exit 0
}

# 인자 파싱
OUTPUT_FILE="output/final.mp4"

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--videos)
            INPUT_VIDEOS="$2"
            shift 2
            ;;
        -s|--script)
            INPUT_SCRIPT="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -n|--max-clips)
            MAX_CLIPS="$2"
            shift 2
            ;;
        --bgm-volume)
            BGM_VOLUME="$2"
            shift 2
            ;;
        --skip-highlights)
            SKIP_HIGHLIGHTS=true
            shift
            ;;
        --skip-subtitles)
            SKIP_SUBTITLES=true
            shift
            ;;
        --skip-organize)
            SKIP_ORGANIZE=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "알 수 없는 옵션: $1"
            show_help
            ;;
    esac
done

# 가상환경 활성화
source venv/bin/activate

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║     ShortVideoGenerator Pipeline                  ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: 하이라이트 추출
if [ "$SKIP_HIGHLIGHTS" = false ]; then
    print_step "1/5" "하이라이트 추출"
    print_info "입력: $INPUT_VIDEOS"
    print_info "출력: $HIGHLIGHTS_DIR"

    python src/extract_highlights.py "$INPUT_VIDEOS" -o "$HIGHLIGHTS_DIR"

    # HyperFrames 에셋 폴더로 복사
    print_info "클립을 HyperFrames로 복사 중..."
    mkdir -p "$HYPERFRAMES_DIR/assets/highlights"
    cp "$HIGHLIGHTS_DIR"/*.mp4 "$HYPERFRAMES_DIR/assets/highlights/"
else
    print_step "1/5" "하이라이트 추출 (건너뜀)"
fi

# Step 2: 자막 생성
if [ "$SKIP_SUBTITLES" = false ]; then
    print_step "2/5" "자막 생성"
    print_info "입력: $INPUT_SCRIPT"
    print_info "출력: $OUTPUT_DIR/subtitles.json"

    if [ -f "$INPUT_SCRIPT" ]; then
        python src/generate_subtitles.py "$INPUT_SCRIPT" -o "$OUTPUT_DIR/subtitles.json"
    else
        print_info "스크립트 파일이 없습니다. 자막 없이 진행합니다."
    fi
else
    print_step "2/5" "자막 생성 (건너뜀)"
fi

# Step 3: 컴포지션 생성
print_step "3/5" "컴포지션 생성"
print_info "클립 수: $MAX_CLIPS"
print_info "BGM 볼륨: $BGM_VOLUME"

python src/generate_composition.py \
    -c "$HYPERFRAMES_DIR/assets/highlights" \
    -s "$OUTPUT_DIR/subtitles.json" \
    -o "$HYPERFRAMES_DIR/index.html" \
    -n "$MAX_CLIPS" \
    --bgm-volume "$BGM_VOLUME"

# Step 4: 렌더링
print_step "4/5" "HyperFrames 렌더링"
print_info "출력: $OUTPUT_FILE"

cd "$HYPERFRAMES_DIR"
npx hyperframes render --output "../$OUTPUT_FILE"
cd ..

# Step 5: 영상 정리
if [ "$SKIP_ORGANIZE" = false ]; then
    print_step "5/5" "영상 정리"
    print_info "사용된 영상 → $INPUT_VIDEOS/used/"
    print_info "미사용 영상 → $INPUT_VIDEOS/unused/"

    python src/organize_videos.py -v "$INPUT_VIDEOS" -c "$HYPERFRAMES_DIR/index.html"
else
    print_step "5/5" "영상 정리 (건너뜀)"
fi

# 완료
echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║                    완료!                          ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# 결과 정보
FILE_SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_FILE" 2>/dev/null | cut -d. -f1)

echo -e "📁 파일: ${GREEN}$OUTPUT_FILE${NC}"
echo -e "📊 크기: ${GREEN}$FILE_SIZE${NC}"
echo -e "⏱️  길이: ${GREEN}${DURATION}초${NC}"
echo ""
echo -e "재생: ${YELLOW}open $OUTPUT_FILE${NC}"
