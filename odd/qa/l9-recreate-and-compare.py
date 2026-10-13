import json, time, urllib.request, sys
B = "http://127.0.0.1:8792/api/v1"
def call(method, path, body=None):
    req = urllib.request.Request(B + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:8792"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())
hist = call("GET", "/reference-labs")["reference_history"]["sha256"]
seed_ids = {i["name"]: i["id"] for i in call("GET", "/laboratories?limit=100")["items"]}
golden = json.load(open("webapp/backend/tests/fixtures/reference_labs_golden.json", encoding="utf-8"))["laboratories"]
KEYS = ["outcome", "start_index", "end_index", "draws", "final_balance", "wagered", "paid"]
report = []
for g in golden:
    started = time.time()
    cfg = {"schema_version": 1, **{k: g[k] for k in ("system", "coverage", "stake_style", "capital", "goal", "prizes", "window_start", "window_end")}}
    d = call("POST", "/laboratories", {"name": "recreada_" + g["lab_id"], "config": cfg})
    run = call("POST", f"/laboratories/{d['id']}/runs", {"required_history_sha256": hist})
    s = run["summary"]
    failures = []
    for k in ("eligible_draws", "gaps", "first", "last"):
        if s[k] != g[k]: failures.append(f"{k}: {s[k]!r} != {g[k]!r}")
    if s["session_count"] != g["session_count"]: failures.append("session_count")
    if s["session_sha256"] != g["session_sha256"]: failures.append("session_sha256")
    for k, v in g["totals"].items():
        if s["totals"].get(k) != v: failures.append(f"totals.{k}: {s['totals'].get(k)!r} != {v!r}")
    for kind, b in g["boundary_sessions"].items():
        page = call("GET", f"/laboratories/{d['id']}/runs/{run['id']}/sessions?offset={b['index']}&limit=1")["items"][0]
        got = [page["summary"][k] for k in KEYS]
        if page["ordinal"] != b["index"] or got != b["session"]: failures.append(f"boundary {kind}: {got} != {b['session']}")
    row = {"lab": g["lab_id"], "pass": not failures, "failures": failures, "fresh_uuid": d["id"] != seed_ids.get(g["lab_id"]),
           "uuid": d["id"], "run_id": run["id"], "session_sha256": s["session_sha256"], "net": s["totals"]["total_net"], "seconds": round(time.time() - started, 1)}
    report.append(row); print(json.dumps(row), flush=True)
json.dump(report, open(".tmp/l9/report.json", "w"), indent=1)
print("SUMMARY", sum(r["pass"] for r in report), "/", len(report), "pass;", sum(r["fresh_uuid"] for r in report), "fresh uuids", flush=True)
