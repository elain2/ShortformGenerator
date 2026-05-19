#!/bin/bash
#
# render_segments.sh - 컴포지션 생성 및 렌더링 스크립트
#
# 하이라이트 추출 후, 자막과 클립을 조합하여 최종 영상을 렌더링합니다.
# 전체 파이프라인(generate_shorts.sh)의 3-4단계를 독립적으로 실행할 때 사용합니다.
#
# 용도:
#   - 자막 수정 후 재렌더링
#   - 클립 순서/개수 조정 후 재렌더링
#   - BGM 볼륨 조정 후 재렌더링
#   - 메모리 이슈 시 분할 렌더링
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 기본 설정
CLIPS_DIR="hyperframes/assets/highlights"
SUBTITLES_FILE="output/subtitles.json"
OUTPUT_FILE="output/final.mp4"
MAX_CLIPS=""
DURATION=""
BGM_VOLUME=0.3
PREVIEW_ONLY=false
SKIP_COMPOSITION=false
REGENERATE_SUBTITLES=false
SCRIPT_FILE="input/script.txt"
SEGMENT_SIZE=""  # 분할 렌더링: 한 세그먼트당 클립 수
TEMP_DIR="output/temp_segments"

# 색상 출력
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

print_step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}[$1]${NC} $2"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_info() {
    echo -e "${YELLOW}→${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_segment() {
    echo -e "${CYAN}  ▶${NC} $1"
}

# 도움말
show_help() {
    cat << EOF
render_segments.sh - 컴포지션 생성 및 렌더링

이 스크립트는 이미 추출된 하이라이트 클립들을 사용하여
자막과 BGM을 포함한 최종 영상을 생성합니다.

사용법:
    ./render_segments.sh [옵션]

옵션:
    -c, --clips PATH        클립 폴더 경로 (기본: hyperframes/assets/highlights)
    -s, --subtitles PATH    자막 JSON 파일 (기본: output/subtitles.json)
    -o, --output PATH       출력 파일 경로 (기본: output/final.mp4)
    -n, --max-clips NUM     사용할 최대 클립 수 (기본: 자막 길이 기준 자동)
    -d, --duration SEC      최종 영상 길이(초) (기본: 클립 합계)
    --bgm-volume FLOAT      BGM 볼륨 0-1 (기본: 0.3)
    --preview               렌더링 없이 미리보기만 실행
    --skip-composition      컴포지션 생성 건너뛰기 (기존 index.html 사용)
    --regenerate-subtitles  자막 JSON 재생성
    --script PATH           자막용 스크립트 파일 (기본: input/script.txt)

    --segment-size NUM      분할 렌더링: 세그먼트당 클립 수 (메모리 이슈 해결용)
                            예: --segment-size 3 → 3개씩 나눠서 렌더링 후 합침

    -h, --help              도움말 출력

메모리 이슈 해결:
    HyperFrames 렌더링 시 메모리 부족 오류가 발생하면
    --segment-size 옵션으로 클립을 나눠서 렌더링합니다.

    ./render_segments.sh --segment-size 3   # 3개씩 분할
    ./render_segments.sh --segment-size 2   # 2개씩 분할 (더 적은 메모리)

예시:
    # 기본 실행 (클립+자막 → 렌더링)
    ./render_segments.sh

    # 메모리 이슈 시 분할 렌더링
    ./render_segments.sh --segment-size 3

    # 미리보기만 (브라우저에서 확인)
    ./render_segments.sh --preview

    # 자막 수정 후 재렌더링
    ./render_segments.sh --regenerate-subtitles

    # 클립 5개, 45초 영상 생성
    ./render_segments.sh -n 5 -d 45

EOF
    exit 0
}

# 클립 길이 조회 함수
get_clip_duration() {
    local dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null)
    # 빈 값이면 0 반환
    if [ -z "$dur" ]; then
        echo "0"
    else
        echo "$dur"
    fi
}

# 소수점 덧셈 함수 (bc 대신 awk 사용)
add_floats() {
    awk "BEGIN {printf \"%.3f\", $1 + $2}"
}

# 분할 렌더링 함수
render_segments() {
    local clips_dir="$1"
    local segment_size="$2"
    local output_file="$3"

    # 클립 목록 가져오기
    local clip_files=($(ls -1 "$clips_dir"/*.mp4 2>/dev/null | sort))
    local total_clips=${#clip_files[@]}

    if [ $total_clips -eq 0 ]; then
        print_error "클립이 없습니다"
        return 1
    fi

    # 자막 길이 읽기 (자막 길이만큼만 클립 사용)
    local subtitle_duration=0
    if [ -f "$SUBTITLES_FILE" ]; then
        subtitle_duration=$(python3 -c "import json; print(json.load(open('$SUBTITLES_FILE')).get('total_duration', 0))" 2>/dev/null || echo "0")
    fi

    # 자막 길이에 맞춰 필요한 클립 수 계산
    if [ -n "$subtitle_duration" ] && [ "$(echo "$subtitle_duration > 0" | bc -l)" -eq 1 ]; then
        print_info "자막 길이: ${subtitle_duration}초"
        local cumulative_duration=0
        local clips_needed=0
        for ((i=0; i<total_clips; i++)); do
            local clip_dur=$(get_clip_duration "${clip_files[$i]}")
            cumulative_duration=$(add_floats "$cumulative_duration" "$clip_dur")
            clips_needed=$((i + 1))
            # 자막 길이를 넘으면 중단
            if [ "$(echo "$cumulative_duration >= $subtitle_duration" | bc -l)" -eq 1 ]; then
                break
            fi
        done
        if [ $clips_needed -lt $total_clips ]; then
            print_info "자막 길이에 맞춰 클립 수 제한: ${total_clips}개 → ${clips_needed}개"
            total_clips=$clips_needed
        fi
    fi

    # 세그먼트 수 계산
    local num_segments=$(( (total_clips + segment_size - 1) / segment_size ))

    print_info "총 클립: ${total_clips}개"
    print_info "세그먼트 크기: ${segment_size}개"
    print_info "세그먼트 수: ${num_segments}개"

    # 임시 디렉토리 생성
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"

    # 누적 시간 추적
    local time_offset=0.0
    local segment_files=()

    # 각 세그먼트 렌더링
    for ((seg=0; seg<num_segments; seg++)); do
        local start_idx=$((seg * segment_size))
        local end_idx=$((start_idx + segment_size))
        if [ $end_idx -gt $total_clips ]; then
            end_idx=$total_clips
        fi

        local segment_file="$TEMP_DIR/segment_$(printf "%03d" $seg).mp4"
        segment_files+=("$segment_file")

        print_step "$((seg+1))/${num_segments}" "세그먼트 렌더링 (클립 $start_idx ~ $((end_idx-1)))"

        # 세그먼트 길이 계산 (현재 세그먼트의 클립 길이 합계)
        local segment_duration=0
        for ((i=start_idx; i<end_idx; i++)); do
            local clip_dur=$(get_clip_duration "${clip_files[$i]}")
            segment_duration=$(add_floats "$segment_duration" "$clip_dur")
        done

        print_segment "시간 오프셋: ${time_offset}s"
        print_segment "세그먼트 길이: ${segment_duration}s"

        # 컴포지션 생성 (세그먼트 모드)
        # 첫 세그먼트만 BGM 포함, 자막은 모든 세그먼트에 포함
        local comp_opts="-c $clips_dir -s $SUBTITLES_FILE --bgm-volume $BGM_VOLUME"
        comp_opts="$comp_opts --clip-start $start_idx --clip-end $end_idx"
        comp_opts="$comp_opts --time-offset $time_offset"
        comp_opts="$comp_opts -o hyperframes/index.html"

        # 첫 세그먼트가 아니면 BGM 제외
        if [ $seg -gt 0 ]; then
            comp_opts="$comp_opts --no-bgm"
        fi

        python3 src/generate_composition.py $comp_opts

        # 렌더링
        print_segment "렌더링 중..."
        cd hyperframes
        npx hyperframes render -o "../$segment_file" 2>&1 | while read line; do
            echo -e "${CYAN}    ${NC}$line"
        done
        cd ..

        # 시간 오프셋 업데이트
        time_offset=$(add_floats "$time_offset" "$segment_duration")

        print_segment "완료: $segment_file"
    done

    # FFmpeg로 세그먼트 합치기
    print_step "합치기" "세그먼트 병합"

    # concat 리스트 파일 생성
    local concat_list="$TEMP_DIR/concat_list.txt"
    > "$concat_list"
    for seg_file in "${segment_files[@]}"; do
        echo "file '$(cd "$(dirname "$seg_file")" && pwd)/$(basename "$seg_file")'" >> "$concat_list"
    done

    print_info "병합할 파일 목록:"
    cat "$concat_list" | while read line; do
        echo -e "${CYAN}    ${NC}$line"
    done

    # FFmpeg concat
    ffmpeg -y -f concat -safe 0 -i "$concat_list" -c copy "$output_file" 2>/dev/null

    # 임시 파일 정리
    print_info "임시 파일 정리 중..."
    rm -rf "$TEMP_DIR"

    return 0
}

# 인자 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--clips)
            CLIPS_DIR="$2"
            shift 2
            ;;
        -s|--subtitles)
            SUBTITLES_FILE="$2"
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
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        --bgm-volume)
            BGM_VOLUME="$2"
            shift 2
            ;;
        --preview)
            PREVIEW_ONLY=true
            shift
            ;;
        --skip-composition)
            SKIP_COMPOSITION=true
            shift
            ;;
        --regenerate-subtitles)
            REGENERATE_SUBTITLES=true
            shift
            ;;
        --script)
            SCRIPT_FILE="$2"
            shift 2
            ;;
        --segment-size)
            SEGMENT_SIZE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            print_error "알 수 없는 옵션: $1"
            show_help
            ;;
    esac
done

# 가상환경 활성화
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║        Segment Renderer                           ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# 클립 존재 확인
if [ ! -d "$CLIPS_DIR" ] || [ -z "$(ls -A "$CLIPS_DIR"/*.mp4 2>/dev/null)" ]; then
    print_error "클립이 없습니다: $CLIPS_DIR"
    echo ""
    echo "먼저 하이라이트를 추출하세요:"
    echo "  python src/extract_highlights.py input/videos"
    echo "  cp output/highlights/*.mp4 hyperframes/assets/highlights/"
    exit 1
fi

# Step 0: 자막 재생성 (선택)
if [ "$REGENERATE_SUBTITLES" = true ]; then
    print_step "0" "자막 재생성"
    if [ -f "$SCRIPT_FILE" ]; then
        print_info "입력: $SCRIPT_FILE"
        print_info "출력: $SUBTITLES_FILE"
        python3 src/generate_subtitles.py "$SCRIPT_FILE" -o "$SUBTITLES_FILE"
    else
        print_error "스크립트 파일이 없습니다: $SCRIPT_FILE"
        exit 1
    fi
fi

# 분할 렌더링 모드
if [ -n "$SEGMENT_SIZE" ]; then
    print_info "분할 렌더링 모드 (segment-size: $SEGMENT_SIZE)"

    render_segments "$CLIPS_DIR" "$SEGMENT_SIZE" "$OUTPUT_FILE"

    # 완료 메시지
    echo -e "\n${GREEN}"
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║              분할 렌더링 완료!                     ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo -e "${NC}"

    if [ -f "$OUTPUT_FILE" ]; then
        FILE_SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
        DURATION_SEC=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_FILE" 2>/dev/null | cut -d. -f1)

        echo -e "📁 파일: ${GREEN}$OUTPUT_FILE${NC}"
        echo -e "📊 크기: ${GREEN}$FILE_SIZE${NC}"
        echo -e "⏱️  길이: ${GREEN}${DURATION_SEC}초${NC}"
        echo ""
        echo -e "재생: ${YELLOW}open $OUTPUT_FILE${NC}"
    fi

    exit 0
fi

# 일반 렌더링 모드
# Step 1: 컴포지션 생성
if [ "$SKIP_COMPOSITION" = false ]; then
    print_step "1/2" "컴포지션 생성"
    print_info "클립: $CLIPS_DIR"
    print_info "자막: $SUBTITLES_FILE"
    print_info "BGM 볼륨: $BGM_VOLUME"

    # 옵션 구성
    COMP_OPTS="-c $CLIPS_DIR -s $SUBTITLES_FILE --bgm-volume $BGM_VOLUME"

    if [ -n "$MAX_CLIPS" ]; then
        COMP_OPTS="$COMP_OPTS -n $MAX_CLIPS"
        print_info "최대 클립: $MAX_CLIPS"
    fi

    if [ -n "$DURATION" ]; then
        COMP_OPTS="$COMP_OPTS -d $DURATION"
        print_info "목표 길이: ${DURATION}초"
    fi

    python3 src/generate_composition.py $COMP_OPTS
else
    print_step "1/2" "컴포지션 생성 (건너뜀)"
    print_info "기존 hyperframes/index.html 사용"
fi

# Step 2: 렌더링 또는 미리보기
if [ "$PREVIEW_ONLY" = true ]; then
    print_step "2/2" "미리보기 실행"
    print_info "브라우저에서 확인하세요 (Ctrl+C로 종료)"
    cd hyperframes
    npx hyperframes preview
else
    print_step "2/2" "HyperFrames 렌더링"
    print_info "출력: $OUTPUT_FILE"

    cd hyperframes
    npx hyperframes render -o "../$OUTPUT_FILE"
    cd ..

    # 완료 메시지
    echo -e "\n${GREEN}"
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║                   렌더링 완료!                     ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # 결과 정보
    if [ -f "$OUTPUT_FILE" ]; then
        FILE_SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
        DURATION_SEC=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_FILE" 2>/dev/null | cut -d. -f1)

        echo -e "📁 파일: ${GREEN}$OUTPUT_FILE${NC}"
        echo -e "📊 크기: ${GREEN}$FILE_SIZE${NC}"
        echo -e "⏱️  길이: ${GREEN}${DURATION_SEC}초${NC}"
        echo ""
        echo -e "재생: ${YELLOW}open $OUTPUT_FILE${NC}"
    fi
fi
