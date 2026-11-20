/**
 * Animated page backgrounds, drawn on one canvas behind the glass panels.
 * All of them are thin ink lines or dots at very low opacity (no colour washes); the accent blue only
 * appears near the pointer. Each scene is draw(ctx, w, h, t, pointer, state) and must also look right as a
 * single still frame (used for reduced motion and for the preview tiles).
 */

/* ---- 3D gradient noise (Ken Perlin's improved noise), enough for slow organic motion ---- */
const P = new Uint8Array(512)
;(() => {
  const p = Array.from({ length: 256 }, (_, i) => i)
  let seed = 7
  for (let i = 255; i > 0; i--) {
    seed = (seed * 16807) % 2147483647
    const j = seed % (i + 1)
    ;[p[i], p[j]] = [p[j], p[i]]
  }
  for (let i = 0; i < 512; i++) P[i] = p[i & 255]
})()
const fade = t => t * t * t * (t * (t * 6 - 15) + 10)
const lerp = (a, b, t) => a + t * (b - a)
function grad(h, x, y, z) {
  const u = (h & 15) < 8 ? x : y
  const v = (h & 15) < 4 ? y : (h & 15) === 12 || (h & 15) === 14 ? x : z
  return ((h & 1) ? -u : u) + ((h & 2) ? -v : v)
}
export function noise(x, y, z) {
  const X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255
  x -= Math.floor(x); y -= Math.floor(y); z -= Math.floor(z)
  const u = fade(x), v = fade(y), w = fade(z)
  const A = P[X] + Y, AA = P[A] + Z, AB = P[A + 1] + Z, B = P[X + 1] + Y, BA = P[B] + Z, BB = P[B + 1] + Z
  return lerp(
    lerp(lerp(grad(P[AA], x, y, z), grad(P[BA], x - 1, y, z), u),
         lerp(grad(P[AB], x, y - 1, z), grad(P[BB], x - 1, y - 1, z), u), v),
    lerp(lerp(grad(P[AA + 1], x, y, z - 1), grad(P[BA + 1], x - 1, y, z - 1), u),
         lerp(grad(P[AB + 1], x, y - 1, z - 1), grad(P[BB + 1], x - 1, y - 1, z - 1), u), v), w)
}

/* scene colours come from the page's theme (--scene-ink / --scene-accent / --scene-alpha), so the same
   drawing works on the light and the dark canvas; readSceneColors() is called when the mode changes */
let ink = '11, 18, 32', accent = '47, 75, 224', alpha = 1
export function readSceneColors() {
  const css = getComputedStyle(document.documentElement)
  const rgb = name => css.getPropertyValue(name).trim().split(/\s+/).join(', ')
  ink = rgb('--scene-ink') || ink
  accent = rgb('--scene-accent') || accent
  alpha = parseFloat(css.getPropertyValue('--scene-alpha')) || 1
}
const INK = (a) => `rgba(${ink}, ${a * alpha})`
const ACCENT = (a) => `rgba(${accent}, ${a})`

/* ---- Contours: a slowly shifting topographic map ---- */
function contours(ctx, w, h, t, pointer, state) {
  const cell = 14
  const cols = Math.ceil(w / cell) + 1, rows = Math.ceil(h / cell) + 1
  const f = new Float32Array(cols * rows)
  const z = t * 0.00003
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      const x = i * cell, y = j * cell
      f[j * cols + i] = noise(x * 0.0021, y * 0.0021, z) + 0.35 * noise(x * 0.006, y * 0.006, z * 1.7 + 9)
    }
  }
  ctx.lineWidth = state.lw || 1
  for (let k = -7; k <= 7; k++) {
    const level = k * 0.085
    ctx.strokeStyle = INK(k % 3 === 0 ? 0.12 : 0.065)
    ctx.beginPath()
    for (let j = 0; j < rows - 1; j++) {
      for (let i = 0; i < cols - 1; i++) {
        const a = f[j * cols + i], b = f[j * cols + i + 1], c = f[(j + 1) * cols + i + 1], d = f[(j + 1) * cols + i]
        const idx = (a > level ? 8 : 0) | (b > level ? 4 : 0) | (c > level ? 2 : 0) | (d > level ? 1 : 0)
        if (idx === 0 || idx === 15) continue
        const x = i * cell, y = j * cell
        const top = [x + cell * (level - a) / (b - a), y]
        const right = [x + cell, y + cell * (level - b) / (c - b)]
        const bottom = [x + cell * (level - d) / (c - d), y + cell]
        const left = [x, y + cell * (level - a) / (d - a)]
        const seg = (p, q) => { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]) }
        switch (idx) {
          case 1: case 14: seg(left, bottom); break
          case 2: case 13: seg(bottom, right); break
          case 3: case 12: seg(left, right); break
          case 4: case 11: seg(top, right); break
          case 6: case 9: seg(top, bottom); break
          case 7: case 8: seg(left, top); break
          case 5: seg(left, top); seg(bottom, right); break
          case 10: seg(top, right); seg(left, bottom); break
        }
      }
    }
    ctx.stroke()
  }
}

/* ---- Constellation: drifting points joined by fine lines; lines near the pointer turn blue ---- */
function constellation(ctx, w, h, t, pointer, state) {
  if (!state.pts || state.w !== w || state.h !== h) {
    let seed = 11
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647
    const n = Math.round(Math.min(110, Math.max(30, (w * h) / 16000)))
    state.pts = Array.from({ length: n }, () => ({ x: rnd() * w, y: rnd() * h, a: rnd() * Math.PI * 2, s: 0.008 + rnd() * 0.012 }))
    state.w = w; state.h = h
  }
  const pts = state.pts.map(p => {
    // each point drifts on a slow loop, so the still frame and the animation agree
    const r = 40 + 30 * Math.sin(p.a * 3)
    return { x: p.x + Math.cos(p.a + t * p.s * 0.01) * r, y: p.y + Math.sin(p.a + t * p.s * 0.013) * r }
  })
  const max = 150
  ctx.lineWidth = state.lw || 1
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y
      const d2 = dx * dx + dy * dy
      if (d2 > max * max) continue
      const k = 1 - Math.sqrt(d2) / max
      const mx = (pts[i].x + pts[j].x) / 2, my = (pts[i].y + pts[j].y) / 2
      const near = pointer ? Math.max(0, 1 - Math.hypot(mx - pointer.x, my - pointer.y) / 220) : 0
      ctx.strokeStyle = near > 0 ? ACCENT(k * (0.12 + 0.35 * near)) : INK(k * 0.11)
      ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[j].x, pts[j].y); ctx.stroke()
    }
  }
  for (const p of pts) {
    const near = pointer ? Math.max(0, 1 - Math.hypot(p.x - pointer.x, p.y - pointer.y) / 220) : 0
    ctx.fillStyle = near > 0 ? ACCENT(0.25 + 0.5 * near) : INK(0.2)
    ctx.beginPath(); ctx.arc(p.x, p.y, 1.6 + near * 1.4, 0, Math.PI * 2); ctx.fill()
  }
}

/* ---- Living grid: a dot grid that breathes in slow waves and swells under the pointer ---- */
function livingGrid(ctx, w, h, t, pointer) {
  const gap = 24
  for (let y = gap / 2; y < h; y += gap) {
    for (let x = gap / 2; x < w; x += gap) {
      const wave = 0.5 + 0.5 * noise(x * 0.004, y * 0.004, t * 0.00012)
      const near = pointer ? Math.max(0, 1 - Math.hypot(x - pointer.x, y - pointer.y) / 170) : 0
      const r = 0.7 + wave * 0.9 + near * near * 1.8
      ctx.fillStyle = near > 0.05 ? ACCENT(0.18 + 0.4 * near) : INK(0.07 + wave * 0.1)
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill()
    }
  }
}

/* ---- Flow lines: fine horizontal threads moved by a slow current ---- */
function flow(ctx, w, h, t, pointer, state) {
  const lines = Math.round(h / 26)
  ctx.lineWidth = state.lw || 1
  for (let i = 0; i <= lines; i++) {
    const base = (i / lines) * h
    ctx.strokeStyle = INK(i % 4 === 0 ? 0.1 : 0.055)
    ctx.beginPath()
    for (let x = -10; x <= w + 10; x += 14) {
      const y = base + 34 * noise(x * 0.0018, i * 0.09, t * 0.00006) + 10 * noise(x * 0.006, i * 0.2, t * 0.0001 + 5)
      x < 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.stroke()
  }
}

export const SCENES = { contours, constellation, grid: livingGrid, flow }

/** One still frame, e.g. for a preview tile. `zoom` > 1 shows a larger area shrunk down, so a small tile
 *  shows the overall pattern rather than a single line of it. */
export function drawStill(canvas, kind, scale = 1, zoom = 1) {
  const ctx = canvas.getContext('2d')
  const s = scale / zoom
  const w = canvas.width / s, h = canvas.height / s
  ctx.setTransform(s, 0, 0, s, 0, 0)
  ctx.clearRect(0, 0, w, h)
  SCENES[kind]?.(ctx, w, h, 20000, null, { lw: Math.max(1, zoom * 0.8) })
}
