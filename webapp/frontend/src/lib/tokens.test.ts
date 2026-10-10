// Contract coverage for the BossFarmer-only token system and accessible contrast.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio, WCAG_AA_TEXT_RATIO } from "./contrast";

const tokensCss = readFileSync(resolve(import.meta.dirname, "../styles/tokens.css"), "utf-8");
const indexCss = readFileSync(resolve(import.meta.dirname, "../styles/index.css"), "utf-8");
const tailwindConfig = readFileSync(resolve(import.meta.dirname, "../../tailwind.config.ts"), "utf-8");
const rootBlock = tokensCss.match(/:root\s*\{([^}]+)\}/)?.[1];
if (!rootBlock) throw new Error("BossFarmer token definition not found in tokens.css");
const tokens = new Map(Array.from(rootBlock.matchAll(/(--[\w-]+):\s*([^;]+);/g), ([, name, value]) => [name, value.trim()]));

const expectedTokens = {
  "--bf-chassis": "#17191a", "--bf-chassis-rail": "#121415", "--bf-rule": "#2e3233",
  "--bf-legend": "#e6e4de", "--bf-legend-dim": "#9aa097", "--bf-signal": "#1db954",
  "--bf-alerta": "#e8b12c", "--bf-field-sunken": "#0e1010", "--bf-field-placeholder": "#80857d",
  "--bf-font-display": "\"Archivo Narrow\", ui-sans-serif, sans-serif",
  "--bf-font-body": "\"Archivo\", ui-sans-serif, sans-serif",
  "--bf-font-mono": "ui-monospace, \"SFMono-Regular\", Consolas, monospace",
  "--bf-type-display": "2.6rem", "--bf-type-display-sm": "3.4rem", "--bf-type-display-lg": "4rem",
  "--bf-type-headline": "1.6rem", "--bf-type-headline-sm": "2rem",
  "--bf-type-title-min": "1.05rem", "--bf-type-title-max": "1.3rem",
  "--bf-type-numeral": "2.4rem", "--bf-type-numeral-sm": "3.4rem",
  "--bf-type-body-default": "1rem", "--bf-type-body-min": "0.95rem", "--bf-type-body-max": "1.1rem",
  "--bf-type-body-small": "0.8rem", "--bf-type-label-min": "0.6rem", "--bf-type-label-max": "0.7rem",
  "--bf-line-display": "0.9", "--bf-line-headline": "1", "--bf-line-body": "1.625",
  "--bf-tracking-display": "0.01em", "--bf-tracking-legend": "0.16em", "--bf-tracking-numeral": "-0.02em",
  "--bf-space-gutter": "20px", "--bf-space-gutter-sm": "32px", "--bf-space-row-y": "16px",
  "--bf-space-row-x": "20px", "--bf-space-section-min": "40px", "--bf-space-section-max": "72px",
  "--bf-space-container": "72rem", "--bf-space-touch": "48px",
  "--bf-motion-duration-short3": "150ms", "--bf-motion-duration-medium1": "200ms",
  "--bf-motion-easing-standard": "cubic-bezier(0.2, 0, 0, 1)",
  "--bf-motion-easing-emphasized": "cubic-bezier(0.2, 0, 0, 0.2)",
} as const;

const colors = ["chassis", "chassis-rail", "rule", "legend", "legend-dim", "signal", "alerta", "field-sunken", "field-placeholder"] as const;
function color(name: typeof colors[number]): string { return tokens.get(`--bf-${name}`)!; }

function cssBorderColor(selector: string): string {
  const rules = Array.from(indexCss.matchAll(/([^{}]+)\{([^{}]*)\}/g), ([, selectors, declarations]) => ({ selectors, declarations }));
  const matching = rules.filter(({ selectors }) => selectors.split(",").some((candidate) => candidate.trim() === selector));
  const declaration = matching.map(({ declarations }) => declarations.match(/border-color:\s*([^;]+)|border:\s*[^;]*?\bsolid\s+([^;]+);/)?.slice(1).find(Boolean)).filter(Boolean).at(-1);
  if (!declaration) throw new Error(`No border color declaration found for ${selector}`);
  const token = declaration.match(/var\((--[\w-]+)\)/)?.[1];
  return token ? tokens.get(token)! : declaration;
}

const colorKeys: Record<string, string> = {
  bg: "chassis", surface: "chassis-rail", field: "field-sunken", text: "legend",
  "text-secondary": "legend-dim", accent: "legend", border: "rule", "border-control": "rule",
  chassis: "chassis", rail: "chassis-rail", rule: "rule", legend: "legend", "legend-dim": "legend-dim",
  signal: "signal", alerta: "alerta", sunken: "field-sunken", "field-placeholder": "field-placeholder",
};

describe("BossFarmer design tokens", () => {
  it("defines only the exact BossFarmer token contract, with one dark root and no compatibility aliases", () => {
    expect(tokensCss.match(/:root\s*\{/g)).toHaveLength(1);
    expect(tokensCss).not.toMatch(/\[data-theme\s*=|:root:not\s*\(|prefers-color-scheme/);
    expect(tokensCss).not.toContain("md" + "-sys");
    expect(tokensCss).not.toContain("--" + "color-");
    expect(indexCss).not.toContain("md" + "-sys");
    expect(indexCss).not.toContain("--" + "color-");
    expect(tokens.size).toBe(Object.keys(expectedTokens).length);
    for (const [name, value] of Object.entries(expectedTokens)) expect(tokens.get(name)).toBe(value);
    expect(tokensCss).toContain("font-variant-numeric: tabular-nums");
  });

  it("keeps shape and elevation out of the token contract and fixes them through Tailwind", () => {
    expect(tokensCss).not.toMatch(/--bf-(?:shape|elevation|radius|shadow)[\w-]*\s*:/i);
    expect(tailwindConfig).toMatch(/borderRadius:\s*\{[\s\S]*?DEFAULT:\s*"0px"/);
    expect(tailwindConfig).toMatch(/boxShadow:\s*\{[\s\S]*?DEFAULT:\s*"none"/);
  });

  it("gives enabled controls and their focus boundaries 3:1 contrast using declared CSS colors", () => {
    const controlSelectors = [
      '.control:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      '.ledger-control:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      'input:not([type="checkbox"]):not([type="radio"]):not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      'select:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      'textarea:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      'input[type="checkbox"]:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      'input[type="radio"]:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      '[role="switch"]:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
    ];
    for (const selector of controlSelectors) {
      const border = cssBorderColor(selector);
      expect(contrastRatio(border, color("field-sunken")), `${selector} border against field`).toBeGreaterThanOrEqual(3);
      expect(contrastRatio(border, color("chassis")), `${selector} border against chassis`).toBeGreaterThanOrEqual(3);
    }
    const focusedBorder = cssBorderColor(".control:focus");
    expect(contrastRatio(focusedBorder, color("field-sunken"))).toBeGreaterThanOrEqual(3);
    for (const selector of [
      'input[type="checkbox"]:checked:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      'input[type="radio"]:checked:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
      '[role="switch"][aria-checked="true"]:not(:disabled):not([aria-disabled="true"]):not([aria-invalid="true"])',
    ]) {
      expect(contrastRatio(cssBorderColor(selector), color("signal")), `${selector} border against signal`).toBeGreaterThanOrEqual(3);
    }
  });

  it("keeps required BossFarmer text and field pairs at WCAG AA contrast", () => {
    for (const [foreground, background] of [
      [color("legend"), color("chassis")],
      [color("chassis"), color("signal")],
      [color("legend-dim"), color("chassis")],
      [color("alerta"), color("chassis")],
      [color("field-placeholder"), color("field-sunken")],
    ]) expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
  });

  it("maps all semantic and BossFarmer Tailwind color names directly to BossFarmer variables", () => {
    for (const [key, token] of Object.entries(colorKeys)) {
      const configKey = key.includes("-") ? `"${key}"` : key;
      expect(tailwindConfig).toContain(`${configKey}: "var(--bf-${token})"`);
    }
    expect(tailwindConfig).toContain('heading: "var(--bf-font-display)"');
    expect(tailwindConfig).toContain('body: "var(--bf-font-body)"');
    expect(tailwindConfig).toContain('mono: "var(--bf-font-mono)"');
    expect(tailwindConfig).toContain('"page-margin": "var(--bf-space-gutter)"');
    expect(tailwindConfig).toContain('"section-gap": "var(--bf-space-section-min)"');
    expect(tailwindConfig).toContain('control: "var(--bf-space-touch)"');
  });
});
