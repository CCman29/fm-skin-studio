import { useEffect, useRef, useState } from "react";
import { formatColour, fromHex, parseColour, toHex } from "../colour";

/** Swatch + popover: colour, opacity and a raw value field (accepts rgb(), rgba(), #hex or var(--token)). */
export default function ColorInput({ value, fallback, onChange }: {
  value: string | null; fallback: string | null; onChange: (v: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(value ?? "");
  const ref = useRef<HTMLDivElement>(null);
  const shown = parseColour(value ?? fallback) ?? { r: 0, g: 0, b: 0, a: 0 };
  useEffect(() => setText(value ?? ""), [value]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div className="swatch" title={value ?? fallback ?? ""} onClick={() => setOpen(!open)}>
        <div style={{ background: formatColour(shown) }} />
      </div>
      {open && <div className="popover stack">
        <div className="row">
          <input type="color" value={toHex(shown)} style={{ width: 48, height: 32, border: "none", background: "none" }}
            onChange={(e) => onChange(formatColour(fromHex(e.target.value, shown.a)))} />
          <div className="grow">
            <div className="small muted">Opacity {Math.round(shown.a * 100)}%</div>
            <input type="range" min={0} max={100} value={Math.round(shown.a * 100)} style={{ width: "100%" }}
              onChange={(e) => onChange(formatColour({ ...shown, a: +e.target.value / 100 }))} />
          </div>
        </div>
        <input type="text" value={text} placeholder={fallback ?? ""} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onChange(text.trim() || null); }}
          onBlur={() => { if ((text.trim() || null) !== value) onChange(text.trim() || null); }} />
        <div className="row"><span className="small muted grow">Game default: {fallback}</span>
          <button className="link small" onClick={() => { onChange(null); setOpen(false); }}>Reset</button></div>
      </div>}
    </div>
  );
}
