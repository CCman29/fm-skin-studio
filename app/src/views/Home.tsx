import { useEffect, useState } from "react";
import { call, onCoreEvent, pickFiles, reveal, type IndexStatus, type Paths, type SkinRow } from "../api";
import { errorText, useToast } from "../App";
import ThemePicker from "../components/ThemePicker";
import UpdateBadge from "../components/UpdateBadge";
import { useUnsavedGuard } from "../components/UnsavedGuard";
import WindowControls from "../components/WindowControls";
import ExitButton from "../components/ExitButton";

export default function Home({ onOpen }: { onOpen: (id: string) => void }) {
  const toast = useToast();
  const [paths, setPaths] = useState<Paths | null>(null);
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [skins, setSkins] = useState<SkinRow[]>([]);
  const [building, setBuilding] = useState<{ stage: string; done: number; total: number } | null>(null);
  const [name, setName] = useState("");
  const [coreDown, setCoreDown] = useState(false);
  const guard = useUnsavedGuard();
  const [unsaved, setUnsaved] = useState<string[]>([]);
  // opening or creating a skin first asks about unsaved changes in any other skin
  const open = async (id: string) => { if (await guard("open", id)) onOpen(id); };

  const refresh = async (autoBuild = false) => {
    try {
      const [p, s] = await Promise.all([call<Paths>("paths.get"), call<IndexStatus>("index.status")]);
      setPaths(p); setStatus(s); setCoreDown(false);
      if (p.skins_root) setSkins(await call<SkinRow[]>("packs.list"));
      call<{ id: string }[]>("drafts.dirty").then((d) => setUnsaved(d.map((x) => x.id))).catch(() => {});
      // The index is missing or from an older version of the app: rebuild it straight away.
      if (autoBuild && !s.ready && p.bundles) buildIndex();
    } catch (e) {
      setCoreDown(true);
      toast({ text: errorText(e), error: true });
    }
  };
  useEffect(() => { refresh(true); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => onCoreEvent((m) => {
    if (m.event === "progress") setBuilding(m.data as { stage: string; done: number; total: number });
  }), []);

  const buildIndex = async () => {
    setBuilding({ stage: "starting", done: 0, total: 1 });
    try { await call("index.build"); toast("Game index ready"); }
    catch (e) { toast({ text: errorText(e), error: true }); }
    setBuilding(null); refresh(false);
  };
  const create = async (source?: string, label?: string) => {
    const packName = (label ?? name).trim();
    if (!packName) return toast("Give the new skin a name first");
    if (!(await guard("create"))) return;
    try {
      const pack = await call<{ id: string }>("packs.create", { name: packName, source });
      setName(""); onOpen(pack.id);
    } catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const importPack = async () => {
    const file = await pickFiles([{ name: "Skin pack", extensions: ["fmskin", "zip"] }]);
    if (!file || !(await guard("create"))) return;
    try { const pack = await call<{ id: string }>("packs.import", { file }); toast("Imported as a new pack"); onOpen(pack.id); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const remove = async (id: string) => {
    if (!window.confirm(`Delete the skin pack "${id}" from your skins folder? This can't be undone.`)) return;
    try { await call("packs.delete", { pack: id }); refresh(); } catch (e) { toast({ text: errorText(e), error: true }); }
  };

  const mine = skins.filter((s) => s.managed), others = skins.filter((s) => !s.managed);
  const ready = status?.ready;

  return (
    <div className="app">
      <div className="topbar"><img src="./icon.png" alt="" className="brand-icon" /><div className="brand">FM <span>Skin Studio</span></div>
        <div className="top-right"><UpdateBadge /><ThemePicker /><ExitButton /><WindowControls /></div></div>
      <div className="main">
        {coreDown && <div className="card" style={{ marginBottom: 16, borderColor: "var(--err)" }}>
          The engine isn't responding. {window.fmskin ? "Restart the app." : "Start it with: npm run dev:core"}</div>}
        {!ready && !coreDown && <div className="card" style={{ marginBottom: 16, borderColor: "var(--warn)" }}>
          {building ? <>Preparing the game index (about a minute). Your packs open as soon as it's done.</>
            : <>The game index needs updating before packs can be opened. <button className="primary" disabled={!paths?.bundles}
                onClick={buildIndex}>Update now</button></>}</div>}
        <div className="home-grid">
          <div className="stack">
            <div className="card stack">
              <h2>Your skin packs</h2>
              <p className="muted small" style={{ margin: 0 }}>Each pack is a new skin in your FM27 skins folder. Pick it in
                FM27 under Preferences. Your current skin is never changed.</p>
              <div className="row">
                <input type="text" className="grow" placeholder="New skin name, e.g. Midnight Green" value={name}
                  onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
                <button className="primary" disabled={!ready} onClick={() => create()}>Create pack</button>
                <button onClick={importPack} disabled={!paths?.skins_root}>Import .fmskin</button>
              </div>
              <div className="list">
                {mine.length === 0 && <div className="muted small">No packs yet.</div>}
                {mine.map((s) => (
                  <div className="list-item" key={s.id}>
                    <div className="grow"><div>{s.name}{unsaved.includes(s.id) && <span className="badge warn" style={{ marginLeft: 8 }}>Unsaved changes</span>}</div>
                      <div className="muted small mono">{s.id}</div></div>
                    <button onClick={() => reveal(s.path)} disabled={!window.fmskin}>Show folder</button>
                    <button className="danger" onClick={() => remove(s.id)}>Delete</button>
                    <button className="primary" disabled={!ready} title={ready ? "" : "Waiting for the game index"}
                      onClick={() => open(s.id)}>{ready ? "Open" : "Preparing…"}</button>
                  </div>
                ))}
              </div>
            </div>
            <div className="card stack">
              <h2>Other skins in your folder</h2>
              <p className="muted small" style={{ margin: 0 }}>Read-only. Duplicate one to use it as a starting point.</p>
              <div className="list">
                {others.length === 0 && <div className="muted small">None.</div>}
                {others.map((s) => (
                  <div className="list-item" key={s.id}>
                    <div className="grow"><div>{s.name}</div><div className="muted small mono">{s.id}</div></div>
                    <button disabled={!ready} onClick={() => create(s.id, `${s.name} copy`)}>Duplicate as new pack</button>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="home-logo"><img src="./logo.png" alt="FM Skin Studio" /></div>
        </div>
      </div>
    </div>
  );
}
