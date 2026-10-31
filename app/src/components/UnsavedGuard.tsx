import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { call, pickFolder } from "../api";
import { errorText, useToast } from "../App";

interface Dirty { id: string; name: string }
type Reason = "exit" | "open" | "create";
type Guard = (reason: Reason, except?: string) => Promise<boolean>;
const GuardCtx = createContext<Guard>(async () => true);
/** Ask to save or discard unsaved skin changes before something that would leave them (exit, opening another skin). */
export const useUnsavedGuard = () => useContext(GuardCtx);

const ACTION: Record<Reason, string> = { exit: "closing FM Skin Studio", open: "opening another skin", create: "starting a new skin" };

export function UnsavedGuardProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [ask, setAsk] = useState<{ reason: Reason; skins: Dirty[] } | null>(null);
  const [backup, setBackup] = useState(true);
  const [busy, setBusy] = useState(false);
  const answer = useRef<(ok: boolean) => void>();

  const guard = useCallback<Guard>(async (reason, except) => {
    let skins: Dirty[] = [];
    try { skins = (await call<Dirty[]>("drafts.dirty")).filter((s) => s.id !== except); } catch { return true; }
    if (!skins.length) return true;
    return new Promise<boolean>((resolve) => { answer.current = resolve; setAsk({ reason, skins }); });
  }, []);

  // keep the window's close button informed, and answer it when it asks
  useEffect(() => {
    const bridge = window.fmskin;
    const tick = () => call<Dirty[]>("drafts.dirty").then((d) => bridge?.setUnsaved?.(d.length > 0)).catch(() => {});
    tick();
    const t = window.setInterval(tick, 3000);
    const off = bridge?.onCloseRequested?.(async () => { if (await guard("exit")) bridge.closeNow?.(); });
    return () => { window.clearInterval(t); off?.(); };
  }, [guard]);

  const finish = (ok: boolean) => { setAsk(null); setBusy(false); answer.current?.(ok); };
  const save = async () => {
    if (!ask) return;
    setBusy(true);
    try {
      let dir: string | null = null;
      if (backup) {
        const status = await call<{ backupFolder?: string | null }>("drafts.status", { pack: ask.skins[0].id });
        dir = status.backupFolder ?? await pickFolder("Choose a folder for skin backups");
        if (!dir) { setBusy(false); return toast("Choose a backup folder, or untick the backup option"); }
      }
      for (const s of ask.skins) await call("drafts.save", { pack: s.id, backup, backup_dir: dir });
      toast(ask.skins.length > 1 ? "Skins saved" : `${ask.skins[0].name} saved`);
      finish(true);
    } catch (e) { toast({ text: errorText(e), error: true }); setBusy(false); }
  };
  const discard = async () => {
    if (!ask) return;
    setBusy(true);
    try { for (const s of ask.skins) await call("drafts.discard", { pack: s.id }); finish(true); }
    catch (e) { toast({ text: errorText(e), error: true }); setBusy(false); }
  };

  return (
    <GuardCtx.Provider value={guard}>
      {children}
      {ask && <div className="modal-backdrop">
        <div className="modal card stack" role="dialog" aria-modal="true">
          <h2 style={{ margin: 0 }}>Save your changes?</h2>
          <div className="small">Before {ACTION[ask.reason]}: {ask.skins.length === 1
            ? <><b>{ask.skins[0].name}</b> has changes that aren't saved.</>
            : <>these skins have changes that aren't saved: <b>{ask.skins.map((s) => s.name).join(", ")}</b>.</>}</div>
          <label className="row small"><input type="checkbox" checked={backup} onChange={(e) => setBackup(e.target.checked)} />
            Back up the previous version first</label>
          <div className="row wrap">
            <button className="primary" disabled={busy} onClick={save}>{busy ? "Working…" : "Save"}</button>
            <button className="danger" disabled={busy} onClick={discard}>Discard changes</button>
            <span className="grow" />
            <button disabled={busy} onClick={() => finish(false)}>Cancel</button>
          </div>
        </div>
      </div>}
    </GuardCtx.Provider>
  );
}
