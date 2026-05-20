/**
 * HyperFrames Animation Controller
 * 다중 클립 + 자막 애니메이션
 */

class ShortsComposition {
    constructor() {
        this.videos = document.querySelectorAll('#video-layer video');
        this.subtitleText = document.getElementById('subtitle-text');
        this.bgm = document.getElementById('bgm');
        this.compositionRoot = document.getElementById('composition-root');

        this.subtitles = [];
        this.duration = parseFloat(this.compositionRoot?.getAttribute('data-duration')) || 60;
        this.currentSubtitle = null;

        this.settings = {
            bgmVolume: 0.3
        };

        this.init();
    }

    async init() {
        await this.loadSubtitles();
        this.setupVideoLayers();
        this.registerTimeline();

        // 초기 상태: 자막 숨김
        if (this.subtitleText) {
            this.subtitleText.textContent = '';
        }

        console.log('Shorts composition initialized');
        console.log(`  - 비디오: ${this.videos.length}개`);
        console.log(`  - 자막: ${this.subtitles.length}개`);
        console.log(`  - 총 길이: ${this.duration}초`);
    }

    async loadSubtitles() {
        // 내장 자막 데이터 로드
        const dataElement = document.getElementById('subtitles-data');
        if (dataElement) {
            try {
                this.subtitles = JSON.parse(dataElement.textContent) || [];
                console.log(`자막 로드됨: ${this.subtitles.length}개`);
            } catch (e) {
                console.warn('자막 파싱 실패:', e);
            }
        }

        // 외부 파일 시도
        if (this.subtitles.length === 0) {
            try {
                const response = await fetch('assets/subtitles.json');
                if (response.ok) {
                    const data = await response.json();
                    this.subtitles = data.subtitles || [];
                }
            } catch (e) {
                console.log('외부 자막 파일 없음');
            }
        }
    }

    setupVideoLayers() {
        this.videos.forEach((video, index) => {
            video.style.zIndex = index + 1;
        });
    }

    registerTimeline() {
        if (!window.__timelines) {
            window.__timelines = {};
        }

        const compositionId = this.compositionRoot?.getAttribute('data-composition-id') || 'shorts-main';

        window.__timelines[compositionId] = {
            duration: this.duration,
            seek: (time) => this.seek(time),
            play: () => this.play(),
            pause: () => this.pause(),
            getState: (time) => this.getState(time)
        };

        // HyperFrames 공식 API 등록
        window.__hf = {
            duration: this.duration,
            seek: (time) => this.seek(time)
        };

        console.log(`Timeline registered: ${compositionId}`);
    }

    seek(time) {
        console.log(`[Seek] time=${time.toFixed(2)}`);
        this.syncSubtitles(time);
        this.syncCSSAnimations(time);
    }

    syncCSSAnimations(time) {
        // JavaScript로 직접 자막 visibility 제어 (HyperFrames 렌더링 호환)
        const items = document.querySelectorAll('.subtitle-item');

        items.forEach((item) => {
            // data-start, data-end 속성에서 시간 정보 읽기
            const startTime = parseFloat(item.dataset.start || 0);
            const endTime = parseFloat(item.dataset.end || 0);

            // 현재 시간이 자막 표시 구간인지 확인
            if (time >= startTime && time < endTime) {
                item.style.opacity = '1';
            } else {
                item.style.opacity = '0';
            }
        });
    }

    syncSubtitles(currentTime) {
        if (!this.subtitleText) return;

        const activeSubtitle = this.subtitles.find(sub => {
            const start = sub.start_time ?? sub.startTime ?? 0;
            const end = sub.end_time ?? sub.endTime ?? 0;
            return currentTime >= start && currentTime < end;
        });

        if (activeSubtitle) {
            // 자막 표시
            this.subtitleText.textContent = activeSubtitle.text;

            // 텍스트 길이에 따른 스타일
            const textLength = activeSubtitle.text.replace(/\n/g, '').length;
            this.subtitleText.classList.remove('long-text', 'very-long-text');
            if (textLength > 25) {
                this.subtitleText.classList.add('very-long-text');
            } else if (textLength > 18) {
                this.subtitleText.classList.add('long-text');
            }
        } else {
            // 자막 숨김
            this.subtitleText.textContent = '';
        }
    }

    play() {
        this.videos.forEach(v => v.play().catch(() => {}));
        if (this.bgm) {
            this.bgm.volume = this.settings.bgmVolume;
            this.bgm.play().catch(() => {});
        }
    }

    pause() {
        this.videos.forEach(v => v.pause());
        if (this.bgm) this.bgm.pause();
    }

    getState(time) {
        const activeSubtitle = this.subtitles.find(sub => {
            const start = sub.start_time ?? sub.startTime ?? 0;
            const end = sub.end_time ?? sub.endTime ?? 0;
            return time >= start && time < end;
        });

        return {
            time,
            subtitle: activeSubtitle ? activeSubtitle.text : null
        };
    }
}

// 초기화
let composition;
document.addEventListener('DOMContentLoaded', () => {
    composition = new ShortsComposition();
    window.shortsComposition = composition;
});

// HyperFrames API
window.HyperFramesAPI = {
    getComposition: () => composition,
    seek: (time) => composition?.seek(time),
    getState: (time) => composition?.getState(time),
    play: () => composition?.play(),
    pause: () => composition?.pause()
};
