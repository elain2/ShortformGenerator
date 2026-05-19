#!/usr/bin/env node
/**
 * 실시간 프레임 캡처 렌더러
 * 프리뷰를 실시간으로 재생하면서 프레임을 캡처하여 영상 생성
 */

const puppeteer = require('puppeteer');
const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');

// 설정
const CONFIG = {
    port: 3333,
    fps: 30,
    width: 1080,
    height: 1920,
    outputDir: 'renders',
    framesDir: 'renders/frames',
};

// 간단한 정적 파일 서버
function startStaticServer(dir, port) {
    return new Promise((resolve) => {
        const server = http.createServer((req, res) => {
            let filePath = path.join(dir, req.url === '/' ? 'index.html' : req.url);
            const ext = path.extname(filePath).toLowerCase();

            const mimeTypes = {
                '.html': 'text/html',
                '.js': 'text/javascript',
                '.css': 'text/css',
                '.json': 'application/json',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.mp4': 'video/mp4',
                '.mp3': 'audio/mpeg',
                '.webm': 'video/webm',
            };

            fs.readFile(filePath, (err, data) => {
                if (err) {
                    res.writeHead(404);
                    res.end('Not found');
                    return;
                }
                res.writeHead(200, {
                    'Content-Type': mimeTypes[ext] || 'application/octet-stream',
                    'Access-Control-Allow-Origin': '*'
                });
                res.end(data);
            });
        });

        server.listen(port, () => {
            console.log(`   정적 서버 시작: http://localhost:${port}`);
            resolve(server);
        });
    });
}

async function render() {
    console.log('=== 실시간 프레임 캡처 렌더러 ===\n');

    // 출력 폴더 생성
    if (fs.existsSync(CONFIG.framesDir)) {
        fs.rmSync(CONFIG.framesDir, { recursive: true });
    }
    fs.mkdirSync(CONFIG.framesDir, { recursive: true });
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });

    console.log('1. 정적 서버 시작...');
    const server = await startStaticServer(__dirname, CONFIG.port);
    const previewUrl = `http://localhost:${CONFIG.port}`;

    console.log('2. 브라우저 시작 (GUI 모드)...');
    const browser = await puppeteer.launch({
        headless: false,  // 실제 브라우저 창 표시
        args: [
            `--window-size=${CONFIG.width},${CONFIG.height}`,
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--autoplay-policy=no-user-gesture-required',
            '--disable-features=TranslateUI',
            '--disable-extensions',
        ],
    });

    const page = await browser.newPage();
    await page.setViewport({
        width: CONFIG.width,
        height: CONFIG.height,
        deviceScaleFactor: 1,
    });

    console.log('3. 페이지 로드...');
    await page.goto(previewUrl, {
        waitUntil: 'domcontentloaded',
        timeout: 120000
    });

    // 비디오 로딩 대기
    await page.waitForSelector('video', { timeout: 60000 });
    console.log('   비디오 요소 발견');

    // 모든 비디오가 로드될 때까지 대기
    await page.evaluate(async () => {
        const videos = document.querySelectorAll('video');
        await Promise.all(Array.from(videos).map(v => {
            return new Promise((resolve) => {
                if (v.readyState >= 2) resolve();
                else v.addEventListener('loadeddata', resolve, { once: true });
            });
        }));
    });
    console.log('   비디오 로드 완료');

    await new Promise(r => setTimeout(r, 1000)); // 추가 안정화 대기

    // 컴포지션 정보 가져오기
    const compositionInfo = await page.evaluate(() => {
        const root = document.getElementById('composition-root');
        return {
            duration: parseFloat(root?.getAttribute('data-duration')) || 60,
            fps: parseInt(root?.getAttribute('data-fps')) || 30,
        };
    });

    const duration = compositionInfo.duration;
    const fps = CONFIG.fps;
    const totalFrames = Math.ceil(duration * fps);
    const frameInterval = 1000 / fps; // ms per frame

    console.log(`   duration: ${duration}s, fps: ${fps}, totalFrames: ${totalFrames}\n`);

    console.log('4. 프레임 캡처 시작...');
    const startTime = Date.now();

    // 비디오 및 애니메이션 시작
    await page.evaluate(() => {
        // 모든 비디오 음소거 및 재생 준비
        document.querySelectorAll('video').forEach(v => {
            v.muted = true;
            v.currentTime = 0;
        });
        // BGM 음소거
        const bgm = document.getElementById('bgm');
        if (bgm) bgm.muted = true;
    });

    // 프레임별 캡처
    for (let frame = 0; frame < totalFrames; frame++) {
        const currentTime = frame / fps;

        // 진행률 표시 (10프레임마다)
        if (frame % 30 === 0) {
            const progress = ((frame / totalFrames) * 100).toFixed(1);
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
            process.stdout.write(`\r   프레임 ${frame}/${totalFrames} (${progress}%) - ${elapsed}s 경과`);
        }

        // 현재 시간으로 이동 및 자막/비디오 동기화
        await page.evaluate(async (time, duration) => {
            // CSS 애니메이션 동기화 - 모든 자막 요소
            document.querySelectorAll('.subtitle-item').forEach(item => {
                const style = window.getComputedStyle(item);
                const animName = style.animationName;
                if (animName && animName !== 'none') {
                    // 애니메이션 리셋 후 해당 시점으로 이동
                    item.style.animation = 'none';
                    void item.offsetWidth; // reflow
                    item.style.animation = `${animName} ${duration}s linear -${time}s forwards paused`;
                }
            });

            // 비디오 동기화 - seeked 이벤트 대기
            const videos = document.querySelectorAll('video');
            const seekPromises = [];

            videos.forEach(video => {
                const videoStart = parseFloat(video.getAttribute('data-start')) || 0;
                const videoTime = time - videoStart;

                if (videoTime >= 0 && videoTime < video.duration) {
                    video.style.opacity = '1';
                    video.style.visibility = 'visible';
                    video.style.display = 'block';

                    // seek이 필요한 경우에만 seeked 이벤트 대기
                    if (Math.abs(video.currentTime - videoTime) > 0.01) {
                        const seekPromise = new Promise(resolve => {
                            video.addEventListener('seeked', resolve, { once: true });
                            video.currentTime = videoTime;
                        });
                        seekPromises.push(seekPromise);
                    }
                } else {
                    video.style.opacity = '0';
                }
            });

            // 모든 비디오 seek 완료 대기
            if (seekPromises.length > 0) {
                await Promise.all(seekPromises);
            }
        }, currentTime, duration);

        // 프레임 렌더링 안정화 대기
        await new Promise(r => setTimeout(r, 50));

        // 스크린샷 캡처
        const framePath = path.join(CONFIG.framesDir, `frame_${String(frame).padStart(6, '0')}.png`);
        await page.screenshot({
            path: framePath,
            type: 'png',
        });
    }

    console.log('\n\n5. 브라우저 종료...');
    await browser.close();

    const captureTime = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`   캡처 완료: ${totalFrames}프레임, ${captureTime}초 소요\n`);

    console.log('6. FFmpeg로 영상 생성...');

    // 타임스탬프로 고유한 파일명 생성
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const outputFile = path.join(CONFIG.outputDir, `render_${timestamp}.mp4`);

    const ffmpegCmd = [
        'ffmpeg', '-y',
        '-framerate', String(fps),
        '-i', path.join(CONFIG.framesDir, 'frame_%06d.png'),
        '-i', 'assets/bgm.mp3',  // BGM 추가
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '18',
        '-b:v', '8M',           // 최소 비트레이트 8Mbps
        '-maxrate', '12M',      // 최대 비트레이트 12Mbps
        '-bufsize', '16M',      // 버퍼 크기
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        outputFile
    ].join(' ');

    try {
        execSync(ffmpegCmd, { stdio: 'inherit' });
        console.log(`\n=== 렌더링 완료 ===`);
        console.log(`출력: ${outputFile}`);
    } catch (e) {
        console.error('FFmpeg 오류:', e.message);

        // BGM 없이 재시도
        console.log('BGM 없이 재시도...');
        const ffmpegCmdNoAudio = [
            'ffmpeg', '-y',
            '-framerate', String(fps),
            '-i', path.join(CONFIG.framesDir, 'frame_%06d.png'),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '18',
            '-b:v', '8M',
            '-maxrate', '12M',
            '-bufsize', '16M',
            '-pix_fmt', 'yuv420p',
            outputFile
        ].join(' ');

        execSync(ffmpegCmdNoAudio, { stdio: 'inherit' });
        console.log(`\n=== 렌더링 완료 (BGM 없음) ===`);
        console.log(`출력: ${outputFile}`);
    }

    // 프레임 폴더 정리 (선택적)
    // fs.rmSync(CONFIG.framesDir, { recursive: true });

    // 서버 종료
    server.close();

    const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`총 소요 시간: ${totalTime}초`);
}

render().catch(err => {
    console.error(err);
    process.exit(1);
});
