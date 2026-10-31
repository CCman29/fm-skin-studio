/** A labelled Exit in the top bar. Closing goes through the same check as the window's X: unsaved skin changes are
 *  offered for saving first. */
export default function ExitButton() {
  const bridge = window.fmskin;
  if (!bridge?.windowControl) return null;
  return <button className="exit-btn" title="Exit FM Skin Studio" onClick={() => bridge.windowControl!("close")}>⏻ Exit</button>;
}
