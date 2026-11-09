/* Selected Gilgit-Baltistan district (top-bar selector), remembered in localStorage. */
import { createContext, useContext, useState, type ReactNode } from "react";

export const DISTRICTS = [
  "Skardu",
  "Gilgit",
  "Hunza",
  "Nagar",
  "Ghizer",
  "Astore",
  "Diamer",
  "Ghanche",
  "Shigar",
  "Kharmang",
] as const;

const STORAGE_KEY = "cropdoc.district";

interface DistrictValue {
  district: string; // "" = all of Gilgit-Baltistan
  setDistrict: (value: string) => void;
}

const DistrictContext = createContext<DistrictValue | null>(null);

export function DistrictProvider({ children }: { children: ReactNode }) {
  const [district, setState] = useState<string>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) ?? "";
      return (DISTRICTS as readonly string[]).includes(stored) ? stored : "";
    } catch {
      return "";
    }
  });
  const setDistrict = (value: string) => {
    setState(value);
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      /* ignore */
    }
  };
  return <DistrictContext.Provider value={{ district, setDistrict }}>{children}</DistrictContext.Provider>;
}

export function useDistrict(): DistrictValue {
  const value = useContext(DistrictContext);
  if (!value) throw new Error("useDistrict must be used inside <DistrictProvider>");
  return value;
}
