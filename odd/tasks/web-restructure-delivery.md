# Web restructuring delivery

## Authorization

User explicitly requested build, browser verification, commit and push.
Target observed: branch `stage`, upstream `origin/stage`, remote
`https://github.com/LMiguelGJ/analyzer_lotoFlet.git`. Initial HEAD `7d69af8`;
local tracking comparison showed 9 commits ahead, 0 behind (not yet refreshed).
No force push, destructive reset, live-data mutation or dependency installation.

## Tasks

- [x] D1 — Build production frontend and verify critical browser journeys.
  Status: complete with documented network-policy caveat. Rebuild exit 0,
  browser assertions 8/8, focused component tests 14/14.
  Delegate command/browser execution to verifier. Run
  `npm.cmd run build` in `webapp/frontend`; use an owned preview server and
  browser session. Never take over or stop existing port 5173. Verify built UI,
  preferably with explicit synthetic API fixtures to avoid production DB writes;
  document that this is browser UI verification, not live backend integration.
  Cover start/replay, historical sessions and keyboard paging/retry, old reports,
  and parity-17 creation/repeat plus representative navigation/mobile layout.
  Tests/typecheck are not included in this request unless a focused diagnostic
  is needed for a concrete build/browser failure. No blanket suite reruns.
- [x] D2 — Resolve concrete failures and prepare the authorized commit scope.
  Status: complete. Staged 73 files; whitespace check passed; only excluded
  historical QA harness remains untracked. Dedicated ledger class and two CSS rules
  verified with component semantic/class assertions; aggregate mobile-card rules
  unchanged. Actual browser RED then GREEN observed at 390px.
  Preserve legitimate
  prior changes; inspect staged/untracked files for unintended data, credentials
  and generated artifacts before committing. Include source, regressions and
  relevant task records; retain documented prior checks and limits.
- [x] D3 — Commit and non-force push to the configured upstream.
  Status: implementation published. Commit
  `8b413c539977084cc3c35675d4102e79e9f57ff9` pushed without force to `origin/stage`
  (`21faa78..8b413c5`). This documentation closure is a follow-up commit.
  Refresh remote state without merging/rebasing automatically;
  stop if divergence or destination ambiguity appears. Use Conventional Commit
  messages, record exact commit identities and verify push result. No PR requested.

## Evidence

Verifier reports `npm.cmd run build` PASS: Vite 7.3.6, 90 modules, 13 seconds.
JavaScript 631.49 kB (179.39 kB gzip), CSS 50.56 kB (9.55 kB gzip). Only warning:
chunk larger than 500 kB. Browser checks are still running against an owned strict
port 5187 production preview with synthetic API responses. This is not live
backend integration. Typecheck and unit suites remain unrun.

Publication inventory: read-only scan covered 73 existing candidate files (75
paths including deletions), with no apparent credentials or personal-data
payloads found. Existing `.env` is unchanged from `origin/stage` and its contents
were not inspected. Preserve but exclude `odd/qa/reestructura-profile-repeat.cjs`
from staging: historical harness embeds a user-specific temporary directory.
Two newly introduced personal absolute paths in the restructuring ledger were
replaced with `<TEMP>` placeholders. Existing synthetic test paths remain.

After `git fetch origin`, comparison is 0 behind / 9 ahead. Index is empty
apart from four pre-existing intent-to-add markers. Prefer one coherent feature
commit rather than artificial splits of interleaved native/UI contracts.

Initial production browser run: 7/8 groups passed. Sole application failure:
historical bet table hidden at 390px (shared desktop-only report CSS). This is
observed RED, not acceptance. Scoped correction is in progress; fresh build and
same browser assertions must pass before delivery. External evidence directory:
`<TEMP>/loto-d1-verify-20260903/` (`result.json`, `history-mobile.png`, `checks.js`,
`runtime.cjs`, `native.ps1`, `native-final.log`). Installed Node Playwright runtime
was used after CLI daemon failure, without installing dependencies. Owned browser
and preview processes were cleaned up; zero listeners on 5187, 5173 untouched.
External Google Fonts requests were blocked by the verification network policy.

Fresh verification after correction:
- `npm.cmd run build`: exit 0 (large-chunk warning remains).
- `npm.cmd run test -- --run src/components/BacktestSessions.test.tsx`: exit 0,
  14/14 tests passed. Full suites and typecheck remain unrun.
- Browser: 8/8 assertion groups passed; mobile ledger `display:block`, horizontal
  keyboard scroll 0 to 40 inside 334px region with 1024px content; no document
  horizontal overflow. Desktop region/table both 1112px. Aggregate cards/table
  retain their original responsive behavior.
- 41 mocked API requests, including one exact synthetic POST; no unknown API
  requests or page errors. Ten console errors: two intentional 409 responses,
  eight blocked Google Fonts requests. Runtime exit 1 is retained and disclosed:
  the external-network guard classified font requests as unexpected, although
  all application assertion groups passed. Not a clean overall harness exit.
- Owned browser/preview cleaned up; zero listeners on 5187. Evidence retained at
  `<TEMP>/loto-d1-verify-fixed/`; original RED evidence preserved separately.
- Synthetic browser responses do not validate live backend integration. Native
  assessment unavailable due to undeclared untracked paths; RDD off. Independent
  verification supplied by the separate browser/test verifier.
