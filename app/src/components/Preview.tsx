import type { CSSProperties } from "react";
import type { BarSetting } from "../api";

/** Approximate FM27 screen drawn from the pack's values. Click an area to edit what paints it. */
export default function Preview({ value, bars, onPick, fontNote }: {
  value: (token: string) => string; bars: Record<string, BarSetting>; onPick: (token: string) => void; fontNote?: string;
}) {
  const v = value;
  const bar = (area: string, club: string): CSSProperties => {
    const b = bars[area];
    if (!b || b.mode === "club") return { background: club };
    if (b.mode === "image") return { background: `repeating-linear-gradient(45deg, #333 0 10px, #444 10px 20px)` };
    const [c1, c2] = b.colours ?? ["#000000"];
    if (b.mode === "solid" || !c2) return { background: c1 };
    const dir = b.angle === "vertical" ? "180deg" : b.angle === "diagonal" ? "135deg" : "90deg";
    const stripes = area === "backdrop" && b.stripes
      ? `repeating-linear-gradient(-45deg, transparent 0 60px, ${b.stripeColour ?? "#14303a"} 60px 75px), ` : "";
    return { background: `${stripes}linear-gradient(${dir}, ${c1}, ${c2})` };
  };
  const backdropStyle = (): CSSProperties => {
    const b = bars.backdrop;
    if (b && b.mode === "solid" && b.stripes) {
      return { background: `repeating-linear-gradient(-45deg, ${b.colours?.[0]} 0 60px, ${b.stripeColour ?? "#14303a"} 60px 75px)` };
    }
    return bar("backdrop", "linear-gradient(135deg, #3a0508, #1c0101 60%, #45070c)");
  };
  const text = v("--global-text-primary"), sub = v("--global-text-secondary");
  const pick = (token: string) => (e: React.MouseEvent) => { e.stopPropagation(); onPick(token); };
  const clubHint = (area: string) => (!bars[area] || bars[area].mode === "club") ? " (club colours)" : "";

  return (
    <div className="preview">
      <div className="pv-hint">Approximate preview — click an area to edit it{fontNote ? ` · ${fontNote}` : ""}</div>
      <div className="pv-top pv-pickable" style={{ ...bar("topBar", "#bd1b29"), color: text }} onClick={pick("bars:topBar")}
        title={`Top menu bar${clubHint("topBar")}`}>
        <span>PORTAL</span><span>SQUAD</span><span>TACTICS</span><span>RECRUITMENT</span><span>TRAINING</span>
        <span className="grow" />
        <span className="pv-btn pv-pickable" style={{ marginTop: 0, background: v("--continue-button-standard-surface"), color: "#fff" }}
          onClick={pick("--continue-button-standard-surface")}>Continue »</span>
      </div>
      <div className="pv-sub pv-pickable" style={{ ...bar("subBar", "#3d1018"), color: sub }} onClick={pick("bars:subBar")}
        title={`Sub-navigation bar${clubHint("subBar")}`}>
        <b style={{ color: text }}>Benfica</b><span>Overview</span><span>First Team</span><span>Team Report</span><span>Transfers</span>
      </div>
      <div className="pv-header pv-pickable" style={{ ...bar("pageHeader", "linear-gradient(90deg, #5a1010, #2a0606)"), color: text }}
        onClick={pick("bars:pageHeader")} title={`Page header${clubHint("pageHeader")}`}>
        <div style={{ width: 34, height: 34, borderRadius: 17, background: "#fff3" }} />
        <div><div style={{ fontWeight: 700, fontSize: 15 }}>Gil Vicente</div><div style={{ color: sub }}>Premier League (13th)</div></div>
      </div>
      <div className="pv-body pv-pickable" style={backdropStyle()} onClick={pick("bars:backdrop")} title={`Page backdrop${clubHint("backdrop")}`}>
        <div className="pv-block pv-pickable" style={{ background: v("--layout-modules-block-surface"), color: text }}
          onClick={pick("--layout-modules-block-surface")} title="Content block">
          <div className="pv-title">Messages</div>
          {["Training Review", "Scouting report", "Match Preparation"].map((m, i) => (
            <div key={m} className="pv-row" style={{ color: i === 0 ? text : sub }}><span>{m}</span><span>20:5{i}</span></div>))}
          <span className="pv-btn pv-pickable" style={{ background: v("--brand-theme-ui-base"), color: "#fff" }}
            onClick={pick("--brand-theme-ui-base")}>All</span>
        </div>
        <div className="pv-block pv-pickable" style={{ background: v("--layout-modules-block-surface"), color: text }}
          onClick={pick("--layout-modules-block-surface")} title="Content block">
          <div className="pv-title pv-pickable" onClick={pick("--global-text-primary")}>League Table</div>
          {["Estoril Praia", "Ac. Viseu", "MRT", "Santa Clara", "Sporting CP"].map((t, i) => (
            <div key={t} className="pv-row pv-pickable" onClick={pick(i % 2 ? "--data-tables-background-accent" : "--data-tables-background")}
              style={{ background: i % 2 ? v("--data-tables-background-accent") : v("--data-tables-background") }}>
              <span>{i + 1}. {t}</span><span style={{ color: sub }}>{3 - Math.min(i, 2)}</span></div>))}
        </div>
        <div className="stack" style={{ gap: 10 }}>
          <div className="pv-block pv-pickable" style={{ background: v("--layout-modules-tiles-background"), color: text, minHeight: 70 }}
            onClick={pick("--layout-modules-tiles-background")} title="Tile / side card">
            <div className="pv-title">Transfer budget</div><div style={{ color: v("--brand-theme-accent"), fontSize: 18, fontWeight: 700 }}>€20.06M</div>
          </div>
          <div className="pv-block pv-pickable" style={{ background: v("--layout-surfaces-cards-surface"), color: text, minHeight: 70 }}
            onClick={pick("--layout-surfaces-cards-surface")} title="Card">
            <div className="pv-title">General performance</div><div style={{ color: sub }}>No data available</div>
          </div>
        </div>
      </div>
    </div>
  );
}
