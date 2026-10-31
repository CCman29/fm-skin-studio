import { useEffect, useState } from "react";
import { call, pickFiles } from "../api";
import { errorText, useToast } from "../App";

interface Area { id: string; title: string; where: string; drivenBy: string; skin: string | null; kind: "bars" | "image" | null;
  area?: string; size?: string; hide?: string; cannot?: string; tested?: boolean; state: { mode: string; url?: string } }

/** Parts of FM27 the game paints from its own code: what drives each one, what a skin can do about it, and what it can't. */
export default function GamePainted({ packId, onOpenTab }: { packId: string; onOpenTab: (tab: string, focus?: string) => void }) {
  const toast = useToast();
  const [data, setData] = useState<{ areas: Area[]; logicNote: string } | null>(null);
  useEffect(() => { call<{ areas: Area[]; logicNote: string }>("coded.list", { pack: packId }).then(setData)
    .catch((e) => toast({ text: errorText(e), error: true })); }, [packId]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = async (a: Area, mode: "image" | "hide" | "default") => {
    let file: string | null = null;
    if (mode === "image") {
      file = await pickFiles([{ name: "Pictures", extensions: ["png", "jpg", "jpeg"] }]);
      if (!file) return;
    }
    if (mode === "hide" && !window.confirm(`Hide the game's ${a.title.toLowerCase()}? The panel colour shows instead.`)) return;
    try { setData(await call("coded.set", { pack: packId, area: a.id, mode, file })); toast("Saved to the pack"); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };

  if (!data) return <div className="muted">Loading…</div>;
  return (
    <div className="stack">
      <div className="card stack intro-strong">
        <h2 style={{ margin: 0 }}>Game-painted areas: read this first</h2>
        <p>Most of FM27's look comes from stylesheets, which a skin can change freely. These parts are different: the game's code decides
          how they look while it runs (club colours, the story you're reading, the competition you're on). A skin can't change that code,
          but it can often draw its own picture over the area or hide the painted layer.</p>
      </div>
      <div className="coded-grid">
      {data.areas.map((a) => (
        <div key={a.id} className="card coded-area">
          <div className="row"><h3 className="grow" style={{ margin: 0, color: "var(--text)" }}>{a.title}</h3>
            {a.kind === null ? <span className="badge err">Skin can't change</span>
              : a.tested === false ? <span className="badge warn">Untested in game</span> : <span className="badge ok">Works</span>}</div>
          <div className="small muted">{a.where}</div>
          <div className="small"><b>What drives it:</b> {a.drivenBy}</div>
          {a.skin && <div className="small"><b>What a skin can do:</b> {a.skin}{a.size ? ` Suggested picture size: ${a.size}.` : ""}</div>}
          {a.cannot && <div className="small" style={{ color: "var(--warn)" }}><b>Why not:</b> {a.cannot}</div>}
          <div className="grow-space" />
          {a.kind === "bars" && <div><button onClick={() => onOpenTab("Bars & backgrounds", a.area)}>Set it in Bars & backgrounds ›</button></div>}
          {a.kind === "image" && <div className="row wrap">
            <span className="small muted">Now: {a.state.mode === "image" ? "your picture" : a.state.mode === "hide" ? "hidden" : "game default"}</span>
            <button onClick={() => set(a, "image")}>{a.state.mode === "image" ? "Replace picture…" : "Use a picture…"}</button>
            {a.hide && a.state.mode !== "hide" && <button onClick={() => set(a, "hide")}>Hide it</button>}
            {a.state.mode !== "default" && <button className="link small" onClick={() => set(a, "default")}>Back to game default</button>}
          </div>}
          {a.kind === "image" && a.tested === false && <div className="small muted">Not confirmed in FM27 yet: if nothing changes in game,
            reset it to the game default.</div>}
        </div>))}
      </div>
      <div className="card stack light-warning">
        <h3 style={{ margin: 0, color: "var(--warn)" }}>Can I change the logic behind these areas?</h3>
        <div className="small">{data.logicNote}</div>
        <div className="small muted">What you can do instead: cover an area with a picture, hide it, keep surfaces dark where the game
          draws white text, and pick colours that work with club colours you can't control.</div>
      </div>
    </div>
  );
}
