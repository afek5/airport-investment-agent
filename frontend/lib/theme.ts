"use client";
import { useCallback, useEffect, useState } from "react";

import { THEME_KEY } from "@/lib/theme-boot";

export type Theme = "dark" | "light";

export function applyTheme(theme: Theme) {
  const c = document.documentElement.classList;
  c.toggle("dark", theme === "dark");
  c.toggle("light", theme === "light");
  document.documentElement.style.colorScheme = theme;
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>("dark");
  useEffect(() => {
    // Sync from the class the boot script set (an external system, so read it once on mount).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(document.documentElement.classList.contains("light") ? "light" : "dark");
  }, []);
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next: Theme = t === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* storage blocked: the toggle still works for this visit */
      }
      return next;
    });
  }, []);
  return [theme, toggle];
}
