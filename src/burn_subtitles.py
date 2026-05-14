#!/usr/bin/env python3
"""
자막 번인 모듈
FFmpeg drawtext 필터를 사용하여 영상에 자막을 직접 입히기
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path


def burn_subtitles(
    input_video: str,
    subtitles_json: str,
    output_video: str,
    font_size: int = 48,
    position: str = "center"
) -> bool:
    """FFmpeg drawtext로 자막을 영상에 번인"""

    with open(subtitles_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    subtitles = data.get('subtitles', [])

    if not subtitles:
        print("자막이 없습니다.")
        # 자막 없이 복사
        subprocess.run(['cp', input_video, output_video])
        return True

    # 자막 위치
    if position == "center":
        y_expr = "(h-text_h)/2"
    else:
        y_expr = "h-text_h-100"

    # drawtext 필터 체인 생성
    filters = []
    for sub in subtitles:
        start = sub.get('start_time', sub.get('startTime', 0))
        end = sub.get('end_time', sub.get('endTime', 0))
        text = sub.get('text', '').replace("'", "'\\''").replace(":", "\\:")
        # 줄바꿈을 실제 줄바꿈으로
        text = text.replace('\n', '\\n')

        filter_str = (
            f"drawtext=text='{text}':"
            f"fontsize={font_size}:"
            f"fontcolor=white:"
            f"borderw=3:"
            f"bordercolor=black:"
            f"x=(w-text_w)/2:"
            f"y={y_expr}:"
            f"enable='between(t,{start},{end})'"
        )
        filters.append(filter_str)

    filter_complex = ",".join(filters)

    cmd = [
        'ffmpeg', '-y',
        '-i', input_video,
        '-vf', filter_complex,
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'copy',
        output_video
    ]

    print(f"자막 번인 중: {input_video}")
    print(f"  - 자막 수: {len(subtitles)}개")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg 오류: {result.stderr[-500:]}")
        return False

    print(f"완료: {output_video}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description='자막 번인')
    parser.add_argument('input', help='입력 비디오 파일')
    parser.add_argument('-s', '--subtitles', default='output/subtitles.json',
                        help='자막 JSON 파일')
    parser.add_argument('-o', '--output', default=None,
                        help='출력 파일')
    parser.add_argument('--font-size', type=int, default=48,
                        help='폰트 크기')
    parser.add_argument('--position', choices=['center', 'bottom'], default='center',
                        help='자막 위치')
    args = parser.parse_args()

    if args.output is None:
        input_path = Path(args.input)
        args.output = str(input_path.parent / f"{input_path.stem}_subtitled{input_path.suffix}")

    burn_subtitles(
        args.input,
        args.subtitles,
        args.output,
        font_size=args.font_size,
        position=args.position
    )


if __name__ == '__main__':
    main()
