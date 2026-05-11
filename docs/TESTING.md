# 테스트 가이드

## 사전 요구사항

### 필수 설치
```bash
# Python 패키지
pip install opencv-python numpy

# FFmpeg (macOS)
brew install ffmpeg
```

### 설치 확인
```bash
python3 -c "import cv2; print('OpenCV:', cv2.__version__)"
ffmpeg -version
```

---

## 하이라이트 추출 테스트

### 1. 테스트 영상 준비

`input/videos/` 폴더에 테스트할 영상 파일을 넣습니다.

```bash
# 예시: 영상 파일 복사
cp ~/Movies/test_video.mp4 input/videos/

# 또는 여러 파일
cp ~/Movies/*.mp4 input/videos/
```

**지원 포맷**: `.mp4`, `.mov`, `.avi`, `.mkv`

**권장 테스트 영상**:
- 16:9 가로 영상 (1920x1080 등) - 센터 크롭 테스트
- 9:16 세로 영상 (1080x1920 등) - 크롭 없이 처리 확인
- 다양한 장면이 포함된 1-3분 길이 영상

### 2. 하이라이트 추출 실행

```bash
cd /Users/kayoung/Github/ShortVideoGenerator

# 기본 실행
python src/extract_highlights.py input/videos -o output/highlights

# 특정 파일만 처리
python src/extract_highlights.py input/videos/test_video.mp4 -o output/highlights

# 커스텀 설정 사용
python src/extract_highlights.py input/videos -c input/config.json -o output/highlights
```

### 3. 출력 확인

```bash
# 추출된 클립 목록
ls -la output/highlights/

# 매니페스트 확인
cat output/highlights_manifest.json
```

**예상 출력 구조**:
```
output/
├── highlights/
│   ├── test_video_clip_001.mp4
│   ├── test_video_clip_002.mp4
│   └── ...
└── highlights_manifest.json
```

### 4. 결과 검증

#### 콘솔 출력 확인
```
비디오 분석 중: input/videos/test_video.mp4
  - 해상도: 1920x1080 (16:9 가로 → 9:16 센터크롭)
  - 길이: 120.0초, FPS: 30.0
  - 5개 하이라이트 구간 탐지됨
클립 추출 중: test_video_clip_001.mp4 (12.5s - 18.3s)
...
```

#### 클립 해상도 확인
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 output/highlights/test_video_clip_001.mp4
# 예상 출력: 1080,1920
```

---

## 자막 생성 테스트

### 1. 스크립트 파일 확인
```bash
cat input/script.txt
```

### 2. 자막 생성 실행
```bash
python src/generate_subtitles.py input/script.txt -o output/subtitles.json
```

### 3. 결과 확인
```bash
cat output/subtitles.json
```

---

## 전체 파이프라인 테스트

### 1. 하이라이트 추출
```bash
python src/extract_highlights.py input/videos -o output/highlights
```

### 2. 자막 생성
```bash
python src/generate_subtitles.py input/script.txt -o output/subtitles.json
```

### 3. HyperFrames 에셋 복사
```bash
cp output/highlights/*.mp4 hyperframes/assets/highlights/
cp input/bgm.mp3 hyperframes/assets/bgm.mp3  # BGM 파일 필요
```

### 4. 최종 영상 렌더링
```bash
cd hyperframes
npx hyperframes render -o ../output/final.mp4
```

### 5. 결과 확인
```bash
open ../output/final.mp4  # macOS에서 영상 재생
```

---

## 설정 조정

`input/config.json`에서 파라미터 조정 가능:

```json
{
  "highlight_extraction": {
    "min_clip_duration": 3.0,      // 최소 클립 길이 (초)
    "max_clip_duration": 15.0,     // 최대 클립 길이 (초)
    "highlight_threshold": 0.5,    // 하이라이트 임계값 (0-1)
    "scoring_weights": {
      "motion": 0.40,              // 움직임 가중치
      "color": 0.35,               // 색감 가중치
      "subject": 0.25              // 피사체 가중치
    }
  }
}
```

---

## 문제 해결

### OpenCV 설치 오류
```bash
pip install --upgrade pip
pip install opencv-python-headless  # GUI 없는 버전
```

### FFmpeg 권한 오류
```bash
chmod +x /opt/homebrew/bin/ffmpeg
```

### 클립이 추출되지 않는 경우
- `highlight_threshold` 값을 낮춰보세요 (예: 0.3)
- `min_clip_duration` 값을 낮춰보세요 (예: 2.0)
