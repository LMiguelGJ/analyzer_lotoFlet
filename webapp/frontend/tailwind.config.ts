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
      none: "0px", DEFAULT: "0px", sm: "0px", md: "0px", lg: "0px",
      xl: "0px", "2xl": "0px", "3xl": "0px", full: "0px",
    },
    boxShadow: {
      DEFAULT: "none", sm: "none", md: "none", lg: "none", xl: "none",
      "2xl": "none", inner: "none", none: "none",
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
        bg: "var(--bf-chassis)",
        surface: "var(--bf-chassis-rail)",
        field: "var(--bf-field-sunken)",
        text: "var(--bf-legend)",
        "text-secondary": "var(--bf-legend-dim)",
        accent: "var(--bf-legend)",
        border: "var(--bf-rule)",
        "border-control": "var(--bf-rule)",
        chassis: "var(--bf-chassis)",
        rail: "var(--bf-chassis-rail)",
        rule: "var(--bf-rule)",
        legend: "var(--bf-legend)",
        "legend-dim": "var(--bf-legend-dim)",
        signal: "var(--bf-signal)",
        alerta: "var(--bf-alerta)",
        sunken: "var(--bf-field-sunken)",
      },
      fontFamily: {
        heading: "var(--bf-font-display)",
        mono: "var(--bf-font-mono)",
        body: "var(--bf-font-body)",
      },
      borderRadius: { control: "0px" },
      spacing: {
        "page-margin": "var(--bf-space-gutter)",
        "section-gap": "var(--bf-space-section-min)",
        control: "var(--bf-space-touch)",
      },
      transitionDuration: { motion: "var(--bf-motion-duration-short3)" },
    },
  },
  plugins: [],
} satisfies Config;
