#!/usr/bin/env python3
"""
HyperFrames 컴포지션 생성기
클립과 자막을 조합하여 index.html 생성
"""

import json
import os
import subprocess
from pathlib import Path


def get_video_duration(video_path: str) -> float:
    """FFprobe로 비디오 길이 조회"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def generate_composition(
    clips_dir: str = "hyperframes/assets/highlights",
    subtitles_path: str = "output/subtitles.json",
    output_path: str = "hyperframes/index.html",
    max_clips: int = 5,
    bgm_path: str = "assets/bgm.mp3",
    bgm_volume: float = 0.3
):
    """다중 클립 컴포지션 HTML 생성"""

    # 클립 파일 목록
    clips_path = Path(clips_dir)
    clip_files = sorted([f for f in clips_path.glob("*.mp4")])[:max_clips]

    if not clip_files:
        print("클립 파일이 없습니다.")
        return

    # 클립 정보 수집
    clips = []
    current_time = 0.0

    for clip_file in clip_files:
        duration = get_video_duration(str(clip_file))
        clips.append({
            'filename': clip_file.name,
            'path': f"assets/highlights/{clip_file.name}",
            'start': current_time,
            'duration': duration
        })
        current_time += duration
        print(f"  클립: {clip_file.name} (시작: {clips[-1]['start']:.2f}s, 길이: {duration:.2f}s)")

    total_duration = current_time
    print(f"총 길이: {total_duration:.2f}초")

    # 자막 로드
    subtitles = []
    if os.path.exists(subtitles_path):
        with open(subtitles_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            subtitles = data.get('subtitles', [])

    # 비디오 요소 HTML 생성
    video_elements = []
    for i, clip in enumerate(clips):
        video_html = f'''        <video class="clip"
               src="{clip['path']}"
               data-component="video"
               data-start="{clip['start']:.3f}"
               muted playsinline preload="auto">
        </video>'''
        video_elements.append(video_html)

    videos_html = "\n".join(video_elements)

    # 자막 JSON
    subtitles_json = json.dumps(subtitles, ensure_ascii=False, indent=2)

    # HTML 생성
    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1080, height=1920">
    <title>Shorts Video Composition</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <!-- HyperFrames 루트 컴포지션 -->
    <div id="composition-root"
         data-composition-id="shorts-main"
         data-width="1080"
         data-height="1920"
         data-fps="30"
         data-duration="{total_duration:.3f}"
         data-start="0">

        <!-- 비디오 레이어 (다중 클립) -->
        <div id="video-layer" class="layer">
{videos_html}
        </div>

        <!-- 자막 레이어 -->
        <div id="subtitle-layer" class="layer">
            <div id="subtitle-container">
                <p id="subtitle-text"></p>
            </div>
        </div>

        <!-- BGM -->
        <audio id="bgm"
               src="{bgm_path}"
               data-component="audio"
               data-start="0"
               data-volume="{bgm_volume}"
               loop
               preload="auto">
        </audio>
    </div>

    <!-- 자막 데이터 -->
    <script type="application/json" id="subtitles-data">
{subtitles_json}
    </script>

    <!-- 스크립트 -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
    <script src="animation.js"></script>
</body>
</html>
'''

    # 파일 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"컴포지션 생성 완료: {output_path}")
    print(f"  - 클립: {len(clips)}개")
    print(f"  - 자막: {len(subtitles)}개")
    print(f"  - 총 길이: {total_duration:.2f}초")

    return {
        'clips': clips,
        'total_duration': total_duration,
        'subtitles_count': len(subtitles)
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='HyperFrames 컴포지션 생성')
    parser.add_argument('-c', '--clips', default='hyperframes/assets/highlights',
                        help='클립 폴더 경로')
    parser.add_argument('-s', '--subtitles', default='output/subtitles.json',
                        help='자막 파일 경로')
    parser.add_argument('-o', '--output', default='hyperframes/index.html',
                        help='출력 HTML 경로')
    parser.add_argument('-n', '--max-clips', type=int, default=5,
                        help='최대 클립 수')
    parser.add_argument('--bgm-volume', type=float, default=0.3,
                        help='BGM 볼륨 (0-1)')

    args = parser.parse_args()

    generate_composition(
        clips_dir=args.clips,
        subtitles_path=args.subtitles,
        output_path=args.output,
        max_clips=args.max_clips,
        bgm_volume=args.bgm_volume
    )


if __name__ == '__main__':
    main()
