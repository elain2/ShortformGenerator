# 테스트 가이드

## 사전 요구사항

### 필수 설치
```bash
# FFmpeg (macOS)
brew install ffmpeg

# Node.js (HyperFrames 렌더링용)
brew install node
```

### Python 환경 설정
```bash
# 가상환경 생성 및 패키지 설치
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 설치 확인
```bash
source venv/bin/activate
python -c "import cv2; print('OpenCV:', cv2.__version__)"
ffmpeg -version
node -v
```

---

## 빠른 시작

### 원클릭 실행 (권장)

`generate_shorts.sh` 스크립트로 전체 파이프라인을 한 번에 실행:

```bash
# 기본 실행
./generate_shorts.sh

# 10개 클립 사용
./generate_shorts.sh -n 10

# 기존 클립 재사용 (하이라이트 추출 건너뛰기)
./generate_shorts.sh --skip-highlights

# 도움말 보기
./generate_shorts.sh --help
```

### 파이프라인 단계

| 단계 | 설명 | 건너뛰기 옵션 |
|------|------|--------------|
| 1/5 | 하이라이트 추출 | `--skip-highlights` |
| 2/5 | 자막 생성 | `--skip-subtitles` |
| 3/5 | 컴포지션 생성 | - |
| 4/5 | HyperFrames 렌더링 | - |
| 5/5 | 영상 정리 (used/unused) | `--skip-organize` |

### 전체 옵션

```
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
```

### 사용 예시

```bash
# 커스텀 비디오 폴더에서 3개 클립으로 생성
./generate_shorts.sh -v ~/Movies -n 3

# BGM 볼륨 조정
./generate_shorts.sh --bgm-volume 0.5

# 기존 클립으로 자막만 새로 생성
./generate_shorts.sh --skip-highlights -s new_script.txt
```

---

## 수동 실행 (개별 단계)

### 1. 하이라이트 추출

```bash
source venv/bin/activate

# 기본 실행
python src/extract_highlights.py input/videos -o output/highlights

# 특정 파일만 처리
python src/extract_highlights.py input/videos/video.mp4 -o output/highlights
```

**출력**: `output/highlights/` 폴더에 클립 생성

### 2. 자막 생성

```bash
python src/generate_subtitles.py input/script.txt -o output/subtitles.json
```

**출력**: `output/subtitles.json`

### 3. 컴포지션 생성

```bash
# 클립을 HyperFrames로 복사
cp output/highlights/*.mp4 hyperframes/assets/highlights/

# 컴포지션 HTML 생성
python src/generate_composition.py -n 5
```

**출력**: `hyperframes/index.html` (다중 클립 + 자막 포함)

### 4. 렌더링

```bash
cd hyperframes
npx hyperframes render -o ../output/final.mp4
```

**출력**: `output/final.mp4`

### 5. 영상 정리

렌더링 후 원본 비디오를 사용 여부에 따라 분류:

```bash
python src/organize_videos.py

# 실제 이동 없이 결과만 확인
python src/organize_videos.py --dry-run
```

**결과**:
- `input/videos/used/` - 숏폼에 사용된 원본 비디오
- `input/videos/unused/` - 재활용 가능한 비디오

---

## 개별 스크립트 상세

### extract_highlights.py

비디오에서 하이라이트 구간을 자동 감지하여 클립 추출.

```bash
python src/extract_highlights.py [입력] [옵션]

옵션:
    -o, --output PATH    출력 폴더 (기본: output/highlights)
    -c, --config PATH    설정 파일 (기본: input/config.json)
    --manifest PATH      매니페스트 출력 경로
```

**스코어링 기준**:
- 모션 (40%): 프레임 간 움직임
- 컬러 (35%): 채도, 밝기, 색상 다양성
- 피사체 (25%): 에지 밀도, 중앙 집중도

### generate_subtitles.py

스크립트 파일에서 자막 타이밍 자동 생성.

```bash
python src/generate_subtitles.py [스크립트] [옵션]

옵션:
    -o, --output PATH    출력 파일 (기본: output/subtitles.json)
```

### generate_composition.py

다중 클립과 자막을 조합하여 HyperFrames 컴포지션 생성.

```bash
python src/generate_composition.py [옵션]

옵션:
    -c, --clips PATH        클립 폴더 (기본: hyperframes/assets/highlights)
    -s, --subtitles PATH    자막 파일 (기본: output/subtitles.json)
    -o, --output PATH       출력 HTML (기본: hyperframes/index.html)
    -n, --max-clips NUM     최대 클립 수 (기본: 5)
    --bgm-volume FLOAT      BGM 볼륨 (기본: 0.3)
```

### organize_videos.py

렌더링 후 원본 비디오를 사용 여부에 따라 분류.

```bash
python src/organize_videos.py [옵션]

옵션:
    -v, --videos PATH       비디오 폴더 (기본: input/videos)
    -c, --composition PATH  컴포지션 HTML (기본: hyperframes/index.html)
    --dry-run               실제 이동 없이 결과만 표시
```

**분류 기준**: 컴포지션 HTML에서 실제로 참조된 클립의 원본 비디오

---

## 설정 조정

### input/config.json

```json
{
  "highlight_extraction": {
    "min_clip_duration": 3.0,
    "max_clip_duration": 15.0,
    "highlight_threshold": 0.5,
    "scoring_weights": {
      "motion": 0.40,
      "color": 0.35,
      "subject": 0.25
    }
  },
  "subtitle": {
    "syllable_rate": 3.5,
    "max_chars_per_line": 20
  },
  "bgm": {
    "volume": 0.3,
    "fade_in_duration": 1.0,
    "fade_out_duration": 2.0
  }
}
```

| 파라미터 | 설명 | 기본값 |
|---------|------|-------|
| `min_clip_duration` | 최소 클립 길이 (초) | 3.0 |
| `max_clip_duration` | 최대 클립 길이 (초) | 15.0 |
| `highlight_threshold` | 하이라이트 임계값 (0-1) | 0.5 |
| `syllable_rate` | 초당 음절 수 | 3.5 |

---

## 입력 파일 준비

### 비디오 파일
- 위치: `input/videos/`
- 포맷: `.mp4`, `.mov`, `.avi`, `.mkv`
- 16:9 가로 영상 → 자동 90도 회전
- 9:16 세로 영상 → 그대로 처리

### 스크립트 파일
- 위치: `input/script.txt`
- 형식: 한 줄에 한 문장
```
오늘은 정말 좋은 날이에요.
여행을 떠나볼까요?
함께 아름다운 풍경을 감상해봐요.
```

### BGM 파일
- 위치: `hyperframes/assets/bgm.mp3`
- 형식: MP3

---

## 문제 해결

### ModuleNotFoundError: No module named 'cv2'
```bash
source venv/bin/activate
pip install opencv-python numpy
```

### OpenCV 설치 오류
```bash
pip install --upgrade pip
pip install opencv-python-headless
```

### 클립이 추출되지 않는 경우
- `highlight_threshold` 값을 낮춰보세요 (예: 0.3)
- `min_clip_duration` 값을 낮춰보세요 (예: 2.0)

### HyperFrames 렌더링 실패
```bash
cd hyperframes
npm install
npx hyperframes render -o ../output/final.mp4
```

### 비디오가 첫 프레임에서 멈춤
- `data-component="video"` 속성 확인
- `data-start="0"` 속성 확인

### BGM이 포함되지 않음
- `hyperframes/assets/bgm.mp3` 파일 존재 확인
- `data-component="audio"` 속성 확인
