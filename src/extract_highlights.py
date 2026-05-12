#!/usr/bin/env python3
"""
하이라이트 추출 모듈
비디오에서 시각적으로 흥미로운 구간을 자동 감지하여 클립으로 추출
"""

import cv2
import numpy as np
import subprocess
import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class HighlightSegment:
    """하이라이트 구간 정보"""
    start_time: float
    end_time: float
    score: float
    motion_score: float
    color_score: float
    subject_score: float


class HighlightExtractor:
    """비디오에서 하이라이트 구간을 추출하는 클래스"""

    # 분석 설정 (9:16 세로 비율)
    ANALYSIS_WIDTH = 180
    ANALYSIS_HEIGHT = 320
    ANALYSIS_FPS = 2

    # 스코어링 가중치
    MOTION_WEIGHT = 0.40
    COLOR_WEIGHT = 0.35
    SUBJECT_WEIGHT = 0.25

    # 출력 설정
    OUTPUT_WIDTH = 1080
    OUTPUT_HEIGHT = 1920

    def __init__(self, config_path: str = "input/config.json"):
        self.config = self._load_config(config_path)
        self.min_clip_duration = self.config.get("min_clip_duration", 3.0)
        self.max_clip_duration = self.config.get("max_clip_duration", 15.0)
        self.highlight_threshold = self.config.get("highlight_threshold", 0.5)
        self._is_landscape = False  # 현재 처리 중인 영상의 가로/세로 여부

    def _load_config(self, config_path: str) -> dict:
        """설정 파일 로드"""
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _rotate_to_portrait(self, frame: np.ndarray) -> np.ndarray:
        """16:9 가로 영상을 90도 회전하여 세로로 변환"""
        h, w = frame.shape[:2]

        # 이미 세로 영상이면 그대로 반환
        if h >= w:
            return frame

        # 시계방향 90도 회전
        rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        return rotated

    def analyze_video(self, video_path: str) -> List[HighlightSegment]:
        """비디오 분석하여 하이라이트 구간 탐지"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"비디오를 열 수 없습니다: {video_path}")

        original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / original_fps

        # 가로/세로 영상 판별
        self._is_landscape = original_width > original_height
        aspect_info = "16:9 가로 → 90도 회전" if self._is_landscape else "세로 영상"

        print(f"비디오 분석 중: {video_path}")
        print(f"  - 해상도: {original_width}x{original_height} ({aspect_info})")
        print(f"  - 길이: {duration:.1f}초, FPS: {original_fps:.1f}")

        # 분석용 프레임 샘플링 간격
        frame_interval = int(original_fps / self.ANALYSIS_FPS)

        prev_frame = None
        frame_scores = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 샘플링 간격에 맞는 프레임만 분석
            if frame_idx % frame_interval == 0:
                # 가로 영상이면 90도 회전 후 분석
                converted_frame = self._rotate_to_portrait(frame)

                # 분석용 해상도로 리사이즈
                small_frame = cv2.resize(converted_frame, (self.ANALYSIS_WIDTH, self.ANALYSIS_HEIGHT))

                # 각 스코어 계산
                motion = self._calc_motion_score(small_frame, prev_frame)
                color = self._calc_color_score(small_frame)
                subject = self._calc_subject_score(small_frame)

                # 가중 평균 스코어
                total_score = (
                    motion * self.MOTION_WEIGHT +
                    color * self.COLOR_WEIGHT +
                    subject * self.SUBJECT_WEIGHT
                )

                timestamp = frame_idx / original_fps
                frame_scores.append({
                    'time': timestamp,
                    'total': total_score,
                    'motion': motion,
                    'color': color,
                    'subject': subject
                })

                prev_frame = small_frame.copy()

            frame_idx += 1

        cap.release()

        # 하이라이트 구간 추출
        highlights = self._extract_highlight_segments(frame_scores)
        print(f"  - {len(highlights)}개 하이라이트 구간 탐지됨")

        return highlights

    def _calc_motion_score(self, frame: np.ndarray, prev_frame: np.ndarray) -> float:
        """움직임 스코어 계산 (프레임 간 차이)"""
        if prev_frame is None:
            return 0.0

        # 그레이스케일 변환
        gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 프레임 차이 계산
        diff = cv2.absdiff(gray1, gray2)
        motion = np.mean(diff) / 255.0

        # 0~1 범위로 정규화 (적당한 움직임이 최고점)
        # 너무 많은 움직임은 흔들림일 수 있음
        if motion < 0.02:
            return motion * 10  # 적은 움직임: 낮은 점수
        elif motion < 0.15:
            return 0.2 + (motion - 0.02) * 6  # 적당한 움직임: 높은 점수
        else:
            return max(0.3, 1.0 - (motion - 0.15) * 3)  # 과한 움직임: 감점

    def _calc_color_score(self, frame: np.ndarray) -> float:
        """색감 스코어 계산 (채도와 밝기 기반)"""
        # HSV 변환
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 채도 분석
        saturation = hsv[:, :, 1]
        avg_saturation = np.mean(saturation) / 255.0

        # 밝기 분석 (너무 어둡거나 밝지 않은 것이 좋음)
        value = hsv[:, :, 2]
        avg_value = np.mean(value) / 255.0

        # 밝기 스코어: 0.3~0.7 범위가 최적
        if 0.3 <= avg_value <= 0.7:
            brightness_score = 1.0
        else:
            dist = min(abs(avg_value - 0.3), abs(avg_value - 0.7))
            brightness_score = max(0.3, 1.0 - dist * 2)

        # 색감 다양성 (히스토그램 분산)
        hue = hsv[:, :, 0]
        hue_std = np.std(hue) / 180.0

        # 종합 색감 스코어
        color_score = (avg_saturation * 0.4 + brightness_score * 0.4 + hue_std * 0.2)
        return min(1.0, color_score)

    def _calc_subject_score(self, frame: np.ndarray) -> float:
        """피사체 스코어 계산 (중앙 집중도, 에지 밀도)"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 에지 검출
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.mean(edges) / 255.0

        # 중앙 영역 가중치
        h, w = gray.shape
        center_region = edges[h//4:3*h//4, w//4:3*w//4]
        center_density = np.mean(center_region) / 255.0

        # 중앙 집중도
        center_ratio = center_density / (edge_density + 0.01)
        center_score = min(1.0, center_ratio * 0.5)

        # 적당한 에지 밀도가 좋음
        if 0.05 <= edge_density <= 0.3:
            edge_score = 1.0
        else:
            edge_score = max(0.3, 1.0 - abs(edge_density - 0.15) * 3)

        return edge_score * 0.6 + center_score * 0.4

    def _extract_highlight_segments(self, frame_scores: List[dict]) -> List[HighlightSegment]:
        """프레임 스코어에서 하이라이트 구간 추출"""
        if not frame_scores:
            return []

        # 스코어 정규화
        scores = [f['total'] for f in frame_scores]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score > min_score else 1.0

        normalized_scores = [(s - min_score) / score_range for s in scores]

        # 임계값 이상인 구간 찾기
        highlights = []
        in_highlight = False
        start_idx = 0

        for i, norm_score in enumerate(normalized_scores):
            if norm_score >= self.highlight_threshold and not in_highlight:
                in_highlight = True
                start_idx = i
            elif norm_score < self.highlight_threshold and in_highlight:
                in_highlight = False
                # 구간 생성
                segment = self._create_segment(frame_scores, start_idx, i)
                if segment:
                    highlights.append(segment)

        # 마지막 구간 처리
        if in_highlight:
            segment = self._create_segment(frame_scores, start_idx, len(frame_scores) - 1)
            if segment:
                highlights.append(segment)

        # 구간 병합 및 필터링
        highlights = self._merge_nearby_segments(highlights)
        highlights = self._filter_by_duration(highlights)

        # 스코어 순 정렬
        highlights.sort(key=lambda x: x.score, reverse=True)

        return highlights

    def _create_segment(self, frame_scores: List[dict], start_idx: int, end_idx: int) -> HighlightSegment:
        """구간 정보 생성"""
        if end_idx <= start_idx:
            return None

        segment_scores = frame_scores[start_idx:end_idx + 1]

        return HighlightSegment(
            start_time=segment_scores[0]['time'],
            end_time=segment_scores[-1]['time'],
            score=np.mean([s['total'] for s in segment_scores]),
            motion_score=np.mean([s['motion'] for s in segment_scores]),
            color_score=np.mean([s['color'] for s in segment_scores]),
            subject_score=np.mean([s['subject'] for s in segment_scores])
        )

    def _merge_nearby_segments(self, segments: List[HighlightSegment], gap_threshold: float = 1.0) -> List[HighlightSegment]:
        """인접한 구간 병합"""
        if len(segments) <= 1:
            return segments

        # 시간순 정렬
        segments.sort(key=lambda x: x.start_time)

        merged = [segments[0]]
        for seg in segments[1:]:
            last = merged[-1]
            if seg.start_time - last.end_time <= gap_threshold:
                # 병합
                merged[-1] = HighlightSegment(
                    start_time=last.start_time,
                    end_time=seg.end_time,
                    score=(last.score + seg.score) / 2,
                    motion_score=(last.motion_score + seg.motion_score) / 2,
                    color_score=(last.color_score + seg.color_score) / 2,
                    subject_score=(last.subject_score + seg.subject_score) / 2
                )
            else:
                merged.append(seg)

        return merged

    def _filter_by_duration(self, segments: List[HighlightSegment]) -> List[HighlightSegment]:
        """길이 기준 필터링"""
        filtered = []
        for seg in segments:
            duration = seg.end_time - seg.start_time
            if duration >= self.min_clip_duration:
                if duration > self.max_clip_duration:
                    # 최대 길이로 자르기 (중앙 기준)
                    center = (seg.start_time + seg.end_time) / 2
                    seg = HighlightSegment(
                        start_time=center - self.max_clip_duration / 2,
                        end_time=center + self.max_clip_duration / 2,
                        score=seg.score,
                        motion_score=seg.motion_score,
                        color_score=seg.color_score,
                        subject_score=seg.subject_score
                    )
                filtered.append(seg)
        return filtered

    def extract_clip(self, video_path: str, segment: HighlightSegment, output_path: str, is_landscape: bool = False) -> bool:
        """FFmpeg로 클립 추출 (9:16 세로, 무음)"""
        if is_landscape:
            # 가로 영상: 시계방향 90도 회전 후 스케일
            filter_complex = (
                f"transpose=1,scale={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT},"
                f"setsar=1:1"
            )
        else:
            # 세로 영상: 스케일만 적용
            filter_complex = (
                f"scale={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT},"
                f"setsar=1:1"
            )

        cmd = [
            'ffmpeg', '-y',
            '-ss', str(segment.start_time),
            '-i', video_path,
            '-t', str(segment.end_time - segment.start_time),
            '-vf', filter_complex,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-an',  # 무음
            '-movflags', '+faststart',
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"FFmpeg 오류: {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"클립 추출 실패: {e}")
            return False

    def process_video(self, video_path: str, output_dir: str = "output/highlights") -> dict:
        """비디오 처리 전체 파이프라인"""
        os.makedirs(output_dir, exist_ok=True)

        video_name = Path(video_path).stem

        # 하이라이트 분석
        highlights = self.analyze_video(video_path)

        # 클립 추출
        clips = []
        for i, segment in enumerate(highlights):
            clip_filename = f"{video_name}_clip_{i+1:03d}.mp4"
            clip_path = os.path.join(output_dir, clip_filename)

            print(f"클립 추출 중: {clip_filename} ({segment.start_time:.1f}s - {segment.end_time:.1f}s)")

            if self.extract_clip(video_path, segment, clip_path, self._is_landscape):
                clips.append({
                    'filename': clip_filename,
                    'path': clip_path,
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'duration': segment.end_time - segment.start_time,
                    'score': segment.score,
                    'scores': {
                        'motion': segment.motion_score,
                        'color': segment.color_score,
                        'subject': segment.subject_score
                    }
                })

        return {
            'source_video': video_path,
            'video_name': video_name,
            'clips': clips,
            'total_clips': len(clips)
        }


def main():
    """메인 실행"""
    import argparse

    parser = argparse.ArgumentParser(description='비디오 하이라이트 추출')
    parser.add_argument('input', nargs='?', default='input/videos',
                        help='입력 비디오 파일 또는 폴더')
    parser.add_argument('-o', '--output', default='output/highlights',
                        help='출력 폴더')
    parser.add_argument('-c', '--config', default='input/config.json',
                        help='설정 파일 경로')
    parser.add_argument('--manifest', default='output/highlights_manifest.json',
                        help='매니페스트 출력 경로')
    args = parser.parse_args()

    extractor = HighlightExtractor(args.config)

    # 입력 처리
    input_path = Path(args.input)
    video_files = []

    if input_path.is_file():
        video_files = [str(input_path)]
    elif input_path.is_dir():
        video_files = [
            str(f) for f in input_path.glob('*')
            if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']
        ]

    if not video_files:
        print("처리할 비디오 파일이 없습니다.")
        return

    # 전체 결과
    manifest = {
        'videos': [],
        'total_clips': 0
    }

    for video_path in video_files:
        print(f"\n{'='*50}")
        result = extractor.process_video(video_path, args.output)
        manifest['videos'].append(result)
        manifest['total_clips'] += result['total_clips']

    # 매니페스트 저장
    os.makedirs(os.path.dirname(args.manifest) or '.', exist_ok=True)
    with open(args.manifest, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"완료! 총 {manifest['total_clips']}개 클립 추출됨")
    print(f"매니페스트: {args.manifest}")


if __name__ == '__main__':
    main()
