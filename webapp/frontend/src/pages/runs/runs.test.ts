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

  it("allows the complete SHA-256 value to wrap within the history metadata", () => {
    expect(css).toMatch(/\.runs-history-meta\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.runs-sha\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.runs-sha\s*\{[^}]*overflow-wrap:\s*anywhere/s);
    expect(css).not.toMatch(/\.runs-sha\s*\{[^}]*(?:text-overflow|line-clamp|overflow:\s*hidden)/s);
  });
});
