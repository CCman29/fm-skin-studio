import { useEffect, useState } from "react";
import { call, type BarSetting } from "../api";
import { errorText, useToast } from "../App";

type Palette = Record<string, string | string[]>;

// [key, label, what it changes] — single colours
const FIELDS: [string, string, string][] = [
  ["panel", "Panels", "The big boxes that hold messages, tables and news."],
  ["tile", "Tiles & cards", "The smaller boxes, like budget and report tiles."],
  ["dark", "Header strips", "Darker strips at the top of boxes and sunken areas."],
  ["accent", "Buttons & selected tabs", "Filled buttons and the tab you're on."],
  ["highlight", "Highlight text", "Numbers that stand out, like budgets and links."],
  ["continue_colour", "Continue button", "The big button at the top right."],
];
// [key, label, what it changes] — two-colour gradients
const PAIRS: [string, string, string][] = [
  ["top_bar", "Top menu bar", "The bar with Portal, Squad, Tactics…"],
  ["sub_bar", "Sub menu bar", "The thinner bar under it."],
  ["page_header", "Page header", "The strip at the top of club and player pages."],
  ["backdrop", "Background", "Behind all the boxes (a picture can replace it in Bars & backgrounds)."],
];

const PRESETS: Record<string, Palette> = {
  "Midnight blue": { panel: "#0a1e5c", tile: "#0e2876", dark: "#08184e", accent: "#2e68d6", highlight: "#84c8ff", continue_colour: "#04145a",
    top_bar: ["#0a1a5c", "#061038"], sub_bar: ["#103f98", "#06123d"], page_header: ["#0e2470", "#071442"], backdrop: ["#2a3658", "#121a38"] },
  "Classic red": { panel: "#2a0d10", tile: "#36121a", dark: "#1c070a", accent: "#c8102e", highlight: "#ffc857", continue_colour: "#8f0c20",
    top_bar: ["#8f0c20", "#5a0814"], sub_bar: ["#3d1018", "#22080c"], page_header: ["#5a1010", "#2a0606"], backdrop: ["#3a0508", "#160203"] },
  "Forest green": { panel: "#10241a", tile: "#163222", dark: "#0b1a12", accent: "#2f9e5b", highlight: "#e6c068", continue_colour: "#1d5e38",
    top_bar: ["#123524", "#0a1f15"], sub_bar: ["#1d4a33", "#0d2419"], page_header: ["#17402c", "#0b1f15"], backdrop: ["#1b3326", "#0c1812"] },
  "Royal purple": { panel: "#1e1636", tile: "#281d48", dark: "#150f28", accent: "#7b3fd6", highlight: "#3fc8ff", continue_colour: "#5a27a8",
    top_bar: ["#38043f", "#1b001d"], sub_bar: ["#2c1f52", "#150a2a"], page_header: ["#32033a", "#1e0828"], backdrop: ["#240c2c", "#122a42"] },
  "Charcoal & gold": { panel: "#17191d", tile: "#1f2228", dark: "#111317", accent: "#c99a3b", highlight: "#f2cf73", continue_colour: "#2a2d33",
    top_bar: ["#111317", "#0b0c0f"], sub_bar: ["#1f2228", "#15171b"], page_header: ["#24272d", "#17191d"], backdrop: ["#202329", "#0d0e11"] },
};

const asHex = (v: unknown, fallback: string) => typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v) ? v : fallback;

/** The simple way to colour a skin: a few colours, applied everywhere FM27 allows (panels, tabs, the Continue button, the
 *  processing pop-up, the Tactics screen and the bars). The pitch stays green. */
export type PreviewFn = (tokens: Record<string, string> | null, bars: Record<string, BarSetting> | null) => void;

export default function ThemeRecipe({ packId, onApplied, initial, backdropImage, onPreview, onHover }: { packId: string; onApplied: () => void;
  initial?: Record<string, unknown> | null; backdropImage?: string | null; onPreview?: PreviewFn;
  onHover?: (field: string | null) => void }) {
  const hover = (k: string) => ({ onMouseEnter: () => onHover?.(k), onMouseLeave: () => onHover?.(null),
    onFocus: () => onHover?.(k), onBlur: () => onHover?.(null) });
  const toast = useToast();
  const [p, setP] = useState<Palette>(PRESETS["Midnight blue"]);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);

  // start from the colours this skin was last built with, if any
  useEffect(() => {
    if (!initial) return;
    const base = PRESETS["Midnight blue"];
    const next: Palette = {};
    for (const [k] of FIELDS) next[k] = asHex(initial[k], base[k] as string);
    for (const [k] of PAIRS) {
      const pair = Array.isArray(initial[k]) ? initial[k] as unknown[] : [];
      next[k] = [asHex(pair[0], (base[k] as string[])[0]), asHex(pair[1], (base[k] as string[])[1])];
    }
    setP(next);
  }, [initial]);

  const opacity = typeof initial?.panel_opacity === "number" ? initial.panel_opacity : undefined;
  const change = (next: Palette) => { setP(next); setDirty(true); };

  // live preview of colours that aren't applied yet (nothing is written until Apply)
  useEffect(() => {
    if (!dirty || !onPreview) return;
    const t = window.setTimeout(async () => {
      try {
        const tokens = await call<Record<string, string>>("recipe.preview", { palette: { ...p, accent_hover: p.accent, border: p.accent,
          processing: [p.accent, p.dark], ...(opacity !== undefined ? { panel_opacity: opacity } : {}) } });
        const grad = (k: string, angle: string): BarSetting => ({ mode: "gradient", colours: p[k] as string[], angle });
        const previewBars: Record<string, BarSetting> = { topBar: grad("top_bar", "horizontal"), subBar: grad("sub_bar", "horizontal"),
          pageHeader: grad("page_header", "horizontal") };
        if (!backdropImage) previewBars.backdrop = grad("backdrop", "diagonal");
        onPreview(tokens, previewBars);
      } catch { /* preview only */ }
    }, 120);
    return () => window.clearTimeout(t);
  }, [p, dirty]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onPreview?.(null, null), []); // eslint-disable-line react-hooks/exhaustive-deps
  const apply = async () => {
    setBusy(true);
    try {
      const r = await call<{ warnings: { area: string }[] }>("packs.applyRecipe", {
        pack: packId, palette: { ...p, accent_hover: p.accent, processing: [p.accent, p.dark], border: p.accent,
          ...(opacity !== undefined ? { panel_opacity: opacity } : {}),
          backdrop_image: backdropImage ?? null } });  // a background picture the skin already has is kept
      setWarnings(r.warnings.map((w) => w.area));
      toast(r.warnings.length ? "Colours applied, with a readability warning below. Save them in Check and Save."
        : "Colours applied. Press Save skin in Check and Save to put them in FM27.");
      setDirty(false);
      onPreview?.(null, null);
      onApplied();
    } catch (e) { toast({ text: errorText(e), error: true }); }
    setBusy(false);
  };

  return (
    <>
      <details className="section" open>
        <summary>Start from</summary>
        <div className="body">
          <select value="" onChange={(e) => { if (e.target.value) change(PRESETS[e.target.value]); }}>
            <option value="">Choose a ready-made look…</option>
            {Object.keys(PRESETS).map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
          <div className="note">Fills in every colour below. You can still change any of them.</div>
        </div>
      </details>

      <details className="section" open>
        <summary>Colours</summary>
        <div className="body">
          <div className="tiles">
            {FIELDS.map(([k, label, hint]) => (
              <label key={k} className="tile" title={hint} {...hover(k)}>
                <span className="swatches"><input type="color" value={p[k] as string} onChange={(e) => change({ ...p, [k]: e.target.value })} /></span>
                <span className="tile-label">{label}</span>
              </label>))}
          </div>
        </div>
      </details>

      <details className="section" open>
        <summary>Bars & background</summary>
        <div className="body">
          <div className="tiles">
            {PAIRS.map(([k, label, hint]) => (
              <div key={k} className="tile" title={`${hint} Two colours blend from one to the other.`} {...hover(k)}>
                <span className="swatches">
                  <input type="color" title="Left / top colour" value={(p[k] as string[])[0]}
                    onChange={(e) => change({ ...p, [k]: [e.target.value, (p[k] as string[])[1]] })} />
                  <input type="color" title="Right / bottom colour" value={(p[k] as string[])[1]}
                    onChange={(e) => change({ ...p, [k]: [(p[k] as string[])[0], e.target.value] })} />
                </span>
                <span className="tile-label">{label}</span>
                {k === "backdrop" && backdropImage && <span className="tile-sub">Picture in use</span>}
              </div>))}
          </div>
          <div className="note">Point at a tile to light up what it colours in the preview. Keep panels and bars fairly dark: FM27 writes team
            names in white.</div>
        </div>
      </details>

      {warnings.length > 0 && <div className="section small light-warning">
        These may be hard to read with white team names: <b>{warnings.join(", ")}</b>. Try a darker colour.</div>}
      <div className="apply-bar">
        <button className="primary" disabled={busy} onClick={apply}>{busy ? "Applying…" : "Apply colours to my skin"}</button>
        <span className="note">{dirty && !busy ? "Previewing colours that aren't applied yet." : "Applied colours are saved with your other changes in Check and Save."}</span>
      </div>
    </>
  );
}
