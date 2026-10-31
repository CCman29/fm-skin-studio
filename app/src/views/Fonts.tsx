import type { ReactNode } from "react";
import { call, type FontCatalog } from "../api";
import { errorText, useToast } from "../App";
import type { Theme } from "./Workspace";

const ROLES: [string, string, string][] = [
  ["body", "--typography-family-primary", "Body text — most of the interface"],
  ["condensed", "--typography-family-condensed", "Small labels — table headers, pitch roles"],
  ["headings", "--typography-family-thematic", "Headings and the top menu"],
];

export default function Fonts({ catalog, theme, packId, preview }: {
  catalog: FontCatalog; theme: Theme; packId: string; preview?: ReactNode;
}) {
  const toast = useToast();
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
