// Contract coverage: Material 3 token completeness and accessible role-pair contrast.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio, WCAG_AA_TEXT_RATIO, WCAG_AA_UI_RATIO } from "./contrast";

const tokensCss = readFileSync(resolve(import.meta.dirname, "../styles/tokens.css"), "utf-8");

function scheme(selector: string): Map<string, string> {
  const block = tokensCss.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\\]\\]/g, "\\$&")}\\s*\\{([^}]+)\\}`))?.[1];
  if (!block) throw new Error(`scheme ${selector} not found in tokens.css`);
  return new Map(Array.from(block.matchAll(/(--[\w-]+):\s*([^;]+);/g), ([, name, value]) => [name, value.trim()]));
}

const light = scheme(":root");
const dark = scheme('[data-theme="dark"]');
const requiredColors = [
  "primary", "on-primary", "primary-container", "on-primary-container",
  "secondary", "on-secondary", "tertiary", "on-tertiary",
  "background", "on-background", "surface", "on-surface", "surface-variant",
  "on-surface-variant", "surface-container-low", "surface-container",
  "surface-container-high", "surface-container-highest", "outline", "outline-variant",
  "error", "on-error",
];

function color(tokens: Map<string, string>, role: string): string {
  const value = tokens.get(`--md-sys-color-${role}`);
  if (!value || !/^#[\da-f]{6}$/i.test(value)) throw new Error(`invalid or missing color role ${role}`);
  return value;
}

describe("Material 3 design tokens", () => {
  it("provides complete light and dark color schemes and the full type/shape/motion system", () => {
    for (const tokens of [light, dark]) {
      for (const role of requiredColors) expect(color(tokens, role)).toMatch(/^#[\da-f]{6}$/i);
      for (const name of [
        "--md-sys-typescale-display-large-size", "--md-sys-typescale-headline-small-size",
        "--md-sys-typescale-title-medium-size", "--md-sys-typescale-body-large-size",
        "--md-sys-typescale-label-small-size", "--md-sys-shape-corner-xs",
        "--md-sys-shape-corner-xl", "--md-sys-motion-duration-medium2",
        "--md-sys-motion-easing-emphasized", "--md-sys-elevation-level2",
      ]) expect(tokensCss).toContain(name);
    }
    expect(tokensCss).toContain("prefers-color-scheme: dark");
    expect(tokensCss).toContain("font-variant-numeric: tabular-nums");
    expect(tokensCss).not.toMatch(/Georgia|Times New Roman|border-radius:\s*0(?:px|rem)?\b/i);
  });

  it.each([["claro", light], ["oscuro", dark]] as const)("keeps key %s role pairs accessible", (_scheme, tokens) => {
    for (const [foreground, background] of [
      ["on-surface", "surface"],
      ["on-background", "background"],
      ["on-primary", "primary"],
      ["on-primary-container", "primary-container"],
      ["on-tertiary", "tertiary"],
    ]) expect(contrastRatio(color(tokens, foreground), color(tokens, background))).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
    expect(contrastRatio(color(tokens, "outline"), color(tokens, "surface"))).toBeGreaterThanOrEqual(WCAG_AA_UI_RATIO);
  });
});
