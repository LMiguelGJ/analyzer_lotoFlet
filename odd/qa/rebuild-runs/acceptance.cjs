#!/usr/bin/env node
/*
 * Bounded independent acceptance harness for feat/rebuild-corridas.
 * Run from the repository root: node odd/qa/rebuild-runs/acceptance.cjs
 * All writable state (SQLite, parity cache, logs, reference exports, screenshots) is
 * isolated under one retained OS temporary directory. This script does not retire code.
 */
'use strict';

const assert = require('node:assert/strict');
const { spawn, execFileSync, spawnSync } = require('node:child_process');
const { createRequire } = require('node:module');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const { setTimeout: delay } = require('node:timers/promises');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '../../..');
const BACKEND = path.join(ROOT, 'webapp', 'backend');
const REQUIRE_PLAYWRIGHT = createRequire('C:/Users/luism/AppData/Roaming/npm/node_modules/@playwright/cli/package.json');
const { chromium } = REQUIRE_PLAYWRIGHT('playwright');
const CHECKS = [];
const failures = [];
let server = null;
let browser = null;
let context = null;

function check(name, fn) {
  try {
    const value = fn();
    assert.notEqual(value, false);
    CHECKS.push({ name, status: 'pass' });
  } catch (error) {
    failures.push({ name, error: error.stack || String(error) });
    CHECKS.push({ name, status: 'fail', message: error.message });
    throw error;
  }
}
async function step(name, fn) {
  try {
    await fn();
    CHECKS.push({ name, status: 'pass' });
  } catch (error) {
    failures.push({ name, error: error.stack || String(error) });
    CHECKS.push({ name, status: 'fail', message: error.message });
    throw error;
  }
}
function resolvePythonExecutable() {
  const result = spawnSync('py', ['-3.14', '-c', 'import sys; print(sys.executable)'], {
    cwd: BACKEND, encoding: 'utf8', windowsHide: true,
  });
  if (result.status !== 0) throw new Error(`could not resolve Python 3.14 executable: ${result.stderr || result.error}`);
  const executable = result.stdout.trim();
  if (!path.isAbsolute(executable) || !fs.statSync(executable).isFile()) {
    throw new Error(`Python 3.14 executable is not an existing absolute file: ${executable}`);
  }
  return executable;
}
function runPython(pythonExecutable, args, env, outputPath) {
  const result = execFileSync(pythonExecutable, args, {
    cwd: BACKEND,
    env: { ...env, PYTHONPATH: BACKEND },
    encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
    maxBuffer: 16 * 1024 * 1024,
  });
  fs.writeFileSync(outputPath, result, 'utf8');
  return result;
}
async function portIsClosed(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port });
    let settled = false;
    const finish = (closed) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(closed);
    };
    socket.once('connect', () => finish(false));
    socket.once('error', (error) => finish(error.code === 'ECONNREFUSED'));
    socket.setTimeout(500, () => finish(false));
  });
}
async function waitForOwnedServerCleanup(child, port) {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    const processExited = child.exitCode !== null || child.signalCode !== null;
    const portClosed = await portIsClosed(port);
    if (processExited && portClosed) return { processExited, portClosed, forced: false };
    await delay(100);
  }
  let forced = false;
  if (child.exitCode === null && child.signalCode === null) {
    forced = true;
    child.kill('SIGKILL'); // Exact directly-spawned Python child PID; no launcher or port-owner termination.
    await Promise.race([
      new Promise((resolve) => child.once('exit', resolve)),
      delay(5_000),
    ]);
  }
  const forcedDeadline = Date.now() + 5_000;
  while (Date.now() < forcedDeadline) {
    const processExited = child.exitCode !== null || child.signalCode !== null;
    const portClosed = await portIsClosed(port);
    if (processExited && portClosed) return { processExited, portClosed, forced };
    await delay(100);
  }
  return {
    processExited: child.exitCode !== null || child.signalCode !== null,
    portClosed: await portIsClosed(port),
    forced,
  };
}
async function freeLoopbackPort() {
  const listener = net.createServer();
  await new Promise((resolve, reject) => listener.once('error', reject).listen(0, '127.0.0.1', resolve));
  const { port } = listener.address();
  await new Promise((resolve, reject) => listener.close((error) => error ? reject(error) : resolve()));
  assert.notEqual(port, 5173);
  assert.notEqual(port, 8765);
  return port;
}
async function waitForApi(base, child, logPath) {
  const deadline = Date.now() + 180_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`backend exited (${child.exitCode}); see ${logPath}`);
    if (!child.ready) {
      await delay(250);
      continue;
    }
    try {
      const response = await fetch(`${base}/api/v1/settings`);
      if (response.ok) return;
    } catch { /* startup is still in progress */ }
    await delay(250);
  }
  throw new Error(`backend did not become ready; see ${logPath}`);
}
function responseTotals(report) { return report.summary.totals; }
function compareOldReference(actual, expected) {
  for (const key of ['sessions', 'goal', 'ruin', 'limit', 'incomplete', 'bets', 'wagered', 'paid', 'net', 'return_pct', 'mean_net_closed']) {
    assert.equal(actual[key], expected[key], `totals.${key}: API vs legacy reference`);
  }
  assert.equal(actual.net, actual.paid - actual.wagered, 'net must reconcile as paid - wagered');
  assert.equal(actual.sessions, actual.goal + actual.ruin + actual.limit + actual.incomplete);
  assert.equal(actual.bets, expected.bets);
}
async function apiJson(base, route, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('Origin', base);
  if (options.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${base}${route}`, { ...options, headers });
  let body = null;
  if (response.status !== 204) {
    const text = await response.text();
    try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  }
  return { response, body };
}
async function expectStatus(base, route, status, options) {
  const result = await apiJson(base, route, options);
  assert.equal(result.response.status, status, `${route}: expected ${status}, got ${result.response.status}: ${JSON.stringify(result.body)}`);
  return result.body;
}
function reportIdFromUrl(page) {
  let pathname;
  try { pathname = new URL(page.url()).pathname; }
  catch (error) { throw new Error(`invalid browser URL ${page.url()}: ${error.message}`); }
  const match = pathname.match(/^\/corridas\/([^/]+)$/);
  assert.ok(match, `expected result route, got ${page.url()}`);
  return decodeURIComponent(match[1]);
}
function isAbortedApiRead(request) {
  return request.method() === 'GET'
    && request.failure()?.errorText === 'net::ERR_ABORTED'
    && new URL(request.url()).pathname.startsWith('/api/v1/');
}
// A DELETE of a saved run that already got its 204 can still surface as ERR_ABORTED when the page navigates before the empty body is consumed.
const ABORTED_DELETE_RUN_PATH = /^\/api\/v1\/runs\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function isAbortedDeleteAfterResponse(request, response) {
  return request.method() === 'DELETE'
    && request.failure()?.errorText === 'net::ERR_ABORTED'
    && response !== null
    && response.status() === 204
    && ABORTED_DELETE_RUN_PATH.test(new URL(request.url()).pathname);
}
// A 409 console line is only explained when it pairs 1:1 with a recorded 409 response; leftovers stay browser errors.
function reconcileConflictConsoleErrors(conflicts, consoleErrors, errors) {
  const pending = conflicts.slice();
  for (const entry of consoleErrors) {
    const index = pending.findIndex((conflict) => !entry.url || conflict.url === entry.url);
    if (index === -1) errors.push(`console: ${entry.text} ${entry.url}`);
    else pending.splice(index, 1);
  }
}
function requestOrigin(url) {
  try { return new URL(url).origin; }
  catch (error) { throw new Error(`unexpected invalid request URL ${url}: ${error.message}`); }
}
async function assertLayout(page, label) {
  const metrics = await page.evaluate(() => {
    const isVisible = (element) => !!(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
    const actions = [...document.querySelectorAll('button, a, [role="navigation"] a')].filter(isVisible);
    const badTargets = actions.filter((el) => {
      const rect = el.getBoundingClientRect();
      return rect.height < 48 || rect.width < 48;
    }).map((el) => ({ text: el.textContent.trim(), height: el.getBoundingClientRect().height, width: el.getBoundingClientRect().width }));
    const unlabelled = [...document.querySelectorAll('input:not([type="hidden"]), select, textarea')]
      .filter((el) => !el.labels?.length && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby'))
      .map((el) => el.outerHTML.slice(0, 120));
    const fingerprints = [...document.querySelectorAll('.runs-sha')].map((el) => ({
      length: el.textContent.trim().length,
      elementWidth: el.getBoundingClientRect().width,
      parentWidth: el.parentElement.getBoundingClientRect().width,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      overflowWrap: getComputedStyle(el).overflowWrap,
    }));
    const tableOverflow = [...document.querySelectorAll('.runs-table-wrap')].map((el) => ({
      client: el.clientWidth, scroll: el.scrollWidth,
      contained: getComputedStyle(el).overflowX === 'auto' || getComputedStyle(el).overflowX === 'scroll',
    }));
    return {
      viewport: innerWidth, documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth, badTargets, unlabelled, fingerprints, tableOverflow,
      focus: (() => { const el = document.activeElement; return el ? { tag: el.tagName, outlineStyle: getComputedStyle(el).outlineStyle, outlineWidth: getComputedStyle(el).outlineWidth } : null; })(),
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
    };
  });
  assert.equal(metrics.documentWidth, metrics.viewport, `${label}: page horizontal overflow ${JSON.stringify(metrics)}`);
  assert.equal(metrics.bodyWidth, metrics.viewport, `${label}: body horizontal overflow`);
  assert.deepEqual(metrics.badTargets, [], `${label}: interactive target under 48px`);
  assert.deepEqual(metrics.unlabelled, [], `${label}: unlabeled controls`);
  for (const fingerprint of metrics.fingerprints) {
    assert.equal(fingerprint.length, 64, `${label}: SHA-256 must display all 64 characters`);
    assert.ok(fingerprint.elementWidth <= fingerprint.parentWidth + 1, `${label}: SHA overflowed its parent`);
    assert.ok(fingerprint.scrollWidth <= fingerprint.clientWidth + 1, `${label}: SHA content overflowed its box`);
  }
  assert.equal(metrics.reducedMotion, true, `${label}: reduced motion must be emulated`);
  for (const table of metrics.tableOverflow) {
    assert.ok(table.contained, `${label}: wide table must be in an overflow container`);
    assert.ok(table.scroll <= table.client || table.client > 0, `${label}: table container has dimensions`);
  }
  return metrics;
}
async function saveShot(page, dir, name) {
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true });
}

async function main() {
  const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'rebuild-runs-acceptance-'));
  const dataDir = path.join(artifacts, 'laboratorio-data');
  fs.mkdirSync(dataDir);
  const port = await freeLoopbackPort();
  const base = `http://127.0.0.1:${port}`;
  const originalHistorySha = crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, 'chance_express_history.json'))).digest('hex');
  const env = {
    ...process.env,
    PYTHONDONTWRITEBYTECODE: '1',
    LABORATORIO_DATA_DIR: dataDir,
    LABORATORIO_PORT: String(port),
    LABORATORIO_HISTORY: path.join(ROOT, 'chance_express_history.json'),
    LABORATORIO_RANKINGS: path.join(ROOT, 'repo_ref', 'reports', 'chance_rank_v1', 'predictions', 'pos1.npz'),
  };
  delete env.LABORATORIO_QUOTA_BYTES;
  const backendLog = fs.createWriteStream(path.join(artifacts, 'backend.log'));
  const referenceStdout = path.join(artifacts, 'reference.stdout.json');
  let browserErrors = [];
  let externalRequests = [];
  let unexpectedResponses = [];
  // Classified, never ignored: the one deliberate import conflict and GET reads cancelled by the frontend's AbortController.
  let expectedConflicts = [];
  let abortedReads = [];
  let abortedAfterResponse = [];
  // request.response() is async: every lookup is awaited before the final classification is asserted.
  const pendingRequestEvents = [];
  let conflictConsoleErrors = [];
  // Evidence lists shared by every report branch so a failed run still leaves them behind.
  const browserEvidence = () => ({
    external_requests: externalRequests,
    browser_errors: browserErrors,
    expected_conflicts: expectedConflicts,
    aborted_reads: abortedReads,
    aborted_after_response: abortedAfterResponse,
    unexpected_responses: unexpectedResponses,
  });
  let summary = null;
  let acceptanceError = null;
  const cleanup = { browserClosed: false, contextClosed: false, processExited: true, portClosed: true, forced: false, errors: [] };
  let pythonExecutable;

  try {
    pythonExecutable = resolvePythonExecutable();
    runPython(pythonExecutable, [path.join(ROOT, 'odd', 'qa', 'rebuild-runs', 'reference.py'), artifacts], env, referenceStdout);
    const reference = JSON.parse(fs.readFileSync(path.join(artifacts, 'reference.json'), 'utf8'));
    assert.equal(reference.draws, 105426, 'frozen history draw count');
    assert.equal(reference.ranked_draws, 65235, 'ranked draw count');
    assert.equal(reference.legacy_parity_five_position_flat_golden.totals.goal, 13);
    assert.equal(reference.legacy_parity_five_position_flat_golden.totals.ruin, 78);
    assert.equal(reference.legacy_parity_five_position_flat_golden.totals.mean_net_closed, -1572.8);
    check('independent legacy references exported; five-position parity golden is 13/78/-1572.8', () => true);

    const bootstrap = [
      'from laboratorio.settings import Settings',
      'from laboratorio.app import create_app',
      'import uvicorn',
      'settings = Settings.from_environment()',
      'app = create_app(settings, serve_frontend=True)',
      'config = uvicorn.Config(app, host=settings.host, port=settings.port)',
      'uvicorn.Server(config).run()',
    ].join('; ');
    server = spawn(pythonExecutable, ['-c', bootstrap], {
      cwd: BACKEND, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    });
    server.ready = false;
    const readyLine = `Uvicorn running on http://127.0.0.1:${port}`;
    for (const stream of [server.stdout, server.stderr]) {
      let pending = '';
      stream.on('data', (chunk) => {
        pending += chunk.toString('utf8');
        if (pending.includes(readyLine)) server.ready = true;
        if (pending.length > readyLine.length * 2) pending = pending.slice(-readyLine.length * 2);
      });
      stream.pipe(backendLog);
    }
    await waitForApi(base, server, path.join(artifacts, 'backend.log'));
    check(`owned backend ready on isolated 127.0.0.1:${port}`, () => true);

    const initial = await apiJson(base, '/api/v1/runs');
    assert.equal(initial.response.status, 200);
    assert.equal(initial.body.total, 0, 'temporary database must start empty');
    const options = await apiJson(base, '/api/v1/runs/options');
    assert.equal(options.response.status, 200);
    assert.equal(options.body.history.sha256, reference.frozen_history_sha256);
    assert.equal(originalHistorySha, reference.frozen_history_sha256, 'raw bundled history snapshot SHA');
    assert.deepEqual(options.body.defaults.rules, { positions: 3, prizes: [60, 10, 5], minimum_stake: 1 });
    assert.deepEqual(options.body.defaults.strategy, {
      kind: 'mix', components: [{ system: 'transition', percent: 60 }, { system: 'cold', percent: 40 }], coverage: 10,
    });
    assert.deepEqual(options.body.defaults.conditions, { capital: 2000, goal: 2800, max_draws: null });

    browser = await chromium.launch({ channel: 'chrome', headless: true });
    context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    await context.route('**/*', async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== base) {
        externalRequests.push(url.href);
        await route.abort('blockedbyclient');
      } else await route.continue();
    });
    const page = await context.newPage();
    page.on('console', (message) => {
      if (message.type() !== 'error') return;
      if (/^Failed to load resource: the server responded with a status of 409 \(Conflict\)$/.test(message.text())) {
        conflictConsoleErrors.push({ text: message.text(), url: message.location()?.url || '' });
      } else browserErrors.push(`console: ${message.text()}`);
    });
    page.on('pageerror', (error) => browserErrors.push(`pageerror: ${error.message}`));
    page.on('requestfailed', (request) => {
      if (requestOrigin(request.url()) !== base) externalRequests.push(request.url());
      else if (isAbortedApiRead(request)) abortedReads.push({ method: request.method(), url: request.url() });
      else {
        pendingRequestEvents.push((async () => {
          const response = await request.response().catch(() => null);
          if (isAbortedDeleteAfterResponse(request, response)) abortedAfterResponse.push({ method: request.method(), status: response.status(), url: request.url() });
          else browserErrors.push(`requestfailed: ${request.method()} ${request.resourceType()} ${request.url()} ${request.failure()?.errorText} response=${response ? response.status() : 'none'}`);
        })());
      }
    });
    page.on('response', (response) => {
      if (requestOrigin(response.url()) === base && response.status() === 409) {
        expectedConflicts.push({ method: response.request().method(), url: response.url(), status: 409 });
      }
      if (requestOrigin(response.url()) === base && response.status() >= 500) unexpectedResponses.push(`${response.status()} ${response.url()}`);
    });

    await page.goto(`${base}/corridas`, { waitUntil: 'networkidle' });
    await page.locator('main').getByRole('heading', { name: 'Todavía no hay corridas', level: 2, exact: true }).waitFor();
    await saveShot(page, artifacts, 'desktop-list-empty');
    await assertLayout(page, 'desktop empty list');
    await step('browser empty-list state and desktop layout', async () => {});

    await page.getByRole('link', { name: 'Nueva corrida' }).click();
    await page.locator('main').getByRole('heading', { name: 'Nueva corrida', level: 2, exact: true }).waitFor();
    const runForm = page.locator('main form.runs-form');
    await runForm.waitFor({ state: 'visible' });
    await runForm.getByLabel(/^Posiciones \(1–5\)/).selectOption('3');
    await runForm.getByLabel('Premio posición 1', { exact: true }).fill('60');
    await runForm.getByLabel('Premio posición 2', { exact: true }).fill('10');
    await runForm.getByLabel('Premio posición 3', { exact: true }).fill('5');
    await runForm.getByLabel('Apuesta mínima (RD$)', { exact: true }).fill('1');
    await runForm.getByLabel('Sistema 1', { exact: true }).selectOption('transition');
    await runForm.getByLabel('Porcentaje 1', { exact: true }).fill('60');
    await runForm.getByLabel('Sistema 2', { exact: true }).selectOption('cold');
    await runForm.getByLabel('Porcentaje 2', { exact: true }).fill('40');
    await runForm.getByLabel('Cobertura (1–50 números)', { exact: true }).fill('10');
    await runForm.getByLabel('Capital (RD$)', { exact: true }).fill('2000');
    await runForm.getByLabel('Meta (RD$)', { exact: true }).fill('2800');
    await runForm.getByLabel('Duración máxima (sorteos, opcional)', { exact: true }).fill('');
    await saveShot(page, artifacts, 'desktop-form');
    await assertLayout(page, 'desktop create form');
    await runForm.getByRole('button', { name: 'Correr', exact: true }).click();
    await page.locator('main').getByRole('heading', { name: /Transición 60 % \+ Fríos 40 %/, level: 2 }).waitFor({ timeout: 180_000 });
    let browserRunId = reportIdFromUrl(page);
    const firstReport = await apiJson(base, `/api/v1/runs/${encodeURIComponent(browserRunId)}`);
    assert.equal(firstReport.response.status, 200);
    assert.equal(firstReport.body.config.history.sha256, reference.frozen_history_sha256);
    compareOldReference(responseTotals(firstReport.body), reference.legacy_mix_three_position_unlimited.totals);
    assert.equal(responseTotals(firstReport.body).sessions, 81);
    assert.equal(responseTotals(firstReport.body).bets, 65235);
    assert.equal(responseTotals(firstReport.body).net, -159770);
    assert.equal(responseTotals(firstReport.body).return_pct, -24.5);
    assert.match(await page.locator('body').innerText(), /no es una predicción ni garantiza resultados futuros/i);
    const displayedMoney = await page.locator('.result-summary').textContent();
    assert.match(displayedMoney, /−RD\$159[,.]?770/);
    assert.match(displayedMoney, /−24,5\s*%/);
    await saveShot(page, artifacts, 'desktop-result');
    await assertLayout(page, 'desktop result');
    await step('UI-created run matches independent old-run_backtest accounting and actual configured totals', async () => {});

    const firstSessionRow = page.getByRole('region', { name: 'Sesiones de la corrida' }).getByRole('row')
      .filter({ has: page.getByRole('rowheader', { name: 'Sesión 1', exact: true }) });
    await firstSessionRow.getByRole('button', { name: 'Ver apuestas de sesión 1', exact: true }).click();
    await page.getByRole('heading', { name: /Sesión \d+ · (Meta|Quiebra|Incompleta)/ }).waitFor();
    await page.getByRole('region', { name: /Apuestas de sesión/ }).waitFor();
    const betNav = page.getByRole('navigation', { name: 'Paginación de apuestas' });
    if (await betNav.getByRole('button', { name: 'Siguiente apuestas' }).isEnabled()) {
      await betNav.getByRole('button', { name: 'Siguiente apuestas' }).click();
      await page.getByText(/Apuestas: 21–/).waitFor();
    }
    const sessionNav = page.getByRole('navigation', { name: 'Paginación de sesiones' });
    if (await sessionNav.getByRole('button', { name: 'Siguiente sesiones' }).isEnabled()) {
      await sessionNav.getByRole('button', { name: 'Siguiente sesiones' }).click();
      await page.getByText(/Sesiones: 51–/).waitFor();
    }
    const sessionPage = await apiJson(base, `/api/v1/runs/${browserRunId}/sessions?offset=0&limit=1`);
    assert.equal(sessionPage.response.status, 200);
    const legacyFirst = reference.legacy_mix_three_position_unlimited.accounting.first_session;
    const firstSession = sessionPage.body.items[0];
    assert.equal(firstSession.outcome, { reached_goal: 'goal', quiebre: 'ruin', incomplete: 'incomplete' }[legacyFirst.outcome]);
    assert.equal(firstSession.final_balance, legacyFirst.final_balance);
    assert.equal(firstSession.bets, legacyFirst.bets);
    assert.equal(firstSession.wagered, legacyFirst.first_bet.wagered * legacyFirst.bets);
    const ordinal = firstSession.ordinal;
    const sessionPage2 = await apiJson(base, `/api/v1/runs/${browserRunId}/sessions?offset=1&limit=1`);
    assert.equal(sessionPage2.body.items.length, 1);
    assert.notEqual(sessionPage2.body.items[0].ordinal, ordinal);
    const outcomePage = await apiJson(base, `/api/v1/runs/${browserRunId}/sessions?outcome=ruin&limit=2`);
    assert.ok(outcomePage.body.items.every((item) => item.outcome === 'ruin'));
    const bets = await apiJson(base, `/api/v1/runs/${browserRunId}/sessions/${ordinal}/bets?offset=0&limit=20`);
    assert.equal(bets.response.status, 200);
    assert.equal(bets.body.session.ordinal, ordinal);
    assert.ok(bets.body.items.length <= 20);
    assert.equal(bets.body.items[0].label, legacyFirst.first_bet.label);
    assert.deepEqual(bets.body.items[0].numbers, legacyFirst.first_bet.numbers);
    assert.deepEqual(bets.body.items[0].results, legacyFirst.first_bet.results);
    assert.equal(bets.body.items[0].wagered, legacyFirst.first_bet.wagered);
    assert.equal(bets.body.items[0].paid, legacyFirst.first_bet.paid);
    assert.equal(bets.body.items[0].balance, legacyFirst.first_bet.balance);
    const nextBets = await apiJson(base, `/api/v1/runs/${browserRunId}/sessions/${ordinal}/bets?offset=20&limit=20`);
    if (bets.body.total > 20) assert.notEqual(bets.body.items[0]?.index, nextBets.body.items[0]?.index);
    check('API session outcome filter and session/bet pagination', () => true);

    await page.getByRole('link', { name: 'Repetir con cambios' }).click();
    await page.locator('main').getByRole('heading', { name: 'Repetir con cambios', level: 2, exact: true }).waitFor();
    await runForm.waitFor({ state: 'visible' });
    assert.equal(await runForm.getByLabel(/^Posiciones \(1–5\)/).inputValue(), '3');
    assert.equal(await runForm.getByLabel('Premio posición 1', { exact: true }).inputValue(), '60');
    assert.equal(await runForm.getByLabel('Cobertura (1–50 números)', { exact: true }).inputValue(), '10');
    assert.equal(await runForm.getByLabel('Capital (RD$)', { exact: true }).inputValue(), '2000');
    assert.equal(await page.locator('.runs-sha').innerText(), reference.frozen_history_sha256);
    await runForm.getByLabel('Duración máxima (sorteos, opcional)', { exact: true }).fill('12');
    await saveShot(page, artifacts, 'desktop-repeat-form');
    await runForm.getByRole('button', { name: 'Correr', exact: true }).click();
    await page.locator('main').getByRole('heading', { name: /Transición 60 % \+ Fríos 40 %/, level: 2 }).waitFor({ timeout: 180_000 });
    const limitedId = reportIdFromUrl(page);
    const limited = await apiJson(base, `/api/v1/runs/${limitedId}`);
    assert.equal(limited.response.status, 200);
    assert.equal(limited.body.config.conditions.max_draws, 12);
    assert.equal(limited.body.config.history.sha256, firstReport.body.config.history.sha256);
    assert.notEqual(limitedId, browserRunId);
    const claimed = reference.claimed_limited_mix_fixture.totals;
    for (const key of ['sessions', 'limit', 'bets']) assert.equal(limited.body.summary.totals[key], claimed[key], `limited mix ${key}`);
    await page.getByRole('combobox', { name: 'Filtrar sesiones', exact: true }).selectOption('limit');
    await page.getByText(/Sesiones: 1–50 de 5\.931/).waitFor();
    await page.getByRole('navigation', { name: 'Paginación de sesiones' })
      .getByRole('button', { name: 'Siguiente sesiones' }).click();
    await page.getByText(/Sesiones: 51–100 de 5\.931/).waitFor();
    await page.getByRole('button', { name: /Ver apuestas de sesión 51/ }).click();
    await page.getByRole('heading', { name: /Sesión 51 · Límite/ }).waitFor();
    await page.getByRole('region', { name: /Apuestas de sesión 51/ }).waitFor();
    check('limited-run browser session filter/pagination and selected bet detail', () => true);
    check('repeat preserves frozen history/config and verifies bounded 12-draw claimed counts', () => true);

    const apiList = await apiJson(base, '/api/v1/runs?offset=0&limit=100');
    assert.equal(apiList.body.total, 2);
    assert.equal(apiList.body.items.length, 2);
    assert.equal((await expectStatus(base, '/api/v1/runs/not-a-run', 404)).detail, 'La corrida no existe.');
    await expectStatus(base, `/api/v1/runs/${browserRunId}/sessions/999999/bets`, 404);
    const sessionLimit100 = await apiJson(base, `/api/v1/runs/${browserRunId}/sessions?limit=100`);
    assert.equal(sessionLimit100.response.status, 200);
    const betsLimit100 = await apiJson(base, `/api/v1/runs/${browserRunId}/sessions/1/bets?limit=100`);
    assert.equal(betsLimit100.response.status, 200);
    await expectStatus(base, `/api/v1/runs/${browserRunId}/sessions?limit=101`, 422);
    await expectStatus(base, `/api/v1/runs/${browserRunId}/sessions/1/bets?limit=101`, 422);

    const goldenRequest = {
      name: 'Acceptance parity five-position golden',
      rules: { positions: 5, prizes: [80, 8, 4, 2, 1], minimum_stake: 1 },
      strategy: { kind: 'parity', components: [], coverage: 50 },
      conditions: { capital: 2000, goal: 2800, max_draws: null },
      window: { start_date: null, end_date: null },
      history_sha256: reference.frozen_history_sha256,
    };
    const golden = await apiJson(base, '/api/v1/runs', { method: 'POST', body: JSON.stringify(goldenRequest) });
    assert.equal(golden.response.status, 201, JSON.stringify(golden.body));
    const allHistoryParity = reference.legacy_parity_five_position_flat_all_history_unlimited;
    compareOldReference(golden.body.summary.totals, allHistoryParity.totals);
    assert.equal(allHistoryParity.draws, reference.draws, 'all-history parity reference draw scope');
    assert.equal(allHistoryParity.ranked_draws, reference.ranked_draws, 'all-history parity ranked subset');
    assert.equal(golden.body.summary.window.draws, reference.draws, 'API parity window covers full history');
    assert.equal(golden.body.summary.totals.bets, reference.draws, 'one parity bet per historical draw');
    assert.equal(allHistoryParity.totals.bets, reference.draws, 'independent reference bets cover every draw');
    assert.equal(
      allHistoryParity.mean_net_closed_scope.closed_sessions,
      allHistoryParity.totals.goal + allHistoryParity.totals.ruin,
      'closed-session mean excludes incomplete sessions',
    );
    assert.equal(allHistoryParity.mean_net_closed_scope.total_sessions, allHistoryParity.totals.sessions);
    assert.equal(
      allHistoryParity.mean_net_closed_scope.excludes_incomplete_sessions,
      allHistoryParity.totals.incomplete,
    );
    const rankedGolden = reference.legacy_parity_five_position_flat_golden.totals;
    assert.equal(rankedGolden.goal, 13);
    assert.equal(rankedGolden.ruin, 78);
    assert.equal(rankedGolden.mean_net_closed, -1572.8);
    check('all-history parity matches independent old-engine reference; ranked-row 13/78/-1572.8 golden retained separately', () => true);

    await page.goto(`${base}/ajustes`, { waitUntil: 'networkidle' });
    await page.locator('main').getByRole('heading', { name: 'Almacenamiento', level: 2, exact: true }).waitFor();
    const initialSettings = await apiJson(base, '/api/v1/settings');
    assert.equal(initialSettings.response.status, 200);
    assert.match(initialSettings.body.storage.logical_used_bytes_exact, /^[0-9]+$/);
    assert.match(initialSettings.body.quota.effective_bytes, /^[0-9]+$/);
    assert.equal(initialSettings.body.quota.writable, true, 'isolated environment must permit quota setting');
    const quota = (BigInt(initialSettings.body.quota.effective_bytes) + 1_000_000n).toString();
    await page.getByLabel('Cuota en bytes', { exact: true }).fill(quota);
    await page.getByRole('button', { name: 'Guardar cuota' }).click();
    await page.getByRole('status').filter({ hasText: 'Cuota guardada' }).waitFor();
    assert.equal((await apiJson(base, '/api/v1/settings')).body.quota.effective_bytes, quota);
    await saveShot(page, artifacts, 'desktop-settings');
    await assertLayout(page, 'desktop settings');

    const input = page.getByLabel('Elegir archivo de historial', { exact: true });
    await input.setInputFiles(path.join(artifacts, 'synthetic-history.json'));
    await page.getByRole('status').filter({ hasText: 'Importación confirmada: se agregaron 1 sorteos' }).waitFor({ timeout: 30_000 });
    const importedHistory = await apiJson(base, '/api/v1/history');
    assert.equal(importedHistory.body.active.origin, 'import');
    assert.equal(importedHistory.body.active.added_draws, 1);
    assert.equal(importedHistory.body.active.last_label, reference.new_label);
    assert.equal(importedHistory.body.active.ranked_draws, reference.ranked_draws);
    assert.notEqual(importedHistory.body.active.sha256, reference.frozen_history_sha256);
    await input.setInputFiles(path.join(artifacts, 'synthetic-history.json'));
    await page.getByRole('status').filter({ hasText: 'Ya estaba en las fuentes; no se agregaron sorteos.' }).waitFor({ timeout: 30_000 });
    await input.setInputFiles(path.join(artifacts, 'conflicting-history.json'));
    await page.getByRole('alert').filter({ hasText: 'Hay sorteos que contradicen el historial actual' }).waitFor({ timeout: 30_000 });
    assert.equal((await apiJson(base, '/api/v1/history')).body.active.sha256, importedHistory.body.active.sha256);
    await saveShot(page, artifacts, 'desktop-settings-import');
    check('Settings import adds one unranked draw, duplicate is idempotent, conflicting draw is rejected', () => true);

    const importRun = await apiJson(base, '/api/v1/runs', {
      method: 'POST', body: JSON.stringify({ ...goldenRequest, name: 'Acceptance active import source', history_sha256: null }),
    });
    assert.equal(importRun.response.status, 201, JSON.stringify(importRun.body));
    assert.equal(importRun.body.config.history.sha256, importedHistory.body.active.sha256);
    assert.equal(importRun.body.summary.window.draws, reference.draws + 1);
    assert.equal(importRun.body.summary.window.ranked_draws, reference.ranked_draws);
    const duplicateUpload = await expectStatus(base, '/api/v1/history', 200, {
      method: 'POST', body: fs.readFileSync(path.join(artifacts, 'synthetic-history.json')),
      headers: { 'Content-Type': 'application/json' },
    });
    assert.equal(duplicateUpload.added, 0);
    assert.equal(duplicateUpload.created, false);
    assert.equal(duplicateUpload.active.sha256, importedHistory.body.active.sha256);
    await expectStatus(base, '/api/v1/history', 409, {
      method: 'POST', body: fs.readFileSync(path.join(artifacts, 'conflicting-history.json')),
      headers: { 'Content-Type': 'application/json' },
    });
    await expectStatus(base, '/api/v1/runs', 422, { method: 'POST', body: JSON.stringify({ unexpected: true }) });
    await expectStatus(base, '/api/v1/runs', 422, { method: 'POST', body: JSON.stringify({ ...goldenRequest, history_sha256: 'bad' }) });
    check('API import idempotence/conflict, active SHA pinning, and strict request validation', () => true);

    const settingsNow = await apiJson(base, '/api/v1/settings');
    assert.match(settingsNow.body.storage.logical_used_bytes_exact, /^[0-9]+$/);
    await expectStatus(base, '/api/v1/settings', 422, { method: 'PUT', body: JSON.stringify({ quota_bytes: '01' }) });
    await expectStatus(base, '/api/v1/settings', 409, { method: 'PUT', body: JSON.stringify({ quota_bytes: '1' }) });
    const runBeforeDelete = await apiJson(base, `/api/v1/runs/${browserRunId}`);
    assert.equal(runBeforeDelete.body.config.history.sha256, reference.frozen_history_sha256);
    const deletedGolden = await expectStatus(base, `/api/v1/runs/${golden.body.id}`, 204, { method: 'DELETE' });
    assert.equal(deletedGolden, null);
    await expectStatus(base, `/api/v1/runs/${golden.body.id}`, 404);
    await page.goto(`${base}/corridas`, { waitUntil: 'networkidle' });
    const selectedRunRow = page.locator('tr').filter({
      has: page.locator(`a[href="/corridas/${encodeURIComponent(browserRunId)}"]`),
    });
    await selectedRunRow.waitFor();
    await selectedRunRow.getByRole('button', { name: 'Borrar' }).click();
    const dialog = page.getByRole('alertdialog');
    await dialog.getByRole('heading', { name: 'Borrar esta corrida' }).waitFor();
    await dialog.getByRole('button', { name: 'Borrar', exact: true }).click();
    await selectedRunRow.waitFor({ state: 'detached', timeout: 30_000 });
    assert.equal((await apiJson(base, `/api/v1/runs/${browserRunId}`)).response.status, 404);
    assert.equal((await apiJson(base, `/api/v1/runs/${limitedId}`)).response.status, 200);
    await step('UI delete requires confirmation and removes only selected saved run', async () => {});

    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto(`${base}/corridas`, { waitUntil: 'networkidle' });
      await page.getByRole('link', { name: 'Nueva corrida' }).waitFor();
      await assertLayout(page, `${width}px list`);
      await saveShot(page, artifacts, `${width}-list`);
      await page.goto(`${base}/corridas/nueva?base=${encodeURIComponent(limitedId)}`, { waitUntil: 'networkidle' });
      await page.locator('main').getByRole('heading', { name: 'Repetir con cambios', level: 2, exact: true }).waitFor();
      await page.locator('main form.runs-form').waitFor({ state: 'visible' });
      assert.equal(await page.locator('main form.runs-form').getByLabel('Duración máxima (sorteos, opcional)', { exact: true }).inputValue(), '12');
      await assertLayout(page, `${width}px form`);
      await saveShot(page, artifacts, `${width}-form`);
      await page.goto(`${base}/corridas/${encodeURIComponent(limitedId)}`, { waitUntil: 'networkidle' });
      await page.locator('main').getByRole('heading', { name: /Transición 60 % \+ Fríos 40 %/, level: 2 }).waitFor();
      await assertLayout(page, `${width}px result`);
      await saveShot(page, artifacts, `${width}-result`);
      await page.goto(`${base}/ajustes`, { waitUntil: 'networkidle' });
      await page.locator('main').getByRole('heading', { name: 'Almacenamiento', level: 2, exact: true }).waitFor();
      await assertLayout(page, `${width}px settings`);
      await saveShot(page, artifacts, `${width}-settings`);
    }

    await page.goto(`${base}/corridas`, { waitUntil: 'networkidle' });
    await page.keyboard.press('Tab');
    const focus = await page.evaluate(() => {
      const element = document.activeElement;
      const style = element && getComputedStyle(element);
      return { tag: element?.tagName, className: element?.className, outlineStyle: style?.outlineStyle, outlineWidth: style?.outlineWidth };
    });
    assert.ok(focus.tag && focus.tag !== 'BODY', 'Tab must focus an interactive element');
    assert.notEqual(focus.outlineStyle, 'none', `keyboard focus outline missing: ${JSON.stringify(focus)}`);
    assert.ok(parseFloat(focus.outlineWidth) > 0, `keyboard focus width missing: ${JSON.stringify(focus)}`);
    check('keyboard focus is visible; form controls are associated with labels', () => true);

    assert.deepEqual(externalRequests, [], 'external requests must be absent');
    await Promise.all(pendingRequestEvents);
    reconcileConflictConsoleErrors(expectedConflicts, conflictConsoleErrors, browserErrors);
    assert.deepEqual(
      expectedConflicts,
      [{ method: 'POST', url: `${base}/api/v1/history`, status: 409 }],
      'the only browser 409 must be the deliberate conflicting history import',
    );
    assert.ok(abortedReads.every((read) => read.method === 'GET' && new URL(read.url).pathname.startsWith('/api/v1/')), 'aborted requests must be GET reads under /api/v1/');
    assert.deepEqual(
      abortedAfterResponse,
      abortedAfterResponse.map(() => ({ method: 'DELETE', status: 204, url: `${base}/api/v1/runs/${browserRunId}` })),
      'the only abort after a received response must be the UI delete of the check 11 run',
    );
    assert.deepEqual(browserErrors, [], 'unexpected browser console/page/request errors');
    assert.deepEqual(unexpectedResponses, [], 'unexpected API 5xx responses');
    check('browser runtime has no console errors, failed local requests, API 5xx, or external requests', () => true);

    const finalRuns = await apiJson(base, '/api/v1/runs?offset=0&limit=100');
    assert.equal(finalRuns.response.status, 200);
    assert.ok(finalRuns.body.items.every((item) => item.config.history.sha256 === reference.frozen_history_sha256 || item.config.history.sha256 === importedHistory.body.active.sha256));
    const finalHistory = await apiJson(base, '/api/v1/history');
    assert.equal(finalHistory.body.sources.find((item) => item.sha256 === reference.frozen_history_sha256).active, false);
    assert.equal(finalHistory.body.active.sha256, importedHistory.body.active.sha256);
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, 'chance_express_history.json'))).digest('hex'), originalHistorySha, 'bundled base history file must remain byte-identical');
    summary = {
      status: 'pass',
      checks: CHECKS,
      check_count: CHECKS.length,
      artifacts,
      port,
      browser: 'Chrome via Playwright; reducedMotion=reduce; 390px and 1440px',
      references: {
        legacy_mix_three_position_unlimited: reference.legacy_mix_three_position_unlimited.totals,
        legacy_parity_five_position_flat_golden_ranked_65235: reference.legacy_parity_five_position_flat_golden.totals,
        legacy_parity_five_position_flat_all_history_105426: allHistoryParity.totals,
        parity_scope: {
          all_history_draws: allHistoryParity.draws,
          ranked_draws: allHistoryParity.ranked_draws,
          mean_net_closed_sessions: allHistoryParity.mean_net_closed_scope.closed_sessions,
          total_sessions: allHistoryParity.mean_net_closed_scope.total_sessions,
          incomplete_sessions_excluded_from_closed_mean: allHistoryParity.mean_net_closed_scope.excludes_incomplete_sessions,
        },
        limited_mix_api: limited.body.summary.totals,
      },
      ...browserEvidence(),
    };
  } catch (error) {
    if (!failures.length || failures[failures.length - 1].error !== (error.stack || String(error))) {
      failures.push({ name: 'acceptance assertion', error: error.stack || String(error) });
      CHECKS.push({ name: 'acceptance assertion', status: 'fail', message: error.message });
    }
    summary = { status: 'fail', checks: CHECKS, failures, artifacts, ...browserEvidence() };
    acceptanceError = error;
  } finally {
    if (context) {
      try { await context.close(); cleanup.contextClosed = true; }
      catch (error) { cleanup.errors.push(`context close: ${error.message}`); }
    } else cleanup.contextClosed = true;
    if (browser) {
      try { await browser.close(); cleanup.browserClosed = true; }
      catch (error) { cleanup.errors.push(`browser close: ${error.message}`); }
    } else cleanup.browserClosed = true;
    if (server) {
      if (server.exitCode === null && server.signalCode === null) {
        server.kill('SIGINT');
        await Promise.race([
          new Promise((resolve) => server.once('exit', resolve)),
          delay(10_000),
        ]);
      }
      try {
        Object.assign(cleanup, await waitForOwnedServerCleanup(server, port));
      } catch (error) {
        cleanup.errors.push(`server cleanup: ${error.message}`);
        cleanup.processExited = server.exitCode !== null || server.signalCode !== null;
        cleanup.portClosed = false;
      }
    }
    backendLog.end();
    summary = summary || { status: 'fail', checks: CHECKS, failures, artifacts, ...browserEvidence() };
    summary.cleanup = cleanup;
    if (cleanup.errors.length || !cleanup.processExited || !cleanup.portClosed || !cleanup.browserClosed || !cleanup.contextClosed) {
      summary.status = 'fail';
      const cleanupFailure = { name: 'owned process/browser cleanup', error: JSON.stringify(cleanup) };
      summary.failures = [...(summary.failures || failures), cleanupFailure];
    }
    fs.writeFileSync(path.join(artifacts, 'acceptance-report.json'), JSON.stringify(summary, null, 2));
    process[(summary.status === 'pass' ? 'stdout' : 'stderr')].write(`${JSON.stringify(summary, null, 2)}\n`);
  }
  if (acceptanceError) throw acceptanceError;
  if (summary.status !== 'pass') process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
