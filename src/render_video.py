#!/usr/bin/env python3
"""
하이브리드 렌더러
ffmpeg로 비디오 합성 + 자막 오버레이
"""

import json
import os
import subprocess
import re
from pathlib import Path
from datetime import timedelta

# ffmpeg-full 경로 (libass 지원)
FFMPEG = '/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg'
FFPROBE = '/opt/homebrew/opt/ffmpeg-full/bin/ffprobe'


def get_video_duration(video_path: str) -> float:
    """FFprobe로 비디오 길이 조회"""
    cmd = [
        FFPROBE, '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def parse_clips_from_html(html_path: str) -> list:
    """index.html에서 비디오 클립 정보 파싱"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    clips = []
    # video 태그 파싱
    video_pattern = r'<video[^>]*id="clip-(\d+)"[^>]*src="([^"]+)"[^>]*data-start="([^"]+)"'
    matches = re.findall(video_pattern, content)

    for match in matches:
        clip_id, src, start = match
        clips.append({
            'id': int(clip_id),
            'src': src,
            'start': float(start)
        })

    # duration 파싱
    duration_match = re.search(r'data-duration="([^"]+)"', content)
    total_duration = float(duration_match.group(1)) if duration_match else 60.0

    return clips, total_duration


def format_ass_time(seconds: float) -> str:
    """ASS 자막 시간 형식 (H:MM:SS.cc)"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def generate_ass_subtitle(subtitles: list, output_path: str, width: int = 1080, height: int = 1920):
    """ASS 자막 파일 생성"""

    # ASS 헤더
    ass_content = f"""[Script Info]
Title: Shorts Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Pretendard,52,&H00E7F8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,80,80,100,1
Style: Long,Pretendard,44,&H00E7F8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,80,80,100,1
Style: VeryLong,Pretendard,38,&H00E7F8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,80,80,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for sub in subtitles:
        text = sub.get('text', '')
        start_time = sub.get('start_time', sub.get('startTime', 0))
        end_time = sub.get('end_time', sub.get('endTime', 0))

        # 줄 수에 따른 스타일 선택
        line_count = text.count('\n') + 1
        if line_count >= 3:
            style = "VeryLong"
        elif line_count == 2:
            style = "Long"
        else:
            style = "Default"

        # ASS에서 줄바꿈은 \N
        ass_text = text.replace('\n', '\\N')

        start_str = format_ass_time(start_time)
        end_str = format_ass_time(end_time)

        ass_content += f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{ass_text}\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    print(f"ASS 자막 생성: {output_path}")
    return output_path


def render_video(
    clips_dir: str = "hyperframes/assets/highlights",
    subtitles_path: str = "output/subtitles.json",
    html_path: str = "hyperframes/index.html",
    bgm_path: str = "hyperframes/assets/bgm.mp3",
    output_path: str = "output/final.mp4",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30
):
    """하이브리드 렌더링 실행"""

    print("=== 하이브리드 렌더러 ===\n")

    # 1. 클립 정보 파싱
    print("1. 클립 정보 파싱...")
    clips, total_duration = parse_clips_from_html(html_path)
    print(f"   클립: {len(clips)}개, 총 길이: {total_duration}초")

    # 클립 경로를 절대 경로로 변환
    base_dir = os.path.dirname(html_path)
    for clip in clips:
        clip['path'] = os.path.join(base_dir, clip['src'])
        clip['duration'] = get_video_duration(clip['path'])
        print(f"   - {clip['src']}: {clip['start']}s ~ {clip['start'] + clip['duration']:.1f}s")

    # 2. 자막 로드
    print("\n2. 자막 로드...")
    subtitles = []
    if os.path.exists(subtitles_path):
        with open(subtitles_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            subtitles = data.get('subtitles', [])
        print(f"   자막: {len(subtitles)}개")
    else:
        print("   자막 파일 없음")

    # 3. ASS 자막 생성
    ass_path = "output/subtitles.ass"
    os.makedirs("output", exist_ok=True)

    if subtitles:
        print("\n3. ASS 자막 생성...")
        generate_ass_subtitle(subtitles, ass_path, width, height)

    # 4. FFmpeg 필터 구성
    print("\n4. FFmpeg 필터 구성...")

    # 입력 파일 목록
    inputs = []
    for clip in clips:
        inputs.extend(['-i', clip['path']])

    # BGM 추가
    if os.path.exists(bgm_path):
        inputs.extend(['-i', bgm_path])
        bgm_index = len(clips)
        has_bgm = True
    else:
        has_bgm = False
        print("   BGM 파일 없음, 음성 없이 렌더링")

    # 복잡한 필터 구성
    filter_parts = []

    # 유효한 클립만 필터링 (시작 시간이 total_duration 이내인 클립만)
    valid_clips = [(i, clip) for i, clip in enumerate(clips) if clip['start'] < total_duration]
    print(f"   유효 클립: {len(valid_clips)}개 (총 {len(clips)}개 중)")

    # 각 비디오 클립을 타임라인에 배치
    for i, clip in valid_clips:
        # 비디오 스케일, 8bit 변환, 패딩
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"format=yuv420p,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setpts=PTS+{clip['start']}/TB[v{i}]"
        )

    # 비디오 오버레이 (순차적으로)
    if len(valid_clips) == 1:
        i, clip = valid_clips[0]
        filter_parts.append(f"[v{i}]trim=0:{total_duration},setpts=PTS-STARTPTS[vout]")
    else:
        # 검은 배경 베이스 생성
        overlay_chain = f"color=c=black:s={width}x{height}:d={total_duration}[base]"
        filter_parts.append(overlay_chain)

        current = "base"
        for idx, (i, clip) in enumerate(valid_clips):
            enable_start = clip['start']
            enable_end = min(clip['start'] + clip['duration'], total_duration)

            # 마지막 클립이면 vout으로 출력
            is_last = idx == len(valid_clips) - 1
            next_label = "vout" if is_last else f"tmp{idx}"

            filter_parts.append(
                f"[{current}][v{i}]overlay=0:0:enable='between(t,{enable_start},{enable_end})'[{next_label}]"
            )
            current = next_label

    filter_complex = ";".join(filter_parts)

    # 5. FFmpeg 실행 - 1단계: 비디오 합성
    print("\n5. FFmpeg 렌더링...")
    temp_video = "output/temp_video.mp4"

    cmd = [FFMPEG, '-y']
    cmd.extend(inputs)
    cmd.extend([
        '-filter_complex', filter_complex,
        '-map', '[vout]',
    ])

    if has_bgm:
        cmd.extend([
            '-map', f'{bgm_index}:a',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest'
        ])

    cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '18',
        '-r', str(fps),
        '-pix_fmt', 'yuv420p',
        '-t', str(total_duration),
        temp_video
    ])

    print(f"   1단계: 비디오 합성...")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n비디오 합성 실패: {e}")
        print("\n명령어:")
        print(' '.join(cmd))
        raise

    # 6. 2단계: 자막 오버레이
    if subtitles and os.path.exists(ass_path):
        print(f"   2단계: 자막 오버레이...")
        # FFmpeg ass 필터는 경로에서 콜론과 역슬래시를 이스케이프해야 함
        # 상대 경로 사용으로 문제 회피
        escaped_ass_path = ass_path.replace('\\', '/').replace(':', '\\:')

        cmd2 = [
            FFMPEG, '-y',
            '-i', temp_video,
            '-vf', f"ass={escaped_ass_path}",
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '18',
            '-c:a', 'copy',
            output_path
        ]

        try:
            subprocess.run(cmd2, check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n자막 오버레이 실패: {e}")
            # 자막 없이 복사
            print("자막 없이 출력...")
            os.rename(temp_video, output_path)
    else:
        os.rename(temp_video, output_path)

    # 임시 파일 정리
    if os.path.exists(temp_video):
        os.remove(temp_video)

    print(f"\n=== 렌더링 완료 ===")
    print(f"출력: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='하이브리드 비디오 렌더러')
    parser.add_argument('-o', '--output', default='output/final.mp4',
                        help='출력 파일 경로')
    parser.add_argument('--no-subtitles', action='store_true',
                        help='자막 제외')
    args = parser.parse_args()

    render_video(output_path=args.output)


if __name__ == '__main__':
    main()
