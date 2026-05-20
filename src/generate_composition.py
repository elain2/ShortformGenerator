#!/usr/bin/env python3
"""
HyperFrames 컴포지션 생성기
클립과 자막을 조합하여 index.html 생성
CSS 애니메이션 기반 자막 렌더링 지원

스마트 매칭 기능 (--smart-match):
  - Gemini API를 사용하여 영상 썸네일과 자막 내용을 분석
  - 맥락이 맞는 클립을 자막 시간대에 배치
"""

import json
import os
import subprocess
import base64
import tempfile
from pathlib import Path


def extract_thumbnail(video_path: str, output_path: str = None) -> str:
    """비디오에서 첫 프레임 썸네일 추출"""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.jpg')

    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vframes', '1', '-q:v', '2',
        '-vf', 'scale=320:-1',
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path


def image_to_base64(image_path: str) -> str:
    """이미지를 base64로 인코딩"""
    with open(image_path, 'rb') as f:
        return base64.standard_b64encode(f.read()).decode('utf-8')


def analyze_clips_with_gemini(clips: list, subtitles: list, clips_dir: str) -> dict:
    """Gemini API로 클립과 자막 매칭 분석"""
    try:
        import google.generativeai as genai
    except ImportError:
        print("  [스마트 매칭] google-generativeai 패키지가 필요합니다.")
        print("  설치: pip install google-generativeai")
        return {}

    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("  [스마트 매칭] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        return {}

    genai.configure(api_key=api_key)

    print("  [스마트 매칭] 클립 썸네일 추출 중...")

    # 썸네일 추출
    clip_infos = []
    temp_files = []

    for i, clip in enumerate(clips):
        video_path = os.path.join(clips_dir, clip['filename'])
        if not os.path.exists(video_path):
            video_path = clip.get('full_path', video_path)

        thumb_path = extract_thumbnail(video_path)
        temp_files.append(thumb_path)
        clip_infos.append({
            'index': i,
            'filename': clip['filename'],
            'thumbnail_path': thumb_path,
            'duration': clip['duration']
        })

    # 자막 텍스트 수집
    subtitle_texts = [f"자막 {i}: {sub.get('text', '')}" for i, sub in enumerate(subtitles)]

    print("  [스마트 매칭] Gemini 분석 중...")

    # 이미지와 프롬프트 구성
    contents = []
    for info in clip_infos:
        img_data = image_to_base64(info['thumbnail_path'])
        contents.append({'mime_type': 'image/jpeg', 'data': img_data})

    prompt = f"""다음은 영상 클립들의 썸네일(순서대로 클립 0, 1, 2...)과 자막 목록입니다.

자막 목록:
{chr(10).join(subtitle_texts)}

자막의 내러티브 흐름에 맞게 클립을 재정렬해주세요.
예) 고양이, 반려동물 관련 자막 → 고양이가 보이는 클립

모든 클립을 한 번씩 사용하여 최적의 순서를 제안해주세요.
클립은 자막 순서대로 연속 재생됩니다.

JSON 형식으로만 응답하세요:
{{"순서": [3, 0, 1, 4, 2, 5]}}

위 예시는 클립3 → 클립0 → 클립1 → 클립4 → 클립2 → 클립5 순으로 재생한다는 의미입니다."""

    contents.append(prompt)

    # 사용 가능한 모델 목록 조회
    available_models = []
    try:
        for m in genai.list_models():
            methods = m.supported_generation_methods
            method_names = [method if isinstance(method, str) else getattr(method, 'name', '') for method in methods]
            if 'generateContent' in method_names:
                model_name = m.name.replace('models/', '')
                available_models.append(model_name)

        def model_priority(name):
            if 'flash' in name and '1.5' in name: return (0, name)
            elif 'flash' in name and '2.0' in name: return (1, name)
            elif 'flash' in name: return (2, name)
            elif 'pro' in name and '1.5' in name: return (3, name)
            elif 'pro' in name: return (4, name)
            return (99, name)

        available_models.sort(key=model_priority)
        print(f"  [스마트 매칭] 사용 가능한 모델: {available_models[:3]}")
    except Exception as e:
        print(f"  [스마트 매칭] 모델 목록 조회 실패: {e}")
        return {}

    if not available_models:
        print("  [스마트 매칭] 사용 가능한 모델이 없습니다.")
        return {}

    # 모델 시도
    response_text = None
    for model_name in available_models[:5]:
        try:
            print(f"  [스마트 매칭] 모델 시도: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(contents)
            response_text = response.text.strip()
            print(f"  [스마트 매칭] 성공: {model_name}")
            break
        except Exception as e:
            print(f"  [스마트 매칭] {model_name} 실패: {str(e)[:50]}")
            continue

    # 임시 파일 정리
    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)

    if response_text is None:
        print("  [스마트 매칭] 모든 모델 시도 실패")
        return {}

    try:
        # JSON 파싱
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]

        result = json.loads(response_text)

        # 새 형식: {"순서": [3, 0, 1, 4, 2, 5]}
        if '순서' in result:
            clip_order = result['순서']
            print(f"    클립 순서: {clip_order}")
            return {'clip_order': clip_order}

        # 이전 형식 호환: {"매칭": [...]}
        sync_map = {}
        for match in result.get('매칭', []):
            sub_idx = match.get('자막')
            clip_indices = match.get('클립', [])
            if sub_idx is not None and clip_indices:
                if isinstance(clip_indices, int):
                    clip_indices = [clip_indices]
                sync_map[sub_idx] = clip_indices
                print(f"    자막 {sub_idx} ↔ 클립 {clip_indices}")
        return sync_map
    except Exception as e:
        print(f"  [스마트 매칭] JSON 파싱 실패: {e}")
        return {}


def reorder_clips_by_sync(clips: list, subtitles: list, sync_map: dict, total_duration: float) -> list:
    """클립 순서 재배치 (항상 연속 배치, 갭 없음)

    sync_map 형식:
    - 새 형식: {'clip_order': [3, 0, 1, 4, 2, 5]} - 클립 재생 순서
    - 이전 형식: {자막인덱스: [클립인덱스들]} - 자막-클립 매칭 (호환용)
    """
    if not sync_map:
        return clips

    # 새 형식: clip_order가 있으면 해당 순서로 연속 배치
    if 'clip_order' in sync_map:
        clip_order = sync_map['clip_order']
        ordered_clips = []
        current_time = 0.0
        used_indices = set()

        def add_clip_with_trim(clip_data, start_time, remaining_duration):
            """클립 추가 (필요시 트리밍)"""
            new_clip = clip_data.copy()
            new_clip['start'] = start_time

            if new_clip['duration'] > remaining_duration + 0.1:
                # 트리밍 필요
                new_clip['trim_end'] = remaining_duration
                new_clip['original_duration'] = new_clip['duration']
                new_clip['duration'] = remaining_duration
                return new_clip, remaining_duration, True  # trimmed
            return new_clip, new_clip['duration'], False  # not trimmed

        # 지정된 순서대로 클립 배치 (total_duration까지만)
        for idx in clip_order:
            if current_time >= total_duration - 0.1:
                break
            if idx < len(clips) and idx not in used_indices:
                remaining = total_duration - current_time
                clip, duration_added, trimmed = add_clip_with_trim(
                    clips[idx], current_time, remaining
                )
                ordered_clips.append(clip)
                current_time += duration_added
                used_indices.add(idx)
                if trimmed:
                    break

        # 사용되지 않은 클립들 추가 (total_duration까지만)
        for idx, clip in enumerate(clips):
            if current_time >= total_duration - 0.1:
                break
            if idx not in used_indices:
                remaining = total_duration - current_time
                new_clip, duration_added, trimmed = add_clip_with_trim(
                    clip, current_time, remaining
                )
                ordered_clips.append(new_clip)
                current_time += duration_added
                if trimmed:
                    break

        # total_duration까지 채우기 (클립 순환)
        if current_time < total_duration - 0.1 and ordered_clips:
            cycle_ptr = 0
            while current_time < total_duration - 0.1:
                src_clip = ordered_clips[cycle_ptr % len(ordered_clips)]
                remaining = total_duration - current_time
                new_clip, duration_added, trimmed = add_clip_with_trim(
                    src_clip, current_time, remaining
                )
                ordered_clips.append(new_clip)
                current_time += duration_added
                if trimmed:
                    break
                cycle_ptr += 1

        # 디버그 출력
        print("  [스마트 매칭] 최종 클립 배치:")
        for clip in ordered_clips:
            trim_info = f" (트리밍: {clip.get('trim_end', clip['duration']):.1f}s)" if 'trim_end' in clip else ""
            print(f"    {clip['start']:.2f}s: {clip['filename']} ({clip['duration']:.2f}s){trim_info}")

        return ordered_clips

    # 이전 형식 호환: 자막-클립 매칭 → 순서 추출 후 연속 배치
    sub_times = [{'start': sub.get('start_time', 0)} for sub in subtitles]

    # 자막 시간순으로 클립 순서 결정
    sync_entries = []
    for sub_idx, clip_indices in sync_map.items():
        if sub_idx >= len(sub_times):
            continue
        target_time = sub_times[sub_idx]['start']
        for clip_idx in clip_indices:
            if clip_idx < len(clips):
                sync_entries.append((target_time, clip_idx))

    sync_entries.sort(key=lambda x: x[0])
    clip_order = [idx for _, idx in sync_entries]

    # 새 형식으로 변환하여 재귀 호출
    return reorder_clips_by_sync(clips, subtitles, {'clip_order': clip_order}, total_duration)


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
    no_subtitles: bool = False,  # 세그먼트: 자막 제외
    subtitle_scale: float = 1.0,  # 자막 표시 시간 배율 (1.5 = 50% 더 길게)
    smart_match: bool = False  # Gemini로 자막-클립 스마트 매칭
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

    # 자막 표시 시간 배율 적용
    if subtitle_scale != 1.0 and subtitles:
        print(f"자막 표시 시간 배율: {subtitle_scale}x")
        scaled_subtitles = []
        for sub in subtitles:
            start_time = sub.get('start_time', sub.get('startTime', 0))
            end_time = sub.get('end_time', sub.get('endTime', 0))
            duration = end_time - start_time

            # 배율 적용하여 새 end_time 계산
            new_duration = duration * subtitle_scale
            new_end_time = start_time + new_duration

            scaled_subtitles.append({
                'text': sub.get('text', ''),
                'start_time': start_time,
                'end_time': new_end_time
            })
        subtitles = scaled_subtitles

        # 자막이 겹치지 않도록 조정 (다음 자막 시작 전에 끝나도록)
        for i in range(len(subtitles) - 1):
            if subtitles[i]['end_time'] > subtitles[i + 1]['start_time']:
                subtitles[i]['end_time'] = subtitles[i + 1]['start_time'] - 0.1

        # 마지막 자막이 total_duration을 넘지 않도록
        if subtitles and subtitles[-1]['end_time'] > total_duration:
            subtitles[-1]['end_time'] = total_duration

    # 스마트 매칭: Gemini로 클립-자막 맥락 매칭
    if smart_match and subtitles and clips:
        print("\n[스마트 매칭] 클립과 자막 맥락 분석 시작...")
        sync_map = analyze_clips_with_gemini(clips, subtitles, clips_dir)
        if sync_map:
            print(f"[스마트 매칭] {len(sync_map)}개 자막-클립 매칭 발견")
            clips = reorder_clips_by_sync(clips, subtitles, sync_map, total_duration)
            print("[스마트 매칭] 클립 순서 재배치 완료")
        else:
            print("[스마트 매칭] 매칭 결과 없음, 기본 순서 유지")

    # 비디오 요소 HTML 생성
    video_elements = []
    for i, clip in enumerate(clips):
        # 트리밍 정보가 있으면 data-duration 속성 추가
        duration_attr = ""
        if 'trim_end' in clip:
            duration_attr = f'\n               data-duration="{clip["trim_end"]:.3f}"'

        video_html = f'''        <video id="clip-{i}"
               class="clip"
               src="{clip['path']}"
               data-component="video"
               data-start="{clip['start']:.3f}"{duration_attr}
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
    <!-- HyperFrames Timeline 즉시 등록 (lint 요구사항) -->
    <script>
        window.__timelines = window.__timelines || {{}};
        window.__timelines['shorts-main'] = {{
            duration: {total_duration:.3f},
            seek: function(t) {{ if(window.shortsComposition) window.shortsComposition.seek(t); }},
            play: function() {{ if(window.shortsComposition) window.shortsComposition.play(); }},
            pause: function() {{ if(window.shortsComposition) window.shortsComposition.pause(); }}
        }};
    </script>
</head>
<body>
    <!-- HyperFrames 루트 컴포지션 (data-start 제거: 중첩 미디어 문제 방지) -->
    <div id="composition-root"
         data-composition-id="shorts-main"
         data-width="1080"
         data-height="1920"
         data-fps="30"
         data-duration="{total_duration:.3f}">

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
    parser.add_argument('--subtitle-scale', type=float, default=1.0,
                        help='자막 표시 시간 배율 (1.5 = 50%% 더 길게, 2.0 = 2배)')
    parser.add_argument('--smart-match', action='store_true',
                        help='Gemini API로 자막-클립 맥락 스마트 매칭 (GEMINI_API_KEY 필요)')

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
        no_subtitles=args.no_subtitles,
        subtitle_scale=args.subtitle_scale,
        smart_match=args.smart_match
    )


if __name__ == '__main__':
    main()
