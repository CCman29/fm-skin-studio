import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { call, pickFiles, type BarSetting } from "../api";
import { errorText, useToast } from "../App";
import ScreenCanvas from "../components/ScreenCanvas";
import type { Theme } from "./Workspace";

interface Area { id: string; title: string; where: string; drivenBy: string; skin: string | null; kind: "bars" | "image" | null;
  area?: string; size?: string; hide?: string; cannot?: string; tested?: boolean; state: { mode: string; url?: string } }

const CLUB = "linear-gradient(90deg, #a3151f, #5a0a10)";  // stand-in for "your club's colours" in the game-default previews
const urlPath = (u: string) => u.match(/url\("?([^")]+)"?\)/)?.[1] ?? u;

/** Parts of FM27 the game paints from its own code. Same layout as Global settings: the areas and what a skin can do on
 *  the left, the effect of the skin's choice on the right (the game's look next to this skin's). */
export default function GamePainted({ packId, onOpenTab, theme, bars, barImages }: { packId: string;
  onOpenTab: (tab: string, focus?: string) => void; theme: Theme; bars: Record<string, BarSetting>; barImages: Record<string, string> }) {
  const toast = useToast();
  const [data, setData] = useState<{ areas: Area[]; logicNote: string } | null>(null);
  const [selected, setSelected] = useState("top-bar");
  const [pictures, setPictures] = useState<Record<string, string>>({});
  const [processing, setProcessing] = useState<[string, string] | null>(null);
  useEffect(() => { call<{ areas: Area[]; logicNote: string }>("coded.list", { pack: packId }).then(setData)
    .catch((e) => toast({ text: errorText(e), error: true })); }, [packId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {  // this skin's pictures for the areas it covers, and its processing header colours
    if (!data) return;
    let live = true;
    (async () => {
      const out: Record<string, string> = {};
      for (const a of data.areas) {
        if (a.state.mode !== "image" || !a.state.url) continue;
        try { out[a.id] = await call<string>("packs.image", { pack: packId, path: urlPath(a.state.url) }); } catch { /* preview only */ }
      }
      let colours: [string, string] | null = null;
      try {
        const sheet = await call<string>("packs.screenSheet", { pack: packId, screen: "processing" });
        const s = sheet.match(/--start-colour:\s*([^;]+);/)?.[1], e = sheet.match(/--end-colour:\s*([^;]+);/)?.[1];
        if (s && e) colours = [s.trim(), e.trim()];
      } catch { /* the skin doesn't set them */ }
      if (live) { setPictures(out); setProcessing(colours); }
    })();
    return () => { live = false; };
  }, [data, packId]);

  const set = async (a: Area, mode: "image" | "hide" | "default") => {
    let file: string | null = null;
    if (mode === "image") {
      file = await pickFiles([{ name: "Pictures", extensions: ["png", "jpg", "jpeg"] }]);
      if (!file) return;
    }
    if (mode === "hide" && !window.confirm(`Hide the game's ${a.title.toLowerCase()}? The panel colour shows instead.`)) return;
    try { setData(await call("coded.set", { pack: packId, area: a.id, mode, file })); setSelected(a.id); toast("Saved to the pack"); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };

  if (!data) return <div className="muted">Loading…</div>;
  const area = data.areas.find((a) => a.id === selected) ?? data.areas[0];
  const gameValue = (name: string) => {  // the game's own colour (its default can be a reference to another variable)
    const t = theme.tokens.find((x) => x.name === name);
    return t?.resolved ?? (t?.default && !t.default.startsWith("var(") ? t.default : "rgb(30, 33, 41)");
  };
  const looks = { theme, gameValue, bars, barImages, pictures, processing };

  return (
    <div className="studio">
      <div className="inspector">
        <div className="note">These parts of FM27 are painted by the game's own code (club colours, the story you're reading, the
          competition you're on). A skin can't change that code, but it can often cover an area with a picture or hide the painted
          layer. Pick an area to see what your skin does to it.</div>
        {data.areas.map((a) => (
          <details key={a.id} className={`section coded-section ${a.id === area.id ? "selected" : ""}`} open={a.id === area.id}
            onClick={(e) => { if ((e.target as HTMLElement).tagName === "SUMMARY") { e.preventDefault(); setSelected(a.id); } }}>
            <summary>{a.title}
              <span className="grow" />
              {a.kind === null ? <span className="badge err">Can't change</span>
                : a.state.mode !== "default" ? <span className="badge ok">{a.state.mode === "hide" ? "Hidden" : "Your picture"}</span>
                : a.kind === "bars" && bars[a.area ?? ""] && bars[a.area ?? ""].mode !== "club" ? <span className="badge ok">Changed</span>
                : a.tested === false ? <span className="badge warn">Untested</span> : null}
            </summary>
            <div className="body">
              <div className="small muted">{a.where}</div>
              <div className="small"><b>What drives it:</b> {a.drivenBy}</div>
              {a.skin && <div className="small"><b>What a skin can do:</b> {a.skin}{a.size ? ` Suggested picture size: ${a.size}.` : ""}</div>}
              {a.cannot && <div className="small" style={{ color: "var(--warn)" }}><b>Why not:</b> {a.cannot}</div>}
              {a.kind === "bars" && <div><button onClick={() => onOpenTab("Bars & backgrounds", a.area)}>Change it in Bars & backgrounds ›</button></div>}
              {a.kind === "image" && <div className="row wrap">
                <button onClick={() => set(a, "image")}>{a.state.mode === "image" ? "Replace picture…" : "Use a picture…"}</button>
                {a.hide && a.state.mode !== "hide" && <button onClick={() => set(a, "hide")}>Hide it</button>}
                {a.state.mode !== "default" && <button className="link small" onClick={() => set(a, "default")}>Back to game default</button>}
              </div>}
              {a.kind === "image" && a.tested === false && <div className="small muted">Not confirmed in FM27 yet: if nothing changes in
                game, set it back to the game default.</div>}
            </div>
          </details>))}
        <details className="section">
          <summary>Can I change the logic behind these areas?</summary>
          <div className="body"><div className="note">{data.logicNote}</div></div>
        </details>
      </div>

      <div className="stage">
        <div className="row"><h3 style={{ margin: 0 }} className="grow">{area.title}</h3><span className="small muted">{area.where}</span></div>
        {area.kind === "bars"
          ? <><div className="small muted">The Home screen in your skin, with this area outlined. It updates as you change it in Bars &
              backgrounds.</div>
            <ScreenCanvas packId={packId} layout="Portal-Large" bars={bars} backdrop={barImages.backdrop ?? null} images={barImages}
              header={area.area === "pageHeader"} highlightAreas={[area.area ?? ""]} /></>
          : <Compare area={area} looks={looks} />}
      </div>
    </div>
  );
}

type Looks = { theme: Theme; gameValue: (n: string) => string; bars: Record<string, BarSetting>; barImages: Record<string, string>;
  pictures: Record<string, string>; processing: [string, string] | null };

/** The game's look next to this skin's for one area. */
function Compare({ area, looks }: { area: Area; looks: Looks }) {
  const unchangeable = area.kind === null;
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="small muted">{unchangeable ? "A skin can't change this area, so it looks the same in every skin. Shown on your skin's panels."
        : "Left: how FM27 paints it. Right: what your skin does to it."}</div>
      <div className="coded-compare">
        {!unchangeable && <figure><figcaption>Game default</figcaption><Sample area={area} looks={looks} skin={false} /></figure>}
        <figure><figcaption>{unchangeable ? "In your skin" : "Your skin"}</figcaption><Sample area={area} looks={looks} skin /></figure>
      </div>
    </div>
  );
}

function Sample({ area, looks, skin }: { area: Area; looks: Looks; skin: boolean }) {
  const { theme, gameValue, pictures, processing } = looks;
  const tok = (n: string) => (skin ? theme.value(n) : gameValue(n));
  const panel = tok("--layout-modules-block-surface");
  const pic = skin && area.state.mode === "image" ? pictures[area.id] : null;
  const hidden = skin && area.state.mode === "hide";
  const backdrop: CSSProperties = { background: "linear-gradient(135deg, #2b3448, #141a26)" };
  const frame = (children: ReactNode, style?: CSSProperties) => <div className="coded-sample" style={{ ...backdrop, ...style }}>{children}</div>;
  const picture = (url: string): CSSProperties => ({ backgroundImage: `url(${url})`, backgroundSize: "100% 100%" });

  switch (area.id) {
    case "continue": {
      const fill = tok("--continue-button-default-background");
      return frame(<div className="coded-continue" style={pic ? picture(pic) : { background: skin ? fill : CLUB }}>
        <span>CONTINUE</span><span>»</span></div>);
    }
    case "processing": {
      const [s, e] = skin && processing ? processing : ["rgb(255, 0, 140)", "rgb(110, 15, 215)"];
      return frame(<div className="coded-card" style={{ background: panel }}>
        <div className="coded-card-head" style={pic ? picture(pic) : { background: `linear-gradient(90deg, ${s}, ${e})` }}>
          <b>Next match</b><span className="small">Sat 14 Feb · League · v Opponents</span></div>
        <div className="coded-card-body"><div className="coded-line" /><div className="coded-line short" /><div className="small muted-on">Processing…</div></div>
      </div>);
    }
    case "news-backgrounds":
      return frame(<div className="coded-card" style={{ background: panel }}>
        <div className="coded-news-art" style={pic ? picture(pic) : hidden ? { background: "transparent" }
          : { background: `radial-gradient(circle at 70% 40%, rgba(255,255,255,0.25) 0 18%, transparent 19%), ${CLUB}` }}>
          {!pic && !hidden && <span className="small">Club or competition art</span>}</div>
        <div className="coded-card-body"><b>Club confirms new signing</b><div className="small muted-on">2 hours ago · Transfers</div></div>
      </div>);
    case "name-links":
      return frame(<div className="coded-card" style={{ background: panel }}>
        <div className="coded-card-body">
          {[["Your club", "rgb(255, 90, 40)"], ["Rival FC", "#ffffff"], ["A. Player", "#ffffff"], ["Another manager's club", "rgb(63, 145, 253)"]]
            .map(([n, c]) => <div key={n} className="coded-name-row"><span style={{ color: c }}>{n}</span><span className="small muted-on">12  7  3  2</span></div>)}
        </div>
      </div>);
    case "kits":
      return frame(<div className="coded-card" style={{ background: panel }}><div className="coded-card-body coded-kits">
        {["#c8102e", "#0b3d91", "#f5c400"].map((c, i) => <div key={c} className="coded-kit" style={{ background: c }}>{i + 7}</div>)}
        <div className="small muted-on">Kits and badges come from each club's own colours and FM's graphics.</div></div></div>);
    default:
      return frame(<div className="coded-card" style={{ background: panel }}><div className="coded-card-body">
        <b>Competition page</b><div className="small muted-on">The competition's own colours and fonts sit on top of your skin here.</div>
      </div></div>);
  }
}
