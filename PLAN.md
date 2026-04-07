# ShortVideoGenerator iOS MVP 구현 계획

## 개요
음악 비트에 맞춰 자동으로 하이라이트를 추출하고 숏비디오를 생성하는 가벼운 iOS 앱

## 핵심 기능 (MVP Scope)
1. **템플릿 선택** - 미리 정의된 음악 + 비트 포인트
2. **동영상 선택** - Photos에서 다중 선택
3. **하이라이트 자동 추출** - 모션/밝기 기반 휴리스틱
4. **구간 수동 조정** - 드래그로 하이라이트 구간 변경
5. **내보내기** - 1080x1920 (9:16) 고정

## 기술 스택
- SwiftUI + @Observable (iOS 17+)
- AVFoundation (영상 합성/내보내기)
- Photos Framework (PHPicker)
- Clean Architecture (크로스플랫폼 전환 대비)

## 프로젝트 구조
```
ShortVideoGenerator/
├── App/
│   ├── ShortVideoGeneratorApp.swift
│   └── DI/DIContainer.swift
├── Presentation/
│   ├── Screens/
│   │   ├── Home/
│   │   ├── TemplateSelection/
│   │   ├── VideoSelection/
│   │   ├── Editor/
│   │   └── Export/
│   └── Components/
├── Domain/
│   ├── Entities/ (Template, BeatPoint, VideoClip, Highlight, Project)
│   ├── UseCases/
│   └── Interfaces/
├── Data/
│   ├── Repositories/
│   └── DataSources/
├── Infrastructure/
│   └── VideoProcessing/
│       ├── HighlightExtractor.swift
│       ├── AVFoundationComposer.swift
│       └── VideoExporter.swift
└── Resources/
    └── Templates/templates.json
```

## 화면 흐름
```
Home → Template Selection → Video Selection → Editor → Export
```

## 핵심 모델

### Template
```swift
struct Template: Identifiable, Codable {
    let id: String
    let name: String
    let musicFileName: String
    let duration: TimeInterval
    let beatPoints: [BeatPoint]
}
```

### BeatPoint
```swift
struct BeatPoint: Identifiable, Codable {
    let id: String
    let timestamp: TimeInterval
    let duration: TimeInterval
    let intensity: Double // 0.0 ~ 1.0
}
```

### VideoClip
```swift
struct VideoClip: Identifiable {
    let id: String
    let localIdentifier: String
    let duration: TimeInterval
}
```

### Highlight
```swift
struct Highlight: Identifiable {
    let id: String
    let clipId: String
    let beatPointId: String
    var startTime: TimeInterval
    var endTime: TimeInterval
}
```

### Project
```swift
struct Project: Identifiable {
    let id: String
    let template: Template
    var clips: [VideoClip]
    var highlights: [Highlight]
}
```

## 하이라이트 자동 추출 알고리즘

### 분석 방식
- 초당 2프레임 저해상도(320x180) 분석
- 메모리 효율을 위한 배치 처리

### 스코어링 기준
| 요소 | 가중치 | 설명 |
|------|--------|------|
| 모션 | 50% | 프레임 간 픽셀 변화량 |
| 밝기 | 30% | 적정 밝기 범위 선호 |
| 위치 | 20% | 영상 중반부 선호 |

### 구간 선택
- 슬라이딩 윈도우로 비트 포인트 duration에 맞는 최적 구간 선택
- 각 비트 포인트별로 가장 높은 스코어의 구간 할당

## MVP 제외 항목
- 프로젝트 저장/불러오기
- 커스텀 음악 추가
- 전환 효과, 필터, 텍스트 오버레이
- SNS 직접 공유
- 다중 해상도/비율

## 구현 순서

### Phase 1: 프로젝트 기반
1. Xcode 프로젝트 생성 (iOS 17+, SwiftUI)
2. 폴더 구조 및 Domain 모델 정의
3. JSON 템플릿 파싱
4. DIContainer 설정

### Phase 2: 화면 구현
1. HomeView
2. TemplateSelectionView + ViewModel
3. VideoSelectionView (PHPicker 연동)
4. Navigation 흐름

### Phase 3: 핵심 기능
1. HighlightExtractor 구현
2. AVFoundationComposer 구현
3. EditorView + 타임라인 UI
4. 프리뷰 재생

### Phase 4: 마무리
1. ExportView + VideoExporter
2. 에러 처리
3. UI 폴리싱

## 검증 방법
1. 템플릿 3개 이상 로드 확인
2. Photos에서 동영상 5개 이상 선택 테스트
3. 하이라이트 자동 추출 결과 확인 (30초 영상 기준 3초 내 처리)
4. 구간 조정 드래그 동작 테스트
5. 최종 영상 내보내기 → 사진 앱 저장 확인
6. 실제 인스타 릴스 업로드 테스트

## 참고 사항

### 필요한 권한
- `NSPhotoLibraryUsageDescription` - 사진 라이브러리 접근
- `NSPhotoLibraryAddUsageDescription` - 사진 라이브러리 저장

### 최소 요구사항
- iOS 17.0+
- Xcode 15.0+
