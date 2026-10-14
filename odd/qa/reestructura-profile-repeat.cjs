// eslint-disable-next-line no-unused-expressions -- the owned Node runner evaluates this function expression.
async (page, options = {}) => {
  // Bounded mocked browser acceptance for the integrated profile-repeat flow.
  // The runner loads this function from disk; all API traffic is synthetic.
  const BASE = "http://127.0.0.1:5187";
  const RUN_ID = new Date().toISOString().replace(/[:.]/g, "-");
  const OUT = `C:/Users/luism/AppData/Local/Temp/t2-profile-repeat-qa/${RUN_ID}`;
  const HASH = (char) => char.repeat(64);
  // Mirrors BATCH_DRAFT_STORAGE_KEY in batch-model.ts; ProfileBatchPage appends :repeat:<encoded baseId>.
  const BATCH_DRAFT_STORAGE_KEY = "profile-batch-draft-v1";
  const deep = (value) => {
    try { return JSON.parse(JSON.stringify(value)); }
    catch (cause) { throw new TypeError("Fixture snapshot could not be serialized", { cause }); }
  };
  const checks = [];
  const ledger = [];
  const blocked = [];
  const failures = [];
  const screenshots = [];
  const viewportMeasurements = [];
  const storageIsolation = [];
  const externalMocks = [];
  const createdPayloads = new Map();
  let createdSequence = 0;
  let fontFallbackUsed = false;
  let activeId = "";
  let activeSaved = null;
  let activeVersion = 0;
  let scenario = "setup";
  let missingProfileId = "";
  let missingDatasetHash = "";
  let driftDatasetHash = "";
  let datasetLookupCount = 0;
  const check = (name, condition, detail = "") => {
    checks.push({ name, pass: !!condition, detail });
    if (!condition) failures.push(name + (detail ? `: ${detail}` : ""));
  };
  const buildReport = (result, error = null) => ({
    title: "T2 profile repeat mocked browser QA", result, runId: RUN_ID, scenario,
    checks, requestLedger: ledger, blockedRequests: blocked, failures, error,
    screenshots, viewportMeasurements, storageIsolation, externalMocks, fontFallbackUsed,
    executionScope: options.negativesOnly ? "negative cases only; creation matrix retained from prior verified run" : "creation matrix and negative cases",
    widths: options.negativesOnly ? [] : [390, 1440],
    gaps: ["No integrated backend admission or financial outcome reproduction.",
      "Base/fresh/base recovery, stale registry revision races, delayed-response races, and broader retry/error matrices remain uncovered.",
      "Mocked/fallback-font viewport screenshots do not certify production font fidelity or whole-T2 acceptance."],
  });
  const measureViewport = async label => {
    const measurement = await page.evaluate(() => ({ viewportWidth: window.innerWidth, documentWidth: document.documentElement.scrollWidth,
      documentClientWidth: document.documentElement.clientWidth, bodyWidth: document.body.scrollWidth }));
    viewportMeasurements.push({ label, ...measurement });
    check(`${label}: no horizontal overflow`, measurement.documentWidth <= measurement.viewportWidth && measurement.bodyWidth <= measurement.viewportWidth,
      JSON.stringify(measurement));
  };
  const captureScreenshot = async path => {
    await page.screenshot({ path, fullPage: false });
    screenshots.push(path);
  };
  const mkProfile = (id, sha, schema = 1, scale = 2, maxCoverage = 10, staking = ["flat-per-number/v1"]) => ({
    profile: { schema_version: 1, profile_id: id, revision: 2, universe_size: 100, positions: schema === 2 ? 5 : 3,
      allows_repeats: true, multipliers: (schema === 2 ? [80, 8, 4, 2, 1] : [60, 10, 5]).map(numerator => ({ numerator, denominator: 1 })),
      currency: schema >= 3 ? "EUR" : "DOP", scale, stake_increment: schema >= 3 ? 5 : 25, minimum_stake: schema >= 3 ? 5 : 25,
      maximum_stake: 10000, max_coverage: maxCoverage, max_exposure: 20000, best_rule: "maximum-payout/v1" },
    profile_sha256: sha, execution_supported: true,
    profile_execution: { ready: true, selector_capabilities: ["static-numbers/v1", "seeded-random/hash-sha256-v1"],
      staking_capabilities: staking, entry_policies: ["all_rows/v1"], settlements: ["all", "best"], requires_compatible_dataset: true,
      audaz_compatibility: { available: schema === 3, maximum_compatible_coverage: schema === 3 ? 1 : 0, coverage_rule: "coverage below payout multiplier" },
      recovery_compatibility: { available: schema === 4, maximum_compatible_coverage: schema === 4 ? 2 : 0, coverage_rule: "compatible coverage", parameters: ["target_margin", "rounds", "end_mode"] } },
  });
  const profiles = [
    mkProfile("v1-profile", HASH("a"), 1),
    mkProfile("v2-profile", HASH("f"), 2, 0, 79, ["flat-per-number/v1", "q80-first-prize-cycling/v1"]),
    mkProfile("v3-profile", HASH("c"), 3, 2, 8, ["flat-per-number/v1", "profile-audaz/v1"]),
    mkProfile("v4-profile", HASH("d"), 4, 2, 4, ["flat-per-number/v1", "profile-recovery-ladder/v1"]),
    mkProfile("v5-profile", HASH("e"), 5, 0, 10),
  ];
  // Match the rational fixtures used by the existing Audaz/recovery contract tests.
  profiles[2].profile.positions = 2;
  profiles[2].profile.multipliers = [{ numerator: 5, denominator: 4 }, { numerator: 3, denominator: 2 }];
  profiles[3].profile.positions = 2;
  profiles[3].profile.multipliers = [{ numerator: 5, denominator: 2 }, { numerator: 3, denominator: 2 }];
  const datasets = profiles.map((entry, i) => ({
    dataset_sha256: HASH(["b", "9", "8", "7", "6"][i]), source_sha256: HASH("1"), created_at: "2025-01-02T00:00:00Z", execution_supported: false,
    profile_sha256: entry.profile_sha256, profile_id: entry.profile.profile_id, profile_revision: 2,
    source_id: `history-${i + 1}`, source_revision: "v1", source_kind: "historical", positions: entry.profile.positions,
    universe_size: 100, records_total: 1, first_draw: "2025-01-01 08:30", last_draw: "2025-01-01 08:30",
    clock: { mode: "iana", zone: "America/Santo_Domingo" }, profile_execution: entry.profile_execution,
  }));
  const commonConditions = (scale = 2, start = "2025-01-01 08:30") => ({ schema_version: 1, start_draw: start,
    capital: scale === 0 ? 2000 : 200000, goal: scale === 0 ? 2800 : 280000,
    settlement: "best", max_elapsed_draws: 50, max_bet_draws: null, end_minute: null, duration_minutes: null });
  const sessions = [
    { id: "repeat-v1", request_kind: "profile", request_schema_version: 1, request: { kind: "profile", schema_version: 1, name: "Saved v1",
      dataset_sha256: datasets[0].dataset_sha256, profile_id: "v1-profile", profile_revision: 2, profile_sha256: profiles[0].profile_sha256,
      entry_policy: "all_rows/v1", conditions: commonConditions(), selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 2,
        numbers: [0, 1], seed: null, algorithm_version: null }, staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: 125 } } },
    { id: "repeat-v2", request_kind: "profile", request_schema_version: 2, request: { kind: "profile", schema_version: 2, name: "Saved v2",
      dataset_sha256: datasets[1].dataset_sha256, profile_id: "v2-profile", profile_revision: 2, profile_sha256: profiles[1].profile_sha256,
      entry_policy: "all_rows/v1", conditions: commonConditions(0), selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 2,
        numbers: [0, 1], seed: null, algorithm_version: null }, staking: { schema_version: 1, capability: "q80-first-prize-cycling/v1" } } },
    { id: "repeat-v3", request_kind: "profile", request_schema_version: 3, request: { kind: "profile", schema_version: 3, name: "Saved v3",
      dataset_sha256: datasets[2].dataset_sha256, profile_id: "v3-profile", profile_revision: 2, profile_sha256: profiles[2].profile_sha256,
      entry_policy: "all_rows/v1", conditions: commonConditions(), selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 1,
        numbers: [0], seed: null, algorithm_version: null }, staking: { schema_version: 1, capability: "profile-audaz/v1" } } },
    { id: "repeat-v4", request_kind: "profile", request_schema_version: 4, request: { kind: "profile", schema_version: 4, name: "Saved v4",
      dataset_sha256: datasets[3].dataset_sha256, profile_id: "v4-profile", profile_revision: 2, profile_sha256: profiles[3].profile_sha256,
      entry_policy: "all_rows/v1", conditions: commonConditions(), selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 2,
        numbers: [0, 1], seed: null, algorithm_version: null }, staking: { schema_version: 1, target_margin: 1234, rounds: 4, end_mode: "stop" } } },
  ];
  const strategyDef = { definition_version: 1, name: "Fixed one", selector: "static-numbers/v1", coverage: 1,
    staking: "flat-per-number/v1", selector_parameters: { numbers: [3] }, staking_parameters: { per_number_stake: 1 },
    closing_defaults: { settlement: "best" } };
  const strategy = { id: "strategy-fixed", name: "Fixed one", revision: 1, latest_revision: 1, definition_version: 1,
    definition: strategyDef, definition_sha256: HASH("2"), created_at: "2025-01-01", revision_created_at: "2025-01-01", protected: false,
    preset_explanation: null, definition_valid: true, profile_context_provided: true, profile_compatible: true,
    incompatibilities: [], requirements: {}, execution_available: true, execution_unavailable_reason: null };
  const policy = { revision: 1, policy: { max_strategies_per_batch: 3, worker_count: 1, max_pending_runs: 10, max_bet_draws: 100,
    max_elapsed_draws: 1000, run_timeout_seconds: 120 }, effective: {}, defaults: {}, bounds: {}, explanation: "Synthetic policy fixture" };
  const batchSaved = { id: "repeat-v5", request_kind: "profile", request_schema_version: 5, status: "pending", created_at: "2025-01-01T00:00:00Z",
    request: { schema_version: 5, kind: "profile_batch", profile_id: "v5-profile", profile_revision: 2, profile_sha256: profiles[4].profile_sha256,
      dataset_sha256: datasets[4].dataset_sha256, conditions: { ...commonConditions(), start_draw: "2025-01-01 08:30", capital: 100, goal: 200,
        max_elapsed_draws: null, max_bet_draws: 20, end_minute: Math.floor(Date.parse("2025-01-01T08:30:00Z") / 60000) + 45, duration_minutes: 45 }, strategies: [strategyDef], max_draws: 40, source_version: "canonical-history/v1" },
    profile: profiles[4].profile, display: { name: "Saved v5 batch", currency: profiles[4].profile.currency, scale: profiles[4].profile.scale, capital: 100, goal: 200,
      selector_label: "Strategy batch", staking_label: "Per-strategy definitions" },
    sources: { history_id: null, history_sha256: null, rankings_id: null, rankings_sha256: null, code_version: "fixture" },
    runs: [{ result_kind: "profile", ordinal: 0, configuration_id: null, status: "pending", result_schema_version: null,
      strategy: { id: strategy.id, revision: 1, definition_sha256: strategy.definition_sha256, name: strategy.name }, result: null,
      bets_count: 0, complete: false, completion: "incomplete", stop_category: "unknown", stop_reason: "pending", stop_code: "pending", error: null }],
    batch_admission: { strategy_refs: [{ id: strategy.id, revision: 1, definition_sha256: strategy.definition_sha256 }],
      source_identity: { dataset_sha256: datasets[4].dataset_sha256, source_sha256: datasets[4].source_sha256, canonical_sha256: HASH("3"), row_count: 1,
        profile_id: "v5-profile", profile_revision: 2, profile_sha256: profiles[4].profile_sha256, archive_bound: false,
        archive_history_sha256: null, archive_rank_row_ids: null },
      requested_constraints: { max_draws: 40, max_elapsed_draws: null, max_bet_draws: 20 }, effective_constraints: { max_draws: 20 },
      policy_revision: 1, policy: { max_draws: 20 } } };
  const originals = new Map([...sessions, batchSaved].map(item => [item.id, deep(item)]));
  const savedFor = (id) => id === batchSaved.id ? batchSaved : sessions.find(item => item.id === id);
  const profileFor = (id) => profiles.find(item => item.profile.profile_id === id);
  const datasetFor = (hash) => datasets.find(item => item.dataset_sha256 === hash);
  const fixtureErrors = [];
  for (const item of sessions) {
    const request = item.request;
    const profile = profileFor(request.profile_id);
    const dataset = datasetFor(request.dataset_sha256);
    if (![1, 2, 3, 4].includes(request.schema_version) || item.request_schema_version !== request.schema_version ||
      !profile || !dataset || request.profile_sha256 !== profile.profile_sha256 || request.dataset_sha256 !== dataset.dataset_sha256 ||
      request.profile_revision !== profile.profile.revision || request.conditions?.schema_version !== 1 ||
      !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(request.conditions.start_draw)) fixtureErrors.push(item.id);
  }
  if (batchSaved.request.schema_version !== 5 || batchSaved.request_kind !== "profile" ||
    batchSaved.batch_admission.requested_constraints.max_draws !== batchSaved.request.max_draws ||
    batchSaved.batch_admission.source_identity.dataset_sha256 !== batchSaved.request.dataset_sha256 ||
    batchSaved.runs.length !== batchSaved.request.strategies.length || batchSaved.display.currency !== profiles[4].profile.currency ||
    !batchSaved.sources || batchSaved.runs.some(run => run.result !== null || run.status === "completed")) fixtureErrors.push(batchSaved.id);
  if (datasets.some(item => !item.created_at || item.execution_supported !== false || !item.profile_id || !item.clock) ||
    profiles[2].profile.multipliers[0].numerator / profiles[2].profile.multipliers[0].denominator >= 2 ||
    profiles[3].profile.multipliers[0].numerator / profiles[3].profile.multipliers[0].denominator <= 2) fixtureErrors.push("catalog-fixtures");
  check("saved fixtures use matching versioned contracts and immutable bindings", fixtureErrors.length === 0, fixtureErrors.join(","));
  if (!page) return { result: fixtureErrors.length ? "FAIL" : "PASS", fixtureErrors, fixtureCount: sessions.length + 1, checks };
  const response = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  const routeUnknown = async (route, reason) => { blocked.push({ url: route.request().url(), method: route.request().method(), reason }); await route.abort("blockedbyclient"); };
  const sourceSnapshot = { history_id: "synthetic-history", history_sha256: HASH("1"), rankings_id: "synthetic-rankings", rankings_sha256: HASH("2"), code_version: "synthetic-qa" };
  const createdSummary = (id, created) => {
    if (created.kind === "profile") {
      const request = created.body;
      const listing = profileFor(request.profile_id);
      return { id, request_kind: "profile", status: "pending", created_at: "2025-01-02T00:00:00Z", request,
        profile: listing.profile, sources: sourceSnapshot,
        display: { name: request.name, currency: listing.profile.currency, scale: listing.profile.scale,
          capital: request.conditions.capital, goal: request.conditions.goal, selector_label: request.selector.capability,
          staking_label: request.staking.capability ?? "profile-recovery-ladder/v1" },
        runs: [{ result_kind: "profile", ordinal: 0, configuration_id: null, status: "pending", result: null, bets_count: 0 }] };
    }
    const body = created.body;
    const listing = profileFor(body.profile.id);
    const dataset = datasetFor(body.dataset_sha256);
    const strategies = body.strategies.map(ref => {
      if (ref.id !== strategy.id || ref.revision !== strategy.revision || ref.definition_sha256 !== strategy.definition_sha256) {
        throw new Error("Synthetic created batch referenced an unknown strategy identity");
      }
      return strategy.definition;
    });
    const request = { schema_version: 5, kind: "profile_batch", profile_id: body.profile.id, profile_revision: body.profile.revision,
      profile_sha256: body.profile.sha256, dataset_sha256: body.dataset_sha256, conditions: body.conditions,
      strategies, max_draws: body.max_draws, source_version: "canonical-history/v1" };
    const sourceIdentity = { dataset_sha256: dataset.dataset_sha256, source_sha256: dataset.source_sha256, canonical_sha256: HASH("3"), row_count: 1,
      profile_id: request.profile_id, profile_revision: request.profile_revision, profile_sha256: request.profile_sha256,
      archive_bound: false, archive_history_sha256: null, archive_rank_row_ids: null };
    const runs = body.strategies.map((ref, ordinal) => ({ result_kind: "profile", ordinal, configuration_id: null, status: "pending",
      result_schema_version: null, strategy: { id: ref.id, revision: ref.revision, definition_sha256: ref.definition_sha256, name: strategy.name },
      result: null, bets_count: 0, complete: false, completion: "incomplete", stop_category: "unknown", stop_reason: "pending",
      stop_code: "pending", error: null }));
    return { id, request_kind: "profile", request_schema_version: 5, status: "pending", created_at: "2025-01-02T00:00:00Z",
      request, profile: listing.profile, display: { name: strategies[0].name, currency: listing.profile.currency, scale: listing.profile.scale,
        capital: body.conditions.capital, goal: body.conditions.goal, selector_label: "Strategy batch", staking_label: "Per-strategy definitions" },
      sources: sourceSnapshot, runs, batch_admission: { strategy_refs: body.strategies, source_identity: sourceIdentity,
        requested_constraints: { ...body.conditions, max_draws: body.max_draws }, effective_constraints: { ...body.conditions, max_draws: body.max_draws },
        policy_revision: 1, policy: { ...policy.policy } } };
  };

  try {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/*", async route => {
    const req = route.request();
    let url;
    try { url = new URL(req.url()); }
    catch { return routeUnknown(route, "malformed URL denied"); }
    if (url.origin !== BASE) {
      if (url.origin === "https://fonts.googleapis.com") {
        fontFallbackUsed = true;
        externalMocks.push({ url: url.href, action: "fulfilled empty CSS; screenshot uses fallback fonts" });
        return route.fulfill({ status: 200, contentType: "text/css", body: "" });
      }
      return routeUnknown(route, "non-local origin denied");
    }
    if (!url.pathname.startsWith("/api/v1/")) return route.continue();
    const method = req.method();
    let body = null;
    try { body = req.postDataJSON(); } catch {}
    ledger.push({ method, path: url.pathname + url.search, body: body ? deep(body) : null, scenario });
    const path = url.pathname;
    if (method === "POST") {
      if (path === "/api/v1/profile-batches/validate") {
        const valid = { valid: true, reasons: [], profile: body?.profile, dataset: { dataset_sha256: body?.dataset_sha256, row_count: 1,
          archive_bound: false }, strategies: [], requested_constraints: { max_draws: body?.max_draws }, effective_constraints: { max_draws: body?.max_draws },
          limits: { worker_count: 1, max_strategies_per_batch: 3, max_pending_runs: 10, run_timeout_seconds: 120, reservation_created: false }, policy: { revision: 1 } };
        return response(route, valid);
      }
      if (path === "/api/v1/experiments/profiles") {
        const id = (++createdSequence).toString(16).padStart(32, "0");
        createdPayloads.set(id, { kind: "profile", body: deep(body) });
        return response(route, { id, status: "pending" }, 201);
      }
      if (path === "/api/v1/profile-batches") {
        const id = (++createdSequence).toString(16).padStart(32, "0");
        createdPayloads.set(id, { kind: "batch", body: deep(body) });
        return response(route, { id, status: "pending" }, 201);
      }
      return routeUnknown(route, "POST not whitelisted");
    }
    if (method !== "GET") return routeUnknown(route, "non-GET/POST method denied");
    if (path === "/api/v1/simulations") {
      const id = activeId || "repeat-v1"; const saved = savedFor(id);
      if (!saved) return response(route, { total: 0, offset: 0, limit: 20, items: [] });
      const isV5 = id === batchSaved.id;
      const detail = isV5 ? batchSaved : { ...saved, id, status: "pending", created_at: "2025-01-01T00:00:00Z",
        profile: profileFor(saved.request.profile_id).profile,
        display: { name: `Saved v${saved.request.schema_version}`, currency: profileFor(saved.request.profile_id).profile.currency,
          scale: profileFor(saved.request.profile_id).profile.scale, capital: saved.request.conditions.capital, goal: saved.request.conditions.goal,
          selector_label: saved.request.selector.capability, staking_label: saved.request.staking.capability },
        sources: sourceSnapshot,
        runs: [{ result_kind: "profile", ordinal: 0, configuration_id: null, status: "pending", result: null, bets_count: 0 }] };
      const item = { source_kind: "experiment", scope: "profile", id, name: isV5 ? "Saved v5 batch" : `Saved v${saved.request.schema_version}`,
        created_at: "2025-01-01T00:00:00Z", status: "pending", detail };
      return response(route, { total: 1, offset: 0, limit: 20, items: [item] });
    }
    if (path === "/api/v1/queue") return response(route, { active_id: null,
      pending: { total: 0, offset: 0, limit: 20, count: 0, items: [] },
      held: { total: 0, offset: 0, limit: 20, count: 0, items: [] }, last_failure: null });
    const exp = path.match(/^\/api\/v1\/experiments\/([^/]+)$/);
    if (exp) {
      const id = decodeURIComponent(exp[1]);
      const created = createdPayloads.get(id);
      if (created) return response(route, createdSummary(id, created));
      const saved = savedFor(id);
      if (!saved) return response(route, { detail: "not found" }, 404);
      if (id === batchSaved.id) return response(route, batchSaved);
      const p = profileFor(saved.request.profile_id);
      return response(route, { ...saved, id, status: "pending", created_at: "2025-01-01T00:00:00Z", profile: p.profile,
        display: { name: `Saved v${saved.request.schema_version}`, currency: p.profile.currency, scale: p.profile.scale,
          capital: saved.request.conditions.capital, goal: saved.request.conditions.goal,
          selector_label: saved.request.selector.capability, staking_label: saved.request.staking.capability },
        sources: sourceSnapshot,
        runs: [{ result_kind: "profile", ordinal: 0, configuration_id: null, status: "pending", result: null, bets_count: 0 }] });
    }
    if (path === "/api/v1/catalog/profiles") {
      const available = profiles.filter(item => item.profile.profile_id !== missingProfileId);
      const offset = Number(url.searchParams.get("offset") || 0); const pageItems = available.slice(offset, offset + 20);
      return response(route, { total: available.length, offset, limit: 20, items: pageItems, templates: [] });
    }
    if (path === "/api/v1/datasets") {
      const offset = Number(url.searchParams.get("offset") || 0); const page = datasets.slice(offset, offset + 20);
      return response(route, { total: datasets.length, offset, limit: 20, items: page });
    }
    const draws = path.match(/^\/api\/v1\/datasets\/([^/]+)\/draws$/);
    if (draws) return response(route, { total: 1, offset: Number(url.searchParams.get("offset") || 0), limit: 100, items: ["2025-01-01 08:30"] });
    const datasetMatch = path.match(/^\/api\/v1\/datasets\/([^/]+)$/);
    if (datasetMatch) {
      const hash = decodeURIComponent(datasetMatch[1]);
      if (hash === missingDatasetHash) return response(route, { detail: "not found" }, 404);
      const item = datasetFor(hash);
      if (!item) return response(route, { detail: "not found" }, 404);
      if (hash === driftDatasetHash && ++datasetLookupCount > 1) return response(route, { ...item, dataset_sha256: HASH("5") });
      return response(route, item);
    }
    if (path === "/api/v1/strategies") return response(route, { total: 1, offset: 0, limit: 20, items: [strategy] });
    const revisions = path.match(/^\/api\/v1\/strategies\/([^/]+)\/revisions$/);
    if (revisions) return response(route, { total: 1, offset: 0, limit: 100, items: [strategy] });
    if (path === "/api/v1/execution-policy") return response(route, policy);
    if (path === "/api/v1/strategies/strategy-fixed") return response(route, strategy);
    return routeUnknown(route, "unknown API route denied");
  });

  const isolateSyntheticRepeatDraft = async flowId => {
    const key = `${BATCH_DRAFT_STORAGE_KEY}:repeat:${encodeURIComponent(batchSaved.id)}`;
    scenario = `${flowId}:storage-isolation`;
    if (new URL(page.url()).origin !== BASE) await page.goto(`${BASE}/simulaciones`);
    const isolation = await page.evaluate(storageKey => {
      const existed = sessionStorage.getItem(storageKey) !== null;
      sessionStorage.removeItem(storageKey);
      return { existed, absentAfterRemoval: sessionStorage.getItem(storageKey) === null };
    }, key);
    storageIsolation.push({ flowId, key, ...isolation, context: "isolated harness-owned browser context; synthetic fixture key only" });
    check(`${flowId}: isolated synthetic v5 draft before independent flow`, isolation.absentAfterRemoval, key);
  };
  const enterFromList = async (id, flowId) => {
    activeId = id; activeSaved = savedFor(id); activeVersion = id === batchSaved.id ? 5 : activeSaved.request.schema_version;
    scenario = `${flowId}:list-entry`;
    await page.goto(`${BASE}/simulaciones`);
    const name = id === batchSaved.id ? "Saved v5 batch" : `Saved v${activeVersion}`;
    const action = page.getByRole("button", { name: `Acciones de ${name}` });
    await action.waitFor({ state: "visible" });
    await action.click();
    await page.getByRole("menuitem", { name: "Repetir con cambios" }).click();
    await page.waitForURL(new RegExp(activeVersion === 5 ? "/simulaciones/nueva/sesion\\?base=" : "/simulaciones/nueva/perfil\\?base="));
  };
  const enterFromDetail = async (id, flowId) => {
    activeId = id; activeSaved = savedFor(id); activeVersion = id === batchSaved.id ? 5 : activeSaved.request.schema_version;
    scenario = `${flowId}:detail-entry`;
    await page.goto(`${BASE}/simulaciones/${encodeURIComponent(id)}`);
    await page.getByRole("navigation", { name: "Navegación de la simulación" }).waitFor({ state: "visible" });
    await page.getByRole("link", { name: "Repetir con cambios" }).click();
    await page.waitForURL(new RegExp(activeVersion === 5 ? "/simulaciones/nueva/sesion\\?base=" : "/simulaciones/nueva/perfil\\?base="));
  };
  const expectFormReady = async (version, flowId) => {
    if (version === 5) {
      await page.getByRole("heading", { name: "Lote de simulaciones" }).waitFor({ state: "visible" });
      const contextStep = page.getByRole("button", { name: "Historial y perfil", exact: true });
      await contextStep.waitFor({ state: "visible" });
      check(`${flowId}: v5 hydration remains on step 0`, await contextStep.getAttribute("aria-current") === "step");
      await page.getByLabel("Sorteo inicial").waitFor({ state: "visible" });
    } else {
      await page.getByRole("textbox", { name: "Nombre de la simulación" }).waitFor({ state: "visible" });
      await page.getByRole("combobox", { name: "Sorteo inicial" }).waitFor({ state: "visible" });
    }
  };
  const createSession = async (version, flowId) => {
    const original = originals.get(activeId);
    const originalReq = deep(original.request);
    scenario = `${flowId}:create`;
    if (version === 5) {
      const currentStep = name => page.getByRole("navigation", { name: "Pasos de la simulación" }).getByRole("button", { name, exact: true });
      const isCurrent = async name => (await currentStep(name).getAttribute("aria-current")) === "step";
      check(`${flowId}: starts on Historial y perfil`, await isCurrent("Historial y perfil"));
      const continueButton = page.getByRole("button", { name: "Continuar", exact: true });
      await continueButton.click();
      check(`${flowId}: pointer advances to Estrategias`, await isCurrent("Estrategias"));
      await continueButton.focus(); await continueButton.press("Enter");
      check(`${flowId}: Enter advances to Condiciones`, await isCurrent("Condiciones"));
      await continueButton.press("Space");
      check(`${flowId}: Space advances to Validación`, await isCurrent("Validación"));
      check(`${flowId}: pointer/Enter/Space navigation does not create`, ledger.filter(row => row.scenario === scenario && row.path === "/api/v1/profile-batches").length === 0);
      await currentStep("Condiciones").click();
      check(`${flowId}: conditions controls are only asserted on Condiciones step`, await isCurrent("Condiciones"));
      const currency = profiles[4].profile.currency;
      const capital = page.getByLabel(`Capital inicial (${currency})`);
      const goal = page.getByLabel(`Meta de saldo (${currency})`);
      await capital.waitFor({ state: "visible" }); await goal.waitFor({ state: "visible" });
      check(`${flowId}: saved v5 money values hydrated`, await capital.inputValue() === "100" && await goal.inputValue() === "200");
      check(`${flowId}: nullable elapsed limit remains blank`, await page.getByLabel("Máximo sorteos transcurridos").inputValue() === "");
      await page.getByLabel("Límite operativo solicitado").fill("41");
      await currentStep("Validación").click();
      check(`${flowId}: enters Validación step`, await isCurrent("Validación"));
      await page.getByRole("button", { name: "Validar simulación" }).click();
      await page.getByText("Validación aceptada").waitFor({ state: "visible" });
      const create = page.getByRole("button", { name: "Crear simulaciones" });
      check(`${flowId}: successful validation advances to confirmation`, await isCurrent("Simulación"));
      check(`${flowId}: automatic confirmation step does not create`, ledger.filter(row => row.scenario === scenario && row.path === "/api/v1/profile-batches").length === 0);
      await create.click();
      await page.waitForURL(/\/simulaciones\/[a-f0-9]{32}$/);
      const posts = ledger.filter(row => row.scenario === scenario && row.path === "/api/v1/profile-batches");
      check(`${flowId}: exactly one synthetic v5 create`, posts.length === 1, `POSTs=${posts.length}`);
      check(`${flowId}: requested max_draws edit preserved`, posts[0]?.body?.max_draws === 41);
      check(`${flowId}: new request identity`, posts[0]?.body?.client_request_id !== activeId);
      check(`${flowId}: saved v5 fixture immutable`, JSON.stringify(batchSaved) === JSON.stringify(originals.get(activeId)));
      check(`${flowId}: requested nullable elapsed constraint preserved`, posts[0]?.body?.conditions?.max_elapsed_draws === null);
      check(`${flowId}: start and time bounds preserved`, posts[0]?.body?.conditions?.start_draw === originalReq.conditions.start_draw &&
        posts[0]?.body?.conditions?.end_minute === originalReq.conditions.end_minute && posts[0]?.body?.conditions?.duration_minutes === originalReq.conditions.duration_minutes);
    } else {
      const name = page.getByRole("textbox", { name: "Nombre de la simulación" });
      await name.fill(`Repeat v${version} edited`);
      const submit = page.getByRole("button", { name: "Crear simulación y agregar a la cola" });
      // Keyboard-operate a non-submit disclosure, then confirm no POST before explicit Create.
      const summary = page.getByText("Ajustes avanzados", { exact: true }).first();
      await summary.focus(); await summary.press("Enter"); await summary.press("Space");
      check(`${flowId}: no premature session POST`, ledger.filter(row => row.scenario === scenario && row.path === "/api/v1/experiments/profiles").length === 0);
      await submit.click();
      await page.waitForURL(/\/simulaciones\/[a-f0-9]{32}$/);
      const posts = ledger.filter(row => row.scenario === scenario && row.path === "/api/v1/experiments/profiles");
      check(`${flowId}: exactly one synthetic session create`, posts.length === 1, `POSTs=${posts.length}`);
      const sent = posts[0]?.body;
      check(`${flowId}: original schema and immutable bindings`, sent?.schema_version === version && sent?.profile_id === originalReq.profile_id &&
        sent?.profile_revision === originalReq.profile_revision && sent?.profile_sha256 === originalReq.profile_sha256 && sent?.dataset_sha256 === originalReq.dataset_sha256);
      check(`${flowId}: explicit name edit retained`, sent?.name === `Repeat v${version} edited`);
      check(`${flowId}: untouched selector/time wire fields preserved`, JSON.stringify(sent?.selector) === JSON.stringify(originalReq.selector) &&
        sent?.conditions?.start_draw === originalReq.conditions.start_draw && sent?.conditions?.end_minute === originalReq.conditions.end_minute &&
        sent?.conditions?.duration_minutes === originalReq.conditions.duration_minutes && sent?.conditions?.max_elapsed_draws === originalReq.conditions.max_elapsed_draws);
      check(`${flowId}: original saved request immutable`, JSON.stringify(savedFor(activeId)) === JSON.stringify(originals.get(activeId)));
    }
  };

  // Representative screenshots and the same entry/repeat routes at both target widths.
  for (const width of (options.negativesOnly ? [] : [390, 1440])) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    for (const [index, item] of [...sessions, batchSaved].entries()) {
      const useDetail = (index + (width === 1440 ? 1 : 0)) % 2 === 1;
      const flowId = `${width}px-${item.id}-${useDetail ? "detail" : "list"}`;
      if (item.id === batchSaved.id) await isolateSyntheticRepeatDraft(flowId);
      if (useDetail) await enterFromDetail(item.id, flowId); else await enterFromList(item.id, flowId);
      await expectFormReady(activeVersion, flowId);
      check(`${flowId}: entered real ${activeVersion === 5 ? "v5 batch" : `v${activeVersion}`} repeat creator via ${useDetail ? "detail" : "list"}`,
        page.url().includes(activeVersion === 5 ? "/simulaciones/nueva/sesion?base=" : "/simulaciones/nueva/perfil?base="));
      await measureViewport(`${width}px ${item.id} repeat creator`);
      if ((width === 390 && index === 0) || (width === 1440 && index === 4)) {
        await captureScreenshot(`${OUT}/profile-repeat-${width}-${activeVersion}.png`);
      }
      await createSession(activeVersion, flowId);
    }
  }

  // Policy-version caps are exercised as invalid edits against otherwise valid saved requests.
  for (const [id, coverage] of [["repeat-v2", "80"], ["repeat-v3", "2"]]) {
    scenario = `negative-${id}-coverage-cap`;
    activeId = id; activeSaved = savedFor(id);
    await page.goto(`${BASE}/simulaciones/nueva/perfil?base=${id}`);
    await page.getByRole("textbox", { name: "Nombre de la simulación" }).waitFor({ state: "visible" });
    await page.locator('section[aria-labelledby="selection-title"] summary').click();
    await page.getByRole("textbox", { name: /Cobertura/ }).waitFor({ state: "visible" });
    await page.getByRole("textbox", { name: /Cobertura/ }).fill(coverage);
    if (id === "repeat-v2") await page.getByRole("textbox", { name: /Números distintos/ }).fill(Array.from({ length: 80 }, (_, index) => String(index)).join(","));
    else await page.getByRole("textbox", { name: /Números distintos/ }).fill("0,1");
    await page.getByRole("button", { name: "Crear simulación y agregar a la cola" }).click();
    await page.getByRole("alert").waitFor({ state: "visible" });
    check(`${id}: policy-specific coverage cap rejects before create`, ledger.filter(row => row.scenario === scenario)
      .every(row => row.path !== "/api/v1/experiments/profiles"));
  }
  scenario = "negative-profile-binding";
  activeId = "repeat-v1"; activeSaved = sessions[0]; missingProfileId = "v1-profile";
  await page.goto(`${BASE}/simulaciones/nueva/perfil?base=${activeId}`);
  await page.getByRole("alert").waitFor({ state: "visible" });
  check("missing exact v1 profile revision fails closed without POST", ledger.filter(row => row.scenario === scenario).every(row => row.method !== "POST"));
  missingProfileId = "";
  scenario = "missing-dataset"; missingDatasetHash = datasets[0].dataset_sha256;
  await page.goto(`${BASE}/simulaciones/nueva/perfil?base=repeat-v1`);
  await page.getByRole("alert").waitFor({ state: "visible" });
  check("missing exact v1 dataset fails closed without POST", ledger.filter(row => row.scenario === scenario).every(row => row.method !== "POST"));
  missingDatasetHash = "";
  scenario = "changed-current-dataset"; activeId = "repeat-v1"; driftDatasetHash = datasets[0].dataset_sha256; datasetLookupCount = 0;
  await page.goto(`${BASE}/simulaciones/nueva/perfil?base=repeat-v1`);
  await page.getByRole("textbox", { name: "Nombre de la simulación" }).waitFor({ state: "visible" });
  await page.getByRole("button", { name: "Crear simulación y agregar a la cola" }).click();
  await page.getByRole("alert").waitFor({ state: "visible" });
  check("dataset identity drift at submit blocks synthetic create", ledger.filter(row => row.scenario === scenario)
    .every(row => row.path !== "/api/v1/experiments/profiles"));
  driftDatasetHash = "";

  // Global containment: every captured POST was one of the two synthetic create routes or the explicitly synthetic v5 validator.
  const postRows = ledger.filter(row => row.method === "POST");
  check("only synthetic whitelisted POST routes", postRows.every(row => ["/api/v1/experiments/profiles", "/api/v1/profile-batches", "/api/v1/profile-batches/validate"].includes(row.path)));
  check("no unknown or external request escaped interception", blocked.length === 0, JSON.stringify(blocked.slice(0, 5)));
  check("all original fixtures immutable", [...sessions, batchSaved].every(item => JSON.stringify(savedFor(item.id)) === JSON.stringify(originals.get(item.id))));
  if (failures.length) {
    try { await captureScreenshot(`${OUT}/failure.png`); }
    catch (cause) { failures.push(`failure screenshot capture failed: ${cause?.message ?? String(cause)}`); }
  }
  return buildReport(failures.length ? "FAIL" : "PASS");
  } catch (cause) {
    const error = { name: cause?.name ?? "Error", message: cause?.message ?? String(cause), stack: cause?.stack ?? null, scenario };
    check("harness execution completed", false, `${scenario}: ${error.message}`);
    try { await captureScreenshot(`${OUT}/failure.png`); }
    catch (screenshotCause) { error.screenshotError = screenshotCause?.message ?? String(screenshotCause); }
    return buildReport("FAIL", error);
  }
}
