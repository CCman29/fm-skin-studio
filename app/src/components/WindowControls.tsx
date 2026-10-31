import { useEffect, useState } from "react";

/** Minimise / maximise / close for the app's own window frame (Windows and Linux; macOS keeps its traffic lights). */
export default function WindowControls() {
  const bridge = window.fmskin;
  const [maximized, setMaximized] = useState(false);
  useEffect(() => {
    if (!bridge?.windowControl) return;
    bridge.windowControl("state").then((s) => setMaximized(!!s?.maximized));
    return bridge.onMaximized?.(setMaximized);
  }, [bridge]);
  if (!bridge?.windowControl || bridge.platform === "darwin") return null;
  return (
    <div className="win-controls">
      <button title="Minimise" onClick={() => bridge.windowControl!("minimize")}>&#xE921;</button>
      <button title={maximized ? "Restore" : "Maximise"} onClick={() => bridge.windowControl!("maximize")}>{maximized ? "\uE923" : "\uE922"}</button>
      <button className="win-close" title="Exit" onClick={() => bridge.windowControl!("close")}>&#xE8BB;</button>
    </div>
  );
}
