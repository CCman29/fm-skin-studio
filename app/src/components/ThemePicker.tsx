import { useState } from "react";
import { applyTheme, savedTheme, THEMES } from "../theme";

/** Small theme menu for the top bar. */
export default function ThemePicker() {
  const [theme, setTheme] = useState(savedTheme());
  return (
    <label className="theme-picker" title={THEMES.find((t) => t.id === theme)?.hint}>
      <span className="theme-dot" />
      <select value={theme} onChange={(e) => { setTheme(e.target.value); applyTheme(e.target.value); }}>
        {THEMES.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
    </label>
  );
}
