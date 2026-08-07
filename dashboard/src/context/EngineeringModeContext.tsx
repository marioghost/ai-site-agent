import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "./AuthContext";
import {
  readEngineeringModeEnabled,
  resetEngineeringModeOff,
  writeEngineeringModeEnabled,
} from "../lib/engineeringModeStorage";

interface EngineeringModeContextValue {
  enabled: boolean;
  setEnabled: (next: boolean) => void;
}

const EngineeringModeContext = createContext<EngineeringModeContextValue | null>(null);

export function EngineeringModeProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [enabled, setEnabledState] = useState(() => readEngineeringModeEnabled());

  // Q5 — logout / no session → Mode OFF (no cross-user leak).
  // Wait until auth finished bootstrapping so a brief null user on reload
  // does not wipe the localStorage preference.
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      resetEngineeringModeOff();
      setEnabledState(false);
    }
  }, [user, authLoading]);

  const setEnabled = useCallback((next: boolean) => {
    writeEngineeringModeEnabled(next);
    setEnabledState(next);
  }, []);

  const value = useMemo(() => ({ enabled, setEnabled }), [enabled, setEnabled]);

  return (
    <EngineeringModeContext.Provider value={value}>{children}</EngineeringModeContext.Provider>
  );
}

export function useEngineeringMode() {
  const ctx = useContext(EngineeringModeContext);
  if (!ctx) throw new Error("useEngineeringMode must be used within EngineeringModeProvider");
  return ctx;
}
