import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    screens: { sm: "640px", nav: "800px", wide: "1100px" },
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
        paper: "var(--paper)", "paper-sheet": "var(--paper-sheet)", grid: "var(--grid)",
        ink: "var(--ink)", "ink-muted": "var(--ink-muted)", "pencil-red": "var(--pencil-red)",
        highlighter: "var(--highlighter-yellow)", field: "var(--control-fill)",
        bg: "var(--paper)", surface: "var(--paper-sheet)", text: "var(--ink)",
        "text-secondary": "var(--ink-muted)", border: "var(--line)", "border-control": "var(--ink)",
      },
      fontFamily: {
        heading: "var(--font-display)", mono: "var(--font-mono)", body: "var(--font-body)",
      },
      borderRadius: { control: "0px" },
      spacing: { "page-margin": "24px", "section-gap": "48px", control: "var(--touch-size)" },
      transitionDuration: { motion: "120ms" },
    },
  },
  plugins: [],
} satisfies Config;
