"""The skin installer players run (packaged as "Install <skin>.exe" next to a "package" folder).

Window: pick the FM27 install (found automatically: Game Pass, Steam, Epic), pick a backup folder, Install.
"Restore a backup..." puts everything back from a backup folder. Also runs headless:
  installer --install --game <dir> --backup <dir> [--skins <dir>] [--package <dir>]
  installer --restore <backup dir>
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

from . import attributecolours, gamepatch, paths
from .skinpack import PackError


def package_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / "package"


def default_skins() -> Path:
    found = paths.detect().skins_root
    return Path(found) if found else paths._windows_documents() / "Sports Interactive" / paths.GAME_FOLDER / "skins"


def default_backup() -> Path:
    return paths._windows_documents() / "FM27 Skin Backups"


def run_gui(pkg: Path) -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    manifest = json.loads((pkg / gamepatch.PACKAGE_FILE).read_text(encoding="utf-8"))
    name = manifest["name"]
    root = tk.Tk()
    root.title(f"{name} installer")
    root.geometry("720x600")
    root.minsize(640, 540)
    pad = {"padx": 14, "pady": 6}

    ttk.Label(root, text=f"Install the {name} skin for Football Manager 27", font=("Segoe UI", 14, "bold")).pack(anchor="w", **pad)
    about = manifest.get("description") or ""
    changes = ["The skin is copied into your FM27 skins folder."]
    if manifest.get("nameColours"):
        changes.append("FM27's colours for club, team and player names are changed so they're readable on this skin. "
                       "This edits one of the game's own files, which is backed up first.")
    if manifest.get("fromGame"):
        changes.append("Some of the skin's artwork and fonts are made from your own copy of FM27.")
    bands = manifest.get("attributeColours") or []
    if bands:
        changes.append("The skin suggests attribute colours. FM27 keeps those in your own Preferences, so the installer "
                       "can't set them; it lists the values to enter when it's done (they're also in README.txt).")
    ttk.Label(root, text=(about + "\n\n" if about else "") + "\n".join("•  " + c for c in changes),
              wraplength=680, justify="left").pack(anchor="w", **pad)

    # FM27 install
    box = ttk.LabelFrame(root, text="1. Your FM27 install")
    box.pack(fill="x", **pad)
    installs = gamepatch.find_installs()
    game_var = tk.StringVar(value=installs[0]["root"] if installs else "")
    for inst in installs:
        ttk.Radiobutton(box, text=f"{inst['store']}:  {inst['root']}", variable=game_var, value=inst["root"]).pack(anchor="w", padx=8)
    if not installs:
        ttk.Label(box, text="FM27 wasn't found automatically. Choose its folder (Game Pass: XboxGames\\Football Manager 27\\Content).",
                  wraplength=660).pack(anchor="w", padx=8)
    row = ttk.Frame(box); row.pack(fill="x", padx=8, pady=4)
    ttk.Entry(row, textvariable=game_var).pack(side="left", fill="x", expand=True)
    ttk.Button(row, text="Choose…", command=lambda: game_var.set(filedialog.askdirectory(title="FM27 install folder") or game_var.get())).pack(side="left", padx=6)

    # backup folder
    box2 = ttk.LabelFrame(root, text="2. Where to keep the backup")
    box2.pack(fill="x", **pad)
    backup_var = tk.StringVar(value=str(default_backup()))
    ttk.Label(box2, text="Every file the installer changes is copied here first, with RESTORE.txt explaining how to put it back.",
              wraplength=660).pack(anchor="w", padx=8)
    row2 = ttk.Frame(box2); row2.pack(fill="x", padx=8, pady=4)
    ttk.Entry(row2, textvariable=backup_var).pack(side="left", fill="x", expand=True)
    ttk.Button(row2, text="Choose…", command=lambda: backup_var.set(filedialog.askdirectory(title="Backup folder") or backup_var.get())).pack(side="left", padx=6)

    skins_var = tk.StringVar(value=str(default_skins()))
    box3 = ttk.LabelFrame(root, text="3. Your FM27 skins folder")
    box3.pack(fill="x", **pad)
    row3 = ttk.Frame(box3); row3.pack(fill="x", padx=8, pady=4)
    ttk.Entry(row3, textvariable=skins_var).pack(side="left", fill="x", expand=True)
    ttk.Button(row3, text="Choose…", command=lambda: skins_var.set(filedialog.askdirectory(title="FM27 skins folder") or skins_var.get())).pack(side="left", padx=6)

    log = tk.Text(root, height=7, state="disabled")
    log.pack(fill="both", expand=True, **pad)

    def say(msg: str) -> None:
        def put():
            log.configure(state="normal"); log.insert("end", msg + "\n"); log.see("end"); log.configure(state="disabled")
        root.after(0, put)

    buttons = ttk.Frame(root); buttons.pack(fill="x", **pad)

    def busy(on: bool) -> None:
        for b in buttons.winfo_children():
            b.configure(state="disabled" if on else "normal")

    def do_install() -> None:
        if not game_var.get() or not backup_var.get():
            messagebox.showwarning(name, "Choose your FM27 install and a backup folder first.")
            return
        busy(True)

        def work():
            try:
                r = gamepatch.install(pkg, Path(game_var.get()), Path(backup_var.get()), Path(skins_var.get()), log=say)
                root.after(0, lambda: messagebox.showinfo(name, f"{name} is installed.\n\nIn FM27, open Preferences and choose "
                    f"'{name}' as the skin.\n\nYour backup is in:\n{r['backup']}\n\nTo undo everything, run this installer "
                    "again and choose 'Restore a backup', or follow RESTORE.txt in that folder."
                    + ("\n\nAttribute colours (Preferences > Attribute Colours):\n" + "\n".join(attributecolours.lines(bands))
                       if bands else "")))
            except (PackError, OSError) as e:
                msg = str(e)
                if isinstance(e, PermissionError):
                    msg = "Windows didn't allow changes to the FM27 folder. Run the installer as administrator."
                say("Not installed: " + msg)
                root.after(0, lambda: messagebox.showerror(name, msg))
            root.after(0, lambda: busy(False))
        threading.Thread(target=work, daemon=True).start()

    def do_restore() -> None:
        folder = filedialog.askdirectory(title="Choose the backup folder to restore (it holds RESTORE.txt)",
                                         initialdir=backup_var.get())
        if not folder:
            return
        busy(True)

        def work():
            try:
                gamepatch.restore(Path(folder), log=say)
                root.after(0, lambda: messagebox.showinfo(name, "Everything from that backup is back in place."))
            except (PackError, OSError) as e:
                say("Not restored: " + str(e))
                root.after(0, lambda: messagebox.showerror(name, str(e)))
            root.after(0, lambda: busy(False))
        threading.Thread(target=work, daemon=True).start()

    ttk.Button(buttons, text=f"Install {name}", command=do_install).pack(side="right")
    ttk.Button(buttons, text="Restore a backup…", command=do_restore).pack(side="left")
    ttk.Label(root, text="Close Football Manager 27 before installing or restoring.", foreground="#a00").pack(anchor="w", **pad)
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="installer")
    p.add_argument("--package")
    p.add_argument("--install", action="store_true")
    p.add_argument("--game")
    p.add_argument("--backup")
    p.add_argument("--skins")
    p.add_argument("--restore")
    args = p.parse_args(argv)
    try:
        if args.restore:
            print(json.dumps(gamepatch.restore(Path(args.restore))))
        elif args.install:
            pkg = package_dir(args.package)
            print(json.dumps(gamepatch.install(pkg, Path(args.game), Path(args.backup or default_backup()),
                                               Path(args.skins or default_skins()))))
        else:
            run_gui(package_dir(args.package))
    except (PackError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
