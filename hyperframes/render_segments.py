#!/usr/bin/env python3
"""
HyperFrames 세그먼트 렌더링 스크립트

메모리 문제를 해결하기 위해 영상을 세그먼트로 나눠서 렌더링 후 합칩니다.
"""

import os
import re
import subprocess
import sys
import shutil
import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='HyperFrames 세그먼트 렌더링')
    parser.add_argument('-o', '--output', default='../output/final.mp4', help='최종 출력 파일')
    parser.add_argument('-s', '--segment-duration', type=float, default=30.0, help='세그먼트 길이 (초)')
    parser.add_argument('-w', '--workers', type=int, default=1, help='렌더링 워커 수')
    parser.add_argument('-q', '--quality', default='standard', choices=['draft', 'standard', 'high'])
    parser.add_argument('--docker', action='store_true', help='Docker 사용')
    parser.add_argument('--keep-segments', action='store_true', help='세그먼트 파일 유지')
    return parser.parse_args()


def get_composition_info(html_path):
    """index.html에서 컴포지션 정보 추출"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    duration_match = re.search(r'data-duration="([\d.]+)"', content)
    duration = float(duration_match.group(1)) if duration_match else 60.0

    return {'duration': duration, 'content': content}


def get_clips_in_range(content, start_time, end_time):
    """특정 시간 범위에 포함되는 클립들 추출"""
    # 비디오 클립 파싱
    video_pattern = r'<video\s+id="(clip-\d+)"[^>]*src="([^"]+)"[^>]*data-start="([\d.]+)"[^>]*>'
    clips = []

    for match in re.finditer(video_pattern, content):
        clip_id = match.group(1)
        src = match.group(2)
        clip_start = float(match.group(3))

        # 이 클립이 현재 세그먼트와 겹치는지 확인
        # 클립의 실제 재생 시간을 알 수 없으므로, 다음 클립 시작 전까지로 추정
        clips.append({
            'id': clip_id,
            'src': src,
            'start': clip_start,
            'match': match.group(0)
        })

    # 클립 시작 시간 기준 정렬
    clips.sort(key=lambda x: x['start'])

    # 각 클립의 종료 시간 계산 (다음 클립 시작 또는 컴포지션 끝)
    for i, clip in enumerate(clips):
        if i < len(clips) - 1:
            clip['end'] = clips[i + 1]['start']
        else:
            clip['end'] = end_time + 10  # 마지막 클립은 여유있게

    # 세그먼트 범위와 겹치는 클립만 선택
    relevant_clips = []
    for clip in clips:
        # 클립이 세그먼트와 겹치는 경우
        if clip['start'] < end_time and clip['end'] > start_time:
            relevant_clips.append(clip)

    return relevant_clips


def create_segment_html(original_content, segment_start, segment_end, segment_dir, segment_bgm_filename=None):
    """세그먼트용 HTML 생성"""
    content = original_content
    segment_duration = segment_end - segment_start

    # data-duration 수정
    content = re.sub(
        r'data-duration="[\d.]+"',
        f'data-duration="{segment_duration:.3f}"',
        content
    )

    # data-start 추가/수정 (컴포지션 시작 오프셋)
    if 'data-start="' in content:
        content = re.sub(
            r'(data-composition-id="[^"]*"[^>]*?)data-start="[\d.]+"',
            f'\\1data-start="{segment_start:.3f}"',
            content
        )
    else:
        content = re.sub(
            r'(data-composition-id="[^"]*")',
            f'\\1\n         data-start="{segment_start:.3f}"',
            content
        )

    # 세그먼트 범위의 클립만 포함하도록 필터링
    clips = get_clips_in_range(original_content, segment_start, segment_end)

    # 비디오 레이어 재구성
    video_layer_pattern = r'(<div id="video-layer"[^>]*>)(.*?)(</div>\s*<!-- 자막)'

    def rebuild_video_layer(match):
        layer_start = match.group(1)
        layer_end = match.group(3)

        video_html = "\n"
        for i, clip in enumerate(clips):
            # 세그먼트 내에서의 상대적 시작 시간
            relative_start = max(0, clip['start'] - segment_start)
            video_html += f'''        <video id="clip-{i}"
               class="clip"
               src="{clip['src']}"
               data-component="video"
               data-start="{relative_start:.3f}"
               muted playsinline preload="auto">
        </video>
'''

        return layer_start + video_html + "        " + layer_end

    content = re.sub(video_layer_pattern, rebuild_video_layer, content, flags=re.DOTALL)

    # BGM 경로를 세그먼트용 BGM으로 변경
    if segment_bgm_filename:
        content = re.sub(
            r'src="assets/bgm\.mp3"',
            f'src="{segment_bgm_filename}"',
            content
        )
        # loop 속성 제거 (세그먼트는 정확한 길이로 잘린 BGM 사용)
        content = re.sub(
            r'(<audio[^>]*)\s+loop(\s|>)',
            r'\1\2',
            content
        )

    # 세그먼트용 HTML 저장
    segment_html_path = segment_dir / 'index.html'
    with open(segment_html_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return segment_html_path


def render_segment(segment_dir, output_path, args):
    """단일 세그먼트 렌더링"""
    cmd = ['npx', 'hyperframes', 'render', str(segment_dir), '-o', str(output_path)]
    cmd.extend(['-w', str(args.workers)])
    cmd.extend(['-q', args.quality])

    if args.docker:
        cmd.append('--docker')

    print(f"  명령: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    return result.returncode == 0


def concatenate_segments(segment_files, output_path):
    """FFmpeg로 세그먼트 합치기"""
    # concat 파일 생성
    concat_file = Path(output_path).parent / 'concat_list.txt'
    with open(concat_file, 'w') as f:
        for seg_file in segment_files:
            f.write(f"file '{seg_file.absolute()}'\n")

    # FFmpeg로 합치기
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        str(output_path)
    ]

    print(f"\n세그먼트 합치는 중...")
    result = subprocess.run(cmd, capture_output=True)

    # 정리
    concat_file.unlink()

    return result.returncode == 0


def setup_bgm(hyperframes_dir):
    """input 폴더의 mp3 파일을 assets/bgm.mp3로 복사"""
    input_dir = hyperframes_dir.parent / 'input'
    assets_dir = hyperframes_dir / 'assets'

    # input 폴더에서 mp3 파일 찾기
    mp3_files = list(input_dir.glob('*.mp3'))

    if not mp3_files:
        print("경고: input 폴더에 mp3 파일이 없습니다.")
        return None

    # 첫 번째 mp3 파일 사용 (여러 개일 경우)
    source_mp3 = mp3_files[0]
    target_bgm = assets_dir / 'bgm.mp3'

    # assets 디렉토리 생성
    assets_dir.mkdir(exist_ok=True)

    # 복사
    print(f"BGM 설정: {source_mp3.name} → assets/bgm.mp3")
    shutil.copy(source_mp3, target_bgm)

    return target_bgm


def cut_bgm_segment(source_bgm, output_path, start_time, duration):
    """FFmpeg로 BGM을 세그먼트 시간대에 맞게 자르기"""
    cmd = [
        'ffmpeg', '-y',
        '-i', str(source_bgm),
        '-ss', str(start_time),
        '-t', str(duration),
        '-c', 'copy',
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def main():
    args = parse_args()

    hyperframes_dir = Path(__file__).parent
    html_path = hyperframes_dir / 'index.html'

    if not html_path.exists():
        print("오류: index.html을 찾을 수 없습니다.")
        sys.exit(1)

    # BGM 설정 (input 폴더의 mp3 → assets/bgm.mp3)
    source_bgm = setup_bgm(hyperframes_dir)

    # 컴포지션 정보 가져오기
    info = get_composition_info(html_path)
    total_duration = info['duration']

    print(f"총 영상 길이: {total_duration}초")
    print(f"세그먼트 길이: {args.segment_duration}초")

    # 세그먼트 계산
    segments = []
    current_start = 0
    while current_start < total_duration:
        segment_end = min(current_start + args.segment_duration, total_duration)
        segments.append((current_start, segment_end))
        current_start = segment_end

    print(f"총 {len(segments)}개 세그먼트로 분할\n")

    # 임시 디렉토리 생성
    temp_dir = hyperframes_dir / '_segment_temp'
    temp_dir.mkdir(exist_ok=True)

    # assets 심볼릭 링크 생성
    assets_link = temp_dir / 'assets'
    if not assets_link.exists():
        assets_link.symlink_to(hyperframes_dir / 'assets')

    # styles.css 복사
    shutil.copy(hyperframes_dir / 'styles.css', temp_dir / 'styles.css')
    shutil.copy(hyperframes_dir / 'animation.js', temp_dir / 'animation.js')

    # 각 세그먼트 렌더링
    segment_files = []

    for i, (start, end) in enumerate(segments):
        print(f"[{i+1}/{len(segments)}] 세그먼트 렌더링: {start:.1f}초 ~ {end:.1f}초")

        # 세그먼트용 BGM 자르기
        segment_bgm_filename = None
        if source_bgm:
            segment_bgm_path = temp_dir / f'bgm_segment_{i:03d}.mp3'
            segment_duration = end - start
            print(f"  BGM 자르기: {start:.1f}초 ~ {end:.1f}초")
            if cut_bgm_segment(source_bgm, segment_bgm_path, start, segment_duration):
                segment_bgm_filename = segment_bgm_path.name
            else:
                print(f"  경고: BGM 자르기 실패, 원본 사용")

        # 세그먼트 HTML 생성
        create_segment_html(info['content'], start, end, temp_dir, segment_bgm_filename)

        # 렌더링
        segment_output = temp_dir / f'segment_{i:03d}.mp4'
        success = render_segment(temp_dir, segment_output, args)

        if not success:
            print(f"  오류: 세그먼트 {i+1} 렌더링 실패")
            sys.exit(1)

        segment_files.append(segment_output)
        print(f"  완료: {segment_output.name}\n")

    # 세그먼트 합치기
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(segment_files) == 1:
        # 세그먼트가 하나면 그냥 복사
        shutil.copy(segment_files[0], output_path)
    else:
        success = concatenate_segments(segment_files, output_path)
        if not success:
            print("오류: 세그먼트 합치기 실패")
            sys.exit(1)

    # 정리
    if not args.keep_segments:
        shutil.rmtree(temp_dir)
        print("임시 파일 정리 완료")

    print(f"\n렌더링 완료: {output_path}")


if __name__ == '__main__':
    main()
