import { useEffect, useRef, useState, type CSSProperties } from "react";
import { call, type BarSetting, type PlacedPanel, type ScreenDetail } from "../api";
import { errorText, useToast } from "../App";
import MockPanel, { HighlightToken, MOCK_CSS } from "./MockPanel";
import { RealPanel, ShadowFrame, type RenderNode } from "./RealPanel";

interface PreviewPanel { id: string; x: number; y: number; w: number; h: number; uxml: string | null; tree: RenderNode | null }
type Gesture = { id: string; kind: "move" | "resize"; startX: number; startY: number; dx: number; dy: number };

const overlaps = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/** Background for one of the shell areas from the pack's bar settings (club = the game's default red). */
function barCss(b: BarSetting | undefined, club: string, image?: string | null): CSSProperties {
  if (b?.mode === "image" && image) return { backgroundImage: `url(${image})`, backgroundSize: "cover", backgroundPosition: "center" };
  if (!b || b.mode === "club" || b.mode === "image") return { background: club };
  const [c1, c2] = b.colours ?? ["#000000"];
  if (b.mode === "solid" || !c2) return { background: c1 };
  const dir = b.angle === "vertical" ? "180deg" : b.angle === "diagonal" ? "135deg" : "90deg";
  const stripes = b.stripes ? `repeating-linear-gradient(-45deg, transparent 0 60px, ${b.stripeColour ?? "#14303a"} 60px 75px), ` : "";
  return { background: `${stripes}linear-gradient(${dir}, ${c1}, ${c2})` };
}

/** A whole FM27 screen in the pack's look: top bar, sub bar, optional page header, backdrop and the real panels
 *  laid out on the game's grid. With `editable`, panels can be resized by dragging their edges (snapping to the
 *  sizes the game allows) and moved with their grip. */
export default function ScreenCanvas({ packId, layout, bars, backdrop, header, highlight, onPick, editable, onChanged,
  mode = "sample", highlightToken, onPickTokens, images, highlightTokens, highlightAreas }: {
  packId: string; layout: string; bars: Record<string, BarSetting>; backdrop: string | null; header?: boolean;
  highlight?: string[]; onPick?: (classes: string[]) => void; editable?: boolean; onChanged?: () => void;
  mode?: "sample" | "files"; highlightToken?: string | null; onPickTokens?: (tokens: string[]) => void;
  images?: Record<string, string>;  // pictures (data URLs) for bars drawn as a picture
  highlightTokens?: string[]; highlightAreas?: string[];  // light up what a setting or a bar area affects
}) {
  const hlTokens = [...(highlightTokens ?? []), ...(highlightToken ? [highlightToken] : [])];
  const hl = (area: string) => highlightAreas?.includes(area) ? " sc-hl" : "";
  const toast = useToast();
  const [view, setView] = useState<{ columns: number; panels: PreviewPanel[] } | null>(null);
  const [detail, setDetail] = useState<ScreenDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gesture, setGesture] = useState<Gesture | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1000);

  const load = () => {
    setError(null);
    Promise.all([call<{ columns: number; panels: PreviewPanel[] }>("preview.screen", { name: layout, pack: packId }),
      call<ScreenDetail>("screens.get", { name: layout, pack: packId })])
      .then(([v, d]) => { setView(v); setDetail(d); }).catch((e) => setError(errorText(e)));
  };
  useEffect(() => { setView(null); setDetail(null); setSelected(null); load(); }, [layout, packId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const ro = new ResizeObserver(() => setWidth(box.current?.clientWidth ?? 1000));
    if (box.current) ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  const canEdit = !!editable && !!detail?.layoutSource;
  const readOnly = !editable && !onPick && !onPickTokens;  // a plain preview: nothing to click
  const placed: Record<string, PlacedPanel> = Object.fromEntries((detail?.layout ?? []).map((p) => [p.id, p]));
  // drawn at the game's own size (a 1920-wide window) and scaled to fit, so proportions match FM27
  const VIRTUAL = 1920;
  const scale = width / VIRTUAL;
  const columns = view?.columns ?? 20;
  const cell = (VIRTUAL - 40) / columns;
  const rowH = Math.round(cell * 0.88);
  const rows = view ? Math.max(...view.panels.map((p) => p.y + p.h), 1) : 1;
  const shellH = 62 + 40 + (header ? 84 : 0) + 40 + (view ? rows * rowH : 400);

  // where a gesture would put the panel, snapped to the grid and to the sizes the game allows
  const target = (p: PreviewPanel, g: Gesture) => {
    if (g.kind === "move") {
      return { ...p, x: Math.max(0, Math.min(columns - p.w, p.x + Math.round(g.dx / cell))), y: Math.max(0, p.y + Math.round(g.dy / rowH)) };
    }
    const want = { w: (p.w * cell + g.dx) / cell, h: (p.h * rowH + g.dy) / rowH };
    const sizes = placed[p.id]?.sizes?.length ? placed[p.id].sizes : [[p.w, p.h]];
    const [w, h] = sizes.reduce((best, s) => Math.hypot(s[0] - want.w, s[1] - want.h) < Math.hypot(best[0] - want.w, best[1] - want.h) ? s : best);
    return { ...p, w, h };
  };

  const save = async (moves: Record<string, Partial<PlacedPanel>>) => {
    try {
      const r = await call<{ saved: boolean; issues: { panel: string; message: string }[] }>("layouts.place", { pack: packId, name: layout, moves });
      if (r.saved) { toast("Layout saved into the pack (save in Check and Save, then use this pack's layouts there to try it in FM27)"); onChanged?.(); }
      else toast({ text: r.issues.map((i) => `${i.panel}: ${i.message}`).join(" · "), error: true });
    } catch (e) { toast({ text: errorText(e), error: true }); }
    load();
  };

  const finish = () => {
    if (!gesture || !view) return;
    const p = view.panels.find((q) => q.id === gesture.id)!;
    const t = target(p, gesture);
    setGesture(null);
    if (t.x === p.x && t.y === p.y && t.w === p.w && t.h === p.h) return;
    if (t.x + t.w > columns) return toast("That doesn't fit inside the screen");
    const clash = view.panels.find((q) => q.id !== p.id && overlaps(t, q));
    if (clash) {
      if (gesture.kind === "move" && clash.w === p.w && clash.h === p.h && !placed[clash.id]?.locked) {
        return save({ [p.id]: { x: t.x, y: t.y }, [clash.id]: { x: p.x, y: p.y } });  // same-size panels swap, like FM27
      }
      return toast(`That would overlap ${clash.id}. Make room first, or pick a size that fits.`);
    }
    save(gesture.kind === "move" ? { [p.id]: { x: t.x, y: t.y } } : { [p.id]: { w: t.w, h: t.h } });
  };

  const start = (id: string, kind: Gesture["kind"]) => (e: React.MouseEvent) => {
    e.stopPropagation(); e.preventDefault();
    setSelected(id);
    if (placed[id]?.locked) return toast("The game locks this panel: it can't be moved or resized");
    setGesture({ id, kind, startX: e.clientX, startY: e.clientY, dx: 0, dy: 0 });
  };

  const sub = bars.subBar, top = bars.topBar;
  return (
    <div ref={box} className="screen-canvas" onMouseMove={(e) => gesture && setGesture({ ...gesture, dx: (e.clientX - gesture.startX) / scale,
      dy: (e.clientY - gesture.startY) / scale })} onMouseUp={finish} onMouseLeave={finish}>
     <div style={{ height: shellH * scale, overflow: "hidden" }}>
     <div className="sc-scaled" style={{ width: VIRTUAL, transform: `scale(${scale})`, transformOrigin: "0 0", ["--inv" as string]: 1 / Math.max(scale, 0.05) }}>
      <div className={"sc-top" + hl("topBar")} style={barCss(top, "#bd1b29", images?.topBar)}><span>PORTAL</span><span>SQUAD</span><span>TACTICS</span>
        <span>RECRUITMENT</span><span>TRAINING</span><span>CLUB</span><span className="grow" /><span className={"sc-continue" + hl("continue")}>Continue »</span></div>
      <div className={"sc-sub" + hl("subBar")} style={barCss(sub, "#3d1018", images?.subBar)}><b>Your Club</b><span>Overview</span><span>Squad</span><span>Reports</span></div>
      {header && <div className={"sc-header" + hl("pageHeader")} style={barCss(bars.pageHeader, "linear-gradient(90deg, #5a1010, #2a0606)", images?.pageHeader)}>
        <div className="sc-badge" /><div><b>Club or player name</b><div className="small" style={{ opacity: 0.8 }}>Page header</div></div></div>}
      <div className={"sc-body" + hl("backdrop")} style={backdrop ? { backgroundImage: `url(${backdrop})` } : barCss(bars.backdrop, "linear-gradient(135deg, #3a0508, #1c0101 60%, #45070c)")}>
        {error && <div className="card small">{error}</div>}
        {!view && !error && <div className="muted small" style={{ padding: 12 }}>Drawing the screen from your game files…</div>}
        {view && <div style={{ position: "relative", height: rows * rowH }}>
          {view.panels.map((p) => {
            const g = gesture?.id === p.id ? gesture : null;
            const t = g ? target(p, g) : p;
            const pl = placed[p.id];
            const resizable = canEdit && !pl?.locked && (pl?.sizes?.length ?? 0) > 1;
            return (
              <div key={p.id} className={`sc-panel ${selected === p.id ? "selected" : ""}`}
                style={{ left: p.x * cell + 4, top: p.y * rowH + 4, width: p.w * cell - 8, height: p.h * rowH - 8 }}
                onMouseDown={() => { if (!readOnly) setSelected(p.id); }}>
                {mode === "sample"
                  ? <ShadowFrame width={p.w * cell - 8} height={p.h * rowH - 8}>
                      <style>{MOCK_CSS + (readOnly ? ".mk[data-tokens] { cursor: default; } .mk[data-tokens]:hover::after { display: none !important; }" : "")}</style>
                      <div style={{ width: "100%", height: "100%" }} onClick={onPickTokens ? (e) => {
                        const el = (e.target as HTMLElement).closest("[data-tokens]");
                        if (el) {
                          e.stopPropagation();
                          // keep the clicked part lit until another part is clicked (across every panel of the screen)
                          box.current?.querySelectorAll(".sc-panel > div").forEach((h) =>
                            h.shadowRoot?.querySelectorAll("[data-picked]").forEach((x) => x.removeAttribute("data-picked")));
                          el.setAttribute("data-picked", "");
                          onPickTokens((el.getAttribute("data-tokens") ?? "").split(" ").filter(Boolean));
                        }
                      } : undefined}>
                        <HighlightToken.Provider value={hlTokens}><MockPanel id={p.id} file={p.uxml} w={p.w} h={p.h} /></HighlightToken.Provider>
                      </div>
                    </ShadowFrame>
                  : p.tree ? <RealPanel tree={p.tree} width={p.w * cell - 8} height={p.h * rowH - 8} highlight={highlight} file={p.uxml}
                    onPick={onPick ? (n) => onPick(n.c ?? []) : undefined} />
                  : <div className="gpanel" style={{ position: "static", width: "100%", height: "100%" }}>{p.id}</div>}
                {canEdit && !pl?.locked && <div className="sc-grip" title="Drag to move (same-size panels swap)" onMouseDown={start(p.id, "move")}>⠿ {p.id}</div>}
                {resizable && <>
                  <div className="sc-edge right" title="Drag to resize" onMouseDown={start(p.id, "resize")} />
                  <div className="sc-edge bottom" title="Drag to resize" onMouseDown={start(p.id, "resize")} />
                  <div className="sc-edge corner" title="Drag to resize" onMouseDown={start(p.id, "resize")} />
                </>}
                {g && <div className="sc-ghost" style={{ left: (t.x - p.x) * cell, top: (t.y - p.y) * rowH, width: t.w * cell - 8, height: t.h * rowH - 8 }}>
                  {t.w}×{t.h}</div>}
              </div>);
          })}
        </div>}
      </div>
     </div>
     </div>
      {editable && detail && !detail.layoutSource && <div className="sc-note">Resizing is off for this screen: FM27 hasn't saved a layout file
        for it yet. In FM27 open this screen, choose Customise, change anything small and save; it then appears here ready to resize.</div>}
      {canEdit && selected && placed[selected] && <div className="sc-note">
        <b>{selected}</b>: {placed[selected].locked ? "locked by the game" : placed[selected].sizes.length <= 1 ? "the game keeps this panel at one size"
          : `the game allows ${placed[selected].sizes[0].join("×")} up to ${placed[selected].sizes[placed[selected].sizes.length - 1].join("×")}`}
        {" "}· drag the right or bottom edge to resize, the grip to move.</div>}
    </div>
  );
}
