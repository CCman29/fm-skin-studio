import { useEffect, useMemo, useState } from "react";
import { call, pickFiles, type BarSetting, type Token } from "../api";
import { errorText, useToast } from "../App";
import GameInfo from "../components/GameInfo";
import { OutlineToggle } from "../components/RealPanel";
import ScreenCanvas from "../components/ScreenCanvas";
import { SettingRow } from "./GlobalSettings";
import type { Theme } from "./Workspace";

interface ScreenEntry { label: string; group: string; layout: string; backdrop: string; about: string; ownBackdrop: boolean }
type ScreenToken = Token & { onScreen: number; via: boolean; looks: "colour" | "shape" };

const GROUP_ORDER = ["Panels & surfaces", "Text", "Buttons & controls", "Tables", "Borders & lines", "Data & ratings",
  "Charts & graphs", "Tactics & pitch", "Match", "Palette", "Spacing & sizes", "Other"];
const BACKDROP_NAMES: Record<string, string> = { training: "Training screens", recruit: "Recruitment screens", club: "Club pages" };
const urlPath = (u: string) => u.match(/url\("([^"]+)"\)/)?.[1] ?? u;

/** Pick a screen, see it in the pack's look, and edit just the settings that screen uses. */
export default function ScreenEditor({ theme, packId, bars, onOpenTab, focus }: { theme: Theme; packId: string;
  bars: Record<string, BarSetting>; onOpenTab: (tab: string) => void; focus?: string | null }) {
  const toast = useToast();
  const [screens, setScreens] = useState<ScreenEntry[]>([]);
  const [layout, setLayout] = useState("Portal-Large");
  const [settings, setSettings] = useState<ScreenToken[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string[]>([]);
  const [picked, setPicked] = useState<{ classes: string[]; tokens: string[] } | null>(null);
  const [mainBackdrop, setMainBackdrop] = useState<string | null>(null);
  const [own, setOwn] = useState<Record<string, string>>({});
  const [ownImage, setOwnImage] = useState<string | null>(null);
  const [shot, setShot] = useState<string | null>(null);
  const [view, setView] = useState<"skin" | "shot" | "both">("skin");
  const [mode, setMode] = useState<"sample" | "files">("sample");
  const [version, setVersion] = useState(0);

  useEffect(() => { call<ScreenEntry[]>("editor.screens").then(setScreens).catch((e) => toast({ text: errorText(e), error: true })); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const entry = screens.find((s) => s.layout === layout);

  useEffect(() => {
    setSettings(null); setSelected(null); setHighlight([]); setPicked(null);
    call<{ settings: ScreenToken[] }>("editor.settings", { name: layout }).then((r) => setSettings(r.settings))
      .catch((e) => toast({ text: errorText(e), error: true }));
    call<string | null>("editor.shot", { layout }).then((s) => { setShot(s); if (!s) setView("skin"); }).catch(() => setShot(null));
  }, [layout]); // eslint-disable-line react-hooks/exhaustive-deps

  // backdrop pictures: the pack's main one, and this screen's own one if the pack has it
  useEffect(() => {
    const src = bars.backdrop?.mode === "image" ? bars.backdrop.source : null;
    if (src) call<string>("packs.image", { pack: packId, path: src }).then(setMainBackdrop).catch(() => setMainBackdrop(null));
    else setMainBackdrop(null);
    call<Record<string, string>>("packs.screenBackdrops", { pack: packId }).then(setOwn).catch(() => setOwn({}));
  }, [packId, bars, version]);
  useEffect(() => {
    const u = entry && own[entry.backdrop];
    if (u) call<string>("packs.image", { pack: packId, path: urlPath(u) }).then(setOwnImage).catch(() => setOwnImage(null));
    else setOwnImage(null);
  }, [entry, own, packId]);

  // arriving from a link to one setting (a warning, or a click on the Home sample): show just that setting
  useEffect(() => {
    if (!focus || focus.startsWith("bars:") || !theme.tokens.some((t) => t.name === focus)) return;
    const t = setTimeout(() => { setPicked({ classes: [], tokens: [focus] }); setSelected(focus); }, 400);
    return () => clearTimeout(t);
  }, [focus, theme.tokens]);

  useEffect(() => {
    if (!selected) return setHighlight([]);
    call<{ highlight: string[] }>("tokens.usage", { token: selected }).then((u) => setHighlight(u.highlight)).catch(() => setHighlight([]));
  }, [selected]);

  const onPick = async (classes: string[]) => {
    if (!classes.length) return;
    try { setPicked({ classes, tokens: await call<string[]>("editor.pick", { classes }) }); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };

  const shown = useMemo(() => {
    if (!settings) return [];
    if (!picked) return settings;
    const own = settings.filter((t) => picked.tokens.includes(t.name));
    const extra = theme.tokens.filter((t) => picked.tokens.includes(t.name) && !own.some((o) => o.name === t.name))
      .map((t) => ({ ...t, onScreen: 0, via: false, looks: "colour" as const }));
    return [...own, ...extra];
  }, [settings, picked, theme.tokens]);
  const groups = useMemo(() => {
    const m = new Map<string, ScreenToken[]>();
    for (const t of shown) m.set(t.group, [...(m.get(t.group) ?? []), t]);
    return [...m.entries()].sort((a, b) => GROUP_ORDER.indexOf(a[0]) - GROUP_ORDER.indexOf(b[0]));
  }, [shown]);

  const setOwnBackdrop = async (remove = false) => {
    if (!entry) return;
    const file = remove ? null : await pickFiles([{ name: "Pictures", extensions: ["png", "jpg", "jpeg"] }]);
    if (!remove && !file) return;
    try { await call("packs.screenBackdrop", { pack: packId, key: entry.backdrop, file }); setVersion(version + 1);
      toast(remove ? "This screen uses the main backdrop again" : "Backdrop set for these screens"); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const attachShot = async (remove = false) => {
    const file = remove ? null : await pickFiles([{ name: "Screenshots", extensions: ["png", "jpg", "jpeg", "webp"] }]);
    if (!remove && !file) return;
    try { await call("editor.setShot", { layout, file }); const s = await call<string | null>("editor.shot", { layout });
      setShot(s); setView(s ? "both" : "skin"); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };

  const grouped = screens.reduce<Record<string, ScreenEntry[]>>((acc, s) => ({ ...acc, [s.group]: [...(acc[s.group] ?? []), s] }), {});
  const canvas = <ScreenCanvas key={`${layout}-${version}`} packId={packId} layout={layout} bars={bars}
    backdrop={ownImage ?? mainBackdrop} header={!!entry && ["Club", "Players"].includes(entry.group)} highlight={highlight}
    onPick={onPick} editable onChanged={() => setVersion(version + 1)} mode={mode} highlightToken={selected}
    onPickTokens={(tokens) => setPicked({ classes: [], tokens })} />;

  return (
    <>
    <div className="adv-warning" role="alert"><span className="adv-warning-icon">⚠</span>
      <b>Please only use this area if you have a firm understanding of Skinning and be advised that this area is still a work in progress.</b></div>
    <div className="editor-layout">
      <div className="stack editor-left">
        <div className="card stack">
          <label className="small muted">Screen</label>
          <select value={layout} onChange={(e) => setLayout(e.target.value)}>
            {Object.entries(grouped).map(([g, list]) => <optgroup key={g} label={g}>
              {list.map((s) => <option key={s.layout} value={s.layout}>{s.label}</option>)}</optgroup>)}
          </select>
          {entry && <div className="small muted">{entry.about}</div>}
          <div className="callout small">
            <b>These are game-wide settings.</b> FM27 shares its colours across every screen, so changing one here changes it
            everywhere it's used (the "used N×" count). This list is only the settings that appear on this screen, so you can
            see their effect where it matters. Settings marked "through another setting" feed one that's on this screen.
          </div>
        </div>

        {entry && <div className="card stack">
          <h3 style={{ margin: 0 }}>This screen only</h3>
          {entry.ownBackdrop ? <>
            <div className="small">Backdrop for <b>{BACKDROP_NAMES[entry.backdrop]}</b>: {own[entry.backdrop] ? "its own picture" : "the main backdrop"}.</div>
            <div className="row"><button onClick={() => setOwnBackdrop()}>Choose a picture…</button>
              {own[entry.backdrop] && <button className="link small" onClick={() => setOwnBackdrop(true)}>Use the main backdrop</button>}</div>
            <div className="small muted">Untested in game for some screens: if FM27 doesn't show it, the main backdrop stays.</div>
          </> : <div className="small muted">This screen uses the main backdrop. FM27 doesn't mark this screen in a way a skin can
            target on its own, so its colours always come from the game-wide settings below.{" "}
            <button className="link small" onClick={() => onOpenTab("Bars & backgrounds")}>Change the main backdrop ›</button></div>}
        </div>}

        <div className="card stack">
          <h3 style={{ margin: 0 }}>Your screenshot (optional)</h3>
          <div className="small muted">Attach a screenshot of this screen from FM27 to compare it with the preview. It stays on this PC
            and is never put in the skin.</div>
          <div className="row"><button onClick={() => attachShot()}>{shot ? "Replace screenshot…" : "Attach screenshot…"}</button>
            {shot && <button className="link small" onClick={() => attachShot(true)}>Remove</button>}</div>
        </div>

        {picked && <div className="card row wrap" style={{ borderColor: "var(--accent)" }}>
          <span className="small grow">Showing the {shown.length} settings for the part you clicked
            {picked.classes.length > 0 && <span className="mono muted"> ({picked.classes.slice(0, 3).join(" ")})</span>}</span>
          <button className="link small" onClick={() => setPicked(null)}>Show all for this screen</button></div>}

        {!settings ? <div className="muted small">Finding the settings this screen uses…</div> :
          groups.map(([g, list]) => <div key={g} className="stack" style={{ gap: 6 }}>
            <div className="small muted" style={{ textTransform: "uppercase", letterSpacing: 0.6 }}>{g} · {list.length}</div>
            {list.map((t) => <SettingRow key={t.name} token={t} theme={theme} selected={selected === t.name}
              onSelect={() => setSelected(selected === t.name ? null : t.name)}
              note={t.via ? "Through another setting on this screen · changes every screen"
                : `On this screen in ${t.onScreen} style rule${t.onScreen === 1 ? "" : "s"} · changes every screen`} />)}
          </div>)}
        <details className="card"><summary><b>Game and game index</b> <span className="small muted">· where FM27 was found, rebuild the index
          after a game update</span></summary><div style={{ marginTop: 12 }}><GameInfo /></div></details>
      </div>

      <div className="sticky stack editor-right">
        <div className="tabs">
          <button className={view === "skin" ? "active" : ""} onClick={() => setView("skin")}>Skin preview</button>
          {shot && <button className={view === "both" ? "active" : ""} onClick={() => setView("both")}>Side by side</button>}
          {shot && <button className={view === "shot" ? "active" : ""} onClick={() => setView("shot")}>Your screenshot</button>}
          <span className="grow" />
          <OutlineToggle />
          <select value={mode} onChange={(e) => setMode(e.target.value as "sample" | "files")} title="How panels are drawn">
            <option value="sample">Styled sample panels</option><option value="files">Panel frames from game files</option></select>
        </div>
        {mode === "files" && <div className="small" style={{ color: "var(--warn)" }}>Game-file view: FM27 fills these panels with your save's data while
          it runs, so the files only hold empty frames and placeholder labels. Use it to check frames and spacing; the styled samples show colours better.</div>}
        <div className="small muted">The screen's real layout (panel positions and sizes from your game files) with sample content in this pack's colours. Click any
          part to list the settings that paint it; select a setting to outline where it appears. Drag panel edges to resize.</div>
        {view !== "shot" && canvas}
        {view !== "skin" && shot && <img src={shot} alt="Your FM27 screenshot" style={{ width: "100%", borderRadius: 8, border: "1px solid var(--line)" }} />}
      </div>
    </div>
    </>
  );
}
