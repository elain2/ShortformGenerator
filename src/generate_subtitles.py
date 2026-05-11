#!/usr/bin/env python3
"""
자막 타이밍 생성 모듈
한글 스크립트를 기반으로 자막 타이밍 JSON 생성
"""

import json
import re
import os
from typing import List, Tuple
from dataclasses import dataclass, asdict


@dataclass
class SubtitleEntry:
    """자막 항목"""
    id: int
    text: str
    start_time: float
    end_time: float
    duration: float
    syllable_count: int


class SubtitleGenerator:
    """자막 타이밍 생성기"""

    # 한글 유니코드 범위 (AC00-D7A3: 완성형 한글)
    HANGUL_START = 0xAC00
    HANGUL_END = 0xD7A3

    # 기본 더빙 속도 (음절/초)
    DEFAULT_SYLLABLE_RATE = 3.5

    # 자막 간 간격 (초)
    SUBTITLE_GAP = 0.1

    def __init__(self, config_path: str = "input/config.json"):
        self.config = self._load_config(config_path)
        self.syllable_rate = self.config.get("syllable_rate", self.DEFAULT_SYLLABLE_RATE)
        self.min_duration = self.config.get("min_subtitle_duration", 1.0)
        self.max_duration = self.config.get("max_subtitle_duration", 5.0)
        self.max_chars_per_line = self.config.get("max_chars_per_line", 20)

    def _load_config(self, config_path: str) -> dict:
        """설정 파일 로드"""
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def count_korean_syllables(self, text: str) -> int:
        """한글 음절 수 계산"""
        count = 0
        for char in text:
            code = ord(char)
            if self.HANGUL_START <= code <= self.HANGUL_END:
                count += 1
            elif char.isalpha():
                # 영문은 2글자당 1음절로 계산
                count += 0.5
            elif char.isdigit():
                # 숫자는 각각 1음절로 계산
                count += 1
        return max(1, int(count))

    def parse_script(self, script_text: str) -> List[str]:
        """스크립트 텍스트를 문장 단위로 분리"""
        # 줄바꿈으로 분리
        lines = script_text.strip().split('\n')

        sentences = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 문장 부호로 분리 (. ! ? 기준)
            parts = re.split(r'([.!?]+)', line)

            current = ""
            for i, part in enumerate(parts):
                if re.match(r'^[.!?]+$', part):
                    # 문장 부호는 이전 텍스트에 붙임
                    current += part
                    if current.strip():
                        sentences.append(current.strip())
                    current = ""
                else:
                    current = part

            # 남은 텍스트
            if current.strip():
                sentences.append(current.strip())

        return sentences

    def split_long_sentence(self, sentence: str) -> List[str]:
        """긴 문장을 적절한 길이로 분리"""
        if len(sentence) <= self.max_chars_per_line:
            return [sentence]

        # 쉼표, 조사 위치에서 분리 시도
        split_patterns = [
            r',\s*',           # 쉼표
            r'\s+(?=그리고|그러나|하지만|그래서|그런데)',  # 접속어 앞
            r'(?<=[을를이가은는])\s+',  # 조사 뒤
        ]

        parts = [sentence]
        for pattern in split_patterns:
            new_parts = []
            for part in parts:
                if len(part) > self.max_chars_per_line:
                    split = re.split(pattern, part, maxsplit=1)
                    new_parts.extend([s.strip() for s in split if s.strip()])
                else:
                    new_parts.append(part)
            parts = new_parts

        # 여전히 긴 경우 강제 분리
        final_parts = []
        for part in parts:
            while len(part) > self.max_chars_per_line:
                # 단어 경계에서 분리
                split_pos = self.max_chars_per_line
                for i in range(self.max_chars_per_line, max(0, self.max_chars_per_line - 5), -1):
                    if part[i] == ' ':
                        split_pos = i
                        break
                final_parts.append(part[:split_pos].strip())
                part = part[split_pos:].strip()
            if part:
                final_parts.append(part)

        return final_parts

    def calculate_timing(self, text: str, start_time: float) -> Tuple[float, float]:
        """텍스트의 타이밍 계산"""
        syllables = self.count_korean_syllables(text)
        duration = syllables / self.syllable_rate

        # 최소/최대 제한 적용
        duration = max(self.min_duration, min(self.max_duration, duration))

        end_time = start_time + duration
        return duration, end_time

    def generate_subtitles(self, script_text: str, start_offset: float = 0.0) -> List[SubtitleEntry]:
        """스크립트에서 자막 타이밍 생성"""
        sentences = self.parse_script(script_text)

        subtitles = []
        current_time = start_offset
        subtitle_id = 1

        for sentence in sentences:
            # 긴 문장 분리
            parts = self.split_long_sentence(sentence)

            for text in parts:
                syllables = self.count_korean_syllables(text)
                duration, end_time = self.calculate_timing(text, current_time)

                entry = SubtitleEntry(
                    id=subtitle_id,
                    text=text,
                    start_time=round(current_time, 3),
                    end_time=round(end_time, 3),
                    duration=round(duration, 3),
                    syllable_count=syllables
                )
                subtitles.append(entry)

                current_time = end_time + self.SUBTITLE_GAP
                subtitle_id += 1

        return subtitles

    def generate_from_file(self, script_path: str, output_path: str = None,
                          start_offset: float = 0.0) -> dict:
        """파일에서 자막 생성"""
        with open(script_path, 'r', encoding='utf-8') as f:
            script_text = f.read()

        subtitles = self.generate_subtitles(script_text, start_offset)

        # 결과 구성
        result = {
            'source': script_path,
            'settings': {
                'syllable_rate': self.syllable_rate,
                'min_duration': self.min_duration,
                'max_duration': self.max_duration
            },
            'subtitles': [asdict(s) for s in subtitles],
            'total_count': len(subtitles),
            'total_duration': subtitles[-1].end_time if subtitles else 0
        }

        # 파일 저장
        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"자막 저장됨: {output_path}")

        return result

    def to_hyperframes_format(self, subtitles: List[SubtitleEntry]) -> List[dict]:
        """HyperFrames 애니메이션용 포맷으로 변환"""
        return [
            {
                'text': s.text,
                'startTime': s.start_time,
                'endTime': s.end_time,
                'duration': s.duration
            }
            for s in subtitles
        ]


def main():
    """메인 실행"""
    import argparse

    parser = argparse.ArgumentParser(description='자막 타이밍 생성')
    parser.add_argument('input', nargs='?', default='input/script.txt',
                        help='입력 스크립트 파일')
    parser.add_argument('-o', '--output', default='output/subtitles.json',
                        help='출력 JSON 파일')
    parser.add_argument('-c', '--config', default='input/config.json',
                        help='설정 파일 경로')
    parser.add_argument('--offset', type=float, default=0.0,
                        help='시작 시간 오프셋 (초)')
    parser.add_argument('--rate', type=float, default=None,
                        help='음절/초 속도 (기본: 3.5)')
    args = parser.parse_args()

    generator = SubtitleGenerator(args.config)

    # 커맨드라인 옵션으로 속도 재정의
    if args.rate:
        generator.syllable_rate = args.rate

    # 입력 파일 확인
    if not os.path.exists(args.input):
        print(f"스크립트 파일을 찾을 수 없습니다: {args.input}")
        # 샘플 스크립트 생성
        sample_script = """오늘은 정말 좋은 날이에요.
여행을 떠나볼까요?
함께 아름다운 풍경을 감상해봐요."""

        os.makedirs(os.path.dirname(args.input) or '.', exist_ok=True)
        with open(args.input, 'w', encoding='utf-8') as f:
            f.write(sample_script)
        print(f"샘플 스크립트 생성됨: {args.input}")

    # 자막 생성
    result = generator.generate_from_file(args.input, args.output, args.offset)

    print(f"\n자막 생성 완료!")
    print(f"  - 총 {result['total_count']}개 자막")
    print(f"  - 총 길이: {result['total_duration']:.1f}초")
    print(f"  - 음절 속도: {result['settings']['syllable_rate']}음절/초")


if __name__ == '__main__':
    main()
