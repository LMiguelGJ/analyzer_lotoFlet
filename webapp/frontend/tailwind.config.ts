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
    extend: {
      colors: {
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
