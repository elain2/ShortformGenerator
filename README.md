# ShortVideoGenerator

감성 Vlog 스타일 숏츠를 반자동으로 생성하는 파이프라인.
여러 영상에서 하이라이트를 추출하고, HyperFrames로 초안을 렌더링한 뒤, VLLO에서 더빙과 최종 편집을 진행한다.

## 파이프라인 개요

```
┌─────────────────────────────────────────────────────────────┐
│  입력: videos/ + script.txt                                 │
│                         ↓                                   │
│  [1] 하이라이트 추출    → output/highlights/*.mp4           │
│                         ↓                                   │
│  [2] 자막 생성          → output/subtitles.json             │
│                         ↓                                   │
│  [3] 컴포지션 생성      → hyperframes/index.html            │
│                         ↓                                   │
│  [4] HyperFrames 렌더링 → output/final.mp4                  │
│                         ↓                                   │
│  [5] 영상 정리          → videos/used/, videos/unused/      │
└─────────────────────────────────────────────────────────────┘
```

**스크립트 선택:**
- `generate_shorts.sh` - 전체 파이프라인 (1→5)
- `render_segments.sh` - 컴포지션+렌더링만 (3→4)

---

## 사전 준비

### 시스템 요구 사항
- Python 3.10+
- Node.js 22+
- FFmpeg

### FFmpeg 설치

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 의존성 설치

```bash
# Python 의존성
pip install -r requirements.txt

# Node.js 의존성
cd hyperframes && npm install
```

---

## 실행 방법

### 방법 1: 전체 파이프라인 (권장)

```bash
./generate_shorts.sh
```

**옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-v, --videos` | 입력 비디오 폴더 | `input/videos` |
| `-s, --script` | 자막 스크립트 파일 | `input/script.txt` |
| `-o, --output` | 출력 파일 경로 | `output/final.mp4` |
| `-n, --max-clips` | 최대 클립 수 | `5` |
| `--bgm-volume` | BGM 볼륨 (0-1) | `0.3` |
| `--skip-highlights` | 하이라이트 추출 건너뛰기 | |
| `--skip-subtitles` | 자막 생성 건너뛰기 | |

### 방법 2: 세그먼트 렌더링 (재렌더링용)

자막이나 클립을 수정한 후 다시 렌더링할 때 사용:

```bash
./render_segments.sh
```

**옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-c, --clips` | 클립 폴더 경로 | `hyperframes/assets/highlights` |
| `-s, --subtitles` | 자막 JSON 파일 | `output/subtitles.json` |
| `-o, --output` | 출력 파일 경로 | `output/final.mp4` |
| `-n, --max-clips` | 최대 클립 수 | 자동 |
| `-d, --duration` | 영상 길이(초) | 클립 합계 |
| `--bgm-volume` | BGM 볼륨 | `0.3` |
| `--preview` | 미리보기만 실행 | |
| `--skip-composition` | 컴포지션 건너뛰기 | |
| `--regenerate-subtitles` | 자막 재생성 | |

**예시:**
```bash
# 자막 수정 후 재렌더링
./render_segments.sh --regenerate-subtitles

# 미리보기만 (브라우저에서 확인)
./render_segments.sh --preview

# 클립 5개, 45초 영상
./render_segments.sh -n 5 -d 45

# index.html 수동 편집 후 렌더링만
./render_segments.sh --skip-composition

# 메모리 이슈 시 분할 렌더링
./render_segments.sh --segment-size 3
```

### 방법 3: 분할 렌더링 (메모리 이슈 해결)

HyperFrames 렌더링 시 메모리 부족 오류가 발생하면 `--segment-size` 옵션을 사용합니다.

```bash
# 3개씩 나눠서 렌더링 후 자동 병합
./render_segments.sh --segment-size 3

# 2개씩 (더 적은 메모리 사용)
./render_segments.sh --segment-size 2

# 1개씩 (최소 메모리)
./render_segments.sh --segment-size 1
```

**동작 방식:**
1. 클립을 segment-size 단위로 분할
2. 각 세그먼트를 개별 렌더링 (자막 자동 분할)
3. FFmpeg concat으로 최종 병합
4. 임시 파일 자동 정리

**세그먼트 크기 선택 가이드:**
| 메모리 상황 | 권장 segment-size |
|------------|------------------|
| 8GB RAM | 3-4 |
| 4GB RAM | 2 |
| 메모리 부족 심함 | 1 |

---

## 개별 단계 실행

### Step 1: 입력 파일 준비

```
input/
├── videos/          # 원본 비디오 파일들
│   ├── video1.mp4
│   └── video2.mov
└── script.txt       # 자막용 스크립트
```

### Step 2: 하이라이트 추출

```bash
python3 src/extract_highlights.py input/videos
```

**옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-o, --output` | 출력 폴더 | `output/highlights` |
| `-c, --config` | 설정 파일 | `input/config.json` |
| `--manifest` | 매니페스트 경로 | `output/highlights_manifest.json` |

**출력:**
- `output/highlights/` - 1080x1920 무음 클립들
- `output/highlights_manifest.json` - 클립 메타데이터

### Step 3: 자막 생성

```bash
python3 src/generate_subtitles.py input/script.txt
```

**옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-o, --output` | 출력 파일 | `output/subtitles.json` |
| `--rate` | 음절/초 속도 | `3.5` |
| `--offset` | 시작 오프셋(초) | `0.0` |

**출력:**
- `output/subtitles.json` - 자막 타이밍 JSON

### Step 4: HyperFrames 에셋 복사

```bash
cp output/highlights/*.mp4 hyperframes/assets/highlights/
cp your_bgm.mp3 hyperframes/assets/bgm.mp3  # 선택
```

### Step 5: 컴포지션 생성

```bash
python3 src/generate_composition.py
```

**옵션:**
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-c, --clips` | 클립 폴더 경로 | `hyperframes/assets/highlights` |
| `-s, --subtitles` | 자막 파일 경로 | `output/subtitles.json` |
| `-o, --output` | 출력 HTML 경로 | `hyperframes/index.html` |
| `-n, --max-clips` | 최대 클립 수 | 자동 (자막 길이 기준) |
| `-d, --duration` | 최종 영상 길이(초) | 자동 (클립 길이 합계) |
| `--bgm-volume` | BGM 볼륨 (0-1) | `0.3` |

### Step 6: 미리보기

```bash
cd hyperframes
npx hyperframes dev
```

### Step 7: 최종 렌더링

```bash
cd hyperframes
npx hyperframes render --output ../output/final.mp4
```

---

## 자막 시스템

### script.txt 형식

한 줄에 하나의 자막 문장을 작성합니다:

```
저는 제 몸을 삭제하고 싶었습니다.
폐쇄병동 퇴원 후, 약 부작용으로 인해
몸무게는 감당할 수 없게 불어났습니다.
```

**팁:**
- 한 줄은 화면에 표시될 하나의 자막 단위입니다
- 너무 긴 문장은 자동으로 줄바꿈됩니다 (20자 기준)
- 빈 줄은 무시됩니다

### 자막 타이밍 계산

자막 타이밍은 **음절 수 기반**으로 자동 계산됩니다:

```
재생 시간 = 음절 수 ÷ 음절/초 속도(rate)
```

기본 속도는 3.5음절/초로, 일반적인 더빙 속도입니다.

**속도 조정:**
```bash
# 빠른 말하기 (4.0음절/초)
python src/generate_subtitles.py input/script.txt --rate 4.0

# 느린 말하기 (3.0음절/초)
python src/generate_subtitles.py input/script.txt --rate 3.0
```

### subtitles.json 구조

```json
{
  "subtitles": [
    {
      "text": "저는 제 몸을 삭제하고 싶었습니다.",
      "start_time": 0.0,
      "end_time": 4.0,
      "duration": 4.0
    },
    {
      "text": "폐쇄병동 퇴원 후, 약 부작용으로 인해",
      "start_time": 4.1,
      "end_time": 8.4,
      "duration": 4.3
    }
  ],
  "total_duration": 53.2
}
```

**수동 편집:**
- `start_time`, `end_time`을 직접 수정하여 타이밍 조정 가능
- 수정 후 `./render_segments.sh`로 재렌더링

### 자막 렌더링 방식

자막은 **CSS 키프레임 애니메이션**으로 렌더링됩니다:

```css
@keyframes subtitle-0 {
    0%, 0.00% { opacity: 0; }      /* 시작 전: 투명 */
    0.01%, 5.70% { opacity: 1; }   /* 표시 구간: 불투명 */
    5.71%, 100% { opacity: 0; }    /* 종료 후: 투명 */
}
```

**장점:**
- JavaScript 없이 정확한 타이밍
- 프레임 단위 정밀도
- 렌더링 일관성 보장

### 자막 스타일 커스터마이징

**기본 스타일 (generate_composition.py):**
```css
.subtitle-item {
    font-size: 52px;           /* 기본 글자 크기 */
    font-weight: 600;          /* 굵기 */
    color: #FFF8E7;            /* 따뜻한 화이트 */
    text-shadow:               /* 가독성을 위한 그림자 */
        0 2px 4px rgba(0, 0, 0, 0.5),
        0 4px 8px rgba(0, 0, 0, 0.3);
}

.subtitle-item.long-text {     /* 19-25자 */
    font-size: 44px;
}

.subtitle-item.very-long-text { /* 26자 이상 */
    font-size: 38px;
}
```

**위치 스타일 (hyperframes/styles.css):**
```css
#subtitle-container {
    position: absolute;
    bottom: 15%;               /* 하단에서 15% 위치 */
    left: 50%;
    transform: translateX(-50%);
}
```

**스타일 수정 방법:**
1. `src/generate_composition.py`의 `generate_subtitle_css()` 함수 수정
2. 또는 `hyperframes/styles.css` 직접 수정
3. `./render_segments.sh`로 재렌더링

---

## 설정 변경

`input/config.json`에서 조정 가능:

### 하이라이트 추출
```json
{
  "highlight_extraction": {
    "min_clip_duration": 3.0,
    "max_clip_duration": 15.0,
    "highlight_threshold": 0.5
  }
}
```

### 자막
```json
{
  "subtitle": {
    "syllable_rate": 3.5,
    "max_chars_per_line": 20,
    "style": {
      "font_size": 52,
      "color": "#FFF8E7"
    }
  }
}
```

### BGM
```json
{
  "bgm": {
    "volume": 0.3
  }
}
```

---

## 기술 스택

| 단계 | 도구 | 용도 |
|------|------|------|
| 하이라이트 추출 | Python + OpenCV | 장면 분석, 클립 추출 |
| 자막 처리 | Python | 타이밍 계산, JSON 생성 |
| 영상 합성 | HyperFrames | HTML → MP4 렌더링 |
| 최종 편집 | VLLO | 더빙, 미세 조정 |

---

## 설계 결정사항

### 하이라이트 추출
- **추출 기준**: 움직임 + 색감 + 피사체 감지 3가지 점수화
- **클립 길이**: 하이라이트 구간에 따라 가변
- **클립 개수**: 전체 숏츠 길이 대비 자동 계산

### 자막
- **더빙 속도**: 파라미터로 설정 (기본값: 3.5음절/초)
- **영상-자막 싱크**: draft.mp4 생성 시 자동 맞춤
- **강조 표시**: 안 함 (MVP)

### HyperFrames
- **자막 스타일**: 감성 vlog 스타일 1개
- **전환 효과**: 단순 컷전환 (트랜지션 없음)
- **출력**: 1080x1920 (9:16), MP4

### VLLO 연동
- **더빙 가이드**: 안 넣음
- **자막**: draft.mp4에 렌더링하여 포함

---

## 프로젝트 구조

```
ShortVideoGenerator/
├── input/
│   ├── videos/           # 원본 영상들
│   ├── script.txt        # 자막용 스크립트
│   └── config.json       # 설정
├── output/
│   ├── highlights/       # 추출된 하이라이트 클립
│   └── final.mp4         # HyperFrames 출력
├── src/
│   ├── extract_highlights.py
│   ├── generate_subtitles.py
│   ├── generate_composition.py
│   └── render_video.py
├── hyperframes/
│   ├── index.html        # HyperFrames 컴포지션
│   ├── assets/           # 에셋 폴더
│   └── styles.css        # 스타일시트
├── generate_shorts.sh    # 전체 파이프라인
├── render_segments.sh    # 렌더링 전용
└── README.md
```

---

## 워크플로우 예시

### 기본 워크플로우
```bash
# 1. 입력 준비
cp ~/Movies/*.mp4 input/videos/
echo "첫 번째 자막입니다." > input/script.txt

# 2. 전체 파이프라인 실행
./generate_shorts.sh

# 3. 결과 확인
open output/final.mp4
```

### 자막 수정 워크플로우
```bash
# 1. 자막 텍스트 수정
vi input/script.txt

# 2. 자막 재생성 + 렌더링
./render_segments.sh --regenerate-subtitles

# 또는 JSON 직접 수정 후 렌더링
vi output/subtitles.json
./render_segments.sh
```

### 미리보기 → 렌더링 워크플로우
```bash
# 1. 미리보기로 확인
./render_segments.sh --preview

# 2. 만족스러우면 렌더링
./render_segments.sh
```

### 클립 조정 워크플로우
```bash
# 특정 클립만 사용하여 30초 영상 생성
./render_segments.sh -n 5 -d 30
```

---

## 트러블슈팅

### FFmpeg 오류
```bash
# 설치 확인
ffmpeg -version
which ffmpeg
```

### OpenCV 오류
```bash
pip install opencv-python-headless
```

### HyperFrames 오류
```bash
npx hyperframes preview  # npx로 실행
```

### 자막이 표시되지 않음
1. `output/subtitles.json` 파일 존재 확인
2. JSON 형식 유효성 확인
3. `start_time`, `end_time` 값이 영상 길이 내인지 확인

### 자막 타이밍이 맞지 않음
1. `--rate` 옵션으로 음절 속도 조정
2. 또는 `subtitles.json`에서 직접 타이밍 수정
3. `./render_segments.sh`로 재렌더링

---

## 참고 자료

- [HyperFrames](https://github.com/heygen-com/hyperframes)
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect)
- [OpenCV Video Analysis](https://docs.opencv.org/4.x/d7/df3/group__imgproc__motion.html)

## 라이선스

MIT License
