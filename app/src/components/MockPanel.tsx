import { createContext, useContext, type CSSProperties, type ReactNode } from "react";

export const HighlightToken = createContext<string[]>([]);

/** Styled sample content for a grid panel. FM27 fills panels with your save's data while it runs, so the game files
 *  only hold empty frames; these samples show the same kinds of content (lists, tables, stats, calendars, charts,
 *  pitches) painted with the pack's own settings. Every painted part says which setting paints it (data-tokens),
 *  so clicking it finds that setting and selecting a setting outlines it. */

type Kind = "attributes" | "dashboard" | "messages" | "news" | "table" | "stat" | "calendar" | "chart" | "report" | "actions" | "pitch" | "profile" | "generic";

const RULES: [RegExp, Kind][] = [
  [/attribute/i, "attributes"],
  [/playerform|happiness|fitness|trainingoverviewtile|seasonstats/i, "report"],
  [/adaptive|contentblock|overviewblock|firstteamoverview|recruitmentcontent/i, "dashboard"],
  [/message|inbox/i, "messages"],
  [/news|rumou?r|feed/i, "news"],
  [/actions?controlpanel|controlpanel|actionbar/i, "actions"],
  [/calendar|schedule(?!.*fixture)|trainingoverview/i, "calendar"],
  [/graph|chart|xg|projection|trend|form$/i, "chart"],
  [/budget|wage|balance|finance|ffp|value|window|range|transferhistory/i, "stat"],
  [/pitch|formation|matchviewer|lineup|tactic(?!aleffect)/i, "pitch"],
  [/profile|clubsite|clubinfo|playerinfo|personal|bio/i, "profile"],
  [/table|fixture|league|squad|firstteam|staff|injur|database|search|shortlist|recommend|transfer|offer|scout|player|result|score/i, "table"],
  [/report|hub|effectiveness|atmosphere|happiness|feedback|board|vision|support|confidence|focus|facilit|advice|insight|fitness/i, "report"],
];

export function kindOf(id: string, file?: string | null): Kind {
  const key = `${id} ${file ?? ""}`;
  return RULES.find(([re]) => re.test(key))?.[1] ?? "generic";
}

const words = (id: string) => id.replace(/(?<=[a-z])(?=[A-Z])|[_-]+/g, " ").replace(/\b(Block|Tile|Card|Composition)\b/gi, "").trim();

// small helpers: an element painted by one or more settings
function P({ t, style, children, className }: { t: string[]; style?: CSSProperties; children?: ReactNode; className?: string }) {
  const hl = useContext(HighlightToken);
  return <div className={`mk ${className ?? ""} ${hl.some((x) => t.includes(x)) ? "fm-hl" : ""}`} data-tokens={t.join(" ")} style={style}>{children}</div>;
}
const v = (name: string) => `var(${name})`;
const TEXT = v("--global-text-primary"), SUB = v("--global-text-secondary");

function Title({ text, big }: { text: string; big: boolean }) {
  return <P t={["--global-text-primary", "--typography-family-thematic"]} className="mk-title"
    style={{ color: TEXT, fontFamily: v("--typography-family-thematic"), fontSize: big ? 19 : 17, textTransform: big ? "none" : "uppercase",
      textDecoration: big ? "underline" : "none", textDecorationColor: v("--brand-theme-accent") }}>{text}</P>;
}

function Row({ i, cells, widths }: { i: number; cells: ReactNode[]; widths: string }) {
  const bg = i % 2 ? "--data-tables-background-accent" : "--data-tables-background";
  return <P t={[bg]} className="mk-row" style={{ background: v(bg), gridTemplateColumns: widths }}>
    {cells.map((c, j) => <span key={j} style={{ color: j === 0 ? TEXT : SUB }}>{c}</span>)}</P>;
}

const CLUBS = ["Arsenal", "Real Madrid", "Valencia", "Atalanta", "Girona", "Burnley", "Venezia", "Newcastle", "Stuttgart", "Real Betis", "Man Utd", "Marseille"];
const NAMES = ["Mikel Merino", "Ferland Mendy", "Brahim Díaz", "Giovani Lo Celso", "Mason Mount", "Joshua Zirkzee", "Isak Hien", "Atakan Karazor", "Joe Willock", "Tom Heaton", "Alfred Duncan", "Maxwel Cornet"];


const ATTRS: [string, [string, number][]][] = [
  ["Technical", [["Corners", 8], ["Crossing", 11], ["Dribbling", 15], ["Finishing", 13], ["First Touch", 16], ["Free Kick Taking", 9],
    ["Heading", 7], ["Long Shots", 12], ["Long Throws", 4], ["Marking", 6], ["Passing", 17], ["Penalty Taking", 10], ["Tackling", 8], ["Technique", 17]]],
  ["Mental", [["Aggression", 9], ["Anticipation", 15], ["Bravery", 11], ["Composure", 16], ["Concentration", 13], ["Decisions", 16],
    ["Determination", 18], ["Flair", 15], ["Leadership", 10], ["Off the Ball", 14], ["Positioning", 9], ["Teamwork", 15], ["Vision", 18], ["Work Rate", 14]]],
  ["Physical", [["Acceleration", 13], ["Agility", 15], ["Balance", 14], ["Jumping Reach", 6], ["Natural Fitness", 15], ["Pace", 12],
    ["Stamina", 16], ["Strength", 10]]],
];
// FM27's attribute value bands (data-player-stats-*): no stylesheet uses them, the game applies them in code
const band = (n: number) => n >= 16 ? "--data-player-stats-16-20" : n >= 11 ? "--data-player-stats-11-15" : n >= 6 ? "--data-player-stats-6-10" : "--data-player-stats-1-5";

function Body({ kind, w, h, id }: { kind: Kind; w: number; h: number; id: string }) {
  const rows = Math.max(1, Math.min(22, Math.floor(h * 2.4 - 1)));
  switch (kind) {
    case "attributes":
      return <div className="mk-attrs">
        {ATTRS.map(([group, list]) => <div key={group} className="mk-col">
          <P t={["--global-text-primary"]} style={{ color: TEXT, fontWeight: 700, fontSize: 17, marginBottom: 4 }}>{group}</P>
          {list.slice(0, Math.max(4, Math.floor(h * 2.4))).map(([name, n], i) => (
            <P key={name} t={[i % 2 ? "--data-tables-background-accent" : "--data-tables-background"]} className="mk-line mk-attr"
              style={{ background: v(i % 2 ? "--data-tables-background-accent" : "--data-tables-background") }}>
              <span style={{ color: TEXT }}>{name}</span>
              <P t={[band(n)]} style={{ color: v(band(n)), fontWeight: 700, minWidth: 24, textAlign: "right" }}>{n}</P>
            </P>))}
        </div>)}
        {w >= 14 && <div className="mk-col">
          <P t={["--global-text-primary"]} style={{ color: TEXT, fontWeight: 700, fontSize: 17, marginBottom: 4 }}>Role</P>
          <P t={["--layout-surfaces-cards-surface"]} className="mk-kv" style={{ background: v("--layout-surfaces-cards-surface"), color: TEXT }}>
            Advanced Playmaker <span style={{ color: SUB }}>(Support)</span></P>
          <P t={["--layout-modules-tiles-background"]} className="mk-pitch-mini" style={{ background: v("--colours-tactics-base-50") }}>
            <span className="mk-dot" style={{ left: "50%", top: "40%", background: v("--brand-theme-ui-base") }} /></P>
          <P t={["--global-text-primary"]} style={{ color: TEXT, fontWeight: 700, fontSize: 17, margin: "6px 0 4px" }}>Traits</P>
          {["Tries killer balls often", "Likes to switch ball to other flank", "Comes deep to get ball"].map((t) =>
            <span key={t} style={{ color: SUB, fontSize: 14 }}>{t}</span>)}
        </div>}
      </div>;
    case "dashboard":
      return <div className="mk-dash">
        <div className="mk-col"><Title text="Transfer News" big /><Body kind="news" w={w / 2} h={h / 2} id={id} />
          <Title text="Fixture Schedule" big /><Body kind="table" w={w / 2.4} h={h / 2.2} id={id} /></div>
        <div className="mk-col"><Title text="League Table" big /><Body kind="table" w={w / 2} h={h} id={id} /></div>
      </div>;
    case "messages":
      return <>{["Taniguchi offer accepted", "Bernardes joins on loan", "Question from the press", "Agent offers summary", "Scouting report ready",
        "Recruitment advice", "Training review", "Board request answered", "Fitness tests", "Staffing advice"].slice(0, Math.max(1, Math.floor(h * 1.3 - 1))).map((m, i) => (
        <P key={m} t={[i === 0 ? "--brand-theme-ui-base" : "--layout-modules-block-border-colour"]} className="mk-msg"
          style={{ borderBottom: `1px solid ${v("--layout-modules-block-border-colour")}`, background: i === 0 ? v("--global-lift-surface-base") : "transparent" }}>
          <div className="mk-line"><span style={{ color: SUB, fontSize: 13 }}>Mário Branco</span>
            <P t={["--brand-theme-accent"]} className="mk-chip" style={{ borderColor: v("--brand-theme-accent"), color: v("--brand-theme-accent") }}>Transfers</P></div>
          <div className="mk-line"><span style={{ color: i === 0 ? TEXT : SUB }}>{m}</span><span style={{ color: SUB, fontSize: 13 }}>1{i}:3{i}</span></div>
        </P>))}</>;
    case "news":
      return <>{[0, 1, 2].slice(0, Math.max(1, Math.floor(h / 2))).map((i) => (
        <P key={i} t={["--layout-surfaces-cards-surface"]} className="mk-news" style={{ background: v("--layout-surfaces-cards-surface") }}>
          <div className="mk-thumb" /><div style={{ minWidth: 0 }}><div style={{ color: TEXT, fontWeight: 600 }}>{["Labidi joins on loan", "Estoril land Cuba", "Mariners secure loan"][i]}</div>
            <div style={{ color: SUB, fontSize: 13 }}>{15 * (i + 1)}m ago · Liga Portugal</div></div></P>))}</>;
    case "table": {
      const cols = w >= 10 ? 6 : w >= 6 ? 4 : 3;
      const widths = cols === 6 ? "2fr 1.4fr 1fr 0.7fr 1fr 1fr" : cols === 4 ? "2fr 1.4fr 0.8fr 0.8fr" : "2fr 1fr 0.7fr";
      const head = ["Player", "Club", "Age", "Pts", "Value", "Wage"].slice(0, cols);
      return <>
        <P t={["--global-text-secondary"]} className="mk-row mk-head" style={{ gridTemplateColumns: widths, color: SUB }}>{head.map((c) => <span key={c}>{c}</span>)}</P>
        {Array.from({ length: rows }, (_, i) => <Row key={i} i={i} widths={widths}
          cells={[NAMES[i % NAMES.length], CLUBS[i % CLUBS.length], 24 + (i % 9), 30 - i, `€${(i * 3.7 + 2).toFixed(1)}M`, `€${40 + i * 7}K p/w`].slice(0, cols)} />)}
      </>;
    }
    case "stat":
      return <>
        <div style={{ color: SUB, fontSize: 14 }}>Available Budget</div>
        <P t={["--brand-theme-accent"]} style={{ color: v("--brand-theme-accent"), fontSize: h >= 2 ? 28 : 20, fontWeight: 700 }}>€20.2M</P>
        {h >= 2 && <><div style={{ color: SUB, fontSize: 14 }}>Spent This Season <b style={{ color: TEXT }}>€1.11M</b></div>
          <P t={["--brand-theme-ui-base"]} className="mk-bar"><div style={{ width: "62%", background: v("--brand-theme-ui-base") }} /></P></>}
      </>;
    case "calendar":
      return <div className="mk-cal">{Array.from({ length: 7 * Math.max(1, Math.min(4, Math.floor(h / 2.2))) }, (_, i) => (
        <div key={i} className="mk-day" style={{ borderColor: v("--layout-modules-block-border-colour") }}>
          <span style={{ color: TEXT, fontWeight: 700 }}>{(i % 31) + 1}</span>
          {[0, 1, 2].map((j) => { const t = ["--colours-ui-strong", "--global-lift-surface-base", "--brand-theme-ui-base"][(i + j) % 3];
            return <P key={j} t={[t]} className="mk-session" style={{ background: v(t), color: TEXT }}>{["Recovery", "Rest", "Pressing"][(i + j) % 3]}</P>; })}
        </div>))}</div>;
    case "chart":
      return <>{w >= 8 && <div className="mk-line" style={{ justifyContent: "flex-start", gap: 30 }}>
          <div><div style={{ color: SUB, fontSize: 14 }}>Overall Balance</div>
            <P t={["--brand-theme-accent"]} style={{ color: v("--brand-theme-accent"), fontSize: 28, fontWeight: 700 }}>€14,683,842</P></div></div>}
        <P t={["--brand-theme-accent", "--layout-modules-block-border-colour"]} className="mk-chart">
        <svg viewBox="0 0 200 80" preserveAspectRatio="none" width="100%" height="100%">
          <path d="M0 70 C40 20, 70 15, 100 45 S160 75, 200 20 L200 80 L0 80 Z" fill={v("--brand-theme-ui-base")} opacity="0.35" />
          <path d="M0 70 C40 20, 70 15, 100 45 S160 75, 200 20" fill="none" stroke={v("--brand-theme-accent")} strokeWidth="2" />
        </svg></P></>;
    case "pitch":
      return <P t={["--colours-tactics-base-50"]} className="mk-pitch" style={{ background: v("--colours-tactics-base-50") }}>
        {[[50, 88], [20, 70], [40, 72], [60, 72], [80, 70], [35, 50], [65, 50], [20, 28], [50, 32], [80, 28], [50, 12]].map(([x, y], i) =>
          <span key={i} className="mk-dot" style={{ left: `${x}%`, top: `${y}%`, background: v("--brand-theme-ui-base") }} />)}</P>;
    case "profile":
      return <div className="mk-line" style={{ gap: 10, justifyContent: "flex-start" }}><div className="mk-badge" />
        <div><div style={{ color: TEXT, fontWeight: 700 }}>SL Benfica</div><div style={{ color: SUB, fontSize: 14 }}>Portugal · Liga Portugal</div></div></div>;
    case "actions":
      return <div className="mk-line" style={{ justifyContent: "flex-start", gap: 8 }}>{["Advice", "Primary Tactic", "Performances", "Responsibilities"].map((b) => (
        <P key={b} t={["--layout-surfaces-cards-surface"]} className="mk-btn" style={{ background: v("--layout-surfaces-cards-surface"), color: TEXT }}>{b}</P>))}</div>;
    case "report":
      return <>{["Tactical Understanding", "Player Ability", "Player Buy-In", "Next Match Info"].slice(0, Math.max(1, Math.floor(h * 1.2))).map((m, i) => (
        <P key={m} t={[i % 2 ? "--data-tables-background-accent" : "--global-lift-surface-base"]} className="mk-line mk-kv"
          style={{ background: v(i % 2 ? "--data-tables-background-accent" : "--global-lift-surface-base") }}>
          <span style={{ color: TEXT }}>{m}</span>
          <P t={["--brand-theme-accent"]} className="mk-meter"><div style={{ width: `${45 + i * 12}%`, background: v("--brand-theme-accent") }} /></P>
        </P>))}</>;
    default:
      return <><div style={{ color: SUB }}>{words(id)} details</div>
        <P t={["--brand-theme-ui-base"]} className="mk-btn" style={{ background: v("--brand-theme-ui-base"), color: "#fff", alignSelf: "flex-start" }}>View</P></>;
  }
}

export default function MockPanel({ id, file, w, h }: { id: string; file?: string | null; w: number; h: number }) {
  const kind = kindOf(id, file);
  const tile = w <= 4 && h <= 2 || /Tile/.test(file ?? "");
  const surface = tile ? "--layout-modules-tiles-background" : "--layout-modules-block-surface";
  if (kind === "attributes") return (
    <P t={[surface, "--layout-modules-block-radius"]} className="mk-panel"
      style={{ background: v(surface), borderRadius: v("--layout-modules-block-radius"), border: `1px solid ${v("--layout-modules-block-border-colour")}` }}>
      <div className="mk-line" style={{ justifyContent: "flex-start", gap: 14, flex: "none" }}><div className="mk-badge" />
        <div><Title text="Fredrik Aursnes" big /><div style={{ color: SUB, fontSize: 14 }}>M (C), AM (RC) · 30 years old · Norway</div></div>
        <span className="grow" />
        <P t={["--colours-data-ratings-star"]} style={{ color: v("--colours-data-ratings-star"), fontSize: 20 }}>★★★★☆</P></div>
      <div className="mk-body"><Body kind={kind} w={w} h={h} id={id} /></div>
    </P>);
  if (kind === "actions") return <div className="mk-panel mk-actions"><Body kind={kind} w={w} h={h} id={id} /></div>;
  return (
    <P t={[surface, "--layout-modules-block-radius", "--layout-modules-block-border-colour"]} className="mk-panel"
      style={{ background: v(surface), borderRadius: v("--layout-modules-block-radius"), border: `1px solid ${v("--layout-modules-block-border-colour")}` }}>
      {kind !== "dashboard" && <Title text={words(id) || "Panel"} big={!tile} />}
      <div className="mk-body"><Body kind={kind} w={w} h={h} id={id} /></div>
    </P>
  );
}

export const MOCK_CSS = `
.mk-panel { width: 100%; height: 100%; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; overflow: hidden; font-size: 16px; }
.mk-actions { padding: 0; justify-content: center; }
.mk-title { font-weight: 700; letter-spacing: 0.3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: none; }
.mk-attrs { display: grid; grid-template-columns: repeat(auto-fit, minmax(0, 1fr)); gap: 18px; height: 100%; min-height: 0; }
.mk-attr { padding: 3px 8px; border-radius: 3px; font-size: 15px; }
.mk-pitch-mini { position: relative; height: 110px; border-radius: 6px; margin-top: 6px; flex: none; }
.grow { flex: 1; }
.mk-dash { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; height: 100%; min-height: 0; }
.mk-col { display: flex; flex-direction: column; gap: 6px; min-width: 0; overflow: hidden; }
.mk-body { display: flex; flex-direction: column; gap: 4px; min-height: 0; flex: 1; overflow: hidden; }
.mk-row { display: grid; gap: 10px; padding: 6px 8px; border-radius: 3px; white-space: nowrap; }
.mk-row span { overflow: hidden; text-overflow: ellipsis; }
.mk-head { font-size: 13px; }
.mk-line { display: flex; justify-content: space-between; align-items: center; gap: 6px; white-space: nowrap; min-width: 0; }
.mk-line > span { overflow: hidden; text-overflow: ellipsis; }
.mk-msg { padding: 10px 8px; display: flex; flex-direction: column; gap: 3px; }
.mk-chip { border: 1px solid; border-radius: 4px; padding: 1px 8px; font-size: 13px; }
.mk-news { display: flex; gap: 8px; padding: 6px; border-radius: 6px; align-items: center; }
.mk-thumb { width: 44px; height: 34px; border-radius: 4px; background: repeating-linear-gradient(45deg, #ffffff12 0 6px, #ffffff20 6px 12px); flex: none; }
.mk-bar, .mk-meter { height: 6px; border-radius: 3px; background: #ffffff1a; overflow: hidden; flex: none; }
.mk-meter { width: 90px; }
.mk-bar > div, .mk-meter > div { height: 100%; }
.mk-cal { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.mk-day { border: 1px solid; border-radius: 4px; padding: 4px; display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.mk-session { font-size: 13px; border-radius: 3px; padding: 2px 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mk-chart { flex: 1; min-height: 40px; border-bottom: 1px solid; }
.mk-pitch { position: relative; flex: 1; border-radius: 6px; min-height: 60px; }
.mk-dot { position: absolute; width: 12px; height: 12px; border-radius: 6px; transform: translate(-50%, -50%); border: 2px solid #fff; }
.mk-badge { width: 34px; height: 34px; border-radius: 17px; background: #ffffff30; flex: none; }
.mk-btn { padding: 10px 18px; border-radius: var(--buttons-global-radius-regular, 6px); font-weight: 600; white-space: nowrap; font-size: 15px; }
.mk-kv { padding: 6px 8px; border-radius: 4px; }
.mk[data-tokens] { cursor: pointer; }
/* highlight: a translucent white layer over the whole part - on hover (innermost part only), on the part you clicked,
   and on every part the selected setting paints */
.mk[data-tokens] { position: relative; }
.mk[data-tokens]:hover:not(:has(.mk[data-tokens]:hover))::after, .mk[data-picked]::after, .mk.fm-hl::after {
  content: ''; position: absolute; inset: 0; background: rgba(255, 255, 255, .42); border-radius: inherit; pointer-events: none; z-index: 5; }
.mk[data-picked]::after { background: rgba(255, 255, 255, .5); box-shadow: inset 0 0 0 2px #fff; }
`;
