import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const tokens = readFileSync(resolve(process.cwd(), "src/styles/tokens.css"), "utf8");
const styles = readFileSync(resolve(process.cwd(), "src/styles/index.css"), "utf8");
function token(name: string): string {
  const found = tokens.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`));
  if (!found) throw new Error(`Missing hex token --${name}`);
  return found[1];
}
function luminance(hex: string): number {
  const channels = hex.slice(1).match(/../g)!.map((part) => parseInt(part, 16) / 255).map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
function contrast(a: string, b: string): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}
function declarations(selector: string): string {
  const start = styles.indexOf(selector);
  if (start < 0) return "";
  const open = styles.indexOf("{", start);
  const close = styles.indexOf("}", open);
  return open < 0 || close < 0 ? "" : styles.slice(open + 1, close);
}
function property(rule: string, name: string): string {
  return rule.match(new RegExp(`(?:^|;)\\s*${name}\\s*:\\s*([^;]+)`))?.[1] ?? "";
}
function cssColor(value: string): string {
  const variable = value.match(/^var\(--([\w-]+)\)$/);
  return variable ? token(variable[1]) : value;
}

describe("live paper-and-ink tokens", () => {
  it("uses the chosen cool paper, cyan grid, ink, muted ink, red pencil and marker palette", () => {
    expect(token("paper")).toBe("#F7FBFC");
    expect(token("grid")).toBe("#CDE5EA");
    expect(token("ink")).toBe("#142C36");
    expect(token("ink-muted")).toBe("#405B64");
    expect(token("pencil-red")).toBe("#B42332");
    expect(token("highlighter-yellow")).toBe("#FFE66D");
  });

  it("uses the WCAG sRGB transfer curve and checks known contrast references", () => {
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrast(token("pencil-red"), token("ink"))).toBeCloseTo(2.24, 1);
  });

  it("meets text and control boundary contrast from the actual tokens", () => {
    expect(contrast(token("ink"), token("paper"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("ink-muted"), token("paper"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("pencil-red"), token("paper"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("ink"), token("highlighter-yellow"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("ink"), token("paper"))).toBeGreaterThanOrEqual(3);
  });

  it("keeps the 24px grid, 48px controls, 2px control boundary and accessibility fallbacks", () => {
    expect(tokens).toMatch(/--grid-size:\s*24px/);
    expect(styles).toMatch(/\.control[^{]*\{[^}]*min-height:\s*48px/s);
    expect(styles).toMatch(/\.control[^{]*\{[^}]*border:\s*2px solid var\(--ink\)/s);
    expect(styles).toContain("prefers-reduced-motion: reduce");
    expect(styles).toContain(":focus-visible");
    expect(styles).toMatch(/\.ledger-button:focus-visible/);
    expect(styles).toMatch(/\.ledger-control:focus-visible/);
    expect(styles).toMatch(/\.ledger-button-primary:active/);
    expect(styles).toMatch(/\.ledger-button:disabled/);
    expect(styles).toMatch(/\.ledger-button\[aria-busy="true"\]/);
    expect(styles).toMatch(/\.ledger-button\[aria-invalid="true"\]/);
    expect(styles).toMatch(/\.ledger-field-choice \.ledger-choice-label[^{}]*\{[^}]*min-width:\s*48px[^}]*min-height:\s*48px/s);
    expect(styles).toMatch(/\.ledger-field-choice \.ledger-choice-control[^{}]*\{[^}]*width:\s*24px[^}]*height:\s*24px/s);
  });

  it("keeps invalid primary button text and boundary legible in every interaction state", () => {
    for (const state of ["", ":hover", ":focus-visible", ":active"]) {
      const rule = declarations(`.ledger-button-primary[aria-invalid="true"]${state}`);
      expect(rule).not.toBe("");
      const background = cssColor(property(rule, "background"));
      const foreground = cssColor(property(rule, "color"));
      const border = cssColor(property(rule, "border-color"));
      expect(background).toBe(token("pencil-red"));
      expect(foreground).toBe(token("paper"));
      expect(contrast(foreground, background)).toBeGreaterThanOrEqual(4.5);
      if (state === ":focus-visible") {
        expect(border).toBe(token("paper"));
        const outline = cssColor(property(rule, "outline").split(/\s+/).at(-1) ?? "");
        expect(property(rule, "outline")).toBe("3px solid var(--ink)");
        expect(contrast(border, background)).toBeGreaterThanOrEqual(3);
        expect(contrast(outline, token("paper-sheet"))).toBeGreaterThanOrEqual(3);
      } else {
        expect(border).toBe(token("pencil-red"));
        expect(contrast(border, token("paper"))).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("keeps disabled text and boundaries legible without opacity dimming", () => {
    expect(styles).not.toMatch(/opacity:\s*0\.58/);
    const button = declarations(".ledger-button:disabled");
    const input = declarations("input:disabled");
    for (const rule of [button, input]) {
      expect(cssColor(property(rule, "background"))).toBe(token("paper-sheet"));
      expect(cssColor(property(rule, "color"))).toBe(token("ink-muted"));
      expect(cssColor(property(rule, "border-color"))).toBe(token("ink-muted"));
      expect(contrast(cssColor(property(rule, "color")), cssColor(property(rule, "background")))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(cssColor(property(rule, "border-color")), cssColor(property(rule, "background")))).toBeGreaterThanOrEqual(3);
    }
  });

  it("contains no former bf tokens or non-flat shadow styles", () => {
    expect(`${tokens}\n${styles}`).not.toMatch(/--bf-/);
    expect([...styles.matchAll(/box-shadow\s*:\s*([^;]+);/g)].every(([, value]) => value.trim() === "none")).toBe(true);
  });
});
