// NukeMap - Mushroom Cloud (SVG Leaflet overlay, map-anchored, zoom-scaled)
window.NM = window.NM || {};

NM.Mushroom3D = {
  active: false,
  overlays: [],
  currentDet: null,

  init() {},

  show(det, keepExisting) {
    if (!keepExisting) this.hideAll();
    this.currentDet = det;
    const map = NM._map;
    if (!map) return;

    const e = det.effects;
    const footprintKm = Math.max(e.cloudTopR * 1.2, e.fireball * 3, 0.5);
    const R = 6371;
    const dLat = (footprintKm / R) * (180 / Math.PI);
    const totalV = dLat * 3.05; // total vertical extent of bounds
    const hExtent = dLat * 1.4;
    // SVG ground is at 93% from top, so GZ should be 93% down from the top of bounds
    // top = det.lat + totalV * 0.93, bottom = det.lat - totalV * 0.07
    const bounds = L.latLngBounds(
      [det.lat - totalV * 0.07, det.lng - hExtent],
      [det.lat + totalV * 0.93, det.lng + hExtent]
    );

    const svgStr = this._buildSVG(det.yieldKt);
    const wrap = document.createElement('div');
    wrap.innerHTML = svgStr;
    const svgNode = wrap.firstElementChild;

    const overlay = L.svgOverlay(svgNode, bounds, {
      interactive: false, className: 'mushroom-overlay'
    }).addTo(map);
    this.overlays.push(overlay);
    this.active = true;

    // Animate reveal from bottom up
    const clipRect = svgNode.querySelector('.mc-reveal-rect');
    if (clipRect) {
      const totalH = 600;
      const duration = 3200;
      const start = performance.now();
      const tick = (now) => {
        const p = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        const y = totalH * (1 - eased);
        clipRect.setAttribute('y', y.toFixed(1));
        clipRect.setAttribute('height', (totalH - y + 10).toFixed(1));
        if (p < 1 && this.active) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }

    svgNode.style.opacity = '0';
    svgNode.style.transition = 'opacity 0.5s ease-out';
    requestAnimationFrame(() => { svgNode.style.opacity = '1'; });
  },

  _buildSVG(yieldKt) {
    const W = 500, H = 600;
    const cx = W / 2;
    const uid = 'mc' + Date.now() + Math.floor(Math.random() * 1000);

    // Scale intensity by yield (brighter/hotter for bigger)
    const t = Math.min(1, Math.log10(Math.max(yieldKt, 0.1)) / 5 + 0.5);
    const seed1 = Math.floor(Math.random() * 999);
    const seed2 = seed1 + 50;

    // Proportions
    const ground = H * 0.93;
    const stemBotW = W * 0.07;
    const stemTopW = W * 0.04;
    const stemTopY = H * 0.42;
    const capCY = H * 0.28;
    const capW = W * 0.40;
    const capH = H * 0.16;

    // Helper: random offset for organic shapes
    const jit = (base, range) => base + (Math.random() - 0.5) * range;

    // Build cauliflower lobes on the cap
    const lobes = [];
    const lobeCount = 12;
    for (let i = 0; i < lobeCount; i++) {
      const angle = (i / lobeCount) * Math.PI;
      const lx = cx + Math.cos(angle) * capW * (0.7 + Math.random() * 0.35);
      const ly = capCY + Math.sin(angle - Math.PI / 2) * capH * (0.3 + Math.random() * 0.5);
      const lr = 14 + Math.random() * 22;
      lobes.push({ x: lx, y: ly, r: lr });
    }

    // Bottom lobes (underneath the cap)
    const bottomLobes = [];
    for (let i = 0; i < 8; i++) {
      const angle = (i / 8) * Math.PI;
      const lx = cx + Math.cos(angle) * capW * (0.5 + Math.random() * 0.4);
      const ly = capCY + capH * (0.5 + Math.random() * 0.3);
      const lr = 10 + Math.random() * 15;
      bottomLobes.push({ x: lx, y: ly, r: lr });
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" style="overflow:visible">
    <defs>
      <filter id="${uid}t1" x="-25%" y="-25%" width="150%" height="150%">
        <feTurbulence type="fractalNoise" baseFrequency="0.025" numOctaves="5" seed="${seed1}" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="22" xChannelSelector="R" yChannelSelector="G"/>
      </filter>
      <filter id="${uid}t2" x="-15%" y="-15%" width="130%" height="130%">
        <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="4" seed="${seed2}" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="14" xChannelSelector="R" yChannelSelector="G"/>
      </filter>
      <filter id="${uid}t3" x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="3" seed="${seed1+99}" result="n"/>
        <feDisplacementMap in="SourceGraphic" in2="n" scale="8" xChannelSelector="R" yChannelSelector="G"/>
      </filter>
      <filter id="${uid}gl">
        <feGaussianBlur stdDeviation="8" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <filter id="${uid}sh">
        <feGaussianBlur stdDeviation="5" result="b"/>
        <feOffset dy="3" result="o"/>
        <feMerge><feMergeNode in="o"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>

      <clipPath id="${uid}-reveal">
        <rect class="mc-reveal-rect" x="-50" y="${H}" width="${W+100}" height="10"/>
      </clipPath>

      <!-- Cap outer: dark smoke edge -->
      <radialGradient id="${uid}g1" cx="48%" cy="38%" r="58%">
        <stop offset="0%" stop-color="rgb(${Math.round(240*t)},${Math.round(180*t)},${Math.round(100*t)})"/>
        <stop offset="20%" stop-color="rgb(${Math.round(210*t)},${Math.round(140*t)},${Math.round(60*t)})"/>
        <stop offset="45%" stop-color="rgb(${Math.round(170*t)},${Math.round(100*t)},${Math.round(40*t)})"/>
        <stop offset="70%" stop-color="rgb(120,85,60)"/>
        <stop offset="90%" stop-color="rgb(80,65,50)"/>
        <stop offset="100%" stop-color="rgb(55,45,38)"/>
      </radialGradient>

      <!-- Cap inner: hot core -->
      <radialGradient id="${uid}g2" cx="50%" cy="45%" r="40%">
        <stop offset="0%" stop-color="rgba(255,240,200,${(0.7*t).toFixed(2)})"/>
        <stop offset="30%" stop-color="rgba(255,180,80,${(0.5*t).toFixed(2)})"/>
        <stop offset="60%" stop-color="rgba(220,100,30,${(0.3*t).toFixed(2)})"/>
        <stop offset="100%" stop-color="rgba(150,60,20,0)"/>
      </radialGradient>

      <!-- Stem gradient: 3D cylinder shading -->
      <linearGradient id="${uid}sg" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0%" stop-color="rgb(65,50,40)" stop-opacity="0.5"/>
        <stop offset="20%" stop-color="rgb(110,85,65)" stop-opacity="0.8"/>
        <stop offset="40%" stop-color="rgb(140,110,80)" stop-opacity="0.9"/>
        <stop offset="55%" stop-color="rgb(155,120,85)" stop-opacity="0.95"/>
        <stop offset="70%" stop-color="rgb(135,105,75)" stop-opacity="0.85"/>
        <stop offset="85%" stop-color="rgb(100,78,58)" stop-opacity="0.7"/>
        <stop offset="100%" stop-color="rgb(60,48,38)" stop-opacity="0.4"/>
      </linearGradient>

      <!-- Dust cloud at ground -->
      <radialGradient id="${uid}dg" cx="50%" cy="40%" r="55%">
        <stop offset="0%" stop-color="rgba(180,150,110,0.6)"/>
        <stop offset="40%" stop-color="rgba(150,120,85,0.35)"/>
        <stop offset="70%" stop-color="rgba(120,95,70,0.15)"/>
        <stop offset="100%" stop-color="rgba(90,75,55,0)"/>
      </radialGradient>

      <!-- Vortex ring gradient -->
      <radialGradient id="${uid}vg" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(100,75,55,0)"/>
        <stop offset="40%" stop-color="rgba(130,100,70,0.4)"/>
        <stop offset="70%" stop-color="rgba(110,80,55,0.25)"/>
        <stop offset="100%" stop-color="rgba(80,60,45,0)"/>
      </radialGradient>

      <!-- Condensation ring -->
      <radialGradient id="${uid}cg" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(200,200,210,0)"/>
        <stop offset="50%" stop-color="rgba(220,220,230,0.25)"/>
        <stop offset="75%" stop-color="rgba(200,200,210,0.15)"/>
        <stop offset="100%" stop-color="rgba(180,180,190,0)"/>
      </radialGradient>
    </defs>

    <g clip-path="url(#${uid}-reveal)">
      <!-- === GROUND DUST CLOUD === -->
      <ellipse cx="${cx}" cy="${ground}" rx="${W*0.42}" ry="${H*0.055}" fill="url(#${uid}dg)" filter="url(#${uid}t1)"/>
      <!-- Outer dust ring -->
      <ellipse cx="${cx}" cy="${ground+2}" rx="${W*0.48}" ry="${H*0.035}" fill="url(#${uid}dg)" filter="url(#${uid}t2)" opacity="0.5"/>

      <!-- === STEM === -->
      <!-- Stem body: bezier tapered column -->
      <path d="
        M${cx - stemBotW} ${ground}
        C${cx - stemBotW * 1.3} ${ground - H * 0.15},
         ${cx - stemBotW * 1.6} ${ground - H * 0.3},
         ${cx - stemTopW * 1.2} ${stemTopY + capH * 0.3}
        L${cx - stemTopW} ${stemTopY}
        L${cx + stemTopW} ${stemTopY}
        L${cx + stemTopW * 1.2} ${stemTopY + capH * 0.3}
        C${cx + stemBotW * 1.6} ${ground - H * 0.3},
         ${cx + stemBotW * 1.3} ${ground - H * 0.15},
         ${cx + stemBotW} ${ground}
        Z"
        fill="url(#${uid}sg)" filter="url(#${uid}t2)"/>

      <!-- Stem highlight (central bright strip) -->
      <path d="
        M${cx - stemBotW * 0.3} ${ground}
        C${cx - stemBotW * 0.4} ${ground - H * 0.2},
         ${cx - stemTopW * 0.5} ${stemTopY + H * 0.1},
         ${cx - stemTopW * 0.3} ${stemTopY + capH * 0.2}
        L${cx + stemTopW * 0.3} ${stemTopY + capH * 0.2}
        C${cx + stemTopW * 0.5} ${stemTopY + H * 0.1},
         ${cx + stemBotW * 0.4} ${ground - H * 0.2},
         ${cx + stemBotW * 0.3} ${ground}
        Z"
        fill="rgba(180,145,105,0.25)" filter="url(#${uid}t3)"/>

      <!-- === CONDENSATION RING (Wilson cloud) at mid-stem === -->
      <ellipse cx="${cx}" cy="${(ground + stemTopY) * 0.55}" rx="${W * 0.12}" ry="${H * 0.02}"
        fill="url(#${uid}cg)" filter="url(#${uid}t3)" opacity="0.6">
        <animate attributeName="rx" values="${W*0.11};${W*0.14};${W*0.11}" dur="5s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.6;0.3;0.6" dur="5s" repeatCount="indefinite"/>
      </ellipse>

      <!-- === COLLAR (skirt where stem meets cap) === -->
      <ellipse cx="${cx}" cy="${stemTopY + capH * 0.15}" rx="${capW * 0.55}" ry="${capH * 0.35}"
        fill="rgb(105,80,60)" opacity="0.55" filter="url(#${uid}t1)"/>

      <!-- === VORTEX RING (toroidal roll under cap) === -->
      <ellipse cx="${cx}" cy="${capCY + capH * 0.65}" rx="${capW * 0.85}" ry="${capH * 0.3}"
        fill="url(#${uid}vg)" filter="url(#${uid}t1)"/>

      <!-- === BOTTOM LOBES (underneath cap, darker) === -->
      ${bottomLobes.map(l => `<circle cx="${l.x.toFixed(1)}" cy="${l.y.toFixed(1)}" r="${l.r.toFixed(1)}"
        fill="rgb(${75+Math.floor(Math.random()*25)},${55+Math.floor(Math.random()*20)},${40+Math.floor(Math.random()*15)})"
        opacity="${(0.35+Math.random()*0.2).toFixed(2)}" filter="url(#${uid}t2)"/>`).join('\n      ')}

      <!-- === MAIN CAP: large organic shape === -->
      <ellipse cx="${cx}" cy="${capCY}" rx="${capW}" ry="${capH}"
        fill="url(#${uid}g1)" filter="url(#${uid}t1)" opacity="0.92"/>

      <!-- Cap upper dome -->
      <ellipse cx="${cx}" cy="${capCY - capH * 0.2}" rx="${capW * 0.78}" ry="${capH * 0.75}"
        fill="url(#${uid}g1)" filter="url(#${uid}t1)" opacity="0.8"/>

      <!-- Cap top crown (brightest) -->
      <ellipse cx="${cx}" cy="${capCY - capH * 0.3}" rx="${capW * 0.5}" ry="${capH * 0.45}"
        fill="url(#${uid}g1)" filter="url(#${uid}t2)" opacity="0.6"/>

      <!-- === CAULIFLOWER LOBES (bumpy cap edges) === -->
      ${lobes.map(l => `<circle cx="${l.x.toFixed(1)}" cy="${l.y.toFixed(1)}" r="${l.r.toFixed(1)}"
        fill="url(#${uid}g1)" opacity="${(0.4+Math.random()*0.3).toFixed(2)}" filter="url(#${uid}t1)"/>`).join('\n      ')}

      <!-- === HOT CORE GLOW === -->
      <ellipse cx="${cx}" cy="${capCY + capH * 0.05}" rx="${capW * 0.45}" ry="${capH * 0.4}"
        fill="url(#${uid}g2)" filter="url(#${uid}gl)"/>

      <!-- Core pulse -->
      <ellipse cx="${cx}" cy="${capCY}" rx="${capW * 0.25}" ry="${capH * 0.25}"
        fill="rgba(255,210,130,0.12)">
        <animate attributeName="rx" values="${capW*0.22};${capW*0.3};${capW*0.22}" dur="4s" repeatCount="indefinite"/>
        <animate attributeName="ry" values="${capH*0.22};${capH*0.3};${capH*0.22}" dur="4s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.12;0.22;0.12" dur="4s" repeatCount="indefinite"/>
      </ellipse>

      <!-- === SMOKE COLUMN above cap === -->
      <ellipse cx="${cx}" cy="${capCY - capH * 1.1}" rx="${capW * 0.25}" ry="${capH * 0.55}"
        fill="rgb(85,68,52)" opacity="0.3" filter="url(#${uid}t1)"/>
      <ellipse cx="${jit(cx, 10)}" cy="${capCY - capH * 1.5}" rx="${capW * 0.18}" ry="${capH * 0.35}"
        fill="rgb(75,60,48)" opacity="0.2" filter="url(#${uid}t1)"/>

      <!-- === TOP WISPS (dissipating smoke at very top) === -->
      ${[0,1,2,3,4].map(i => {
        const wx = jit(cx, capW * 0.4);
        const wy = jit(capCY - capH * 1.6, capH * 0.5);
        return `<ellipse cx="${wx.toFixed(1)}" cy="${wy.toFixed(1)}" rx="${jit(15,10).toFixed(1)}" ry="${jit(8,5).toFixed(1)}"
          fill="rgb(${70+Math.floor(Math.random()*20)},${55+Math.floor(Math.random()*15)},${42+Math.floor(Math.random()*10)})"
          opacity="${(0.12+Math.random()*0.12).toFixed(2)}" filter="url(#${uid}t2)"/>`;
      }).join('\n      ')}

    </g>
    </svg>`;
  },

  hideAll() {
    this.active = false;
    const map = NM._map;
    if (map) this.overlays.forEach(o => map.removeLayer(o));
    this.overlays = [];
    this.currentDet = null;
  },

  hide() { this.hideAll(); },

  removeAt(idx) {
    const map = NM._map;
    if (map && this.overlays[idx]) map.removeLayer(this.overlays[idx]);
    this.overlays.splice(idx, 1);
    if (!this.overlays.length) this.active = false;
  },

  cleanup() { this.hideAll(); },
  onMapMove() {},

  toggle(det, keepExisting) {
    if (this.active && !keepExisting) this.hideAll();
    else if (det) this.show(det, keepExisting);
  }
};
