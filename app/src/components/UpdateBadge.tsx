import { useEffect, useState } from "react";
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
      <button className={`version-chip ${hasUpdate ? "has-update" : ""}`} onClick={() => setOpen(!open)}
        title="Version and updates">v{version ?? "…"}{hasUpdate && <span className="update-dot" />}</button>
      {open && <div className="update-pop card stack">
        <div className="row"><b className="grow">FM Skin Studio</b><span className="small muted">version {version}</span></div>
        {status.kind === "idle" && <div className="small muted">Check whether a newer version is out.</div>}
        {status.kind === "checking" && <div className="small">Checking…</div>}
        {status.kind === "current" && <div className="small">You're up to date.</div>}
        {status.kind === "dev" && <div className="small muted">Updates are checked in the installed app, not in development.</div>}
        {status.kind === "store" && <div className="small">Opened the Microsoft Store's Downloads and updates page. The Store also
          updates the app on its own.</div>}
        {status.kind === "available" && <>
          <div className="small">Version <b>{status.latest}</b> is available.</div>
          <button className="primary" onClick={async () => { await bridge.downloadUpdate?.();
            if (!status.canInstall) setOpen(false); }}>{status.canInstall ? "Download update" : "Download from GitHub"}</button></>}
        {status.kind === "downloading" && <><div className="small">Downloading… {status.percent}%</div>
          <div className="progress"><div style={{ width: `${status.percent}%` }} /></div></>}
        {status.kind === "ready" && <>
          <div className="small">Version <b>{status.version}</b> is ready. The app restarts to finish installing it.</div>
          <button className="primary" onClick={async () => { if (await guard("exit")) bridge.installUpdate?.(); }}>Restart and update</button></>}
        {status.kind === "error" && <div className="small" style={{ color: "var(--err)" }}>Couldn't check for updates: {status.message}</div>}
        {["idle", "current", "error", "dev"].includes(status.kind) && <button onClick={check}>Check for updates</button>}
      </div>}
    </div>
  );
}
