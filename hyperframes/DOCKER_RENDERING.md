# Docker로 HyperFrames 렌더링하기

HyperFrames 렌더링 중 타임아웃 오류가 발생할 경우 Docker를 사용하면 더 안정적인 렌더링이 가능합니다.

## 1. Docker Desktop 설치

### Homebrew 사용
```bash
brew install --cask docker
```

### 직접 다운로드
[Docker 공식 사이트](https://docs.docker.com/desktop/install/mac-install/)에서 다운로드

## 2. Docker Desktop 실행

설치 후 Docker Desktop 앱을 실행하세요. 메뉴바에 고래 아이콘이 나타나면 준비 완료입니다.

```bash
# Docker가 실행 중인지 확인
docker info
```

## 3. HyperFrames로 렌더링

```bash
npx hyperframes render -o ../output/final.mp4 --docker
```

## Docker 사용의 장점

| 장점 | 설명 |
|------|------|
| 격리된 환경 | 시스템 메모리 압박에 덜 민감 |
| 일관된 결과 | 모든 환경에서 동일한 렌더링 |
| 타임아웃 문제 감소 | 더 안정적인 Chrome 환경 |

## 추가 옵션 조합

```bash
# Docker + 워커 수 제한
npx hyperframes render -o ../output/final.mp4 --docker --workers 2

# Docker + 고품질
npx hyperframes render -o ../output/final.mp4 --docker -q high

# Docker + 워커 수 제한 + 고품질
npx hyperframes render -o ../output/final.mp4 --docker --workers 2 -q high
```

## 참고 사항

- Docker Desktop이 처음 실행될 때 이미지를 다운로드하므로 첫 렌더링은 조금 더 오래 걸릴 수 있습니다.
- Docker 없이 메모리 부족 문제를 해결하려면 다른 앱을 종료하고 `--workers 1` 옵션을 사용하세요.

## 문제 해결

### Docker가 실행되지 않는 경우
```bash
# Docker Desktop 앱을 먼저 실행하세요
open -a Docker
```

### 시스템 상태 확인
```bash
npx hyperframes doctor
```
