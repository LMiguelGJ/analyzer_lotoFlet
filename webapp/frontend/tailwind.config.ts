import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // Keep Tailwind's 640px form-layout breakpoint alongside the shell's
    // 800px navigation and 1100px wide-content breakpoints.
    // Tailwind 3.4+ derives `max-nav:`/`max-wide:` automatically.
    screens: {
      sm: "640px",
      nav: "800px",
      wide: "1100px",
    },
    borderRadius: {
      none: "0px",
      DEFAULT: "0px",
      sm: "0px",
      md: "0px",
      lg: "0px",
      xl: "0px",
      "2xl": "0px",
      "3xl": "0px",
      full: "0px",
    },
    boxShadow: {
      DEFAULT: "none",
      sm: "none",
      md: "none",
      lg: "none",
      xl: "none",
      "2xl": "none",
      inner: "none",
      none: "none",
    },
    extend: {
      colors: {
        bf: {
          chassis: "var(--bf-chassis)",
          "chassis-rail": "var(--bf-chassis-rail)",
          rule: "var(--bf-rule)",
          legend: "var(--bf-legend)",
          "legend-dim": "var(--bf-legend-dim)",
          signal: "var(--bf-signal)",
          alerta: "var(--bf-alerta)",
          "field-sunken": "var(--bf-field-sunken)",
          "field-placeholder": "var(--bf-field-placeholder)",
        },
        bg: "var(--color-bg)",
        surface: "var(--color-surface)",
        field: "var(--color-field)",
        text: "var(--color-text)",
        "text-secondary": "var(--color-text-secondary)",
        accent: "var(--color-accent)",
        border: "var(--color-border)",
        "border-control": "var(--color-border-control)",
      },
      fontFamily: {
        heading: "var(--font-heading)",
        mono: "var(--font-mono)",
        body: "var(--font-body)",
      },
      borderRadius: {
        control: "var(--radius-control)",
      },
      spacing: {
        "page-margin": "var(--space-page-margin)",
        "section-gap": "var(--space-section-gap)",
        control: "var(--control-height)",
      },
      transitionDuration: {
        motion: "var(--motion-fast)",
      },
    },
  },
  plugins: [],
} satisfies Config;
