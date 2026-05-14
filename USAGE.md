# 실행 가이드

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

## 실행 순서

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
python src/extract_highlights.py input/videos
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
python src/generate_subtitles.py input/script.txt
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
python src/generate_composition.py
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

**예시:**
```bash
# 30초 영상 생성
python src/generate_composition.py -d 30

# 60초 영상, 최대 10개 클립
python src/generate_composition.py -d 60 -n 10
```

### Step 6: 미리보기

```bash
cd hyperframes
npx hyperframes preview
```

### Step 7: 최종 렌더링

```bash
cd hyperframes
npx hyperframes render -o ../output/final.mp4
```

---

## 빠른 실행 (전체 파이프라인)

```bash
# 전체 파이프라인 실행
python src/extract_highlights.py input/videos && \
python src/generate_subtitles.py input/script.txt && \
cp output/highlights/*.mp4 hyperframes/assets/highlights/ && \
python src/generate_composition.py && \
cd hyperframes && npx hyperframes render -o ../output/final.mp4
```

```bash
# 영상 길이 지정 (예: 45초)
python src/extract_highlights.py input/videos && \
python src/generate_subtitles.py input/script.txt && \
cp output/highlights/*.mp4 hyperframes/assets/highlights/ && \
python src/generate_composition.py -d 45 && \
cd hyperframes && npx hyperframes render -o ../output/final.mp4
```

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
