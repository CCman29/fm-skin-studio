// Live version of the core's light-surface check (core/src/fmskin/contrast.py): FM27 always draws names, card titles
// and menu text in white, so these surfaces must stay dark enough for white text.
import type { BarSetting } from "./api";
import { parseColour } from "./colour";

export const MIN_RATIO = 3;
const BEHIND = { r: 60, g: 70, b: 90 };
const SURFACES: Record<string, string> = {
  "--layout-modules-block-surface": "Content panels",
  "--layout-modules-tiles-background": "Side tiles",
  "--layout-surfaces-cards-surface": "Cards",
  "--colours-ui-soft": "Base surface (soft)",
  "--layout-surfaces-modules-modal": "Pop-ups and dialogs",
  "--data-tables-background": "Table rows",
  "--data-tables-background-accent": "Table rows (alternate)",
};
const BAR_AREAS: Record<string, string> = { topBar: "Top menu bar", pageHeader: "Page header", backdrop: "Page backdrop" };

export interface LightWarning { area: string; target: string; ratio: number }

function lum(c: { r: number; g: number; b: number }) {
  const ch = (x: number) => { const s = x / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b);
}

export function whiteRatio(c: { r: number; g: number; b: number; a: number }): number {
  const seen = { r: c.r * c.a + BEHIND.r * (1 - c.a), g: c.g * c.a + BEHIND.g * (1 - c.a), b: c.b * c.a + BEHIND.b * (1 - c.a) };
  return 1.05 / (lum(seen) + 0.05);
}

export function lightWarnings(overrides: Record<string, string>, value: (t: string) => string,
  bars: Record<string, BarSetting>): LightWarning[] {
  const out: LightWarning[] = [];
  for (const [token, area] of Object.entries(SURFACES)) {
    if (!(token in overrides)) continue;
    const c = parseColour(value(token));
    if (c && c.a > 0.15) {
      const ratio = whiteRatio(c);
      if (ratio < MIN_RATIO) out.push({ area, target: token, ratio: Math.round(ratio * 10) / 10 });
    }
  }
  for (const [key, area] of Object.entries(BAR_AREAS)) {
    const b = bars[key];
    if (!b || (b.mode !== "solid" && b.mode !== "gradient")) continue;
    const ratios = (b.colours ?? []).slice(0, b.mode === "solid" ? 1 : 2).map(parseColour).filter(Boolean)
      .map((c) => whiteRatio(c!));
    if (ratios.length && Math.min(...ratios) < MIN_RATIO) {
      out.push({ area, target: `bars:${key}`, ratio: Math.round(Math.min(...ratios) * 10) / 10 });
    }
  }
  return out;
}
