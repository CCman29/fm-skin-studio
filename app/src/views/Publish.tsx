import { useEffect, useState } from "react";
import { call, pickFolder, pickSavePath, reveal, type LogEvent, type Pack, type Problem } from "../api";
import { errorText, useToast } from "../App";
import type { DraftStatus } from "./Workspace";

interface Backup { id: string; pack: string; created: string[]; replaced: string[] }

function AdvancedChecks({ pack, draft, onChanged }: { pack: Pack; draft: DraftStatus | null; onChanged: () => void }) {
  const toast = useToast();
  const [folder, setFolder] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!folder && draft?.backupFolder) setFolder(draft.backupFolder); }, [draft, folder]);
  const chooseFolder = async () => { const f = await pickFolder("Choose a folder for skin backups"); if (f) setFolder(f); return f; };
  const needFolder = async () => folder ?? await chooseFolder();

  const save = async () => {
    const dir = await needFolder();
    if (!dir) return toast("Choose a backup folder first: your current skin is copied there before it's replaced");
    setBusy(true);
    try {
      const r = await call<{ backup: string; added: string[]; changed: string[]; removed: string[] }>("drafts.save", { pack: pack.id, backup: true, backup_dir: dir });
      toast(`Saved. Backup of the previous version: ${r.backup}`);
      onChanged(); check();
    } catch (e) { toast({ text: errorText(e), error: true }); }
    setBusy(false);
  };
  const discard = async () => {
    if (!window.confirm("Throw away all unsaved changes and go back to the skin as it was last saved?")) return;
    try { await call("drafts.discard", { pack: pack.id }); toast("Unsaved changes discarded"); onChanged(); check(); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const [problems, setProblems] = useState<Problem[] | null>(null);
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [backups, setBackups] = useState<Backup[]>([]);

  const check = async () => {
    try {
      setProblems(await call<Problem[]>("packs.validate", { pack: pack.id }));
      const log = await call<{ events: LogEvent[] }>("log.events", { offset: 0 });
      setEvents(log.events.filter((e) => !e.skin || e.skin === pack.id).slice(-30));
      setBackups(await call<Backup[]>("layouts.backups"));
    } catch (e) { toast({ text: errorText(e), error: true }); }
  };
  useEffect(() => { check(); }, [pack.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const exportPack = async () => {
    const dir = await needFolder();
    if (!dir) return toast("Choose a backup folder first: the skin is backed up before it's exported");
    const dest = await pickSavePath(`${pack.id}.fmskin`);
    if (!dest) return;
    try { const out = await call<string>("packs.export", { pack: pack.id, dest, backup_dir: dir }); toast(`Exported ${out} (backup made first)`); reveal(out); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const applyLayouts = async () => {
    if (!window.confirm(`Copy this pack's ${pack.layouts.length} layout(s) into FM27? Your current layouts for those screens are backed up first and can be restored.`)) return;
    try { const r = await call<{ applied: string[]; backup: string }>("layouts.apply", { pack: pack.id });
      toast(`Applied ${r.applied.length} layout(s). Reopen those screens in FM27.`); check(); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };
  const restore = async (id?: string) => {
    try { const r = await call<{ restored: string[]; removed: string[] }>("layouts.restore", { backup: id });
      toast(`Restored ${r.restored.length} and removed ${r.removed.length} layout file(s)`); check(); onChanged(); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };

  const errors = problems?.filter((p) => p.severity === "error").length ?? 0;
  const warnings = problems?.filter((p) => p.severity === "warning").length ?? 0;

  const list = draft ? [...draft.changes.added.map((f) => `+ ${f}`), ...draft.changes.changed.map((f) => `~ ${f}`),
    ...draft.changes.removed.map((f) => `- ${f}`)] : [];
  return (
    <div className="split">
      <div className="stack">
        <div className="card stack save-card">
          <div className="row"><h2 className="grow" style={{ margin: 0 }}>Save your skin</h2>
            {draft?.dirty ? <span className="badge warn">Unsaved changes</span> : <span className="badge ok">Everything saved</span>}</div>
          <div className="small muted">Your edits are kept in a working copy, so nothing changes in FM27 until you save here. Saving first copies
            the skin as it is now into your backup folder (a .zip you can restore), then puts your changes into your FM27 skins folder.</div>
          {list.length > 0 && <div className="change-list">{list.map((l) => <div key={l}>{l}</div>)}</div>}
          <div className="row wrap"><span className="small">Backup folder:</span>
            <span className="mono small grow">{folder ?? "not chosen yet"}</span>
            <button onClick={chooseFolder}>{folder ? "Change…" : "Choose…"}</button></div>
          <div className="row">
            <button className="primary" disabled={busy || !draft?.dirty} onClick={save}>{busy ? "Saving…" : "Back up and save"}</button>
            {draft?.dirty && <button className="danger" onClick={discard}>Discard changes</button>}
          </div>
          <div className="small muted">After saving, FM27 picks the skin up straight away if it's selected in Preferences.</div>
        </div>
        <div className="card stack">
          <div className="row"><h2 className="grow">Check against the game's rules</h2>
            {problems && (errors ? <span className="badge err">{errors} error{errors > 1 ? "s" : ""}</span>
              : <span className="badge ok">Ready for FM27</span>)}
            {warnings > 0 && <span className="badge warn">{warnings} warning{warnings > 1 ? "s" : ""}</span>}
            <button onClick={check}>Check again</button></div>
          {problems?.length === 0 && <div className="muted small">No problems. Select "{pack.name}" in FM27 → Preferences to use it.</div>}
          {problems?.map((p, i) => (
            <div key={i} className={`problem ${p.severity}`}>
              <span className="small">{p.severity}</span>
              <span><span className="mono">{p.file}{p.line ? `:${p.line}` : ""}</span> — {p.message}</span>
            </div>))}
        </div>
        <div className="card stack">
          <h2>FM27's own messages about skins</h2>
          <p className="muted small" style={{ margin: 0 }}>From the game's log since it last started.</p>
          {events.length === 0 && <div className="muted small">Nothing reported.</div>}
          {events.map((e) => <div key={e.offset} className="problem warning"><span className="small">{e.kind}</span><span className="small">{e.detail}</span></div>)}
        </div>
      </div>
      <div className="stack">
        <div className="card stack">
          <h2>Share</h2>
          <p className="muted small" style={{ margin: 0 }}>Exports the skin, with your latest edits, as one .fmskin file with only your own
            files. The skin is backed up to your backup folder first. Others can import it here, or unzip it into their FM27 skins folder.</p>
          <div className="row"><button className="primary" onClick={exportPack}>Export .fmskin…</button>
            <button onClick={() => reveal(pack.path)} disabled={!window.fmskin}>Show pack folder</button></div>
        </div>
        <div className="card stack">
          <h2>Panel layouts</h2>
          <p className="muted small" style={{ margin: 0 }}>FM27 reads panel layouts from your own layouts folder, not from skins,
            so choosing the skin in Preferences doesn't move panels. Use this to copy the pack's layouts into the game.</p>
          <div className="muted small">{pack.layouts.length ? `${pack.layouts.length} layout(s) in this pack: ${pack.layouts.join(", ")}` : "No layouts in this pack yet."}</div>
          <div className="row"><button className="primary" disabled={!pack.layouts.length} onClick={applyLayouts}>Use this pack's layouts in FM27</button>
            <button disabled={!backups.length} onClick={() => restore()}>Restore my layouts</button></div>
          {backups.slice(0, 5).map((b) => (
            <div key={b.id} className="list-item small"><div className="grow">{b.id} · from {b.pack} · {b.replaced.length} replaced, {b.created.length} added</div>
              <button onClick={() => restore(b.id)}>Restore</button></div>))}
        </div>
      </div>
    </div>
  );
}

// The checks, FM27 log messages, .fmskin export and panel-layout tools above are hidden for now (code kept).
const SHOW_ADVANCED = false;

/** Check and Save: save the skin into the skins folder (backing up the previous version if wanted) and share it as a .zip. */
export default function Publish({ pack, draft, onChanged }: { pack: Pack; draft: DraftStatus | null; onChanged: () => void }) {
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [skinsFolder, setSkinsFolder] = useState<string | null>(null);
  const [backupFolder, setBackupFolder] = useState<string | null>(null);
  useEffect(() => {
    if (draft?.skinsFolder !== undefined) setSkinsFolder(draft.skinsFolderFound ? draft.skinsFolder ?? null : null);
    if (draft?.backupFolder) setBackupFolder(draft.backupFolder);
  }, [draft]);

  const chooseSkinsFolder = async () => {
    const f = await pickFolder("Choose the FM27 skins folder to save into");
    if (!f) return null;
    try { await call("settings.skinsFolder", { folder: f }); setSkinsFolder(f); toast("Skins folder remembered for next time"); return f; }
    catch (e) { toast({ text: errorText(e), error: true }); return null; }
  };
  const chooseBackupFolder = async () => {
    const f = await pickFolder("Choose a folder for skin backups");
    if (!f) return null;
    try { await call("settings.backupFolder", { folder: f }); setBackupFolder(f); return f; }
    catch (e) { toast({ text: errorText(e), error: true }); return null; }
  };

  const save = async (withBackup: boolean) => {
    setAsking(false);
    const target = skinsFolder ?? await chooseSkinsFolder();
    if (!target) return toast("Choose where your FM27 skins folder is to save the skin");
    let dir = backupFolder;
    if (withBackup && !dir) { dir = await chooseBackupFolder(); if (!dir) return toast("Choose a backup folder, or save without a backup"); }
    setBusy(true);
    try {
      const r = await call<{ backup: string | null; savedTo: string }>("drafts.save", { pack: pack.id, backup: withBackup, backup_dir: dir });
      toast(r.backup ? `Saved. Your previous version is backed up as ${r.backup}` : `Saved to ${r.savedTo}`);
      onChanged();
    } catch (e) { toast({ text: errorText(e), error: true }); }
    setBusy(false);
  };

  const share = async () => {
    const dest = await pickSavePath(`${pack.name}.zip`, [{ name: "Compressed (zipped) folder", extensions: ["zip"] }]);
    if (!dest) return;
    try { const out = await call<string>("packs.share", { pack: pack.id, dest }); toast(`Compressed and saved: ${out}`); reveal(out); }
    catch (e) { toast({ text: errorText(e), error: true }); }
  };

  return (
    <div className="stack" style={{ maxWidth: 820 }}>
      <div className="card stack save-card">
        <div className="row"><h2 className="grow" style={{ margin: 0 }}>Save your skin</h2>
          {draft?.dirty ? <span className="badge warn">Unsaved changes</span> : <span className="badge ok">Everything saved</span>}</div>
        <div className="small muted">Your edits wait here until you save. Saving puts the skin in your FM27 skins folder, where you can pick it in
          FM27 under Preferences › Interface › Skin.</div>
        <div className="row wrap"><span className="small">Skins folder:</span>
          <span className="mono small grow">{skinsFolder ?? "FM27's skins folder wasn't found: choose it"}</span>
          <button onClick={chooseSkinsFolder}>{skinsFolder ? "Change…" : "Choose…"}</button></div>
        <div className="row wrap"><span className="small">Backup folder:</span>
          <span className="mono small grow">{backupFolder ?? "not chosen yet (asked the first time you back up)"}</span>
          <button onClick={chooseBackupFolder}>{backupFolder ? "Change…" : "Choose…"}</button></div>
        {!asking ? <div className="row">
          <button className="primary" disabled={busy || !draft?.dirty} onClick={() => setAsking(true)}>{busy ? "Saving…" : "Save skin"}</button>
          {!draft?.dirty && <span className="small muted">Nothing new to save.</span>}
        </div> : <div className="card stack" style={{ background: "var(--panel-2)" }}>
          <b>Back up your previous skin first?</b>
          <div className="small muted">A copy of the skin as it is now is zipped into your backup folder before your changes replace it, so you
            can always go back.</div>
          <div className="row wrap">
            <button className="primary" onClick={() => save(true)}>Back up, then save</button>
            <button onClick={() => save(false)}>Save without a backup</button>
            <button className="link" onClick={() => setAsking(false)}>Cancel</button>
          </div>
        </div>}
      </div>

      <div className="card stack">
        <h2 style={{ margin: 0 }}>Share</h2>
        <div className="small muted">Saves your skin as one compressed .zip file (the same kind Windows makes with "Send to › Compressed (zipped)
          folder"). Others unzip it into their FM27 skins folder. It includes your latest edits, even ones you haven't saved yet.</div>
        <div><button className="primary" onClick={share}>Share as .zip…</button></div>
      </div>

      {SHOW_ADVANCED && <AdvancedChecks pack={pack} draft={draft} onChanged={onChanged} />}
    </div>
  );
}
