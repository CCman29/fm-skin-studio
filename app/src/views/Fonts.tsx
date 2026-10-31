import { useEffect, useState, type ReactNode } from "react";
import { call, type FontCatalog } from "../api";
import { errorText, useToast } from "../App";
import { parseColour } from "../colour";
import ColorInput from "../components/ColorInput";
import type { Theme } from "./Workspace";

const ROLES: [string, string, string][] = [
  ["body", "--typography-family-primary", "Body text — most of the interface"],
  ["condensed", "--typography-family-condensed", "Small labels — table headers, pitch roles"],
  ["headings", "--typography-family-thematic", "Headings and the top menu"],
];

// the skin's own text colours; names of clubs, teams and players are coloured by the game and stay white
const TEXT_COLOURS: [string, string][] = [
  ["--global-text-primary", "Main text — most labels and values"],
  ["--global-text-secondary", "Secondary text — hints, captions, inactive labels"],
  ["--brand-theme-accent", "Highlighted text — budgets, key figures and accents"],
  ["--layout-tiles-heading", "Tile headings — titles on the home screen tiles"],
  ["--layout-surfaces-breadcrumb-title-active", "Page title — the current page in the breadcrumb"],
  ["--layout-surfaces-breadcrumb-title-inactive", "Earlier pages in the breadcrumb"],
  ["--modal-text-primary", "Pop-up text"],
];

export default function Fonts({ catalog, theme, packId, preview }: {
  catalog: FontCatalog; theme: Theme; packId: string; preview?: ReactNode;
}) {
  const toast = useToast();
  const [system, setSystem] = useState<{ names?: string }>({});
  useEffect(() => { call<{ names?: string }>("packs.systemText", { pack: packId }).then(setSystem).catch(() => setSystem({})); }, [packId]);
  const setNames = async (v: string | null) => {
    const hex = v ? toHex6(v) : null;
    try { setSystem(await call<{ names?: string }>("packs.setSystemText", { pack: packId, names: hex })); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const choose = async (fontId: string, role: string, token: string) => {
    try {
      await call("packs.useBuiltinFont", { pack: packId, font: fontId, role });
      const font = catalog.builtin.find((f) => f.id === fontId)!;
      theme.setTokens({ [token]: font.token === token ? null : `var(${font.token})` });
    } catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const current = (token: string) => {
    const v = theme.overrides[token];
    return catalog.builtin.find((f) => (v ? `var(${f.token})` === v : f.token === token))?.id;
  };

  return (
    <div className={preview ? "studio" : "studio solo"}>
      <div className="inspector">
        <div className="note">FM27 can only use its own four fonts in skins, so this picks which one each kind of text uses.</div>
        <details className="section" open>
          <summary>Fonts</summary>
          <div className="body">
            {ROLES.map(([role, token, label]) => (
              <label key={role} className="field"><span>{label}</span>
                <select value={current(token) ?? ""} onChange={(e) => choose(e.target.value, role, token)}>
                  {catalog.builtin.map((f) => <option key={f.id} value={f.id}>{f.family}{f.note ? ` (${f.note})` : ""}</option>)}
                </select></label>))}
          </div>
        </details>
        <details className="section" open>
          <summary>Text colours</summary>
          <div className="body">
            {TEXT_COLOURS.map(([token, label]) => (
              <div key={token} className="field"><span>{label}</span>
                <div className="row">
                  <ColorInput value={theme.overrides[token] ?? null} fallback={theme.value(token)}
                    onChange={(v) => theme.setTokens({ [token]: v })} />
                  {theme.overrides[token] && <button className="link small" onClick={() => theme.setTokens({ [token]: null })}>Reset to game default</button>}
                </div></div>))}
            <div className="note">Club, team and player names are coloured by FM27 itself (white, orange for your club), so
              keep panels dark enough for white text whatever you choose here.</div>
          </div>
        </details>
        <details className="section" open>
          <summary>System text colours (Game Link)</summary>
          <div className="body">
            <div className="field"><span>Club, team and player names — every clickable name</span>
              <div className="row">
                <ColorInput value={system.names ?? null} fallback="#ffffff" onChange={(v) => setNames(v)} />
                {system.names && <button className="link small" onClick={() => setNames(null)}>Reset to game default</button>}
              </div></div>
            <div className="callout small stack" style={{ gap: 6 }}>
              <b>These colours are applied by Game Link, not by the skin files.</b>
              <span>They show in FM27 only on PCs with Game Link installed (Advanced Editor → Game Link), while this skin is
                selected. Switch FM27 to another skin and the names go back to the game's own colours; to get those back with
                this skin, choose Reset to game default here and save.</span>
              <span>After you save a change, restart FM27 to see it everywhere: names already on screen keep their old colour
                until the game draws them again.</span>
              <span>One colour is used for every name, so your own club is no longer shown in orange while it's set. Useful for
                light skins, where white names would be unreadable.</span>
            </div>
          </div>
        </details>
        <details className="section">
          <summary>Free fonts</summary>
          <div className="body">
            <span className={`badge ${catalog.fontFilesWork ? "ok" : "warn"}`} style={{ alignSelf: "flex-start" }}>
              {catalog.fontFilesWork ? "Available" : "Waiting on FM27 fix"}</span>
            <div className="note">{catalog.fontFilesWork ? "Bundled, licence-free (SIL OFL) fonts matched to the game's spacing."
              : "FM27 can't load font files from skins yet (a game bug). These licence-free fonts switch on once Sports Interactive fixes it."}</div>
            {catalog.fonts.map((f) => <div key={f.id} className="small" style={{ opacity: catalog.fontFilesWork ? 1 : 0.55 }}>{f.family}
              <span className="muted"> · {f.role}</span></div>)}
          </div>
        </details>
      </div>
      {preview && <div className="stage">{preview}</div>}
    </div>
  );
}

/** "#rrggbb" from whatever the colour picker returns (rgb()/rgba()/#hex); names have no transparency. */
function toHex6(v: string): string | null {
  const c = parseColour(v);
  if (!c) return null;
  const h = (n: number) => Math.round(n).toString(16).padStart(2, "0");
  return `#${h(c.r)}${h(c.g)}${h(c.b)}`;
}
