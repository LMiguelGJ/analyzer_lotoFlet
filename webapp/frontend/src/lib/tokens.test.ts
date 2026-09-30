import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio, WCAG_AA_TEXT_RATIO, WCAG_AA_UI_RATIO } from "./contrast";

const tokensPath = resolve(import.meta.dirname, "../styles/tokens.css");
const tokensCss = readFileSync(tokensPath, "utf-8");

function readToken(name: string): string {
  const match = tokensCss.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) {
    throw new Error(`token ${name} not found in tokens.css`);
  }
  return match[1];
}

// UX3: 4.5:1 for text on its background, 3:1 for UI-component borders. This test
// measures the actual tokens.css values, it does not assert a hardcoded claim of
// conformance without checking the file.
describe("token contrast (UX2-UX3)", () => {
  const bg = readToken("--color-bg");
  const surface = readToken("--color-surface");
  const field = readToken("--color-field");
  const text = readToken("--color-text");
  const textSecondary = readToken("--color-text-secondary");
  const accent = readToken("--color-accent");
  const borderControl = readToken("--color-border-control");

  it.each([
    ["text on bg", text, bg],
    ["text on surface", text, surface],
    ["text on field", text, field],
    ["secondary text on bg", textSecondary, bg],
    ["secondary text on surface", textSecondary, surface],
    ["secondary text on field", textSecondary, field],
  ])("%s meets WCAG AA text contrast (>=4.5:1)", (_label, fg, bgColor) => {
    expect(contrastRatio(fg, bgColor)).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
  });

  it.each([
    ["accent on bg", accent, bg],
    ["accent on surface", accent, surface],
    ["accent on field", accent, field],
    ["control border on bg", borderControl, bg],
    ["control border on surface", borderControl, surface],
    ["control border on field", borderControl, field],
  ])("%s meets WCAG AA UI-component contrast (>=3:1)", (_label, fg, bgColor) => {
    expect(contrastRatio(fg, bgColor)).toBeGreaterThanOrEqual(WCAG_AA_UI_RATIO);
  });

  // StatusLabel (components/StatusLabel.tsx) renders the "positive" tone as
  // running text (font-mono label + glyph), not just a decorative border, so
  // accent must also clear the 4.5:1 text threshold, not only the 3:1
  // UI-component threshold checked above.
  it.each([
    ["accent as text on bg", accent, bg],
    ["accent as text on surface", accent, surface],
    ["accent as text on field", accent, field],
  ])("%s meets WCAG AA text contrast (>=4.5:1)", (_label, fg, bgColor) => {
    expect(contrastRatio(fg, bgColor)).toBeGreaterThanOrEqual(WCAG_AA_TEXT_RATIO);
  });
});
