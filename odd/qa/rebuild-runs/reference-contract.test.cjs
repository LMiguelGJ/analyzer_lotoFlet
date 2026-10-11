'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const reference = fs.readFileSync(path.join(__dirname, 'reference.py'), 'utf8');
const acceptance = fs.readFileSync(path.join(__dirname, 'acceptance.cjs'), 'utf8');
const allRows = reference.match(/def parity_all_history_rows\(data, \*, coverage: int\) -> list\[Draw\]:([\s\S]*?)\n\ndef mixed_rows/);

test('all-history parity reference is independently built and keeps labels, draws, and votes aligned', () => {
  assert.ok(allRows, 'manual all-history parity row builder exists');
  for (const contract of [
    'votes = parity_votes(history.nums[:, 0])',
    'if len(votes) != len(history.labels)',
    'for index, label in enumerate(history.labels)',
    'int(history.minutes[index])',
    'history.nums[index, :5]',
    'parity_numbers(int(votes[index]))[:coverage]',
  ]) assert.ok(allRows[1].includes(contract), `missing causal alignment contract: ${contract}`);
  assert.doesNotMatch(allRows[1], /rankings|_selection_rows|currentrun|run_data/);
  assert.match(reference, /"scope": "all chronological history labels, including unranked rows"/);
  assert.match(reference, /"ranked_draws": len\(data\.rankings\.row_ids\)/);
});

test('ranked parity golden remains distinct from API all-history comparison', () => {
  assert.match(reference, /legacy_parity_five_position_flat_golden/);
  assert.match(reference, /"scope": "ranked historical rows only; retained 65,235-row golden"/);
  assert.match(acceptance, /compareOldReference\(golden\.body\.summary\.totals, allHistoryParity\.totals\)/);
  assert.match(acceptance, /assert\.equal\(rankedGolden\.goal, 13\)/);
  assert.match(acceptance, /assert\.equal\(rankedGolden\.ruin, 78\)/);
  assert.match(acceptance, /assert\.equal\(rankedGolden\.mean_net_closed, -1572\.8\)/);
});
