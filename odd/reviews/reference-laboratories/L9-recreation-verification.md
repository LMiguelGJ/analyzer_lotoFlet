# L9 — fourteen laboratories recreated manually and compared with their goldens

Base e18c7919091ff4753b2896695217227abdbc3763. Isolated backend (port 8792, temporary data directory); the script uses the same HTTP endpoints as the interface.

For each golden in `webapp/backend/tests/fixtures/reference_labs_golden.json` the script creates a laboratory from the golden's own configuration (`POST /laboratories`), runs it with the frozen history digest, and compares: eligible draws, gaps, first/last labels, session count, session digest, every totals field (floats by exact equality) and the goal/ruin/incomplete/first/last boundary sessions fetched individually by ordinal.

Result: 14/14 PASS, 14 fresh UUIDs (none equals the seeded identity), 0.4–10.3 s per laboratory. Per-laboratory rows, UUIDs and run ids: `L9-recreation-report.json`. Reproduce with `odd/qa/l9-recreate-and-compare.py` against a backend started on port 8792 with its own `LABORATORIO_DATA_DIR`.

Two of the fourteen (`transicion_1_audaz`, `paridad_50_plana`) were also recreated through the browser form in L7/L8 with identical digests.

Limits: this verifies fidelity of the replay engine for the recreated configurations; it is not a Judgment Day verdict. The golden fixture is the project's own protected reference, produced from the archived reference engine in earlier units (L2). No native review, no full-backend run for this unit.
