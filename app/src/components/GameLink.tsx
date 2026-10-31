import { useEffect, useState } from "react";
import { call } from "../api";
import { errorText, useToast } from "../App";

export interface GameLinkStatus {
  available: boolean; reason?: string; loader?: boolean; loaderOurs?: boolean; loaderBuild?: string; bindings?: boolean;
  plugin?: boolean; pluginBundled?: boolean; gameRunning?: boolean; connected?: boolean; otherPlugins?: string[]; logErrors?: string[];
}

/** Reload the skin in FM27 if Game Link is connected; quietly does nothing otherwise. */
export async function reloadInGame(): Promise<boolean> {
  try {
    const s = await call<GameLinkStatus>("gamelink.status");
    if (!s.connected) return false;
    await call("gamelink.reload");
    return true;
  } catch { return false; }
}

/** Optional add-on: a small plugin inside FM27 (via the BepInEx mod loader) that reloads skins, captures
 *  screens and applies a skin's name colour. Nothing is installed until the user asks, and Remove takes out exactly what was added. */
export default function GameLink({ layout, onShot }: { layout?: string; onShot?: () => void }) {
  const toast = useToast();
  const [status, setStatus] = useState<GameLinkStatus | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const refresh = () => call<GameLinkStatus>("gamelink.status").then(setStatus).catch(() => setStatus(null));
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);

  const run = async (method: string, params: object, done: string) => {
    setBusy(true);
    try { await call(method, params); toast(done); } catch (e) { toast({ text: errorText(e), error: true }); }
    setBusy(false); setConfirming(false); refresh();
  };

  if (!status) return <div className="muted small">Checking Game Link…</div>;
  if (!status.available) return <div className="small muted">Game Link isn't available: {status.reason ?? "FM27 wasn't found"}.</div>;
  const installed = status.loader && status.plugin;
  const state = !installed ? "Not installed" : status.connected ? "Connected to FM27" : status.gameRunning
    ? (status.bindings ? "Installed — restart FM27 to connect" : "Installed — FM27 is preparing it (first launch takes a few minutes)")
    : "Installed — start FM27 to connect";

  return (
    <div className="stack">
      <div className="row"><span className={`gl-dot ${status.connected ? "on" : installed ? "idle" : ""}`} /><b>{state}</b></div>
      <div className="small muted">Game Link adds a small helper to FM27 so the studio can reload your skin in the game after
        you save, show what the game is showing, and apply a skin's name colour (Fonts tab). It never touches your saves or
        the game's logic, and only listens on this PC.</div>

      {!installed && !confirming && <div className="row">
        <button onClick={() => setConfirming(true)} disabled={busy || !status.pluginBundled}>Install Game Link…</button>
        {!status.pluginBundled && <span className="small muted">The helper isn't included in this build.</span>}</div>}
      {confirming && <div className="callout small stack">
        <div>This adds the <b>BepInEx</b> mod loader ({status.loader ? "already in your game folder" : "a free, open-source download"})
          and the FM Skin Studio helper to your FM27 folder. The first launch afterwards takes a few extra minutes while BepInEx
          prepares itself. Mods aren't supported by Sports Interactive: if FM27 misbehaves, remove Game Link here.</div>
        {status.gameRunning && <div style={{ color: "var(--err)" }}>Close FM27 first.</div>}
        <div className="row"><button className="primary" disabled={busy || status.gameRunning}
          onClick={() => run("gamelink.install", {}, "Game Link installed. Start FM27 to connect.")}>{busy ? "Installing…" : "Install"}</button>
          <button onClick={() => setConfirming(false)}>Cancel</button></div>
      </div>}

      {installed && <div className="row wrap">
        <button disabled={busy || !status.connected} onClick={() => run("gamelink.reload", {}, "Skins reloaded in FM27")}>Reload skin in FM27</button>
        {layout && <button disabled={busy || !status.connected} onClick={async () => {
          setBusy(true);
          try { await call("gamelink.screenshot", { layout }); toast("Captured from FM27 as this screen's screenshot"); onShot?.(); }
          catch (e) { toast({ text: errorText(e), error: true }); }
          setBusy(false);
        }}>Capture this screen from FM27</button>}
        <span className="grow" />
        <button className="link small" disabled={busy || status.gameRunning} title={status.gameRunning ? "Close FM27 first" : ""}
          onClick={() => run("gamelink.remove", {}, "Game Link removed from FM27")}>Remove Game Link</button>
      </div>}
      {installed && layout && status.connected && <div className="small muted">Capture takes whatever FM27 is showing, so open
        the matching screen in the game first.</div>}
      {(status.otherPlugins?.length ?? 0) > 0 && <div className="small muted">Other mods found: {status.otherPlugins!.join(", ")}.
        Removing Game Link leaves BepInEx in place for them.</div>}
      {(status.logErrors?.length ?? 0) > 0 && <details className="small"><summary>BepInEx reported errors</summary>
        <pre className="mono small" style={{ whiteSpace: "pre-wrap" }}>{status.logErrors!.join("\n")}</pre></details>}
    </div>
  );
}
