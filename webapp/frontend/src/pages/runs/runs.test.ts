import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "src/pages/runs/runs.css"), "utf8");

describe("run pages local touch targets and long-text containment", () => {
  it("gives list actions, page links and deletion at least 48px local targets", () => {
    expect(css).toMatch(/\.runs-delete\s*\{[^}]*min-height:\s*48px/s);
    expect(css).toMatch(/\.runs-page\s+a(?:\.link|\.ledger-button)?\s*\{[^}]*min-height:\s*48px/s);
    expect(css).toMatch(/\.runs-page\s+a(?:\.link|\.ledger-button)?\s*\{[^}]*min-width:\s*48px/s);
  });

  it("contains result tables inside scroll regions and keeps result controls touch-sized", () => {
    expect(css).toMatch(/\.runs-table-wrap\s*\{[^}]*overflow-x:\s*auto/s);
    expect(css).toMatch(/\.result-table-wrap\s*\{[^}]*min-width:\s*0[^}]*max-width:\s*100%/s);
    expect(css).toMatch(/\.result-page,\s*\.result-page\s*\*\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.result-select-session\s*\{[^}]*min-height:\s*48px/s);
    expect(css).toMatch(/\.result-bet-table\s*\{[^}]*min-width:\s*900px/s);
  });

  it("establishes a containing block for absolutely positioned sr-only descendants in scroll regions", () => {
    // jsdom does not measure layout, so this guards the CSS contract. Tailwind's sr-only is
    // position:absolute; without a positioned scroll wrapper its containing block becomes the
    // shell and it escapes the overflow clip, widening the document on narrow viewports.
    expect(css).toMatch(/\.runs-table-wrap\s*\{[^}]*overflow-x:\s*auto/s);
    expect(css).toMatch(/\.runs-table-wrap\s*\{[^}]*position:\s*relative/s);
  });

  it("keeps text and number inputs inside their grid label on narrow viewports", () => {
    // jsdom does not measure layout. Without an explicit column, the implicit `auto` track takes the
    // input's intrinsic width (size=20) and pushes the form past a 390px viewport.
    expect(css).toMatch(/\.runs-field\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s);
    const inputRule = css.match(/\.runs-field\s+input([^{,]*)\s*\{([^}]*)\}/s);
    expect(inputRule).not.toBeNull();
    expect(inputRule![2]).toMatch(/width:\s*100%/);
    expect(inputRule![2]).toMatch(/min-width:\s*0/);
    expect(inputRule![1]).toContain(':not([type="checkbox"])');
    expect(inputRule![1]).toContain(':not([type="radio"])');
  });

  it("allows the complete SHA-256 value to wrap within the history metadata", () => {
    expect(css).toMatch(/\.runs-history-meta\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.runs-sha\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.runs-sha\s*\{[^}]*overflow-wrap:\s*anywhere/s);
    expect(css).not.toMatch(/\.runs-sha\s*\{[^}]*(?:text-overflow|line-clamp|overflow:\s*hidden)/s);
  });
});
