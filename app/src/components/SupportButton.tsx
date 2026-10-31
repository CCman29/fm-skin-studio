import { openLink, SUPPORT_URL } from "../api";

/** Opens the Ko-fi page where people can support FM Skin Studio. */
export default function SupportButton({ compact }: { compact?: boolean }) {
  return <button className={`support-btn ${compact ? "compact" : ""}`} title="Support FM Skin Studio on Ko-fi"
    onClick={() => openLink(SUPPORT_URL)}>{compact ? "♥" : "♥ Support"}</button>;
}
