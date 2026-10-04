import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio, WCAG_AA_TEXT_RATIO, WCAG_AA_UI_RATIO } from "./contrast";

const tokensPath = resolve(import.meta.dirname, "../styles/tokens.css");
const tokensCss = readFileSync(tokensPath, "utf-8");

function readToken(name: string): string {
  const match = tokensCss.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) throw new Error(`token ${name} not found in tokens.css`);
  return match[1];
}

function readRemToken(name: string): number {
  const match = tokensCss.match(new RegExp(`${name}:\\s*([\\d.]+)rem`));
  if (!match) throw new Error(`token ${name} not found as a rem value in tokens.css`);
  return Number(match[1]);
}

describe("typographic scale", () => {
  const scale = ["--type-small", "--type-body", "--type-subsection", "--type-section", "--type-large", "--type-display", "--type-h1"].map(readRemToken);
  it("uses a consistent 1.125–1.2 ratio and keeps desktop H1 within 32–40px", () => {
    for (let index = 1; index < scale.length; index += 1) {
      const ratio = scale[index] / scale[index - 1];
      expect(ratio).toBeGreaterThanOrEqual(1.125);
      expect(ratio).toBeLessThanOrEqual(1.2);
    }
    expect(scale.at(-1)! * 16).toBeGreaterThanOrEqual(32);
    expect(scale.at(-1)! * 16).toBeLessThanOrEqual(40);
  });
});

describe("token contrast (UX2-UX3)", () => {
  const bg = readToken("--color-bg");
  const surface = readToken("--color-surface");
  const field = readToken("--color-field");
  const text = readToken("--color-text");
  const textSecondary = readToken("--color-text-secondary");
  const accent = readToken("--color-accent");
  const borderControl = readToken("--color-border-control");

  it.each([["text on bg", text, bg], ["text on surface", text, surface], ["text on field", text, field], ["secondary text on bg", textSecondary, bg], ["secondary text on surface", textSecondary, surface], ["secondary text on field", textSecondary, field]])("%s meets WCAG AA text contrast (>=4.5:1)", (_label, fg, background) => {
    expect(contrastRatio(fg, background)).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
  });
  it.each([["accent on bg", accent, bg], ["accent on surface", accent, surface], ["accent on field", accent, field], ["control border on bg", borderControl, bg], ["control border on surface", borderControl, surface], ["control border on field", borderControl, field]])("%s meets WCAG AA UI-component contrast (>=3:1)", (_label, fg, background) => {
    expect(contrastRatio(fg, background)).toBeGreaterThanOrEqual(WCAG_AA_UI_RATIO);
  });
  it.each([["accent as text on bg", accent, bg], ["accent as text on surface", accent, surface], ["accent as text on field", accent, field]])("%s meets WCAG AA text contrast (>=4.5:1)", (_label, fg, background) => {
    expect(contrastRatio(fg, background)).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
  });
  it.each(["--color-positive", "--color-negative", "--color-warning", "--color-info"])("%s meets WCAG AA text contrast on ledger surfaces", (token) => {
    const color = readToken(token);
    for (const background of [bg, surface, field]) {
      expect(contrastRatio(color, background)).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
    }
  });
});
