// Colour themes for the studio's own interface (not the skins it makes). Remembered on this PC.
export const THEMES: { id: string; name: string; hint: string }[] = [
  { id: "studio", name: "Studio", hint: "The logo: navy, sky blue, gold and red" },
  { id: "fm", name: "Football Manager", hint: "Midnight indigo with hot pink and cyan" },
  { id: "pitch", name: "Floodlit Pitch", hint: "Night-match charcoal and grass green" },
  { id: "programme", name: "Matchday Programme", hint: "Light: cream paper, bottle green and maroon" },
  { id: "sunset", name: "Sunset Kickoff", hint: "Dusky aubergine with orange and coral" },
];
const KEY = "fmskin.appTheme";

export function savedTheme(): string {
  try { return localStorage.getItem(KEY) ?? "studio"; } catch { return "studio"; }
}

export function applyTheme(id: string) {
  document.documentElement.dataset.theme = id;
  try { localStorage.setItem(KEY, id); } catch { /* the theme still applies for this session */ }
}
