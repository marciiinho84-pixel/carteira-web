// Treemap simples (slice-and-dice recursivo) — sem dependência externa
// (ECharts na versão Streamlit). Aspect ratio pior que squarified, mas
// correto e previsível o suficiente pro tamanho de dados desta página
// (~10-40 itens).

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function treemapLayout<T extends { value: number }>(
  items: T[],
  x: number,
  y: number,
  w: number,
  h: number,
): (T & Rect)[] {
  if (items.length === 0) return [];
  if (items.length === 1) return [{ ...items[0], x, y, w, h }];

  const total = items.reduce((s, i) => s + Math.max(0, i.value), 0);
  if (total <= 0) {
    return items.map((it) => ({ ...it, x, y, w: 0, h: 0 }));
  }

  let acc = 0;
  let splitIdx = 1;
  for (let i = 0; i < items.length; i++) {
    acc += Math.max(0, items[i].value);
    if (acc >= total / 2) {
      splitIdx = i + 1;
      break;
    }
  }
  splitIdx = Math.min(Math.max(splitIdx, 1), items.length - 1);

  const left = items.slice(0, splitIdx);
  const right = items.slice(splitIdx);
  const leftVal = left.reduce((s, i) => s + Math.max(0, i.value), 0);
  const frac = total > 0 ? leftVal / total : 0.5;

  if (w >= h) {
    const w1 = w * frac;
    return [
      ...treemapLayout(left, x, y, w1, h),
      ...treemapLayout(right, x + w1, y, w - w1, h),
    ];
  }
  const h1 = h * frac;
  return [
    ...treemapLayout(left, x, y, w, h1),
    ...treemapLayout(right, x, y + h1, w, h - h1),
  ];
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Interpola uma cor numa escala de N stops distribuídos uniformemente em [min,max]. */
export function interpolateColor(value: number, min: number, max: number, stops: string[]): string {
  const clamped = Math.max(min, Math.min(max, value));
  const t = max > min ? (clamped - min) / (max - min) : 0;
  const scaled = t * (stops.length - 1);
  const i0 = Math.max(0, Math.min(stops.length - 2, Math.floor(scaled)));
  const localT = scaled - i0;
  const [r0, g0, b0] = hexToRgb(stops[i0]);
  const [r1, g1, b1] = hexToRgb(stops[i0 + 1]);
  const r = Math.round(lerp(r0, r1, localT));
  const g = Math.round(lerp(g0, g1, localT));
  const b = Math.round(lerp(b0, b1, localT));
  return `rgb(${r},${g},${b})`;
}
