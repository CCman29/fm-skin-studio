import type { ReactNode } from "react";
import type { Token } from "../api";
import { formatColour, fromHex, parseColour, toHex } from "../colour";
import ThemeRecipe, { type PreviewFn } from "../components/ThemeRecipe";
import type { Theme } from "./Workspace";

/** Always-visible colour picker + opacity for one setting. */
export function ColourField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const c = parseColour(value) ?? { r: 0, g: 0, b: 0, a: 1 };
  return (
    <div className="row" style={{ gap: 6 }} onClick={(e) => e.stopPropagation()}>
      <input type="color" className="colour-input" value={toHex(c)} title="Pick a colour"
        onChange={(e) => onChange(formatColour(fromHex(e.target.value, c.a)))} />
      <input type="range" min={0} max={100} value={Math.round(c.a * 100)} title={`Opacity ${Math.round(c.a * 100)}%`}
        style={{ width: 70 }} onChange={(e) => onChange(formatColour({ ...c, a: +e.target.value / 100 }))} />
      <span className="small muted" style={{ width: 34, textAlign: "right" }}>{Math.round(c.a * 100)}%</span>
    </div>
  );
}

export function SettingRow({ token, theme, selected, onSelect, note }: { token: Token; theme: Theme; selected: boolean; onSelect: () => void;
  note?: string }) {
  const override = theme.overrides[token.name] ?? null;
  const shown = theme.value(token.name);
  const isColour = !token.technical && !!parseColour(shown);
  return (
    <div className={`setting-row ${override ? "changed" : ""} ${selected ? "selected" : ""}`} id={`tok-${token.name}`} onClick={onSelect}>
      {isColour ? <ColourField value={shown} onChange={(v) => theme.setTokens({ [token.name]: v })} />
        : <input type="text" style={{ width: 160 }} placeholder={token.default} defaultValue={override ?? ""} onClick={(e) => e.stopPropagation()}
            onBlur={(e) => { const v = e.target.value.trim() || null; if (v !== override) theme.setTokens({ [token.name]: v }); }} />}
      <div className="grow" style={{ minWidth: 0 }}>
        <div className="setting-label">{token.label}{override && <span className="badge ok" style={{ marginLeft: 8 }}>changed</span>}</div>
        <div className="small muted">{token.description || (token.usedFor ? `Colours ${token.usedFor}` : "")}
          {token.description && token.usedFor ? ` · colours ${token.usedFor}` : ""} · used {token.useCount}×</div>
        {note && <div className="small" style={{ color: "var(--info)" }}>{note}</div>}
        <div className="mono muted" style={{ fontSize: 11 }}>{token.name}</div>
      </div>
      {override && <button className="link small" onClick={(e) => { e.stopPropagation(); theme.setTokens({ [token.name]: null }); }}>Reset</button>}
    </div>
  );
}

/** The skin's core look in one place: a few colours applied everywhere FM27 allows. Individual settings live in the
 *  Advanced Editor, where each one is shown on the screens that use it. */
export default function GlobalSettings({ preview, banner, packId, onApplied, initial, backdropImage, onOpenTab, onPreview, onHover }: {
  preview: ReactNode; banner?: ReactNode; packId: string; onApplied: () => void; initial?: Record<string, unknown> | null;
  backdropImage?: string | null; onOpenTab: (tab: string) => void; onPreview: PreviewFn; onHover: (field: string | null) => void }) {
  return (
    <div className="studio">
      <div className="inspector">
        {banner}
        <div className="note">The main colours of your skin. FM27 shares them across every screen, so one change here restyles the whole game.
          To fine-tune a single colour, use the <button className="link small" onClick={() => onOpenTab("Advanced Editor")}>Advanced Editor</button>.</div>
        <ThemeRecipe packId={packId} onApplied={onApplied} initial={initial} backdropImage={backdropImage} onPreview={onPreview} onHover={onHover} />
      </div>
      <div className="stage">{preview}</div>
    </div>
  );
}
