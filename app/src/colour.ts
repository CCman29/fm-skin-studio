// Parse/format the colour values used in FM27 stylesheets: rgb(), rgba(), #hex.

export interface RGBA { r: number; g: number; b: number; a: number }

export function parseColour(value: string | null | undefined): RGBA | null {
  if (!value) return null;
  const v = value.trim();
  const m = v.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] };
  const h = v.match(/^#([0-9a-f]{6})([0-9a-f]{2})?$/i);
  if (h) {
    const n = parseInt(h[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: h[2] ? parseInt(h[2], 16) / 255 : 1 };
  }
  return null;
}

export function formatColour(c: RGBA): string {
  const r = Math.round(c.r), g = Math.round(c.g), b = Math.round(c.b);
  if (c.a >= 0.999) return `rgb(${r}, ${g}, ${b})`;
  return `rgba(${r}, ${g}, ${b}, ${+c.a.toFixed(2)})`;
}

export function toHex(c: RGBA): string {
  return "#" + [c.r, c.g, c.b].map((x) => Math.round(x).toString(16).padStart(2, "0")).join("");
}

export function fromHex(hex: string, a = 1): RGBA {
  const n = parseInt(hex.replace("#", ""), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a };
}

/** WCAG contrast ratio between two opaque colours. */
export function contrast(a: RGBA, b: RGBA): number {
  const lum = (c: RGBA) => {
    const ch = [c.r, c.g, c.b].map((x) => { const s = x / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  };
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

/** Blend a translucent colour over an opaque background (to judge what the player actually sees). */
export function over(top: RGBA, bottom: RGBA): RGBA {
  return { r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a),
           b: top.b * top.a + bottom.b * (1 - top.a), a: 1 };
}

/** Lighten (amount > 0) or darken (< 0) towards white/black. */
export function shade(c: RGBA, amount: number): RGBA {
  const t = amount > 0 ? 255 : 0, k = Math.abs(amount);
  return { r: c.r + (t - c.r) * k, g: c.g + (t - c.g) * k, b: c.b + (t - c.b) * k, a: c.a };
}
