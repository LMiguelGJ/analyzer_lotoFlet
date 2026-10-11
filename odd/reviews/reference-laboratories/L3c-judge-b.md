```json
{
  "rows": [
    {
      "id": "JD-B-001",
      "lens": "judgment-day",
      "location": "webapp/backend/laboratorio/api/reference_labs.py:160",
      "severity": "CRITICAL",
      "status_at_freeze": "open",
      "evidence_class": "static-analysis",
      "evidence_claim": "ReferenceLabServiceError exception handler performs unchecked dictionary lookup `_SERVICE_ERRORS[exc.kind]` without fallback. If execute_reference_lab() raises error with unknown kind, KeyError bubbles up as unhandled exception → 500 with traceback. Only 3 kinds defined ('invalid', 'not_found', 'conflict'); if service layer adds a 4th kind without updating this dict, production breaks. Defensive gap: no try/except KeyError or .get() with default."
    },
    {
      "id": "JD-B-002",
      "lens": "judgment-day",
      "location": "webapp/backend/laboratorio/app.py:20",
      "severity": "WARNING",
      "status_at_freeze": "open",
      "evidence_class": "architectural-note",
      "evidence_claim": "Regex pattern `_REFERENCE_RUNS_PATH = r'/api/v1/reference-labs/[^/]+/runs'` guards body size limit for POST /reference-labs/{lab_id}/runs but NOT for DELETE /reference-labs/{lab_id}/runs/{run_id}. By design (DELETE rarely has body) but worth noting: if protocol changes to allow DELETE body, size validation is bypassed. Current tests show no DELETE body is sent, so not a bug today."
    }
  ]
}
```
