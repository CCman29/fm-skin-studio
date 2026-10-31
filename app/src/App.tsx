import { createContext, useCallback, useContext, useState } from "react";
import type { CoreError } from "./api";
import { UnsavedGuardProvider } from "./components/UnsavedGuard";
import Home from "./views/Home";
import Workspace from "./views/Workspace";

interface Toast { text: string; error?: boolean }
const ToastCtx = createContext<(t: Toast | string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

/** Turn any thrown core error into a toast message. */
export function errorText(e: unknown): string {
  const err = e as CoreError;
  return err?.message ?? String(e);
}

export default function App() {
  const [packId, setPackId] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const show = useCallback((t: Toast | string) => {
    const value = typeof t === "string" ? { text: t } : t;
    setToast(value);
    setTimeout(() => setToast((cur) => (cur === value ? null : cur)), value.error ? 7000 : 3500);
  }, []);

  return (
    <ToastCtx.Provider value={show}>
      <UnsavedGuardProvider>
        {packId ? <Workspace packId={packId} onClose={() => setPackId(null)} /> : <Home onOpen={setPackId} />}
      </UnsavedGuardProvider>
      {toast && <div className={`toast ${toast.error ? "err" : ""}`}>{toast.text}</div>}
    </ToastCtx.Provider>
  );
}
