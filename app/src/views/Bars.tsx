import { useEffect, useRef, useState, type ReactNode } from "react";
import { call, pickFiles, type BarSetting } from "../api";
import { errorText, useToast } from "../App";

const AREAS: [string, string, string][] = [
  ["topBar", "Top menu bar", "The bar with Portal, Squad, Tactics…"],
  ["subBar", "Sub menu bar", "The thinner bar under it."],
  ["pageHeader", "Page header", "Club, player and team pages."],
  ["backdrop", "Background", "Behind all the boxes."],
];
const MODES: [BarSetting["mode"], string][] = [["club", "Club colours (game default)"], ["solid", "Solid colour"], ["gradient", "Gradient"],
  ["image", "My own picture"]];

function swatch(s: BarSetting | undefined): string {
  if (!s || s.mode === "club") return "repeating-linear-gradient(45deg, #8a1c26 0 6px, #5a0d14 6px 12px)";
  if (s.mode === "image") return "repeating-linear-gradient(45deg, #444 0 6px, #666 6px 12px)";
  const [a, b] = s.colours ?? ["#000000"];
  return s.mode === "gradient" && b ? `linear-gradient(90deg, ${a}, ${b})` : a;
}

/** Bars & backgrounds: pick an area, set how it's drawn; the preview follows live. Apply stores it as an unsaved change. */
export default function Bars({ packId, bars, setBars, focus, preview, banner, onDiscard, onArea }: {
  packId: string; bars: Record<string, BarSetting>; setBars: (b: Record<string, BarSetting>) => void;
  focus: string | null; preview?: ReactNode; banner?: ReactNode; onDiscard: () => void;
  onArea?: (area: string | null) => void;  // the area being edited (or pointed at), lit up in the preview
}) {
  const toast = useToast();
  const [draft, setDraft] = useState<Record<string, BarSetting>>(bars);
  const [area, setArea] = useState(focus && AREAS.some(([a]) => a === focus) ? focus : "topBar");
  const [busy, setBusy] = useState(false);
  const dirty = useRef(false);
  const [hovered, setHovered] = useState<string | null>(null);
  useEffect(() => { onArea?.(hovered ?? area); }, [area, hovered]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onArea?.(null), []); // eslint-disable-line react-hooks/exhaustive-deps
  // leaving without applying drops the trial settings, so the preview elsewhere shows the skin as it is
  useEffect(() => () => { if (dirty.current) onDiscard(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const update = (patch: Partial<BarSetting>) => {
    const next = { ...draft, [area]: { ...(draft[area] ?? { mode: "club" }), ...patch } };
    dirty.current = true;
    setDraft(next); setBars(next);  // the preview follows straight away
  };
  const apply = async () => {
    setBusy(true);
    try {
      const saved = await call<Record<string, BarSetting>>("packs.setBars", { pack: packId, settings: draft });
      dirty.current = false;
      setDraft(saved); setBars(saved); toast("Applied. Press Save skin in Check and Save to put it in FM27.");
    } catch (e) { toast({ text: errorText(e), error: true }); }
    setBusy(false);
  };
  const choosePicture = async () => {
    const file = await pickFiles([{ name: "Pictures", extensions: ["png", "jpg", "jpeg"] }]);
    if (file) update({ mode: "image", source: file });
  };

  const s = draft[area] ?? { mode: "club" as const };
  const colours = s.colours ?? ["#003322", "#00664a"];
  const label = AREAS.find(([a]) => a === area)!;
  return (
    <div className={preview ? "studio" : "studio solo"}>
      <div className="inspector">
        {banner}
        <div className="note">FM27 paints these areas in your club's colours. A skin can cover them with its own colour, gradient or picture.</div>
        <details className="section" open>
          <summary>Area</summary>
          <div className="body">
            <div className="tiles">{AREAS.map(([a, name, hint]) => (
              <button key={a} className={`tile ${area === a ? "active" : ""}`} title={hint} onClick={() => setArea(a)}
                onMouseEnter={() => setHovered(a)} onMouseLeave={() => setHovered(null)}>
                <span style={{ height: 22, borderRadius: 4, background: swatch(draft[a]), border: "1px solid var(--swatch-line)" }} />
                <span className="tile-label">{name}</span>
                <span className="tile-sub">{MODES.find(([m]) => m === (draft[a]?.mode ?? "club"))?.[1]}</span>
              </button>))}</div>
          </div>
        </details>
        <details className="section" open>
          <summary>{label[1]}</summary>
          <div className="body">
            <div className="note">{label[2]}</div>
            <label className="field"><span>Drawn as</span>
              <select value={s.mode} onChange={(e) => update({ mode: e.target.value as BarSetting["mode"], colours })}>
                {MODES.map(([m, name]) => <option key={m} value={m}>{name}</option>)}</select></label>
            {(s.mode === "solid" || s.mode === "gradient") && <div className="tiles">
              <label className="tile"><span className="swatches"><input type="color" value={colours[0]}
                onChange={(e) => update({ colours: [e.target.value, colours[1] ?? e.target.value] })} /></span>
                <span className="tile-label">{s.mode === "gradient" ? "From" : "Colour"}</span></label>
              {s.mode === "gradient" && <label className="tile"><span className="swatches"><input type="color" value={colours[1] ?? colours[0]}
                onChange={(e) => update({ colours: [colours[0], e.target.value] })} /></span><span className="tile-label">To</span></label>}
            </div>}
            {s.mode === "gradient" && <label className="field"><span>Direction</span>
              <select value={s.angle ?? "horizontal"} onChange={(e) => update({ angle: e.target.value })}>
                <option value="horizontal">Left to right</option><option value="vertical">Top to bottom</option><option value="diagonal">Diagonal</option>
              </select></label>}
            {area === "backdrop" && (s.mode === "solid" || s.mode === "gradient") && <label className="row small">
              <input type="checkbox" checked={!!s.stripes} onChange={(e) => update({ stripes: e.target.checked })} />Diagonal stripes
              {s.stripes && <input type="color" className="colour-input" value={s.stripeColour ?? "#14303a"}
                onChange={(e) => update({ stripeColour: e.target.value })} />}</label>}
            {s.mode === "image" && <>
              <button onClick={choosePicture}>Choose picture…</button>
              <span className="note mono">{s.source ? s.source.split(/[\/]/).pop() : "Uses the picture already in the skin"}</span></>}
          </div>
        </details>
        <div className="apply-bar">
          <button className="primary" disabled={busy} onClick={apply}>{busy ? "Applying…" : "Apply bars & backgrounds"}</button>
          <span className="note">Applied changes are saved with your other changes in Check and Save.</span>
        </div>
      </div>
      {preview && <div className="stage">{preview}</div>}
    </div>
  );
}
