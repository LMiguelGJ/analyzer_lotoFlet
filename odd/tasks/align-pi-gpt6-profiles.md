# Align Pi GPT-6 profiles

## Scope
Update the explicit OpenAI-Codex `low-cost`, `recommended`, and `powerful` profiles in the user Pi configuration, activate the equivalent GitHub Copilot Low-cost mapping, and retain a verified backup before modification.

## Constraints
- Back up the original configuration to `C:\Users\luism\OneDrive\Escritorio\gentle-ai-config` before any target-file modification.
- Copy `profiles.json`, `profiles.export.json`, and `models.json`, with a SHA-256 manifest.
- Keep all 35 assignments explicit; do not use inheritance.
- Update only the requested three OpenAI-Codex profiles and the active GitHub Copilot `models.json` mapping.
- Do not alter unrelated profiles.

## Tasks
- [x] Back up current Pi profile artifacts and record SHA-256 evidence.
- [x] Rebuild the three OpenAI-Codex GPT-6 profiles with explicit assignments.
- [x] Activate and verify the GitHub Copilot Low-cost GPT-6 mapping.
- [x] Back up and align only `low-cost-copilot` to the approved explicit OpenAI-Codex Astra-low mapping.
- [x] Correct only the `low-cost-copilot` provider prefix to `github-copilot`, preserving the approved GPT-6 role and effort map.
- [x] Back up and change only `powerful` GPT-6 Astra effort to `low` (15 roles from `xhigh`, orchestrator from `medium`). Fresh backup: `C:/Users/luism/OneDrive/Escritorio/gentle-ai-config/2026-09-24T05-38-46-427Z-powerful-astra-low`. Independent Node whole-document deep equality and backup SHA-256 verification passed. Provider remains `openai-codex`; user deletion of `powerful-astra` preserved.

## Evidence
- Backup: `C:\Users\luism\OneDrive\Escritorio\gentle-ai-config\20260924-011241`.
- SHA-256 verification: `profiles.json`, `profiles.export.json`, and `models.json` all verified successfully against `manifest.sha256`.
- `profiles.json`: `low-cost`, `recommended`, and `powerful` each contain the approved, explicit 35-role GPT-6 matrix; unrelated `economy`, `low-cost-copilot`, and `powerful-astra` entries remain semantically unchanged.
- `profiles.export.json`: explicit OpenAI-Codex Low-cost GPT-6 configuration matches `profiles.json`.
- `models.json`: explicit GitHub Copilot Low-cost GPT-6 configuration contains 35 assignments.
- Independent read-only verification: PASS; Python was unavailable, so an equivalent Node.js semantic verifier was used.
- `low-cost-copilot` backup: `C:\Users\luism\OneDrive\Escritorio\gentle-ai-config\20260924-012354-low-cost-copilot-before-astra-low`; its SHA-256 manifest verified successfully.
- Targeted verification: PASS. Only `low-cost-copilot` changed; it has 35 explicit roles, 16 approved Astra-low roles, and the approved Sol/Luna groups.
- Provider correction backup: `C:\Users\luism\OneDrive\Escritorio\gentle-ai-config\20260924-012934-low-cost-copilot-before-provider-fix`; its SHA-256 manifest verified successfully. Read-only verification confirmed only `low-cost-copilot` changed, all 35 assignments now use `github-copilot/`, and their model suffixes and effort values were preserved.
