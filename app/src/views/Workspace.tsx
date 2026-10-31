import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { call, type BarSetting, type FontCatalog, type Pack, type Token } from "../api";
import { errorText, useToast } from "../App";
import ScreenCanvas from "../components/ScreenCanvas";
import ThemePicker from "../components/ThemePicker";
import UpdateBadge from "../components/UpdateBadge";
import WindowControls from "../components/WindowControls";
import ExitButton from "../components/ExitButton";
import SupportButton from "../components/SupportButton";
import { setPreviewOverrides } from "../components/RealPanel";
import LightWarningBanner from "../components/LightWarningBanner";
import { lightWarnings } from "../lightWarnings";
import Bars from "./Bars";
import Fonts from "./Fonts";
import GamePainted from "./GamePainted";
import GlobalSettings from "./GlobalSettings";
import Publish from "./Publish";
import ScreenEditor from "./ScreenEditor";
import Screens from "./Screens";

// "Screens & layouts" (the full list of ~1,800 layouts) is hidden for now; its code is kept in Screens.tsx.
const TABS = ["Global settings", "Bars & backgrounds", "Fonts", "Game-painted areas", "Advanced Editor", "Check and Save"] as const;
const SHOW_LAYOUTS_TAB = false;
type Tab = (typeof TABS)[number] | "Screens & layouts";
export interface DraftStatus { open: boolean; dirty: boolean; resumed?: boolean; backupFolder?: string | null;
  skinsFolder?: string | null; skinsFolderFound?: boolean;
  changes: { added: string[]; removed: string[]; changed: string[] } }

export interface Theme {
  tokens: Token[];
  overrides: Record<string, string>;
  value: (name: string) => string;
  setTokens: (changes: Record<string, string | null>) => void;
}

export default function Workspace({ packId, onClose }: { packId: string; onClose: () => void }) {
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("Global settings");
  const [pack, setPack] = useState<Pack | null>(null);
  const [tokens, setTokenList] = useState<Token[]>([]);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [bars, setBars] = useState<Record<string, BarSetting>>({});
  const [fonts, setFonts] = useState<FontCatalog | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [screenTarget] = useState<{ layout: string; highlight: string[] } | null>(null);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<DraftStatus | null>(null);
  const refreshDraft = useCallback(() => {
    call<DraftStatus>("drafts.status", { pack: packId }).then(setDraft).catch(() => {});
  }, [packId]);
  const pendingRef = useRef<Record<string, string | null>>({});
  const timerRef = useRef<number>();

  const reloadPack = useCallback(async () => {
    const p = await call<Pack>("packs.get", { pack: packId });
    setPack(p); setOverrides(p.tokens);
  }, [packId]);

  useEffect(() => {
    (async () => {
      try {
        // edits go to a working copy; the real skin only changes when it's saved in Check and Save
        const d = await call<DraftStatus>("drafts.open", { pack: packId });
        setDraft(d);
        if (d.resumed && d.dirty) toast("You have unsaved changes from last time. Save them in Check and Save, or discard them there.");
        await reloadPack();
        const [t, b, f] = await Promise.all([call<Token[]>("tokens.list"), call<Record<string, BarSetting>>("packs.bars", { pack: packId }),
          call<FontCatalog>("fonts.catalog")]);
        setTokenList(t); setBars(b); setFonts(f);
      } catch (e) { toast({ text: errorText(e), error: true }); }
    })();
  }, [packId]); // eslint-disable-line react-hooks/exhaustive-deps

  // colours being tried in Global settings (not applied yet) show on top of the pack's own settings
  const [trial, setTrial] = useState<{ tokens: Record<string, string>; bars: Record<string, BarSetting> } | null>(null);
  useEffect(() => setPreviewOverrides(trial ? { ...overrides, ...trial.tokens } : overrides), [overrides, trial]);
  const defaults = useMemo(() => Object.fromEntries(tokens.map((t) => [t.name, t.default])), [tokens]);
  const value = useCallback((name: string): string => {
    let cur = name, guard = 0;
    while (guard++ < 20) {
      const raw = overrides[cur] ?? defaults[cur];
      if (raw === undefined) return "transparent";
      const m = raw.match(/^var\((--[\w-]+)/);
      if (!m) return raw;
      cur = m[1];
    }
    return "transparent";
  }, [overrides, defaults]);

  const flush = useCallback(async () => {
    const changes = pendingRef.current;
    pendingRef.current = {};
    if (!Object.keys(changes).length) return;
    setSaving(true);
    try { setOverrides(await call<Record<string, string>>("packs.setTokens", { pack: packId, changes })); }
    catch (e) { toast({ text: errorText(e), error: true }); reloadPack(); }
    setSaving(false);
    refreshDraft();
  }, [packId, reloadPack, toast, refreshDraft]);
  useEffect(() => {  // other tabs write pictures and sheets too; keep the unsaved-changes note current
    const t = window.setInterval(refreshDraft, 4000);
    return () => window.clearInterval(t);
  }, [refreshDraft]);

  const setTokens = useCallback((changes: Record<string, string | null>) => {
    setOverrides((cur) => {
      const next = { ...cur };
      for (const [k, v] of Object.entries(changes)) { if (v === null) delete next[k]; else next[k] = v; }
      return next;
    });
    Object.assign(pendingRef.current, changes);
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(flush, 350);
  }, [flush]);

  const rename = async () => {
    const name = window.prompt("Skin name shown in FM27's Preferences:", pack?.name);
    if (!name) return;
    try { setPack(await call<Pack>("packs.rename", { pack: packId, name })); } catch (e) { toast({ text: errorText(e), error: true }); }
  };

  // pictures for every area drawn as a picture: ones in the skin, or ones just picked (not applied yet)
  const [barImages, setBarImages] = useState<Record<string, string>>({});
  useEffect(() => {
    let live = true;
    (async () => {
      const out: Record<string, string> = {};
      for (const [area, b] of Object.entries(bars)) {
        if (b?.mode !== "image" || !b.source) continue;
        const inPack = !/^[a-zA-Z]:[\\/]|^[\\/]/.test(b.source);
        try { out[area] = await call<string>(inPack ? "packs.image" : "preview.localImage", inPack ? { pack: packId, path: b.source } : { path: b.source }); }
        catch { /* preview only */ }
      }
      if (live) setBarImages(out);
    })();
    return () => { live = false; };
  }, [bars, packId]);
  const backdrop = barImages.backdrop ?? null;
  // pointing at a colour in Global settings lights up what it changes in the preview
  const [fieldTokens, setFieldTokens] = useState<Record<string, string[]>>({});
  useEffect(() => { call<Record<string, string[]>>("recipe.fields").then(setFieldTokens).catch(() => {}); }, []);
  const [hoverField, setHoverField] = useState<string | null>(null);
  const [barArea, setBarArea] = useState<string | null>(null);  // Bars & backgrounds: the area being edited
  const AREA_OF: Record<string, string> = { top_bar: "topBar", sub_bar: "subBar", page_header: "pageHeader", backdrop: "backdrop",
    continue_colour: "continue" };
  const hoverTokens = hoverField ? fieldTokens[hoverField] ?? [] : [];
  const hoverAreas = hoverField && AREA_OF[hoverField] ? [AREA_OF[hoverField]] : [];
  const openTab = (t: string, focusOn?: string) => { setTab(t as Tab); if (focusOn) setFocus(focusOn); };

  const onPick = (token: string) => {
    if (token.startsWith("bars:")) { setTab("Bars & backgrounds"); setFocus(token.slice(5)); return; }
    setTab("Advanced Editor"); setFocus(token);  // single settings are fine-tuned in the Advanced Editor
  };

  const theme: Theme = { tokens, overrides, value, setTokens };
  const warnings = useMemo(() => lightWarnings(overrides, value, bars), [overrides, value, bars]);
  const banner = <LightWarningBanner warnings={warnings} onGo={onPick} />;
  // one read-only preview for Global settings, Bars & backgrounds and Fonts: it shows changes live, clicks do nothing
  const preview = (
    <div className="stack" style={{ gap: 8 }}>
      <div className="small muted">Preview: the Home screen with your changes. It updates as you make them.</div>
      <ScreenCanvas packId={packId} layout="Portal-Large" bars={trial ? { ...bars, ...trial.bars } : bars} backdrop={backdrop} images={barImages}
        header={tab === "Bars & backgrounds"} highlightTokens={tab === "Global settings" ? hoverTokens : []}
        highlightAreas={tab === "Global settings" ? hoverAreas : tab === "Bars & backgrounds" && barArea ? [barArea] : []} />
    </div>);


  return (
    <div className="app">
      <div className="topbar">
        <button className="icon-btn" title="Back to your skins (unsaved changes are kept)" onClick={onClose}>←</button>
        <button className="skin-name" title="Rename this skin" onClick={rename}>{pack?.name ?? packId}<span className="pencil">✎</span></button>
        <nav className="tabs">{TABS.map((t) => <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>{t}</button>)}</nav>
        <div className="top-right">
          {draft?.dirty
            ? <button className="status-chip unsaved" title="Save in Check and Save" onClick={() => setTab("Check and Save")}>● Unsaved</button>
            : <span className="status-chip" title="All changes are saved to your skins folder">{saving ? "Updating…" : "✓ Saved"}</span>}
          <SupportButton compact /><UpdateBadge /><ThemePicker /><ExitButton /><WindowControls />
        </div>
      </div>
      <div className="main">
        {!pack || !tokens.length ? <div className="muted">Loading…</div> : <>
          {tab === "Global settings" && <GlobalSettings preview={preview} banner={banner} packId={packId}
            onPreview={(tokens, previewBars) => setTrial(tokens ? { tokens, bars: previewBars ?? {} } : null)} onHover={setHoverField}
            initial={(pack.info?.recipe as Record<string, unknown> | undefined) ?? null}
            backdropImage={bars.backdrop?.mode === "image" ? bars.backdrop.source ?? null : null} onOpenTab={openTab}
            onApplied={async () => { await reloadPack(); setBars(await call<Record<string, BarSetting>>("packs.bars", { pack: packId })); refreshDraft(); }} />}
          {tab === "Advanced Editor" && <ScreenEditor theme={theme} packId={packId} bars={bars} onOpenTab={openTab} focus={focus} />}
          {tab === "Game-painted areas" && <GamePainted packId={packId} onOpenTab={openTab} theme={theme} bars={bars} barImages={barImages} />}
          {tab === "Bars & backgrounds" && <Bars packId={packId} bars={bars} setBars={setBars} focus={focus} preview={preview} banner={banner}
            onDiscard={async () => setBars(await call<Record<string, BarSetting>>("packs.bars", { pack: packId }))} onArea={setBarArea} />}
          {tab === "Fonts" && fonts && <Fonts catalog={fonts} theme={theme} packId={packId} preview={preview} />}
          {SHOW_LAYOUTS_TAB && tab === "Screens & layouts" && <Screens packId={packId} onChanged={reloadPack} target={screenTarget} />}
          {tab === "Check and Save" && <Publish pack={pack} draft={draft} onChanged={async () => {
            await reloadPack(); setBars(await call<Record<string, BarSetting>>("packs.bars", { pack: packId })); refreshDraft(); }} />}
        </>}
      </div>
    </div>
  );
}
