import { MIN_RATIO, type LightWarning } from "../lightWarnings";

/** Explains why some colours won't work and lets the user jump to each one. */
export default function LightWarningBanner({ warnings, onGo }: { warnings: LightWarning[]; onGo: (target: string) => void }) {
  if (!warnings.length) return null;
  return (
    <div className="card stack light-warning">
      <div><b>Too light for FM27's white text</b></div>
      <div className="small">FM27 always draws club, team and player names, card titles, menu text and the tabs and labels that sit on the backdrop in white, and a skin
        can't change that. These areas need to be dark enough for white text (at least {MIN_RATIO}:1 contrast):</div>
      <div className="row wrap">{warnings.map((w) => (
        <button key={w.target} className="chip" onClick={() => onGo(w.target)}>{w.area} · {w.ratio}:1 ›</button>))}</div>
    </div>
  );
}
