// NukeMap - Sound Effects (Web Audio API, no external files)
window.NM = window.NM || {};

NM.Sound = {
  ctx: null,
  enabled: true,

  init() {
    try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
  },

  resume() {
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
  },

  detonate(yieldKt) {
    if (!this.enabled || !this.ctx) return;
    this.resume();
    const ctx = this.ctx;
    const now = ctx.currentTime;
    const vol = Math.min(0.7, 0.3 + Math.log10(Math.max(yieldKt, 0.01)) * 0.1);
    // Yield-proportional parameters
    const yLog = Math.log10(Math.max(yieldKt, 0.01));
    const boomPitch = Math.max(30, 180 - yLog * 25); // larger = deeper
    const crackPitch = Math.max(1500, 3500 - yLog * 400); // larger = duller crack

    // Initial flash crack (bright transient, pitch varies with yield)
    const crack = ctx.createBufferSource();
    const crackBuf = ctx.createBuffer(1, ctx.sampleRate * 0.05, ctx.sampleRate);
    const crackData = crackBuf.getChannelData(0);
    for (let i = 0; i < crackData.length; i++) {
      crackData[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * (0.005 + yLog * 0.001)));
    }
    crack.buffer = crackBuf;
    const crackGain = ctx.createGain();
    crackGain.gain.setValueAtTime(vol * 0.8, now);
    crackGain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
    const crackFilter = ctx.createBiquadFilter();
    crackFilter.type = 'highpass';
    crackFilter.frequency.value = crackPitch;
    crack.connect(crackFilter).connect(crackGain).connect(ctx.destination);
    crack.start(now);

    // Deep boom (duration and pitch scale with yield)
    const boomLen = 1.5 + Math.min(4, yLog * 0.9);
    const boom = ctx.createBufferSource();
    const boomBuf = ctx.createBuffer(1, ctx.sampleRate * boomLen, ctx.sampleRate);
    const boomData = boomBuf.getChannelData(0);
    for (let i = 0; i < boomData.length; i++) {
      const t = i / ctx.sampleRate;
      boomData[i] = (Math.random() * 2 - 1) * Math.exp(-t / (boomLen * 0.4));
    }
    boom.buffer = boomBuf;
    const boomFilter = ctx.createBiquadFilter();
    boomFilter.type = 'lowpass';
    boomFilter.frequency.setValueAtTime(boomPitch, now);
    boomFilter.frequency.exponentialRampToValueAtTime(Math.max(20, boomPitch * 0.3), now + boomLen);
    boomFilter.Q.value = 0.7;
    const boomGain = ctx.createGain();
    boomGain.gain.setValueAtTime(0.001, now);
    boomGain.gain.linearRampToValueAtTime(vol, now + 0.15);
    boomGain.gain.exponentialRampToValueAtTime(0.001, now + boomLen);
    boom.connect(boomFilter).connect(boomGain).connect(ctx.destination);
    boom.start(now + 0.05);

    // Sub bass throb (deeper and longer for bigger weapons)
    const subFreq = Math.max(12, 40 - yLog * 5);
    const sub = ctx.createOscillator();
    sub.type = 'sine';
    sub.frequency.setValueAtTime(subFreq * 1.5, now + 0.1);
    sub.frequency.exponentialRampToValueAtTime(subFreq, now + boomLen);
    const subGain = ctx.createGain();
    subGain.gain.setValueAtTime(0.001, now);
    subGain.gain.linearRampToValueAtTime(vol * 0.6, now + 0.2);
    subGain.gain.exponentialRampToValueAtTime(0.001, now + boomLen * 0.8);
    sub.connect(subGain).connect(ctx.destination);
    sub.start(now + 0.1);
    sub.stop(now + boomLen);

    // Mid-frequency pressure wave (new: adds body for larger yields)
    if (yieldKt >= 10) {
      const mid = ctx.createBufferSource();
      const midLen = boomLen * 0.6;
      const midBuf = ctx.createBuffer(1, ctx.sampleRate * midLen, ctx.sampleRate);
      const midData = midBuf.getChannelData(0);
      for (let i = 0; i < midData.length; i++) {
        const t = i / ctx.sampleRate;
        midData[i] = (Math.random() * 2 - 1) * Math.exp(-t / (midLen * 0.25)) * Math.sin(t * 8);
      }
      mid.buffer = midBuf;
      const midFilter = ctx.createBiquadFilter();
      midFilter.type = 'bandpass'; midFilter.frequency.value = 80 + yLog * 15; midFilter.Q.value = 1.2;
      const midGain = ctx.createGain();
      midGain.gain.setValueAtTime(0.001, now + 0.08);
      midGain.gain.linearRampToValueAtTime(vol * 0.4, now + 0.2);
      midGain.gain.exponentialRampToValueAtTime(0.001, now + 0.08 + midLen);
      mid.connect(midFilter).connect(midGain).connect(ctx.destination);
      mid.start(now + 0.08);
    }

    // Distant rumble / echo (delayed, longer for bigger weapons)
    const echo = ctx.createBufferSource();
    const echoLen = boomLen * 1.5;
    const echoBuf = ctx.createBuffer(1, ctx.sampleRate * echoLen, ctx.sampleRate);
    const echoData = echoBuf.getChannelData(0);
    for (let i = 0; i < echoData.length; i++) {
      const t = i / ctx.sampleRate;
      echoData[i] = (Math.random() * 2 - 1) * Math.exp(-t / (echoLen * 0.3)) * (0.5 + 0.5 * Math.sin(t * 3));
    }
    echo.buffer = echoBuf;
    const echoFilter = ctx.createBiquadFilter();
    echoFilter.type = 'bandpass';
    echoFilter.frequency.value = Math.max(60, 100 - yLog * 8);
    echoFilter.Q.value = 0.5;
    const echoGain = ctx.createGain();
    echoGain.gain.setValueAtTime(vol * 0.3, now + 0.5);
    echoGain.gain.exponentialRampToValueAtTime(0.001, now + 0.5 + echoLen);
    echo.connect(echoFilter).connect(echoGain).connect(ctx.destination);
    echo.start(now + 0.5);
  }
};
