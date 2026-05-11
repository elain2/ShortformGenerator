# ShortVideoGenerator

감성 Vlog 스타일 숏츠를 반자동으로 생성하는 파이프라인.
여러 영상에서 하이라이트를 추출하고, HyperFrames로 초안을 렌더링한 뒤, VLLO에서 더빙과 최종 편집을 진행한다.

## 워크플로우

```
원본 영상들 + 스크립트
        │
        ▼
[1] 하이라이트 추출 (Python + OpenCV)
        │
        ▼
[2] 자막 타이밍 계산
        │
        ▼
[3] HyperFrames 렌더링 → draft.mp4
        │
        ▼
[4] VLLO 최종 편집 + 더빙
        │
        ▼
    완성된 숏츠
```

## 요구사항

- Python 3.10+
- Node.js 22+
- FFmpeg

## 기술 스택

| 단계 | 도구 | 용도 |
|------|------|------|
| 하이라이트 추출 | Python + OpenCV | 장면 분석, 클립 추출 |
| 자막 처리 | Python | 타이밍 계산, JSON 생성 |
| 영상 합성 | HyperFrames | HTML → MP4 렌더링 |
| 최종 편집 | VLLO | 더빙, 미세 조정 |

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

## 프로젝트 구조

```
ShortVideoGenerator/
├── input/
│   ├── videos/           # 원본 영상들
│   ├── script.txt        # 자막용 스크립트
│   └── config.json       # 설정
├── output/
│   ├── highlights/       # 추출된 하이라이트 클립
│   └── draft.mp4         # HyperFrames 출력
├── src/
│   ├── extract_highlights.py
│   └── generate_subtitles.py
├── hyperframes/
│   └── composition/      # HyperFrames 프로젝트
└── README.md
```

## 사용법

```bash
# 1. 하이라이트 추출
python src/extract_highlights.py ./input/videos/ --output ./output/highlights/

# 2. 자막 타이밍 생성
python src/generate_subtitles.py ./input/script.txt --speaking-rate 3.5 --output ./hyperframes/subtitles.json

# 3. HyperFrames 렌더링
cd hyperframes && npx hyperframes render --output ../output/draft.mp4

# 4. VLLO로 draft.mp4 열어서 최종 편집 + 더빙
```

## 참고 자료

- [HyperFrames](https://github.com/heygen-com/hyperframes)
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect)
- [OpenCV Video Analysis](https://docs.opencv.org/4.x/d7/df3/group__imgproc__motion.html)

## 라이선스

MIT License
