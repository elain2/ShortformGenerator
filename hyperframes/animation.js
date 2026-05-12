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

        this.settings = {
            bgmVolume: 0.3,
            subtitleFadeIn: 0.3,
            subtitleFadeOut: 0.2
        };

        this.init();
    }

    async init() {
        await this.loadSubtitles();
        this.setupVideoLayers();
        this.registerTimeline();
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
        // 각 비디오의 z-index 설정 (나중 클립이 위로)
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

        console.log(`Timeline registered: ${compositionId}`);
    }

    seek(time) {
        // 현재 시간에 맞는 자막 표시
        this.syncSubtitles(time);
    }

    syncSubtitles(currentTime) {
        const activeSubtitle = this.subtitles.find(sub => {
            const start = sub.start_time || sub.startTime || 0;
            const end = sub.end_time || sub.endTime || 0;
            return currentTime >= start && currentTime < end;
        });

        if (activeSubtitle) {
            this.showSubtitle(activeSubtitle.text);
        } else {
            this.hideSubtitle();
        }
    }

    showSubtitle(text) {
        if (this.subtitleText.textContent === text) return;

        // 텍스트 길이에 따른 스타일
        this.subtitleText.classList.remove('long-text', 'very-long-text');
        if (text.length > 25) {
            this.subtitleText.classList.add('very-long-text');
        } else if (text.length > 18) {
            this.subtitleText.classList.add('long-text');
        }

        this.subtitleText.textContent = text;
        this.subtitleText.style.opacity = '1';
    }

    hideSubtitle() {
        this.subtitleText.style.opacity = '0';
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
            const start = sub.start_time || sub.startTime || 0;
            const end = sub.end_time || sub.endTime || 0;
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
