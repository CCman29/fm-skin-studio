import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { call } from "../api";

export interface RenderNode { t: string; n?: string; c?: string[]; css?: string; text?: string; img?: boolean;
  tpl?: string; ch?: RenderNode[]; truncated?: boolean }

// One shared copy of the converted game stylesheets + fonts, adopted by every preview's shadow root.
let baseSheet: Promise<CSSStyleSheet> | null = null;
const overrideSheet = new CSSStyleSheet();
const outlineSheet = new CSSStyleSheet();  // empty = outlines on; hides them when switched off
let outlinesOn = true;
const outlineListeners = new Set<(on: boolean) => void>();

/** Show or hide the dashed "where this setting is used" outlines in every preview. */
export function setOutlines(on: boolean) {
  outlinesOn = on;
  outlineSheet.replaceSync(on ? "" : ".fm-hl::after { display: none !important; }");
  outlineListeners.forEach((fn) => fn(on));
}

/** A checkbox bound to the shared outline switch. */
export function OutlineToggle() {
  const [on, setOn] = useState(outlinesOn);
  useEffect(() => { outlineListeners.add(setOn); return () => { outlineListeners.delete(setOn); }; }, []);
  return <label className="row small" style={{ gap: 6 }} title="Dashed yellow lines show where the selected setting is used">
    <input type="checkbox" checked={on} onChange={(e) => setOutlines(e.target.checked)} />Show where it's used</label>;
}

function loadBase(): Promise<CSSStyleSheet> {
  if (!baseSheet) {
    baseSheet = call<{ css: string; fonts: string }>("preview.assets").then(({ css, fonts }) => {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(css);
      // @font-face isn't allowed in constructed sheets inside shadow roots everywhere; add fonts to the document.
      const style = document.createElement("style");
      style.textContent = fonts.replace(/\.fm-root \{[^}]*\}\s*$/, "");
      document.head.appendChild(style);
      sheet.insertRule(fonts.match(/\.fm-root \{[^}]*\}\s*$/)?.[0] ?? ".fm-root {}", sheet.cssRules.length);
      return sheet;
    });
  }
  return baseSheet;
}

/** The pack's token overrides applied on top of the game's theme in every preview. */
export function setPreviewOverrides(overrides: Record<string, string>) {
  const body = Object.entries(overrides).map(([k, v]) => `${k}: ${v};`).join(" ");
  overrideSheet.replaceSync(`.fm-root { ${body} }`);
}

function styleFrom(css?: string): CSSProperties | undefined {
  if (!css) return undefined;
  const out: Record<string, string> = {};
  for (const decl of css.split(";")) {
    const i = decl.indexOf(":");
    if (i < 0) continue;
    const name = decl.slice(0, i).trim(), value = decl.slice(i + 1).trim();
    const key = name.startsWith("--") ? name : name.replace(/-([a-z])/g, (_m, c: string) => c.toUpperCase());
    out[key] = value;
  }
  return out as CSSProperties;
}

function Node({ node, highlight, onPick }: { node: RenderNode; highlight: Set<string>; onPick?: (n: RenderNode) => void }) {
  const hit = node.c?.some((c) => highlight.has(c));
  const cls = [...(node.c ?? []), node.text !== undefined ? "fm-text" : "", node.img ? "fm-img" : "", hit ? "fm-hl" : "",
    onPick ? "fm-pick" : ""].filter(Boolean).join(" ");
  return (
    <div data-t={node.t} data-n={node.n} className={cls} style={styleFrom(node.css)}
      onClick={onPick ? (e) => { e.stopPropagation(); onPick(node); } : undefined}>
      {node.text}
      {node.ch?.map((c, i) => <Node key={i} node={c} highlight={highlight} onPick={onPick} />)}
    </div>
  );
}

/** Renders game screen elements inside an isolated shadow root using the game's own stylesheets. */
export function ShadowFrame({ width, height, children }: { width: number; height: number; children: ReactNode }) {
  const host = useRef<HTMLDivElement>(null);
  const [root, setRoot] = useState<ShadowRoot | null>(null);
  useLayoutEffect(() => {
    if (!host.current || host.current.shadowRoot) return;
    const shadow = host.current.attachShadow({ mode: "open" });
    shadow.adoptedStyleSheets = [overrideSheet, outlineSheet];
    loadBase().then((sheet) => { shadow.adoptedStyleSheets = [sheet, overrideSheet, outlineSheet]; setRoot(shadow); });
  }, []);
  return (
    <div ref={host} style={{ width, height, flex: "none" }}>
      {root && createPortal(<div className="fm-root" style={{ width, height }}>{children}</div>, root as unknown as Element)}
    </div>
  );
}

/** The frame the game draws around a grid panel: tiles use the tile surface, larger blocks the content-panel surface. */
export function frameStyle(file: string | null | undefined): CSSProperties {
  const tile = !!file && /Tile/.test(file);
  return { width: "100%", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden", borderRadius: 6,
    padding: 8, background: tile ? "var(--layout-modules-tiles-background)" : "var(--layout-modules-block-surface)" };
}

export function RealPanel({ tree, width, height, highlight, onPick, file }: {
  tree: RenderNode; width: number; height: number; highlight?: string[]; onPick?: (n: RenderNode) => void; file?: string | null;
}) {
  const set = new Set(highlight ?? []);
  return (
    <ShadowFrame width={width} height={height}>
      <div data-t="Panel" style={frameStyle(file)}>
        <Node node={tree} highlight={set} onPick={onPick} />
      </div>
    </ShadowFrame>
  );
}

/** Size of a tile from its file name (…_4x2) at a given cell size; blocks default to 8x4. */
export function tileSize(name: string, cell = 92): { w: number; h: number } {
  const m = name.match(/_(\d+)x(\d+)/);
  const [w, h] = m ? [+m[1], +m[2]] : /Tile/.test(name) ? [4, 4] : [8, 4];
  return { w: w * cell, h: h * cell };
}

/** Loads and shows one screen file (panel) by name. */
export function PanelByName({ name, highlight, onPick, cell }: { name: string; highlight?: string[];
  onPick?: (n: RenderNode) => void; cell?: number }) {
  const [tree, setTree] = useState<RenderNode | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setTree(null); setError(null);
    call<{ tree: RenderNode }>("preview.panel", { name }).then((r) => setTree(r.tree)).catch((e) => setError(e.message));
  }, [name]);
  if (error) return <div className="muted small">{error}</div>;
  if (!tree) return <div className="muted small">Drawing {name}…</div>;
  const size = tileSize(name, cell);
  return <RealPanel tree={tree} width={size.w} height={size.h} highlight={highlight} onPick={onPick} file={name} />;
}
