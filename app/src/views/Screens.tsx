import { useEffect, useMemo, useRef, useState } from "react";
import { call, type PlacedPanel, type ScreenDetail, type ScreenRow } from "../api";
import { errorText, useToast } from "../App";
import { RealPanel, type RenderNode } from "../components/RealPanel";

interface PreviewPanel { id: string; x: number; y: number; w: number; h: number; uxml: string | null; tree: RenderNode | null }

/** The whole screen drawn from the game's own panel files, laid out on its grid, in this pack's colours. */
function ScreenPreview({ name, packId, highlight }: { name: string; packId: string; highlight: string[] }) {
  const [data, setData] = useState<{ columns: number; panels: PreviewPanel[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1000);
  useEffect(() => {
    setData(null); setError(null);
    call<{ columns: number; panels: PreviewPanel[] }>("preview.screen", { name, pack: packId }).then(setData).catch((e) => setError(e.message));
  }, [name, packId]);
  useEffect(() => {
    const ro = new ResizeObserver(() => setWidth(box.current?.clientWidth ?? 1000));
    if (box.current) ro.observe(box.current);
    return () => ro.disconnect();
  }, []);
  const cell = data ? Math.floor((width - 16) / data.columns) : 60;
  const rowH = Math.round(cell * 0.9);
  const rows = data ? Math.max(...data.panels.map((p) => p.y + p.h), 1) : 1;
  return (
    <div ref={box} className="screen-stage">
      {error && <div className="muted small">{error}</div>}
      {!data && !error && <div className="muted small">Drawing the screen from your game files…</div>}
      {data && <div style={{ position: "relative", height: rows * rowH + 8 }}>
        {data.panels.map((p) => (
          <div key={p.id} style={{ position: "absolute", left: p.x * cell + 4, top: p.y * rowH + 4 }} title={`${p.id} (${p.w}×${p.h})`}>
            {p.tree ? <RealPanel tree={p.tree} width={p.w * cell - 8} height={p.h * rowH - 8} highlight={highlight} file={p.uxml} />
              : <div className="gpanel" style={{ position: "static", width: p.w * cell - 8, height: p.h * rowH - 8 }}>{p.id}</div>}
          </div>))}
      </div>}
    </div>
  );
}

const AREAS = ["All areas", "Match", "Tactics", "Training", "Squad", "Scouting & recruitment", "Club & staff",
  "Competitions", "Data hub", "Inbox & news", "Game setup & menus", "Cards", "Other"];
const BREAKPOINTS = ["Large", "Standard", "Small", "NONE", "Phone_Landscape", "Phone_Portrait"];

function overlaps(a: PlacedPanel, b: PlacedPanel) {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

function LayoutEditor({ detail, packId, onSaved }: { detail: ScreenDetail; packId: string; onSaved: () => void }) {
  const toast = useToast();
  const [panels, setPanels] = useState<PlacedPanel[]>(detail.layout);
  const [selected, setSelected] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number; startX: number; startY: number } | null>(null);
  const [issues, setIssues] = useState<{ panel: string; message: string }[]>([]);
  const canvas = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  useEffect(() => setPanels(detail.layout), [detail]);
  useEffect(() => {
    const ro = new ResizeObserver(() => setWidth(canvas.current?.clientWidth ?? 900));
    if (canvas.current) ro.observe(canvas.current);
    return () => ro.disconnect();
  }, []);

  const cols = detail.columns;
  const cell = width / cols;
  const rowH = Math.max(40, cell * 0.75);
  const rows = Math.max(10, ...panels.map((p) => p.y + p.h)) + 1;

  const save = async (moves: Record<string, Partial<PlacedPanel>>) => {
    try {
      const r = await call<{ saved: boolean; issues: { panel: string; message: string }[] }>("layouts.place",
        { pack: packId, name: detail.name, moves });
      setIssues(r.issues);
      if (r.saved) { toast("Layout saved into the pack"); onSaved(); } else setPanels(detail.layout);
    } catch (e) { toast({ text: errorText(e), error: true }); setPanels(detail.layout); }
  };

  const onMouseDown = (p: PlacedPanel) => (e: React.MouseEvent) => {
    setSelected(p.id);
    if (p.locked) return;
    setDrag({ id: p.id, dx: 0, dy: 0, startX: e.clientX, startY: e.clientY });
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!drag) return;
    setDrag({ ...drag, dx: e.clientX - drag.startX, dy: e.clientY - drag.startY });
  };
  const onMouseUp = () => {
    if (!drag) return;
    const p = panels.find((q) => q.id === drag.id)!;
    const nx = Math.max(0, Math.min(cols - p.w, p.x + Math.round(drag.dx / cell)));
    const ny = Math.max(0, p.y + Math.round(drag.dy / rowH));
    setDrag(null);
    if (nx === p.x && ny === p.y) return;
    const moved = { ...p, x: nx, y: ny };
    const clash = panels.find((q) => q.id !== p.id && overlaps(moved, q));
    if (clash) {
      // swap places when two panels are the same size, like FM27's own editor
      if (clash.w === p.w && clash.h === p.h && !clash.locked) {
        setPanels(panels.map((q) => q.id === p.id ? moved : q.id === clash.id ? { ...q, x: p.x, y: p.y } : q));
        save({ [p.id]: { x: nx, y: ny }, [clash.id]: { x: p.x, y: p.y } });
      } else toast(`That spot overlaps ${clash.id}`);
      return;
    }
    setPanels(panels.map((q) => (q.id === p.id ? moved : q)));
    save({ [p.id]: { x: nx, y: ny } });
  };
  const resize = (p: PlacedPanel, w: number, h: number) => {
    const next = { ...p, w, h };
    if (next.x + w > cols) return toast("That size doesn't fit here; move the panel left first");
    const clash = panels.find((q) => q.id !== p.id && overlaps(next, q));
    if (clash) return toast(`That size would overlap ${clash.id}`);
    setPanels(panels.map((q) => (q.id === p.id ? next : q)));
    save({ [p.id]: { w, h } });
  };
  const sel = panels.find((p) => p.id === selected);

  return (
    <div className="stack">
      <div ref={canvas} className="grid-canvas" style={{ height: rows * rowH }} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
        {Array.from({ length: cols + 1 }, (_, i) => <div key={`c${i}`} className="grid-cell-line" style={{ left: i * cell }} />)}
        {Array.from({ length: rows + 1 }, (_, i) => <div key={`r${i}`} className="grid-row-line" style={{ top: i * rowH }} />)}
        {panels.map((p) => {
          const d = drag?.id === p.id ? drag : null;
          return (
            <div key={p.id} className={`gpanel ${p.locked ? "locked" : ""} ${selected === p.id ? "selected" : ""} ${issues.some((i) => i.panel === p.id) ? "bad" : ""}`}
              style={{ left: p.x * cell + 2 + (d?.dx ?? 0), top: p.y * rowH + 2 + (d?.dy ?? 0), width: p.w * cell - 4, height: p.h * rowH - 4,
                zIndex: d ? 10 : 1, opacity: d ? 0.85 : 1 }}
              onMouseDown={onMouseDown(p)} title={p.locked ? "Locked by the game" : "Drag to move"}>
              {p.id}{p.locked ? " 🔒" : ""}<span className="gsize">{p.w}×{p.h}</span>
            </div>);
        })}
      </div>
      {sel && <div className="card row wrap">
        <b>{sel.id}</b>
        {sel.locked ? <span className="muted small">Locked by the game: it can't be moved or resized.</span> : <>
          <span className="muted small">Size (the game allows {sel.sizes[0]?.join("×")} up to {sel.sizes[sel.sizes.length - 1]?.join("×")}):</span>
          <select value={sel.w} onChange={(e) => resize(sel, +e.target.value, sel.h)}>
            {[...new Set(sel.sizes.map((s) => s[0]))].map((w) => <option key={w} value={w}>{w} wide</option>)}</select>
          <select value={sel.h} onChange={(e) => resize(sel, sel.w, +e.target.value)}>
            {[...new Set(sel.sizes.map((s) => s[1]))].map((h) => <option key={h} value={h}>{h} tall</option>)}</select>
        </>}
      </div>}
      {issues.map((i) => <div key={i.panel + i.message} className="problem error"><b>{i.panel}</b><span>{i.message}</span></div>)}
    </div>
  );
}

export default function Screens({ packId, onChanged, target }: { packId: string; onChanged: () => void;
  target?: { layout: string; highlight: string[] } | null }) {
  const toast = useToast();
  const [rows, setRows] = useState<ScreenRow[]>([]);
  const [search, setSearch] = useState("");
  const [area, setArea] = useState("All areas");
  const [bp, setBp] = useState("Large");
  const [editableOnly, setEditableOnly] = useState(true);
  const [current, setCurrent] = useState<string | null>(null);
  const [detail, setDetail] = useState<ScreenDetail | null>(null);
  const [view, setView] = useState<"preview" | "layout">("preview");
  const [highlight, setHighlight] = useState<string[]>([]);

  useEffect(() => {
    call<ScreenRow[]>("screens.list", { breakpoint: bp, editable_only: editableOnly })
      .then(setRows).catch((e) => toast({ text: errorText(e), error: true }));
  }, [bp, editableOnly]); // eslint-disable-line react-hooks/exhaustive-deps
  const load = async (name: string) => {
    setCurrent(name);
    try { setDetail(await call<ScreenDetail>("screens.get", { name, pack: packId })); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };
  useEffect(() => {
    if (!target) return;
    const bpName = ["Large", "Standard", "Small", "Phone_Landscape", "Phone_Portrait"].find((b) => target.layout.includes(b)) ?? "NONE";
    setBp(bpName); setEditableOnly(false); setArea("All areas"); setView("preview"); setHighlight(target.highlight);
    load(target.layout);
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown = useMemo(() => rows.filter((r) => (area === "All areas" || r.area === area)
    && (!search || r.name.toLowerCase().includes(search.toLowerCase()))), [rows, area, search]);

  return (
    <div className="screens-layout">
      <div className="card stack" style={{ overflow: "hidden" }}>
        <input type="search" placeholder="Search screens, e.g. Training, Match" value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="row"><select className="grow" value={area} onChange={(e) => setArea(e.target.value)}>
          {AREAS.map((a) => <option key={a}>{a}</option>)}</select>
          <select value={bp} onChange={(e) => setBp(e.target.value)}>{BREAKPOINTS.map((b) => <option key={b}>{b}</option>)}</select></div>
        <label className="row small"><input type="checkbox" checked={editableOnly} onChange={(e) => setEditableOnly(e.target.checked)} />
          Only screens whose layout can change</label>
        <div className="muted small">{shown.length} screens</div>
        <div className="screen-list">
          {shown.map((r) => (
            <button key={r.name} className={`screen-item ${current === r.name ? "active" : ""}`} onClick={() => load(r.name)}>
              <div>{r.screen}{r.inMatch ? " ⚽" : ""}</div>
              <div className="muted small">{r.area} · {r.panels} panels · {r.columns} columns</div>
            </button>))}
        </div>
      </div>
      <div className="stack" style={{ overflow: "auto" }}>
        {!detail ? <div className="card muted">Pick a screen to see its panel layout.</div> : <>
          <div className="card stack">
            <div className="row"><h2 className="grow">{detail.screen}</h2>
              <span className="badge">{detail.breakpoint}</span><span className="badge">{detail.columns} columns</span>
              {detail.layoutSource === "pack" && <span className="badge ok">Layout in this pack</span>}
              {detail.layoutSource === "player" && <span className="badge">Starting from your saved layout</span>}</div>
            <div className="muted small mono">{detail.name}</div>
            <p className="muted small" style={{ margin: 0 }}>Real preview draws each panel from your game files in this pack's colours
              (sample text, placeholder pictures). Edit layout lets you drag panels (same-size panels swap) and pick sizes the game allows.</p>
          </div>
          <div className="tabs" style={{ marginBottom: -4 }}>
            <button className={view === "preview" ? "active" : ""} onClick={() => setView("preview")}>Real preview</button>
            <button className={view === "layout" ? "active" : ""} onClick={() => setView("layout")}>Edit layout</button>
            {highlight.length > 0 && <button className="link small" onClick={() => setHighlight([])}>Clear yellow outlines</button>}
          </div>
          {view === "preview" && <ScreenPreview name={detail.name} packId={packId} highlight={highlight} />}
          {view === "layout" && (detail.layoutSource
            ? <LayoutEditor detail={detail} packId={packId} onSaved={() => { load(detail.name); onChanged(); }} />
            : <div className="card small" style={{ color: "var(--warn)" }}>FM27 hasn't saved a layout for this screen yet. Open it in FM27 and
                customise it once (any small change), then come back to edit it here.</div>)}
          <div className="card stack">
            <h3>Panels this screen can hold ({detail.catalogue.length})</h3>
            <div className="row wrap">{detail.catalogue.map((c) => <span key={c.id} className="badge" title={c.sizes.map((s) => s.join("×")).join(", ")}>{c.id}</span>)}</div>
          </div>
        </>}
      </div>
    </div>
  );
}
