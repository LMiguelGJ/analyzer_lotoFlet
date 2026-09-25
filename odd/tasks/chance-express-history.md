# Chance Express Dated Historical Downloader

## Objective
Create a root-level downloader that retrieves the complete Chance Express archive currently exposed by the available paginated source and writes dated records containing all five ordered positions.

## Problem and rationale
`lagacy_loto/loteka_numbers.json` is a flattened one-number-per-draw history. `lagacy_loto/scrapy.py` extracts only the first prize position and has no draw date/time/contest ID. Analysis and the parity simulator need complete, timestamped draw records. Loteka's date endpoint is empty for several tested older dates; the GanaMas archive currently exposes 29,155 entries over 584 pages, with earliest observed draw 774903 dated 2026-03-20. Therefore the script must report the actual available coverage and must not claim it reconstructed all historical data since inception.

## Scope
- Add one root-level Python script using existing Python dependencies (`requests`, `beautifulsoup4`).
- Crawl the paginated ChanceExpress archive, parse draw ID, local date/time, and all five displayed number positions in order.
- Preserve duplicate values across positions; validate five values in range 00-99.
- Store numbers as two-character strings, source provenance, and stable ordering; deduplicate by draw ID and sort chronologically.
- Detect pagination/coverage and clearly report earliest/latest records and count. Fail on structural parse errors rather than silently saving a falsely complete archive.
- Support output path and bounded-page option for safe smoke checks; do not run full scrape unless separately authorized.

## Constraints / non-goals
- Do not alter legacy files or the existing JSON.
- Do not fabricate missing historical results or claim all-time completeness when the source archive starts later.
- Do not mix regular ChanceExpress and Extra hourly draws.
- Do not infer unique numbers per draw; repeats were observed across positions.
- No bets, account access, commits, or dependency installation.

## Tasks
- [x] CEH-1 — Inspect official rules, legacy scraper/simulator, and alternative historical-source coverage.
  - Evidence: official rules describe five 00-99 positions, payouts 70/8/4/2/1; legacy parser retains only first position; live archive exposes 584 pages / 29,155 results; page 584 starts at draw 774903 on 2026-03-20. Older Loteka endpoint probes returned empty bodies.
- [ ] CEH-2 — Implement root-level paginated archive downloader and dated five-position JSON schema.
  - Route: inline single-file implementation; required delegation trigger (long-session context) satisfied by read-only `gentle-ai-explore` task mugi2gew-1-pibj.
- [ ] CEH-3 — Verify parser with bounded page sample and syntax/behavior checks; report actual available range and limitations.
  - Runtime: run one-page smoke download to a temporary output only; no full archive scrape in this task.

## Acceptance criteria
- Script is in repository root, has CLI help, output path and max-pages/bounded run option.
- Every stored record contains draw ID, ISO date, local time, five two-character strings in order, and source URL/page.
- Repeated numbers are retained; malformed cards are surfaced.
- Bounded smoke run produces parseable JSON and accurately reports page coverage; full mode discovers all archive pages but does not claim historical completeness before its earliest available archive record.
- No tracked legacy files are changed; no commit is created.

## Progress
- CEH-1 complete; CEH-2 in progress.
- Existing parent-repository legacy relocation changes and unrelated untracked `odd/` predate this task; do not alter them.
- Last verified external archive endpoint is `https://ganamas.com.do/chance-express-resultados-de-hoy-loteka`; its oldest currently exposed page is page 584 (2026-03-20); archive completeness before that is unknown.
