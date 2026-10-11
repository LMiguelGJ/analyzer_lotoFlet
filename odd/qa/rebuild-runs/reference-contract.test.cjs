'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const reference = fs.readFileSync(path.join(__dirname, 'reference.py'), 'utf8');
const acceptance = fs.readFileSync(path.join(__dirname, 'acceptance.cjs'), 'utf8');
const golden = JSON.parse(fs.readFileSync(path.join(__dirname, 'reference-golden.json'), 'utf8'));

const HISTORY_SHA = 'd1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711';
const RANKINGS_SHA = 'b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d';

test('reference.py has no dependency on the retired legacy engine', () => {
  assert.doesNotMatch(reference, /laboratorio\.domain\.backtest/);
  assert.doesNotMatch(reference, /laboratorio\.api\.backtests/);
  assert.doesNotMatch(reference, /laboratorio\.storage\.backtest_trace/);
  assert.doesNotMatch(reference, /\b(run_backtest|BacktestConfig|_selection_rows)\b/);
});

test('reference.py reads the frozen golden and checks its provenance against the data in use', () => {
  assert.match(reference, /reference-golden\.json/);
  assert.match(reference, /provenance/);
  for (const field of ['frozen_history_sha256', 'rankings_sha256', 'base_commit', 'frozen_on']) {
    assert.ok(reference.includes(field), `reference.py must use provenance field: ${field}`);
  }
  assert.match(reference, /reference\.json/);
});

test('golden carries provenance with the frozen history and rankings digests', () => {
  const p = golden.provenance;
  assert.equal(p.frozen_on, '2026-10-10');
  assert.match(p.base_commit, /^704a02d[0-9a-f]{33}$/);
  assert.match(p.note, /frozen from the legacy flat engine before its retirement/);
  assert.equal(p.frozen_history_sha256, HISTORY_SHA);
  assert.equal(p.rankings_sha256, RANKINGS_SHA);
  assert.equal(golden.reference.frozen_history_sha256, HISTORY_SHA);
  assert.equal(golden.reference.rankings_sha256, RANKINGS_SHA);
});

test('golden keeps every scenario the acceptance consumes', () => {
  const ref = golden.reference;
  for (const key of [
    'legacy_mix_three_position_unlimited',
    'legacy_parity_five_position_flat_golden',
    'legacy_parity_five_position_flat_all_history_unlimited',
    'claimed_limited_mix_fixture',
  ]) assert.ok(ref[key], `golden lacks scenario: ${key}`);
  assert.equal(ref.draws, 105426);
  assert.equal(ref.ranked_draws, 65235);
});

test('ranked parity golden remains distinct from API all-history comparison', () => {
  const ref = golden.reference;
  const ranked = ref.legacy_parity_five_position_flat_golden;
  const all = ref.legacy_parity_five_position_flat_all_history_unlimited;
  assert.equal(ranked.scope, 'ranked historical rows only; retained 65,235-row golden');
  assert.equal(all.scope, 'all chronological history labels, including unranked rows');
  assert.equal(all.draws, ref.draws);
  assert.equal(all.ranked_draws, ref.ranked_draws);
  assert.equal(ranked.totals.goal, 13);
  assert.equal(ranked.totals.ruin, 78);
  assert.equal(ranked.totals.bets, 65235);
  assert.equal(ranked.totals.mean_net_closed, -1572.8);
  assert.equal(ranked.mean_net_closed_scope.closed_sessions, 91);
  assert.equal(ranked.mean_net_closed_scope.total_sessions, 92);
  assert.match(acceptance, /compareOldReference\(golden\.body\.summary\.totals, allHistoryParity\.totals\)/);
  assert.match(acceptance, /assert\.equal\(rankedGolden\.goal, 13\)/);
  assert.match(acceptance, /assert\.equal\(rankedGolden\.ruin, 78\)/);
  assert.match(acceptance, /assert\.equal\(rankedGolden\.mean_net_closed, -1572\.8\)/);
});
