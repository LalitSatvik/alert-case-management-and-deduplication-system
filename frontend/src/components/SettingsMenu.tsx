import { useState, type ReactNode } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/Popover";
import {
  getThemePref,
  getDensityPref,
  setThemePref,
  setDensityPref,
  type ThemePref,
  type DensityPref,
} from "../lib/prefs";
import { cn } from "./ui/cn";

const THEMES: { value: ThemePref; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const DENSITIES: { value: DensityPref; label: string }[] = [
  { value: "comfortable", label: "Comfortable" },
  { value: "compact", label: "Compact" },
  { value: "dense", label: "Dense" },
];

function SegRow<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="space-y-1.5">
      <span className="text-xs font-medium text-ink-tertiary">
        {label}
      </span>
      <div className="flex gap-1 rounded-xl border border-border bg-surface-sunken p-0.5">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={value === o.value}
            onClick={() => onChange(o.value)}
            className={cn(
              "flex-1 rounded-sm px-2 py-1 text-xs font-medium transition-colors",
              value === o.value
                ? "bg-surface text-ink shadow-xs"
                : "text-ink-tertiary hover:text-ink",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SettingsMenu({ trigger }: { trigger: ReactNode }) {
  const [theme, setTheme] = useState<ThemePref>(getThemePref);
  const [density, setDensity] = useState<DensityPref>(getDensityPref);

  return (
    <Popover>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent side="right" align="end" className="w-60 space-y-4">
        <p className="text-sm font-semibold text-ink">Display</p>
        <SegRow
          label="Theme"
          value={theme}
          options={THEMES}
          onChange={(v) => {
            setTheme(v);
            setThemePref(v);
          }}
        />
        <SegRow
          label="Density"
          value={density}
          options={DENSITIES}
          onChange={(v) => {
            setDensity(v);
            setDensityPref(v);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
