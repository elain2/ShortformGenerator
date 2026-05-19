#!/usr/bin/env python3
"""
HyperFrames 컴포지션 생성기
클립과 자막을 조합하여 index.html 생성
CSS 애니메이션 기반 자막 렌더링 지원
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


def generate_subtitle_css(subtitles: list, total_duration: float) -> str:
    """CSS 키프레임 애니메이션 기반 자막 스타일 생성"""
    if not subtitles or total_duration <= 0:
        return ""

    css_parts = []

    # 기본 자막 스타일
    css_parts.append("""
/* CSS 애니메이션 기반 자막 */
.subtitle-item {
    position: absolute;
    opacity: 0;
    font-size: 52px;
    font-weight: 600;
    line-height: 1.5;
    letter-spacing: -0.02em;
    color: #FFF8E7;
    text-shadow:
        0 2px 4px rgba(0, 0, 0, 0.5),
        0 4px 8px rgba(0, 0, 0, 0.3),
        0 0 40px rgba(0, 0, 0, 0.4);
    white-space: pre-line;
    text-align: center;
    max-width: 85%;
    word-break: keep-all;
}

.subtitle-item.long-text {
    font-size: 44px;
}

.subtitle-item.very-long-text {
    font-size: 38px;
}
""")

    # 각 자막에 대한 키프레임 애니메이션
    for i, sub in enumerate(subtitles):
        start_time = sub.get('start_time', sub.get('startTime', 0))
        end_time = sub.get('end_time', sub.get('endTime', 0))
        duration = end_time - start_time

        if duration <= 0:
            continue

        # 퍼센트 계산 (전체 duration 기준)
        start_pct = (start_time / total_duration) * 100
        end_pct = (end_time / total_duration) * 100

        # 키프레임: 시작 전 투명, 표시 구간 불투명, 종료 후 투명
        css_parts.append(f"""
@keyframes subtitle-{i} {{
    0%, {start_pct:.2f}% {{ opacity: 0; }}
    {start_pct + 0.01:.2f}%, {end_pct - 0.01:.2f}% {{ opacity: 1; }}
    {end_pct:.2f}%, 100% {{ opacity: 0; }}
}}

.subtitle-{i} {{
    animation: subtitle-{i} {total_duration}s linear forwards;
}}
""")

    return "\n".join(css_parts)


def generate_subtitle_html(subtitles: list) -> str:
    """자막 HTML 요소 생성"""
    if not subtitles:
        return ""

    html_parts = []
    for i, sub in enumerate(subtitles):
        text = sub.get('text', '')

        # 줄 수에 따른 클래스 (1줄: 기본, 2줄: long-text, 3줄+: very-long-text)
        line_count = text.count('\n') + 1
        size_class = ""
        if line_count >= 3:
            size_class = " very-long-text"
        elif line_count == 2:
            size_class = " long-text"

        # HTML 이스케이프
        escaped_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        html_parts.append(
            f'                <span class="subtitle-item subtitle-{i}{size_class}">{escaped_text}</span>'
        )

    return "\n".join(html_parts)


def generate_composition(
    clips_dir: str = "hyperframes/assets/highlights",
    subtitles_path: str = "output/subtitles.json",
    output_path: str = "hyperframes/index.html",
    max_clips: int = None,  # None = 자막 길이에 맞게 자동 선택
    duration: float = None,  # None = 클립 길이 합계, 지정시 해당 길이로 고정
    bgm_path: str = "assets/bgm.mp3",
    bgm_volume: float = 0.3,
    clip_start: int = None,  # 세그먼트: 시작 클립 인덱스 (0-based)
    clip_end: int = None,    # 세그먼트: 끝 클립 인덱스 (exclusive)
    time_offset: float = 0.0,  # 세그먼트: 시간 오프셋 (이전 세그먼트 누적 시간)
    no_bgm: bool = False,    # 세그먼트: BGM 제외 (나중에 합칠 때 추가)
    no_subtitles: bool = False  # 세그먼트: 자막 제외
):
    """다중 클립 컴포지션 HTML 생성

    세그먼트 모드 (clip_start/clip_end 지정시):
        - 전체 클립 중 일부만 렌더링
        - time_offset으로 자막 타이밍 조정
        - no_bgm, no_subtitles로 세그먼트별 요소 제어
    """

    # 자막 로드 (클립 수 자동 결정을 위해 먼저 로드)
    subtitles = []
    subtitle_duration = 0
    if os.path.exists(subtitles_path) and not no_subtitles:
        with open(subtitles_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            subtitles = data.get('subtitles', [])
            subtitle_duration = data.get('total_duration', 0)
            if subtitle_duration == 0 and subtitles:
                # total_duration이 없으면 마지막 자막의 end_time 사용
                last_sub = subtitles[-1]
                subtitle_duration = last_sub.get('end_time', last_sub.get('endTime', 0))

    # 클립 파일 목록
    clips_path = Path(clips_dir)
    all_clip_files = sorted([f for f in clips_path.glob("*.mp4")])

    if not all_clip_files:
        print("클립 파일이 없습니다.")
        return

    # 세그먼트 모드: 클립 범위 제한
    is_segment_mode = clip_start is not None or clip_end is not None
    if is_segment_mode:
        start_idx = clip_start if clip_start is not None else 0
        end_idx = clip_end if clip_end is not None else len(all_clip_files)
        all_clip_files = all_clip_files[start_idx:end_idx]
        print(f"세그먼트 모드: 클립 {start_idx}~{end_idx-1} ({len(all_clip_files)}개)")

    # 목표 길이 결정 (우선순위: duration 파라미터 > 자막 길이 + 5초 > 무제한)
    if duration is not None:
        target_duration = duration
        print(f"목표 길이: {target_duration:.2f}초 (사용자 지정)")
    elif subtitle_duration > 0 and not is_segment_mode:
        target_duration = subtitle_duration + 5  # 자막 + 5초 여유
        print(f"목표 길이: {target_duration:.2f}초 (자막 기준)")
    else:
        target_duration = float('inf')

    # 클립 정보 수집 (목표 길이에 맞게 자동 선택)
    clips = []
    current_time = 0.0

    for i, clip_file in enumerate(all_clip_files):
        # max_clips가 지정되었으면 그 수만큼만
        if max_clips is not None and i >= max_clips:
            break
        # 목표 길이에 도달하면 중단 (max_clips가 None일 때, 세그먼트 모드 아닐 때)
        if max_clips is None and not is_segment_mode and current_time >= target_duration:
            break
        clip_duration = get_video_duration(str(clip_file))
        clips.append({
            'filename': clip_file.name,
            'path': f"assets/highlights/{clip_file.name}",
            'start': current_time,
            'duration': clip_duration
        })
        current_time += clip_duration
        print(f"  클립: {clip_file.name} (시작: {clips[-1]['start']:.2f}s, 길이: {clip_duration:.2f}s)")

    # 최종 duration 결정: 사용자 지정값 > 자막 길이 > 클립 총 길이
    if duration is not None:
        total_duration = duration
    elif subtitle_duration > 0 and not is_segment_mode:
        total_duration = subtitle_duration
    else:
        total_duration = current_time
    print(f"최종 렌더링 길이: {total_duration:.2f}초")
    if subtitle_duration > 0 and not no_subtitles:
        if duration is None and not is_segment_mode:
            print(f"자막 길이에 맞춤: {subtitle_duration:.2f}초")
        else:
            print(f"자막 길이: {subtitle_duration:.2f}초")

    # 세그먼트 모드: 해당 시간 범위의 자막만 필터링
    if is_segment_mode and subtitles and time_offset > 0:
        segment_start = time_offset
        segment_end = time_offset + total_duration
        filtered_subtitles = []
        for sub in subtitles:
            sub_start = sub.get('start_time', sub.get('startTime', 0))
            sub_end = sub.get('end_time', sub.get('endTime', 0))
            # 세그먼트 시간 범위와 겹치는 자막만 포함
            if sub_end > segment_start and sub_start < segment_end:
                # 시간 오프셋 조정
                filtered_subtitles.append({
                    'text': sub.get('text', ''),
                    'start_time': max(0, sub_start - time_offset),
                    'end_time': min(total_duration, sub_end - time_offset)
                })
        subtitles = filtered_subtitles
        print(f"세그먼트 자막: {len(subtitles)}개 (시간 범위: {segment_start:.1f}s ~ {segment_end:.1f}s)")

    # 비디오 요소 HTML 생성
    video_elements = []
    for i, clip in enumerate(clips):
        video_html = f'''        <video id="clip-{i}"
               class="clip"
               src="{clip['path']}"
               data-component="video"
               data-start="{clip['start']:.3f}"
               muted playsinline preload="auto">
        </video>'''
        video_elements.append(video_html)

    videos_html = "\n".join(video_elements)

    # CSS 애니메이션 기반 자막 생성
    subtitle_css = generate_subtitle_css(subtitles, total_duration)
    subtitle_html = generate_subtitle_html(subtitles)

    # BGM HTML 생성
    if no_bgm:
        bgm_html = "<!-- BGM 제외 (세그먼트 모드) -->"
    else:
        bgm_html = f'''<audio id="bgm"
               src="{bgm_path}"
               data-component="audio"
               data-start="0"
               data-volume="{bgm_volume}"
               loop
               preload="auto">
        </audio>'''

    # HTML 생성
    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1080, height=1920">
    <title>Shorts Video Composition</title>
    <link rel="stylesheet" href="styles.css">
    <style>
{subtitle_css}
    </style>
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

        <!-- 자막 레이어 (CSS 애니메이션 기반) -->
        <div id="subtitle-layer" class="layer">
            <div id="subtitle-container">
{subtitle_html}
            </div>
        </div>

        <!-- BGM -->
        {bgm_html}
    </div>

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
    parser.add_argument('-n', '--max-clips', type=int, default=None,
                        help='최대 클립 수 (미지정시 자막 길이에 맞게 자동 선택)')
    parser.add_argument('-d', '--duration', type=float, default=None,
                        help='최종 영상 길이(초) - 미지정시 클립 길이 합계 사용')
    parser.add_argument('--bgm-volume', type=float, default=0.3,
                        help='BGM 볼륨 (0-1)')
    # 세그먼트 모드 옵션
    parser.add_argument('--clip-start', type=int, default=None,
                        help='세그먼트: 시작 클립 인덱스 (0-based)')
    parser.add_argument('--clip-end', type=int, default=None,
                        help='세그먼트: 끝 클립 인덱스 (exclusive)')
    parser.add_argument('--time-offset', type=float, default=0.0,
                        help='세그먼트: 시간 오프셋 (이전 세그먼트 누적 시간)')
    parser.add_argument('--no-bgm', action='store_true',
                        help='세그먼트: BGM 제외')
    parser.add_argument('--no-subtitles', action='store_true',
                        help='세그먼트: 자막 제외')

    args = parser.parse_args()

    generate_composition(
        clips_dir=args.clips,
        subtitles_path=args.subtitles,
        output_path=args.output,
        max_clips=args.max_clips,
        duration=args.duration,
        bgm_volume=args.bgm_volume,
        clip_start=args.clip_start,
        clip_end=args.clip_end,
        time_offset=args.time_offset,
        no_bgm=args.no_bgm,
        no_subtitles=args.no_subtitles
    )


if __name__ == '__main__':
    main()
