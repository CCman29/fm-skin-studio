"""Command line for FM Skin Studio's core (also the sidecar entry point: `fmskin rpc`)."""

from __future__ import annotations

import argparse
import json
import sys

from .service import ERRORS, Service


def _print(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fmskin", description="FM27 skin pack tools")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rpc", help="run the JSON-RPC sidecar on stdin/stdout")
    p = sub.add_parser("rpc-http", help="development: serve the same API on http://127.0.0.1:PORT")
    p.add_argument("--port", type=int, default=8765)
    sub.add_parser("paths", help="show detected game and user folders")
    sub.add_parser("index", help="build the local index of the game's theme and layouts")
    sub.add_parser("packs", help="list skins in the skins folder")
    p = sub.add_parser("new", help="create a new skin pack")
    p.add_argument("name")
    p.add_argument("--from", dest="source", help="duplicate an existing skin (by folder id) into the new pack")
    p = sub.add_parser("set", help="set theme tokens: fmskin set PACK --token=value ...")
    p.add_argument("pack")
    p.add_argument("pairs", nargs="+", help="--token=value (value 'default' removes the override)")
    p = sub.add_parser("theme", help="apply a full theme to a pack from a palette JSON file (see recipe.Palette)")
    p.add_argument("pack")
    p.add_argument("palette", help="path to a JSON file with palette colours, or '-' for the defaults")
    p = sub.add_parser("validate", help="check a pack against the game's skin rules")
    p.add_argument("pack")
    p = sub.add_parser("export", help="zip a pack as .fmskin")
    p.add_argument("pack")
    p.add_argument("dest")
    p = sub.add_parser("import", help="unpack a .fmskin as a new pack")
    p.add_argument("file")
    p = sub.add_parser("apply-layouts", help="copy a pack's layouts into the game (backs up yours first)")
    p.add_argument("pack")
    p = sub.add_parser("restore-layouts", help="undo the last apply-layouts")
    p.add_argument("--backup")
    sub.add_parser("gamelink-install", help="set up Game Link in FM27 (used by the Windows installer)")
    args = parser.parse_args(argv)

    service = Service()
    try:
        if args.cmd == "rpc":
            from .rpc import serve
            serve(service)
        elif args.cmd == "rpc-http":
            from .rpc import serve_http
            serve_http(args.port, service)
        elif args.cmd == "paths":
            _print(service.get_paths())
        elif args.cmd == "index":
            _print(service.build_index(lambda s, i, n: print(f"{s} {i + 1}/{n}", file=sys.stderr)))
        elif args.cmd == "packs":
            _print(service.packs())
        elif args.cmd == "new":
            _print(service.create_pack(args.name, args.source))
        elif args.cmd == "set":
            changes = {}
            for pair in args.pairs:
                name, _, value = pair.partition("=")
                changes[name] = None if value == "default" else value
            _print(service.set_tokens(args.pack, changes))
        elif args.cmd == "theme":
            palette = {} if args.palette == "-" else json.loads(open(args.palette, encoding="utf-8").read())
            _print(service.apply_recipe(args.pack, palette))
        elif args.cmd == "validate":
            problems = service.validate(args.pack)
            _print(problems)
            return 1 if any(p["severity"] == "error" for p in problems) else 0
        elif args.cmd == "export":
            print(service.export_pack(args.pack, args.dest))
        elif args.cmd == "import":
            _print(service.import_pack(args.file))
        elif args.cmd == "apply-layouts":
            _print(service.apply_layouts(args.pack))
        elif args.cmd == "restore-layouts":
            _print(service.restore_layouts(args.backup))
        elif args.cmd == "gamelink-install":
            service.gamelink_install()
            print("Game Link is set up. Start FM27 once to finish (the first launch takes a few extra minutes).")
    except ERRORS as e:
        if args.cmd == "gamelink-install":  # the installer shows this output to the user
            print(e.args[0] if isinstance(e, KeyError) and e.args else str(e))
            return 2
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
