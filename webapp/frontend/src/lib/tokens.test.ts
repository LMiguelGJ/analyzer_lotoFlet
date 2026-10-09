// Contract coverage: BossFarmer token aliases and accessible text contrast.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio, WCAG_AA_TEXT_RATIO } from "./contrast";

const tokensCss = readFileSync(resolve(import.meta.dirname, "../styles/tokens.css"), "utf-8");
const rootBlock = tokensCss.match(/:root\s*\{([^}]+)\}/)?.[1];
if (!rootBlock) throw new Error(":root token definition not found in tokens.css");
const tokens = new Map(Array.from(rootBlock.matchAll(/(--[\w-]+):\s*([^;]+);/g), ([, name, value]) => [name, value.trim()]));

const bossFarmerColors = {
  "--bf-chassis": "#17191a",
  "--bf-chassis-rail": "#121415",
  "--bf-rule": "#2e3233",
  "--bf-legend": "#e6e4de",
  "--bf-legend-dim": "#9aa097",
  "--bf-signal": "#1db954",
  "--bf-alerta": "#e8b12c",
  "--bf-field-sunken": "#0e1010",
  "--bf-field-placeholder": "#80857d",
} as const;

function resolveToken(name: string, seen = new Set<string>()): string {
  if (seen.has(name)) throw new Error(`cyclic token reference at ${name}`);
  const value = tokens.get(name);
  if (!value) throw new Error(`missing token ${name}`);
  const reference = value.match(/^var\((--[\w-]+)\)$/);
  if (!reference) return value;
  return resolveToken(reference[1], new Set([...seen, name]));
}

const requiredColors = [
  "primary", "on-primary", "primary-container", "on-primary-container",
  "secondary", "on-secondary", "secondary-container", "on-secondary-container",
  "tertiary", "on-tertiary", "tertiary-container", "on-tertiary-container",
  "background", "on-background", "surface", "on-surface", "surface-variant",
  "on-surface-variant", "surface-container-lowest", "surface-container-low", "surface-container",
  "surface-container-high", "surface-container-highest", "outline", "outline-variant",
  "error", "on-error", "error-container", "on-error-container", "shadow", "scrim",
  "inverse-surface", "inverse-on-surface", "inverse-primary", "surface-tint",
];

const requiredLegacyAliases = [
  "--color-bg", "--color-surface", "--color-field", "--color-text", "--color-text-secondary",
  "--color-accent", "--color-border", "--color-border-control", "--color-positive", "--color-negative",
  "--color-warning", "--color-info", "--chart-1", "--chart-2", "--chart-3", "--chart-4",
];

const expectedColorAliases: Record<string, keyof typeof bossFarmerColors | "--bf-elevation-flat"> = {
  primary: "--bf-legend", "on-primary": "--bf-chassis", "primary-container": "--bf-signal",
  "on-primary-container": "--bf-chassis", secondary: "--bf-legend-dim", "on-secondary": "--bf-chassis",
  "secondary-container": "--bf-chassis-rail", "on-secondary-container": "--bf-legend",
  tertiary: "--bf-legend-dim", "on-tertiary": "--bf-chassis", "tertiary-container": "--bf-chassis-rail",
  "on-tertiary-container": "--bf-legend", error: "--bf-alerta", "on-error": "--bf-chassis",
  "error-container": "--bf-chassis-rail", "on-error-container": "--bf-alerta",
  background: "--bf-chassis", "on-background": "--bf-legend", surface: "--bf-chassis",
  "on-surface": "--bf-legend", "surface-variant": "--bf-chassis-rail", "on-surface-variant": "--bf-legend-dim",
  "surface-container-lowest": "--bf-field-sunken", "surface-container-low": "--bf-chassis-rail",
  "surface-container": "--bf-chassis-rail", "surface-container-high": "--bf-chassis-rail",
  "surface-container-highest": "--bf-chassis-rail", outline: "--bf-rule", "outline-variant": "--bf-rule",
  shadow: "--bf-elevation-flat", scrim: "--bf-chassis", "inverse-surface": "--bf-legend",
  "inverse-on-surface": "--bf-chassis", "inverse-primary": "--bf-chassis", "surface-tint": "--bf-legend",
};

describe("BossFarmer design tokens", () => {
  it("defines the exact palette once and retains complete legacy aliases and type/motion tokens", () => {
    expect(tokensCss.match(/:root\s*\{/g)).toHaveLength(1);
    expect(tokensCss).not.toMatch(/\[data-theme\s*=|:root:not\s*\(/);
    expect(tokensCss).not.toContain("prefers-color-scheme");
    for (const [name, value] of Object.entries(bossFarmerColors)) expect(tokens.get(name)).toBe(value);
    for (const role of requiredColors) {
      expect(tokens.get(`--md-sys-color-${role}`)).toBe(`var(${expectedColorAliases[role]})`);
      const resolved = resolveToken(`--md-sys-color-${role}`);
      if (role === "shadow") expect(resolved).toBe("none");
      else expect(resolved).toMatch(/^#[\da-f]{6}$/i);
    }
    for (const name of requiredLegacyAliases) {
      expect(tokens.get(name)).toMatch(/^var\(--bf-[\w-]+\)$/);
      expect(resolveToken(name)).toMatch(/^#[\da-f]{6}$/i);
    }
    for (const name of [
      "--md-sys-typescale-display-large-size", "--md-sys-typescale-headline-small-size",
      "--md-sys-typescale-title-medium-size", "--md-sys-typescale-body-large-size",
      "--md-sys-typescale-label-small-size", "--md-sys-motion-duration-medium2",
      "--md-sys-motion-easing-emphasized",
    ]) expect(tokens.has(name)).toBe(true);
    expect(tokensCss).toContain("font-variant-numeric: tabular-nums");
  });

  it("keeps every shape token square and every elevation token flat", () => {
    expect(tokens.get("--bf-radius-live")).toBe("0px");
    expect(tokens.get("--bf-elevation-flat")).toBe("none");
    for (const corner of ["xs", "sm", "md", "lg", "xl", "full"]) {
      expect(resolveToken(`--md-sys-shape-corner-${corner}`)).toBe("0px");
    }
    for (const level of [0, 1, 2, 3, 4, 5]) {
      expect(resolveToken(`--md-sys-elevation-level${level}`)).toBe("none");
    }
  });

  it("keeps important text role pairs at WCAG AA contrast against resolved palette colors", () => {
    for (const [foreground, background] of [
      ["--md-sys-color-on-surface", "--md-sys-color-surface"],
      ["--md-sys-color-on-background", "--md-sys-color-background"],
      ["--md-sys-color-on-primary", "--md-sys-color-primary"],
      ["--md-sys-color-on-primary-container", "--md-sys-color-primary-container"],
      ["--md-sys-color-on-tertiary", "--md-sys-color-tertiary"],
    ]) expect(contrastRatio(resolveToken(foreground), resolveToken(background))).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
  });
});
