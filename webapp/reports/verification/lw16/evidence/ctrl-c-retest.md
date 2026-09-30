# LW16 true Ctrl+C followup — safety stop (not acceptance)

## Result

**No `CTRL_C_EVENT` was sent.** A dedicated `CREATE_NEW_CONSOLE` dummy host was launched, but the separate control helper could not attach to it. `FreeConsole()` returned success; `AttachConsole(24664)` returned Win32 error **5 (access denied)**. Consequently the helper could not inspect/verify the actual target-console process list, so it stopped before `GenerateConsoleCtrlEvent`. No live BAT case was launched. The prior `CTRL_BREAK_EVENT`/HTTP observations in `../report.md` remain separate evidence, not a true Ctrl+C pass. The instrumented browser stub was not a real browser-open test.

The first `run` command returned 1 with `AssertionError: isolation not proved; CTRL_C_EVENT not sent`. Its helper stderr was captured by the controller but not persisted because this assertion terminated the controller. A subsequent **read-only dry-run** of the same helper against the already-owned dummy, without a signal, emitted: `AttachConsole failed: 5; original=[24108, 17516, 12844] FreeConsole=1/6 after_detach=[]`. Error 6 after successful detachment is the lack of an attached console; error 5 is the actual attach failure. The helper's original console participants were never targeted. `ctrl_c_retest.py` `run` and `send` entrypoints are disabled after this outcome to prevent an accidental repeat.

## Ownership and cleanup state

- `evidence/ctrl-c-probe.json`: new-console host PID **24664**, direct dummy child PID **19436**, command `C:\Python314\python.exe -B <repo>\webapp\.lw16-windows-acceptance\ctrl_c_retest.py probe`, cwd `evidence/`, no new child process group. `ctrl-c-probe.stdout.log` confirms `SIGINT probe ready pid=19436`; `ctrl-c-probe.stderr.log` empty. **No probe receipt, signal JSON, or exit JSON exists**; no SIGINT observation can be claimed.
- Read-only CIM after the failed attempt showed PID 19436 still running, `ParentProcessId=24664`, creation `30/9/2026 7:22:57 a. m.`, executable `C:\Python314\python.exe`, and the exact probe command above. Query for current children of 24664 returned PID 19436 and `conhost.exe` PID 20308 (the latter created at 7:22:56 a. m.); a separate current query for PID 24664 returned no process. A stale PPID or a surviving console host is **not** inferred from this list. The owned dummy is orphaned; **no kill/cleanup has been performed**. This is a harness cleanup defect, not a product result.
- Port **18766 free** at the first stopped attempt and again after the followup query. No BAT, uvicorn, or new browser stub was run. The previous copy manifest and evidence were not overwritten.
- `validate.py` printed 29 original/copy hashes unchanged, both frozen input SHA-256 hashes unchanged (`d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`, `b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d`), and port free, but exited **1** because its old PID-only check briefly listed historical signal-probe-2 PID 1984. A subsequent `tasklist` query for 1984 showed no task. PID-only historical checks are not proof of identity; this validation is **not reported as a pass**. The outstanding PID 19436 is not covered by that old validator.

## Commands and observed outcomes

1. `PYTHONDONTWRITEBYTECODE=1 /c/Python314/python.exe -B webapp/.lw16-windows-acceptance/validate.py` (before attempt): 29 hashes matched, frozen hashes matched, port free, previously recorded PIDs absent; exit 0.
2. `PYTHONDONTWRITEBYTECODE=1 /c/Python314/python.exe -B -c "import ast, pathlib; ast.parse(pathlib.Path('webapp/.lw16-windows-acceptance/ctrl_c_retest.py').read_text())"`: syntax parsed; exit 0.
3. `PYTHONDONTWRITEBYTECODE=1 /c/Python314/python.exe -B webapp/.lw16-windows-acceptance/ctrl_c_retest.py run`: dummy started; helper failed isolation; no event; exit 1. **Do not rerun.**
4. `PYTHONDONTWRITEBYTECODE=1 /c/Python314/python.exe -B webapp/.lw16-windows-acceptance/ctrl_c_retest.py send ctrl-c-probe 24664 19436 0 check`: read-only inspection; `AttachConsole failed: 5`; exit 1. Repeated once with diagnostic output (`FreeConsole=1`, after-detach empty); no signal in either call.
5. `powershell -NoProfile -Command 'Get-CimInstance Win32_Process -Filter "ProcessId=19436" | Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine | Format-List'`: PID 19436 matched the owned Python probe script and recorded child PID.
6. `powershell -NoProfile -Command 'Get-CimInstance Win32_Process -Filter "ParentProcessId=24664" | Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine | Format-List'`: PID 19436 and conhost PID 20308 listed; host liveness not implied.
7. `powershell -NoProfile -Command 'Get-CimInstance Win32_Process -Filter "ProcessId=24664" | Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine | Format-List'`: no process.
8. `PYTHONDONTWRITEBYTECODE=1 /c/Python314/python.exe -B webapp/.lw16-windows-acceptance/validate.py` (after attempt): hash and port fields true but historical PID check listed 1984; exit 1. Subsequent `tasklist` for 1984 showed no matching task; 19436 still listed.

## Parent cleanup executed

The parent executed the identity-guarded cleanup against PID 19436, matching the recorded parent, executable, and exact probe command line. Output: `Owned dummy stopped (cleanup only)`. The immediate CIM query for PID 19436 returned no process. This was targeted non-graceful harness cleanup, not Ctrl+C acceptance. No other process was stopped. The historical proposal below is retained as provenance, no longer a pending cleanup request.

## Historical cleanup proposal

The parent/human must approve or decline **targeted non-graceful cleanup only**; it is not acceptance and must not be conflated with Ctrl+C. Proposed guarded command (not run), matching the exact observed PID, parent, executable, and script command line before stopping:

```powershell
powershell -NoProfile -Command '$p=Get-CimInstance Win32_Process -Filter "ProcessId=19436"; if ($p -and $p.ParentProcessId -eq 24664 -and $p.ExecutablePath -eq "C:\Python314\python.exe" -and $p.CommandLine -eq "C:\Python314\python.exe -B <repo>\webapp\.lw16-windows-acceptance\ctrl_c_retest.py probe") { Stop-Process -Id 19436 } else { throw "Owned dummy identity mismatch; no stop" }'
```

If that guard no longer matches, do not stop anything. Even if approved cleanup succeeds, true Ctrl+C remains **unverified**. Product source is unchanged; functional closure versus manual acceptance is a parent/user decision.
