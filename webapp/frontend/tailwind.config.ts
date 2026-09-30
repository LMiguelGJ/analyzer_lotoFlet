import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // UX16: the sidebar collapses and the shell stacks below 800px (`nav`);
    // `wide` remains 1100px for content such as the wizard summary. These
    // replace Tailwind's default `sm/md/lg/xl/2xl` (unused elsewhere) so
    // there is one breakpoint per concern and no 768px/800px dead zone.
    // Tailwind 3.4+ derives `max-nav:`/`max-wide:` automatically.
    screens: {
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
