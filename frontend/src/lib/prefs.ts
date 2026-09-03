export type ThemePref = "system" | "light" | "dark";
export type DensityPref = "comfortable" | "compact" | "dense";

const THEME_KEY = "acms.theme";
const DENSITY_KEY = "acms.density";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode / disabled storage — prefs just won't persist */
  }
}

export function getThemePref(): ThemePref {
  const v = read(THEME_KEY);
  return v === "light" || v === "dark" ? v : "system";
}

export function getDensityPref(): DensityPref {
  const v = read(DENSITY_KEY);
  return v === "compact" || v === "dense" ? v : "comfortable";
}

export function applyTheme(pref: ThemePref) {
  const root = document.documentElement;
  if (pref === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", pref);
}

export function applyDensity(pref: DensityPref) {
  const root = document.documentElement;
  if (pref === "comfortable") root.removeAttribute("data-density");
  else root.setAttribute("data-density", pref);
}

export function setThemePref(pref: ThemePref) {
  write(THEME_KEY, pref);
  applyTheme(pref);
}

export function setDensityPref(pref: DensityPref) {
  write(DENSITY_KEY, pref);
  applyDensity(pref);
}

/** Re-sync the DOM with stored prefs. The pre-paint script in index.html
 *  handles the initial flash; this keeps things correct if that was skipped. */
export function initPrefs() {
  applyTheme(getThemePref());
  applyDensity(getDensityPref());
}
