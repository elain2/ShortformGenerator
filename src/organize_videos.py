#!/usr/bin/env python3
"""
원본 비디오를 wireframe에서 사용 여부에 따라 분류합니다.
- used/: 최종 숏폼에 사용된 원본 비디오
- unused/: 사용되지 않은 원본 비디오 (재활용 가능)
"""

import os
import re
import shutil
import argparse
from pathlib import Path
from typing import Optional


def extract_used_videos_from_html(html_path: str) -> set:
    """HTML에서 사용된 클립 파일명 추출 후 원본 비디오명 반환"""
    used_sources = set()

    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # src="assets/highlights/파일명.mp4" 패턴 찾기
    pattern = r'src="assets/highlights/([^"]+)"'
    clips = re.findall(pattern, content)

    for clip in clips:
        # 클립명에서 원본 비디오명 추출 (예: DJI_xxx_clip_001.mp4 -> DJI_xxx)
        # _clip_NNN.mp4 제거
        source_name = re.sub(r'_clip_\d+\.mp4$', '', clip)
        used_sources.add(source_name)

    return used_sources


def find_matching_video(source_name: str, video_files: list) -> Optional[str]:
    """원본 비디오명과 매칭되는 실제 파일 찾기"""
    for video in video_files:
        video_stem = Path(video).stem
        if video_stem == source_name:
            return video
    return None


def organize_videos(videos_dir: str, html_path: str, dry_run: bool = False):
    """비디오 파일들을 used/unused 폴더로 분류"""
    videos_path = Path(videos_dir)

    # 비디오 파일 목록
    video_extensions = {'.mp4', '.MP4', '.mov', '.MOV', '.avi', '.mkv'}
    video_files = [
        f.name for f in videos_path.iterdir()
        if f.is_file() and f.suffix in video_extensions
    ]

    # HTML에서 사용된 원본 비디오명 추출
    used_sources = extract_used_videos_from_html(html_path)

    # 폴더 생성
    used_dir = videos_path / 'used'
    unused_dir = videos_path / 'unused'

    if not dry_run:
        used_dir.mkdir(exist_ok=True)
        unused_dir.mkdir(exist_ok=True)

    used_videos = []
    unused_videos = []

    for video in video_files:
        video_stem = Path(video).stem
        if video_stem in used_sources:
            used_videos.append(video)
            if not dry_run:
                shutil.move(videos_path / video, used_dir / video)
        else:
            unused_videos.append(video)
            if not dry_run:
                shutil.move(videos_path / video, unused_dir / video)

    # 결과 출력
    print(f"\n📁 영상 분류 완료{'(dry-run)' if dry_run else ''}")
    print(f"\n✅ used/ - 숏폼에 사용된 원본 ({len(used_videos)}개)")
    for v in sorted(used_videos):
        print(f"   - {v}")

    print(f"\n📦 unused/ - 재활용 가능 ({len(unused_videos)}개)")
    for v in sorted(unused_videos):
        print(f"   - {v}")


def main():
    parser = argparse.ArgumentParser(
        description='원본 비디오를 사용 여부에 따라 분류'
    )
    parser.add_argument(
        '-v', '--videos',
        default='input/videos',
        help='비디오 폴더 경로 (기본: input/videos)'
    )
    parser.add_argument(
        '-c', '--composition',
        default='hyperframes/index.html',
        help='컴포지션 HTML 경로 (기본: hyperframes/index.html)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 이동 없이 결과만 표시'
    )

    args = parser.parse_args()

    if not os.path.exists(args.videos):
        print(f"❌ 비디오 폴더를 찾을 수 없습니다: {args.videos}")
        return 1

    if not os.path.exists(args.composition):
        print(f"❌ 컴포지션 파일을 찾을 수 없습니다: {args.composition}")
        return 1

    organize_videos(args.videos, args.composition, args.dry_run)
    return 0


if __name__ == '__main__':
    exit(main())
