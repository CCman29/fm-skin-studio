// Smoke test: start the core sidecar the same way electron/main.cjs does and run a few JSON-RPC calls.
const { spawn } = require("node:child_process");
const readline = require("node:readline");

const core = spawn(process.env.FMSKIN_PYTHON || "python", ["-m", "fmskin.cli", "rpc"], { stdio: ["pipe", "pipe", "inherit"] });
const pending = new Map();
let nextId = 1;
readline.createInterface({ input: core.stdout }).on("line", (line) => {
  const msg = JSON.parse(line);
  if (msg.event) return console.log("event:", msg.event);
  const p = pending.get(msg.id);
  pending.delete(msg.id);
  msg.error ? p.reject(msg.error) : p.resolve(msg.result);
});
const call = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, { resolve, reject });
  core.stdin.write(JSON.stringify({ id, method, params }) + "\n");
});

(async () => {
  try {
    console.log("ping:", await call("ping"));
    const status = await call("index.status");
    console.log("index ready:", status.ready, status.manifest && status.manifest.tokens, "tokens");
    console.log("skins:", (await call("packs.list")).length);
    console.log("fonts builtin:", (await call("fonts.catalog")).builtin.map((f) => f.family).join(", "));
    await call("packs.get", { pack: "does-not-exist" }).catch((e) => console.log("expected error:", e.message));
    await call("shutdown");
    console.log("OK");
  } catch (e) { console.error("FAILED", e); process.exitCode = 1; }
})();
