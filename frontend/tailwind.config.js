/** @type {import('tailwindcss').Config} */

// Every value here references a CSS custom property defined in src/index.css.
// Tailwind is the authoring surface; the tokens are the source of truth.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "var(--bg)",
          header: "var(--bg-header)",
        },
        surface: {
          DEFAULT: "var(--surface)",
          raised: "var(--surface-raised)",
          sunken: "var(--surface-sunken)",
          hover: "var(--surface-hover)",
        },
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
          subtle: "var(--border-subtle)",
        },
        ink: {
          DEFAULT: "var(--text)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          muted: "var(--text-muted)",
          inverted: "var(--text-inverted)",
          danger: "var(--text-danger)",
          success: "var(--text-success)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          hover: "var(--primary-hover)",
          active: "var(--primary-active)",
          fg: "var(--primary-fg)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          active: "var(--accent-active)",
          fg: "var(--accent-fg)",
          subtle: "var(--accent-subtle)",
          "subtle-fg": "var(--accent-subtle-fg)",
          border: "var(--accent-border)",
        },
        success: {
          DEFAULT: "var(--success)",
          subtle: "var(--success-subtle)",
          "subtle-fg": "var(--success-subtle-fg)",
          border: "var(--success-border)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          subtle: "var(--warning-subtle)",
          "subtle-fg": "var(--warning-subtle-fg)",
          border: "var(--warning-border)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          subtle: "var(--danger-subtle)",
          "subtle-fg": "var(--danger-subtle-fg)",
          border: "var(--danger-border)",
        },
        info: {
          DEFAULT: "var(--info)",
          subtle: "var(--info-subtle)",
          "subtle-fg": "var(--info-subtle-fg)",
          border: "var(--info-border)",
        },
        neutral: {
          subtle: "var(--neutral-subtle)",
          "subtle-fg": "var(--neutral-subtle-fg)",
          border: "var(--neutral-border)",
        },
        code: {
          bg: "var(--code-bg)",
          fg: "var(--code-fg)",
          border: "var(--code-border)",
        },
        focus: "var(--focus-ring)",
        // risk ramp — bands bound to score; -fg text, -bar indicator, -bg wash
        risk: {
          "low-fg": "var(--risk-low-fg)",
          "low-bar": "var(--risk-low-bar)",
          "low-bg": "var(--risk-low-bg)",
          "elev-fg": "var(--risk-elev-fg)",
          "elev-bar": "var(--risk-elev-bar)",
          "elev-bg": "var(--risk-elev-bg)",
          "high-fg": "var(--risk-high-fg)",
          "high-bar": "var(--risk-high-bar)",
          "high-bg": "var(--risk-high-bg)",
          "sev-fg": "var(--risk-sev-fg)",
          "sev-bar": "var(--risk-sev-bar)",
          "sev-bg": "var(--risk-sev-bg)",
          "crit-fg": "var(--risk-crit-fg)",
          "crit-bar": "var(--risk-crit-bar)",
          "crit-bg": "var(--risk-crit-bg)",
        },
        diff: {
          "add-fg": "var(--diff-add-fg)",
          "add-bg": "var(--diff-add-bg)",
          "del-fg": "var(--diff-del-fg)",
          "del-bg": "var(--diff-del-bg)",
        },
      },
      fontFamily: {
        sans: [
          '"IBM Plex Sans Variable"',
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"IBM Plex Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.875rem", { lineHeight: "1.375rem" }],
        md: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.0625rem", { lineHeight: "1.6rem", letterSpacing: "-0.005em" }],
        xl: ["1.25rem", { lineHeight: "1.7rem", letterSpacing: "-0.011em" }],
        "2xl": ["1.5rem", { lineHeight: "1.9rem", letterSpacing: "-0.016em" }],
        "3xl": ["1.875rem", { lineHeight: "2.2rem", letterSpacing: "-0.021em" }],
        // density-aware table body size (driven by --table-font / [data-density])
        table: ["var(--table-font)", { lineHeight: "1.2rem" }],
        // risk gauge readout — heavy mono numerals, tight
        "risk-sm": ["0.9375rem", { lineHeight: "1", letterSpacing: "-0.01em" }],
        "risk-md": ["1.75rem", { lineHeight: "1", letterSpacing: "-0.02em" }],
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        "2xl": "24px",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
        "in-out": "var(--ease-in-out)",
        standard: "var(--ease-standard)",
      },
      transitionDuration: {
        DEFAULT: "160ms",
        1: "120ms",
        2: "160ms",
        3: "200ms",
        4: "240ms",
        5: "320ms",
      },
      minHeight: {
        control: "var(--control-h)",
        row: "var(--row-h)",
      },
      height: {
        control: "var(--control-h)",
        row: "var(--row-h)",
      },
      spacing: {
        "cell-x": "var(--cell-px)",
        "cell-y": "var(--cell-py)",
      },
      backdropBlur: {
        header: "14px",
      },
    },
  },
  plugins: [],
};
