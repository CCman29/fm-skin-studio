import { useEffect, useState } from "react";
import { call, onCoreEvent, type IndexStatus, type Paths } from "../api";
import { errorText, useToast } from "../App";

/** Where the game was found and the game index the editors read from (moved here from the Home screen). */
export default function GameInfo() {
  const toast = useToast();
  const [paths, setPaths] = useState<Paths | null>(null);
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [building, setBuilding] = useState<{ stage: string; done: number; total: number } | null>(null);

  const refresh = () => Promise.all([call<Paths>("paths.get"), call<IndexStatus>("index.status")])
    .then(([p, s]) => { setPaths(p); setStatus(s); }).catch((e) => toast({ text: errorText(e), error: true }));
  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => onCoreEvent((m) => {
    if (m.event === "progress") setBuilding(m.data as { stage: string; done: number; total: number });
  }), []);

  const buildIndex = async () => {
    setBuilding({ stage: "starting", done: 0, total: 1 });
    try { await call("index.build"); toast("Game index ready"); }
    catch (e) { toast({ text: errorText(e), error: true }); }
    setBuilding(null); refresh();
  };
  const ready = status?.ready;

  return (
    <div className="stack">
      <div className="card stack">
        <div className="row"><h2 className="grow">Game</h2>
          {paths && (paths.problems.length ? <span className="badge warn">Check</span> : <span className="badge ok">Found</span>)}</div>
        {paths && <div className="kv">
          <div>Install</div><div className="mono">{paths.game_root ?? "not found"}</div>
          <div>Skins folder</div><div className="mono">{paths.skins_root}</div>
          <div>Layouts folder</div><div className="mono">{paths.layouts_dir}</div>
          <div>Game build</div><div className="mono">{paths.game_build ?? "-"}</div>
        </div>}
        {paths?.problems.map((p) => <div key={p} className="small" style={{ color: "var(--warn)" }}>{p}</div>)}
      </div>
      <div className="card stack">
        <div className="row"><h2 className="grow">Game index</h2>
          {ready ? <span className="badge ok">Ready</span> : <span className="badge warn">Needed</span>}</div>
        <p className="muted small" style={{ margin: 0 }}>Reads the game's own colours, screens and layouts from your
          install so the editors know what can be changed. Stays on this PC; rebuilt when FM27 updates.</p>
        {status?.manifest && <div className="kv">
          <div>Theme settings</div><div>{status.manifest.tokens.toLocaleString()}</div>
          <div>Screen layouts</div><div>{status.manifest.compositions.toLocaleString()}</div>
          <div>Screen designs</div><div>{status.manifest.screens.toLocaleString()}</div>
        </div>}
        {building ? <div className="stack">
          <div className="muted small">Reading {building.stage}... (about a minute)</div>
          <div className="progress"><div style={{ width: `${Math.round((building.done / Math.max(1, building.total)) * 100)}%` }} /></div>
        </div> : <div><button className={ready ? "" : "primary"} disabled={!paths?.bundles} onClick={buildIndex}>
          {ready ? "Rebuild index" : "Build index"}</button></div>}
      </div>
    </div>
  );
}
