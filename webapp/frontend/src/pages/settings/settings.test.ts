import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "src/pages/settings/settings.css"), "utf8");

describe("settings page layout safeguards", () => {
  it("keeps page and data groups shrinkable on narrow screens", () => {
    expect(css).toMatch(/\.settings-page\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.settings-summary\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.settings-history-source\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*540px\)/);
  });
  it("wraps full fingerprints and keeps file controls within their page", () => {
    expect(css).toMatch(/\.settings-fingerprint code\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.settings-fingerprint code\s*\{[^}]*overflow-wrap:\s*anywhere/s);
    expect(css).toMatch(/\.settings-import-form input\[type="file"\]\s*\{[^}]*max-width:\s*100%/s);
  });
  it("uses the established 48px control primitives rather than redefining global tokens", () => {
    expect(css).toMatch(/\.settings-quota-form \.ledger-control/);
    expect(css).toMatch(/\.settings-quota-form \.ledger-button/);
    expect(css).not.toMatch(/(?:--paper|--ink|--focus-width)\s*:/);
  });
});
