import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { UpdateCheck } from "../api";
import { useUnsavedGuard } from "./UnsavedGuard";

type Status = { kind: "idle" } | { kind: "checking" } | { kind: "current" } | { kind: "store" } | { kind: "dev" }
  | { kind: "available"; latest: string; canInstall: boolean } | { kind: "downloading"; percent: number }
  | { kind: "ready"; version: string } | { kind: "error"; message: string };
const DAY = 24 * 60 * 60 * 1000;
const LAST_CHECK = "fmskin.lastUpdateCheck";

/** The current version, and Check for updates (Store copies: the Store's update page; direct downloads: GitHub releases). */
export default function UpdateBadge() {
  const bridge = window.fmskin;
  const guard = useUnsavedGuard();
  const [version, setVersion] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [installWhenReady, setInstallWhenReady] = useState(false);
  useEffect(() => {
    if (status.kind !== "ready" || !installWhenReady) return;
    guard("exit").then((ok) => { if (ok) bridge?.installUpdate?.(); else setInstallWhenReady(false); });
  }, [status, installWhenReady]); // eslint-disable-line react-hooks/exhaustive-deps

  const apply = (r: UpdateCheck) => setStatus(
    r.state === "available" ? { kind: "available", latest: r.latest ?? "", canInstall: !!r.canInstall }
      : r.state === "store" ? { kind: "store" } : r.state === "dev" ? { kind: "dev" } : { kind: "current" });
  const check = async () => {
    if (!bridge?.checkForUpdates) return;
    setStatus({ kind: "checking" });
    try { apply(await bridge.checkForUpdates()); try { localStorage.setItem(LAST_CHECK, String(Date.now())); } catch { /* optional */ } }
    catch (e) { setStatus({ kind: "error", message: (e as Error)?.message ?? String(e) }); }
  };

  useEffect(() => {
    bridge?.appInfo?.().then((i) => {
      setVersion(i.version);
      // a quiet check once a day for copies that update themselves (not the Store, not development)
      let last = 0;
      try { last = Number(localStorage.getItem(LAST_CHECK) ?? 0); } catch { /* optional */ }
      if (i.packaged && !i.store && Date.now() - last > DAY) {
        bridge.checkForUpdates?.().then((r) => { if (r.state === "available") apply(r); }).catch(() => {});
        try { localStorage.setItem(LAST_CHECK, String(Date.now())); } catch { /* optional */ }
      }
    }).catch(() => {});
    return bridge?.onUpdateEvent?.((e) => {
      if (e.type === "progress") setStatus({ kind: "downloading", percent: e.percent ?? 0 });
      else if (e.type === "downloaded") setStatus({ kind: "ready", version: e.version ?? "" });
      else setStatus({ kind: "error", message: e.message ?? "Update failed" });
    });
  }, [bridge]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!bridge?.appInfo) return null;
  const hasUpdate = status.kind === "available" || status.kind === "ready";
  return (
    <div className="update-badge">
      <button className={`version-chip ${hasUpdate ? "has-update" : ""}`} title="Click to check for updates"
        onClick={() => { setOpen(true); if (status.kind !== "downloading" && status.kind !== "ready") check(); }}>
        v{version ?? "…"}{hasUpdate && <span className="update-dot" />}</button>
      {open && createPortal(  // drawn over the whole window so nothing can hide it
        <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget && status.kind !== "downloading") setOpen(false); }}>
          <div className="modal card stack" role="dialog" aria-modal="true">
            <h2 style={{ margin: 0 }}>Updates</h2>
            {(status.kind === "checking" || status.kind === "idle") && <div>Checking for a new version…</div>}
            {status.kind === "current" && <div>Version {version} is up to date.</div>}
            {status.kind === "dev" && <div className="muted">Updates are checked in the installed app, not in development.</div>}
            {status.kind === "store" && <div>Opened the Microsoft Store's Downloads and updates page. The Store also updates the app on its own.</div>}
            {status.kind === "available" && <div>Version <b>{status.latest}</b> is available (you have {version}).
              {status.canInstall ? " Install it now? The app restarts to finish." : " Download it from GitHub?"}</div>}
            {status.kind === "downloading" && <><div>Downloading version… {status.percent}%</div>
              <div className="progress"><div style={{ width: `${status.percent}%` }} /></div></>}
            {status.kind === "ready" && <div>{installWhenReady ? `Installing version ${status.version}. The app restarts in a moment.`
              : `Version ${status.version} is downloaded and ready to install.`}</div>}
            {status.kind === "error" && <div style={{ color: "var(--err)" }}>Couldn't check for updates: {status.message}</div>}
            <div className="row">
              {status.kind === "available" && <button className="primary" onClick={async () => {
                if (!status.canInstall) { await bridge.downloadUpdate?.(); setOpen(false); return; }
                setInstallWhenReady(true);
                setStatus({ kind: "downloading", percent: 0 });
                try { await bridge.downloadUpdate?.(); } catch (e) { setStatus({ kind: "error", message: (e as Error)?.message ?? String(e) }); }
              }}>{status.canInstall ? "Install now" : "Download from GitHub"}</button>}
              {status.kind === "error" && <button onClick={check}>Try again</button>}
              {status.kind === "ready" && !installWhenReady && <button className="primary"
                onClick={async () => { if (await guard("exit")) bridge.installUpdate?.(); }}>Restart and install</button>}
              <span className="grow" />
              {status.kind !== "downloading" && !(status.kind === "ready" && installWhenReady) &&
                <button onClick={() => setOpen(false)}>{status.kind === "available" ? "Later" : "Close"}</button>}
            </div>
          </div>
        </div>, document.body)}
    </div>
  );
}
