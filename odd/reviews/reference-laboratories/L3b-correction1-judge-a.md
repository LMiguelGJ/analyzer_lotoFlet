Excelente. He revisado los fixes de forma exhaustiva. Ahora voy a generar las resoluciones:

**Resumen de análisis:**

**JD-L3b-001** — "Run listing materializes full sessions/results":
- Fix: Cambió list_reference_lab_runs() de _read_run() (full payload) a CTE con json_extract thin projection (id, lab_id, version, created_at, summary capped a 2048 chars)
- Verificación: test_listing_uses_thin_projection_without_decoding_or_fetching_full_records valida memory < 1MB con 3 runs de 1000 sesiones + 3MB metadata cada una
- Status: **VERIFIED**

**JD-L3b-002** — "Digest shape accepted sin canonical agreement":
- Fix 1: Agregó _session_digest() con SHA256 canónico
- Fix 2: Validación bidireccional: `if digest != _session_digest(digest_rows)` en admission y read
- Fix 3: Comparación canónica en _decode_run(): `_canonical(copy) != _canonical(sessions[index])`
- Tests: test_digest_mismatch_is_rejected_before_any_write_and_on_every_read, test_coherent_tampering_in_both_copies_with_fresh_digest_fails_accounting
- Status: **VERIFIED**

**JD-L3b-003** — "Final balance and closed mean not reconciled":
- Fix 1: Validación de capital: `capital = _integer(config.get("capital"), minimum=1)`
- Fix 2: Equation en _check_session(): `final != capital + paid - wagered`
- Fix 3: Reconciliación de media: `mean_net_closed != (closed_net / closed_count if closed_count else None)`
- Tests: test_session_accounting_is_enforced_on_admission, test_stored_capital_tampering_or_bad_capital_is_rejected, test_mean_net_closed_must_match_completed_session_mean
- Status: **VERIFIED**

**JD-L3b-004** — "Session-row bool/float corruption bypass":
- Fix: Strict type checking via _integer() que rechaza bool/float (no `type(value) is int`)
- Comparación canónica en _decode_run()
- Tests: test_corrupt_numeric_row_copy_fails_even_when_python_equal, test_numeric_session_substitutions_are_rejected_on_admission con parametrización exhaustiva
- Status: **VERIFIED**

```json
{
  "resolutions": [
    {
      "id": "JD-L3b-001",
      "outcome": "verified"
    },
    {
      "id": "JD-L3b-002",
      "outcome": "verified"
    },
    {
      "id": "JD-L3b-003",
      "outcome": "verified"
    },
    {
      "id": "JD-L3b-004",
      "outcome": "verified"
    }
  ]
}
```
