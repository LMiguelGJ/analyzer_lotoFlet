'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, 'acceptance.cjs'), 'utf8');

test('acceptance server uses resolved Python and direct uvicorn bootstrap, not production launcher', () => {
  for (const contract of [
    'resolvePythonExecutable', 'sys.executable', 'execFileSync(pythonExecutable',
    'uvicorn.Config(app, host=settings.host, port=settings.port)',
    'create_app(settings, serve_frontend=True)', 'uvicorn.Server(config).run()',
    'Uvicorn running on http://127.0.0.1:${port}', 'if (!child.ready)',
  ]) assert.ok(source.includes(contract), `missing isolation contract: ${contract}`);
  assert.doesNotMatch(source, /spawn\('py', \['-3\.14', '-m', 'laboratorio\.app'\]/);
  assert.doesNotMatch(source, /run_production|webbrowser\.open/);
});

test('acceptance cleanup verifies owned process exit and port closure and reports failures', () => {
  for (const contract of [
    'waitForOwnedServerCleanup', "server.kill('SIGINT')", "child.kill('SIGKILL')",
    'cleanup:', 'portClosed', "summary.status = 'fail'",
  ]) assert.ok(source.includes(contract), `missing cleanup contract: ${contract}`);
});

test('browser error classification admits only the import 409 and aborted GET reads', () => {
  for (const contract of [
    "page.on('response'", 'expectedConflicts', 'abortedReads', 'isAbortedApiRead',
    "request.method() === 'GET'", "errorText === 'net::ERR_ABORTED'", "pathname.startsWith('/api/v1/')",
    'reconcileConflictConsoleErrors', "method: 'POST', url: `${base}/api/v1/history`, status: 409",
    'expected_conflicts: expectedConflicts', 'aborted_reads: abortedReads',
  ]) assert.ok(source.includes(contract), `missing classification contract: ${contract}`);
  const finalAssertions = source.split('\n').filter((line) => line.includes('assert.deepEqual(browserErrors, []'));
  assert.equal(finalAssertions.length, 1, 'browserErrors must stay asserted empty exactly once');
  assert.ok(source.indexOf('reconcileConflictConsoleErrors(expectedConflicts') < source.indexOf('assert.deepEqual(browserErrors, []'));
  assert.ok(source.includes("assert.deepEqual(externalRequests, []") && source.includes("assert.deepEqual(unexpectedResponses, []"));
  // No generic filter: the only console error that is diverted is the 409 line, and ERR_ABORTED is never matched loosely.
  assert.doesNotMatch(source, /browserErrors\s*=\s*browserErrors\.filter|\.includes\('ERR_ABORTED'\)|\.includes\('Failed to load resource'\)/);
  assert.doesNotMatch(source, /ignore(d)?(Errors|Console)|allowlist/i);
});

test('unclassified requestfailed entries carry method and resourceType so an abort is diagnosable', () => {
  const line = source.split('\n').find((l) => l.includes('browserErrors.push(`requestfailed:'));
  assert.ok(line, 'requestfailed entry must be pushed to browserErrors');
  assert.ok(line.includes('${request.method()}'), 'requestfailed message must include the method');
  assert.ok(line.includes('${request.resourceType()}'), 'requestfailed message must include the resourceType');
  assert.ok(line.includes('${request.url()}') && line.includes('${request.failure()?.errorText}'));
  // Diagnosis only: the GET-only abort classification must not be widened.
  assert.equal(source.split('\n').filter((l) => l.includes("request.method() === 'GET'")).length, 1);
});

test('every report branch, failure included, carries the five browser evidence lists', () => {
  const lists = ['external_requests: externalRequests', 'browser_errors: browserErrors', 'expected_conflicts: expectedConflicts',
    'aborted_reads: abortedReads', 'unexpected_responses: unexpectedResponses'];
  const helper = source.match(/const browserEvidence = \(\) => \(\{([\s\S]*?)\}\);/);
  assert.ok(helper, 'browserEvidence helper must define the evidence lists once');
  for (const list of lists) assert.ok(helper[1].includes(list), `browserEvidence missing: ${list}`);
  const failLines = source.split('\n').filter((l) => l.includes("status: 'fail', checks: CHECKS"));
  assert.ok(failLines.length >= 2, 'expected the catch and finally fallback failure summaries');
  for (const l of failLines) assert.ok(l.includes('...browserEvidence()'), `failure report lacks evidence: ${l.trim()}`);
  assert.ok(source.includes("status: 'pass',") && source.includes('...browserEvidence(),'), 'pass report must use the helper too');
});

test('aborted-after-response requires a received response, exact DELETE 204 on a run, and stays strict', () => {
  for (const contract of [
    'abortedAfterResponse', 'aborted_after_response: abortedAfterResponse', 'await request.response()',
    'await Promise.all(pendingRequestEvents)', "method: 'DELETE', status: 204",
    'browserRunId', 'response=${',
  ]) assert.ok(source.includes(contract), `missing aborted-after-response contract: ${contract}`);
  // Pending response lookups must be drained before the reconcile step and the final assertions.
  const drain = source.indexOf('await Promise.all(pendingRequestEvents)');
  assert.ok(drain !== -1 && drain < source.indexOf('reconcileConflictConsoleErrors(expectedConflicts'));
  assert.ok(drain < source.indexOf('assert.deepEqual(browserErrors, []'));
  // The classifier must key on status 204 + DELETE + /api/v1/runs/<uuid>, never on ERR_ABORTED alone.
  assert.ok(source.includes('response.status() === 204') && source.includes('ABORTED_DELETE_RUN_PATH'), 'strict 204 + runs path matcher required');
  assert.doesNotMatch(source, /browserErrors\s*=\s*browserErrors\.filter|\.includes\('ERR_ABORTED'\)/);
  assert.equal(source.split('\n').filter((l) => l.includes('assert.deepEqual(browserErrors, []')).length, 1);
  assert.equal(source.split('\n').filter((l) => l.includes("request.method() === 'GET'")).length, 1, 'GET abort rule must not be widened');
});

test('browserEvidence and every report branch carry aborted_after_response', () => {
  const helper = source.match(/const browserEvidence = \(\) => \(\{([\s\S]*?)\}\);/);
  assert.ok(helper && helper[1].includes('aborted_after_response: abortedAfterResponse'));
});

test('acceptance oracle is frozen data: reference.py never imports the retired legacy engine', () => {
  const oracle = fs.readFileSync(path.join(__dirname, 'reference.py'), 'utf8');
  for (const retired of ['laboratorio.domain.backtest', 'laboratorio.api.backtests', 'laboratorio.storage.backtest_trace']) {
    assert.ok(!oracle.includes(retired), `reference.py must not import ${retired}`);
  }
  assert.ok(oracle.includes('reference-golden.json'), 'reference.py must read the frozen golden');
  assert.ok(source.includes("'reference.py'"), 'acceptance still invokes reference.py');
});
