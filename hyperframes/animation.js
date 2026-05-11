/**
 * HyperFrames Animation Controller
 * GSAP 기반 자막 및 비디오 애니메이션
 */

class ShortsComposition {
    constructor() {
        this.video = document.getElementById('main-video');
        this.subtitleText = document.getElementById('subtitle-text');
        this.bgm = document.getElementById('bgm');

        this.clips = [];
        this.subtitles = [];
        this.currentClipIndex = 0;
        this.currentSubtitleIndex = 0;
        this.timeline = null;

        this.settings = {
            bgmVolume: 0.3,
            subtitleFadeIn: 0.3,
            subtitleFadeOut: 0.2,
            subtitleHold: 0.1  // fade out 전 유지 시간
        };

        this.init();
    }

    async init() {
        // 컴포지션 데이터 로드
        await this.loadCompositionData();

        // 타임라인 생성
        this.createTimeline();

        // 이벤트 리스너
        this.setupEventListeners();

        console.log('Shorts composition initialized');
    }

    async loadCompositionData() {
        // JSON 데이터 로드 시도
        const dataElement = document.getElementById('composition-data');
        if (dataElement) {
            try {
                const data = JSON.parse(dataElement.textContent);
                this.clips = data.clips || [];
                this.subtitles = data.subtitles || [];
                this.settings.bgmVolume = data.bgm?.volume || 0.3;
            } catch (e) {
                console.warn('컴포지션 데이터 파싱 실패:', e);
            }
        }

        // 외부 subtitles.json 로드 시도
        try {
            const response = await fetch('../output/subtitles.json');
            if (response.ok) {
                const subtitleData = await response.json();
                this.subtitles = subtitleData.subtitles || [];
                console.log(`${this.subtitles.length}개 자막 로드됨`);
            }
        } catch (e) {
            console.log('외부 자막 파일 없음, 내장 데이터 사용');
        }
    }

    createTimeline() {
        // GSAP 타임라인 생성
        this.timeline = gsap.timeline({
            paused: true,
            onUpdate: () => this.onTimelineUpdate(),
            onComplete: () => this.onTimelineComplete()
        });

        // 자막 애니메이션 추가
        this.subtitles.forEach((subtitle, index) => {
            const startTime = subtitle.start_time || subtitle.startTime;
            const endTime = subtitle.end_time || subtitle.endTime;
            const duration = endTime - startTime;

            // Fade In
            this.timeline.add(() => {
                this.showSubtitle(subtitle.text);
            }, startTime);

            // Fade Out
            this.timeline.add(() => {
                this.hideSubtitle();
            }, endTime - this.settings.subtitleFadeOut);
        });
    }

    showSubtitle(text) {
        // 텍스트 길이에 따른 클래스 조정
        this.subtitleText.classList.remove('long-text', 'very-long-text');
        if (text.length > 25) {
            this.subtitleText.classList.add('very-long-text');
        } else if (text.length > 18) {
            this.subtitleText.classList.add('long-text');
        }

        // 텍스트 설정
        this.subtitleText.textContent = text;

        // GSAP 애니메이션
        gsap.killTweensOf(this.subtitleText);
        gsap.fromTo(this.subtitleText,
            {
                opacity: 0,
                y: 10
            },
            {
                opacity: 1,
                y: 0,
                duration: this.settings.subtitleFadeIn,
                ease: 'power2.out'
            }
        );
    }

    hideSubtitle() {
        gsap.to(this.subtitleText, {
            opacity: 0,
            y: -10,
            duration: this.settings.subtitleFadeOut,
            ease: 'power2.in'
        });
    }

    setupEventListeners() {
        // 비디오 로드 완료
        this.video.addEventListener('loadedmetadata', () => {
            console.log('비디오 로드됨:', this.video.duration + '초');
        });

        // 비디오 재생 동기화
        this.video.addEventListener('timeupdate', () => {
            this.syncSubtitles(this.video.currentTime);
        });

        // 키보드 컨트롤 (개발용)
        document.addEventListener('keydown', (e) => {
            switch(e.key) {
                case ' ':
                    this.togglePlay();
                    break;
                case 'r':
                    this.restart();
                    break;
            }
        });
    }

    syncSubtitles(currentTime) {
        // 현재 시간에 해당하는 자막 찾기
        const activeSubtitle = this.subtitles.find(sub => {
            const start = sub.start_time || sub.startTime;
            const end = sub.end_time || sub.endTime;
            return currentTime >= start && currentTime < end;
        });

        if (activeSubtitle) {
            if (this.subtitleText.textContent !== activeSubtitle.text) {
                this.showSubtitle(activeSubtitle.text);
            }
        } else if (this.subtitleText.style.opacity !== '0') {
            this.hideSubtitle();
        }
    }

    onTimelineUpdate() {
        // 타임라인 업데이트 콜백
    }

    onTimelineComplete() {
        console.log('재생 완료');
    }

    // 재생 컨트롤
    play() {
        this.video.play();
        this.bgm.volume = this.settings.bgmVolume;
        this.bgm.play();
        this.timeline.play();
    }

    pause() {
        this.video.pause();
        this.bgm.pause();
        this.timeline.pause();
    }

    togglePlay() {
        if (this.video.paused) {
            this.play();
        } else {
            this.pause();
        }
    }

    restart() {
        this.video.currentTime = 0;
        this.bgm.currentTime = 0;
        this.timeline.restart();
    }

    seek(time) {
        this.video.currentTime = time;
        this.bgm.currentTime = time;
        this.timeline.seek(time);
        this.syncSubtitles(time);
    }

    // 클립 전환 (다중 클립 지원)
    loadClip(clipPath) {
        return new Promise((resolve, reject) => {
            this.video.src = clipPath;
            this.video.load();
            this.video.onloadedmetadata = () => resolve();
            this.video.onerror = () => reject(new Error('클립 로드 실패'));
        });
    }

    async playClipsSequentially() {
        for (let i = 0; i < this.clips.length; i++) {
            const clip = this.clips[i];
            await this.loadClip(clip.path || clip.src);

            await new Promise((resolve) => {
                this.video.onended = resolve;
                this.video.play();
            });
        }
    }

    // HyperFrames 렌더링용 API
    getState(time) {
        const activeSubtitle = this.subtitles.find(sub => {
            const start = sub.start_time || sub.startTime;
            const end = sub.end_time || sub.endTime;
            return time >= start && time < end;
        });

        return {
            time,
            subtitle: activeSubtitle ? activeSubtitle.text : null,
            clipIndex: this.currentClipIndex
        };
    }

    // 자막 데이터 업데이트
    updateSubtitles(subtitles) {
        this.subtitles = subtitles;
        this.createTimeline();
    }

    // 설정 업데이트
    updateSettings(settings) {
        Object.assign(this.settings, settings);
        if (settings.bgmVolume !== undefined) {
            this.bgm.volume = settings.bgmVolume;
        }
    }
}

// 전역 인스턴스
let composition;

// DOM 로드 후 초기화
document.addEventListener('DOMContentLoaded', () => {
    composition = new ShortsComposition();

    // 전역 접근용
    window.shortsComposition = composition;
});

// HyperFrames 렌더링 API
window.HyperFramesAPI = {
    getComposition: () => composition,
    seek: (time) => composition?.seek(time),
    getState: (time) => composition?.getState(time),
    updateSubtitles: (data) => composition?.updateSubtitles(data)
};
