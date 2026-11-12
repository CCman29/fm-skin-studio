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
  // options are "game:<id>" (FM27's own fonts, nothing copied) or "file:<id>" (a free font copied into the skin)
  const choose = async (option: string, role: string, token: string) => {
    const [kind, id] = [option.slice(0, option.indexOf(":")), option.slice(option.indexOf(":") + 1)];
    try {
      if (kind === "game") {
        await call("packs.useBuiltinFont", { pack: packId, font: id, role });
        const font = catalog.builtin.find((f) => f.id === id)!;
        theme.setTokens({ [token]: font.token === token ? null : `var(${font.token})` });
      } else {
        const r = await call<{ font: { file: string } }>("packs.useFont", { pack: packId, font: id, role });
        theme.setTokens({ [token]: `url("assets/fonts/${r.font.file}")` });
      }
    } catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const current = (token: string) => {
    const v = theme.overrides[token];
    const file = v?.match(/assets\/fonts\/([^"')]+)/)?.[1];
    if (file) { const f = catalog.fonts.find((x) => x.file === file); return f ? `file:${f.id}` : `own:${file}`; }
    const game = catalog.builtin.find((f) => (v ? `var(${f.token})` === v : f.token === token));
    return game ? `game:${game.id}` : "";
  };
  const roleOf: Record<string, string> = { body: "body", condensed: "condensed", headings: "headings" };

  return (
    <div className={preview ? "studio" : "studio solo"}>
      <div className="inspector">
        <div className="note">Pick the font for each kind of text: one of FM27's own fonts, or a free font that's copied into
          the skin. Free fonts were chosen to match the game's spacing, so text still fits.</div>
        <details className="section" open>
          <summary>Fonts</summary>
          <div className="body">
            {ROLES.map(([role, token, label]) => {
              const value = current(token);
              return <label key={role} className="field"><span>{label}</span>
                <select value={value} onChange={(e) => choose(e.target.value, role, token)}>
                  {value.startsWith("own:") && <option value={value}>Your font file ({value.slice(4)})</option>}
                  <optgroup label="FM27's fonts">
                    {catalog.builtin.map((f) => <option key={f.id} value={`game:${f.id}`}>{f.family}{f.note ? ` (${f.note})` : ""}</option>)}
                  </optgroup>
                  <optgroup label="Free fonts (copied into the skin)">
                    {[...catalog.fonts].sort((a, b) => (a.role === roleOf[role] ? 0 : 1) - (b.role === roleOf[role] ? 0 : 1))
                      .map((f) => <option key={f.id} value={`file:${f.id}`}>{f.family}{f.role === roleOf[role] ? "" : ` (made for ${f.role})`}</option>)}
                  </optgroup>
                </select></label>;
            })}
          </div>
        </details>
        <details className="section">
          <summary>About free fonts</summary>
          <div className="body">
            <div className="note">They're open-licence (SIL OFL) fonts: the licence file goes into the skin with the font, so you can share
              the skin. A skin with a font file also switches FM27's buttons, tooltips and chart labels to the text engine
              that can draw it; without that, FM27's log fills with warnings. The studio adds that rule for you.</div>
            <div className="note">Bold text uses FM27's bold styling of the font you pick, so it may look slightly different from the
              game's own bold weight.</div>
          </div>
        </details>
      </div>
      {preview && <div className="stage">{preview}</div>}
    </div>
  );
}
