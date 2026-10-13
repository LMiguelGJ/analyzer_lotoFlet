import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
const css = readFileSync(resolve(process.cwd(), "src/pages/reference-labs/reference-labs.css"), "utf8");
describe("reference laboratory layout safeguards", () => {
  it("contains responsive pages and long frozen hashes without widening the viewport", () => {
    expect(css).toMatch(/\.reference-page,\s*\.reference-page\s*\*\s*\{[^}]*min-width:\s*0/s);
    expect(css).toMatch(/\.reference-sha\s*\{[^}]*max-width:\s*100%[^}]*overflow-wrap:\s*anywhere/s);
    expect(css).toMatch(/\.reference-table-wrap\s*\{[^}]*max-width:\s*100%[^}]*overflow-x:\s*auto/s);
  });
  it("keeps touch controls and a compact one-column catalog on narrow screens", () => {
    expect(css).toMatch(/\.reference-pagination button,\s*\.reference-row-actions button\s*\{[^}]*min-height:\s*48px/s);
    expect(css).toMatch(/@media\s*\(max-width:\s*720px\)\s*\{[^}]*\.reference-catalog\s*\{\s*grid-template-columns:\s*minmax\(0,\s*1fr\)/s);
  });
});
