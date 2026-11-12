import { useEffect, useState } from "react";
import { call } from "../api";
import { errorText, useToast } from "../App";
import type { Theme } from "./Workspace";

export interface Band { from: number; label?: string; text: string; background: string; border: string }
interface State { bands: Band[]; warnings: string[]; instructions: string }

const STARTER: Band[] = [  // a neutral starting point; each skin picks its own colours
  { from: 16, label: "Excellent", text: "#ffffff", background: "#1f6f3a", border: "#ffffff" },
  { from: 11, label: "Good", text: "#1b1b1b", background: "#f2c94c", border: "#ffffff" },
  { from: 1, label: "Weak", text: "#ffffff", background: "#1b1b1b", border: "#ffffff" },
];
const SAMPLE: [string, number][] = [["Finishing", 18], ["First Touch", 16], ["Passing", 15], ["Technique", 13], ["Dribbling", 11],
  ["Heading", 9], ["Long Shots", 6], ["Tackling", 3]];

function lum(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  const ch = (x: number) => { const s = x / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * ch(n >> 16 & 255) + 0.7152 * ch(n >> 8 & 255) + 0.0722 * ch(n & 255);
}
const ratio = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const sorted = (bands: Band[]) => [...bands].sort((a, b) => b.from - a.from);
const bandFor = (bands: Band[], v: number) => sorted(bands).find((b) => v >= b.from);
const rangeOf = (bands: Band[], i: number) => { const s = sorted(bands); return `${s[i].from}-${i === 0 ? 20 : s[i - 1].from - 1}`; };

/** A skin's suggested attribute colours. FM27 keeps the real ones in each player's Preferences (Attribute Colours), so a
 *  skin can't switch them on: the studio previews them and installer packages tell players what to enter. */
export default function AttributeColours({ packId, theme }: { packId: string; theme: Theme }) {
  const toast = useToast();
  const [saved, setSaved] = useState<State | null>(null);
  const [bands, setBands] = useState<Band[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    call<State>("packs.attributeColours", { pack: packId }).then((s) => { setSaved(s); setBands(sorted(s.bands)); })
      .catch((e) => toast({ text: errorText(e), error: true }));
  }, [packId]); // eslint-disable-line react-hooks/exhaustive-deps

  const edit = (i: number, patch: Partial<Band>) => setBands((bs) => bs.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  const save = async (next: Band[] | null) => {
    setBusy(true);
    try {
      const s = await call<State>("packs.setAttributeColours", { pack: packId, bands: next });
      setSaved(s); setBands(sorted(s.bands));
      toast(next ? "Saved with the skin. Players set them in FM27's Preferences (see the note)." : "Attribute colours removed from the skin");
    } catch (e) { toast({ text: errorText(e), error: true }); }
    setBusy(false);
  };
  if (!saved) return <div className="muted">Loading…</div>;
  const panel = theme.value("--layout-modules-block-surface") || "rgb(30, 33, 41)";
  const text = theme.value("--global-text-primary") || "#ffffff";
  const changed = JSON.stringify(sorted(bands)) !== JSON.stringify(sorted(saved.bands));

  return (
    <div className="studio">
      <div className="inspector">
        <div className="note">Colour player attributes (1-20) by band: the number, the cell behind it and its border. FM27 keeps
          attribute colours in each player's own Preferences, so a skin can't switch them on by itself. The skin carries your
          suggestion, and its installer package tells players exactly what to enter in Preferences &gt; Attribute Colours.</div>
        {bands.length === 0 ? (
          <details className="section" open><summary>No attribute colours yet</summary>
            <div className="body"><button onClick={() => setBands(STARTER)}>Start with three bands</button></div></details>
        ) : bands.map((b, i) => {
          const r = ratio(b.text, b.background);
          return (
            <details key={i} className="section" open>
              <summary>{rangeOf(bands, i)}{b.label ? ` · ${b.label}` : ""}<span className="grow" />
                {r < 3 && <span className="badge warn" title="The number is hard to read on this background">Low contrast {r.toFixed(1)}:1</span>}</summary>
              <div className="body">
                <div className="row wrap">
                  <label className="field"><span>From value</span>
                    <input type="number" min={1} max={20} value={b.from} disabled={i === bands.length - 1 && b.from === 1}
                      onChange={(e) => edit(i, { from: Math.max(1, Math.min(20, Number(e.target.value) || 1)) })} /></label>
                  <label className="field"><span>Name (optional)</span>
                    <input type="text" value={b.label ?? ""} maxLength={30} onChange={(e) => edit(i, { label: e.target.value })} /></label>
                </div>
                <div className="tiles">
                  {(["text", "background", "border"] as const).map((k) => (
                    <label key={k} className="tile"><span className="swatches"><input type="color" value={b[k]}
                      onChange={(e) => edit(i, { [k]: e.target.value })} /></span>
                      <span className="tile-label">{k === "text" ? "Number" : k === "background" ? "Background" : "Border"}</span>
                      <span className="tile-sub mono">{b[k]}</span></label>))}
                </div>
                {bands.length > 2 && <button className="link small" onClick={() => setBands((bs) => bs.filter((_, j) => j !== i))}>Remove band</button>}
              </div>
            </details>);
        })}
        {bands.length > 0 && <div className="row wrap">
          {bands.length < 6 && <button onClick={() => setBands((bs) => sorted([...bs, { ...sorted(bs)[0], from: Math.min(20, sorted(bs)[0].from + 2), label: "" }]))}>
            Add band</button>}
          <span className="grow" />
          {saved.bands.length > 0 && <button className="link small" disabled={busy} onClick={() => save(null)}>Remove from skin</button>}
        </div>}
        {bands.length > 0 && <div className="apply-bar">
          <button className="primary" disabled={busy || !changed} onClick={() => save(bands)}>{busy ? "Saving…" : "Save attribute colours"}</button>
          <span className="note">Saved straight into the skin's settings file.</span>
        </div>}
        {saved.warnings.map((w) => <div key={w} className="note" style={{ color: "var(--warn)" }}>{w}</div>)}
      </div>

      <div className="stage">
        <div className="row"><h3 style={{ margin: 0 }} className="grow">Preview</h3>
          <span className="small muted">On your skin's panel colour</span></div>
        <div className="attr-preview" style={{ background: panel, color: text, padding: 16, borderRadius: 8, maxWidth: 360 }}>
          <b>Technical</b>
          {SAMPLE.map(([name, v]) => {
            const b = bandFor(bands, v);
            return <div key={name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "3px 0" }}>
              <span>{name}</span>
              <span style={{ minWidth: 30, textAlign: "center", fontWeight: 700, borderRadius: 4, padding: "1px 6px",
                color: b?.text ?? text, background: b?.background ?? "transparent", border: `1px solid ${b?.border ?? "transparent"}` }}>{v}</span>
            </div>;
          })}
        </div>
        {saved.instructions && <>
          <h4>What players are told</h4>
          <pre className="note mono" style={{ whiteSpace: "pre-wrap" }}>{saved.instructions}</pre>
        </>}
      </div>
    </div>
  );
}
