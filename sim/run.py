"""
Harness.

    python -m sim.run              run everything, summary table
    python -m sim.run -v           add the rail's trace and evidence status
    python -m sim.run <key> ...    run named scenarios only
    python -m sim.run --list       list scenario keys
"""

from __future__ import annotations

import sys

from .scenarios import SCENARIOS, Scenario, Result

GREEN, RED, YELLOW, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)


def _verdict(sc: Scenario, r: Result) -> tuple[bool, str]:
    """Did the system behave as the scenario predicted?"""
    if r.approved != sc.expect_approved:
        want = "APPROVE" if sc.expect_approved else "REFUSE"
        got = "APPROVE" if r.approved else "REFUSE"
        return False, f"expected {want}, got {got}"
    if sc.expect_violation and r.result:
        kinds = {v.kind for v in r.result.fatal}
        if sc.expect_violation not in kinds:
            return False, (f"expected a '{sc.expect_violation}' violation, "
                           f"got {sorted(kinds) or 'none'}")
    return True, ""


def run(keys: list[str], verbose: bool) -> int:
    chosen = [s for s in SCENARIOS if not keys or s.key in keys]
    if not chosen:
        print(f"no scenario matches {keys}")
        return 2

    rows, failures = [], 0
    family = None

    for sc in chosen:
        if sc.family != family:
            family = sc.family
            print(f"\n{BOLD}{family.upper()}{OFF}")

        r = sc.run()
        ok, why = _verdict(sc, r)
        failures += 0 if ok else 1

        decision = f"{GREEN}APPROVED{OFF}" if r.approved else f"{RED}REFUSED{OFF}"
        mark = f"{GREEN}ok{OFF}" if ok else f"{RED}UNEXPECTED{OFF}"
        score = f"{r.result.score:.2f}" if r.result else "-"

        print(f"\n  {BOLD}{sc.title}{OFF}  {DIM}[{sc.key}]{OFF}")
        print(f"    {DIM}{sc.premise}{OFF}")
        if r.note:
            print(f"    {DIM}{r.note}{OFF}")
        print(f"    -> {decision}   score {score}   {mark}")
        if not ok:
            print(f"       {RED}{why}{OFF}")
        if r.result and r.result.violations:
            for v in r.result.violations:
                colour = RED if v.severity.value == "fatal" else YELLOW
                print(f"       {colour}{v}{OFF}")
        elif not r.approved:
            print(f"       {YELLOW}{r.reason}{OFF}")

        if r.approved and r.outcome and r.outcome.funding:
            f = r.outcome.funding
            print(f"       {DIM}funded by {f.principal.name}, "
                  f"{f.remaining} of {f.budget} left{OFF}")

        if verbose:
            if r.outcome:
                print(f"    {DIM}rail:{OFF}")
                for line in r.outcome.trace:
                    print(f"      {DIM}{line}{OFF}")
            if r.outcome and r.outcome.evidence:
                e = r.outcome.evidence
                print(f"    {DIM}evidence bundle complete: {e.complete()}{OFF}")

        rows.append((sc, r, ok))

    total = len(rows)
    refused = sum(1 for _, r, _ in rows if not r.approved)
    print(f"\n{BOLD}{'-' * 66}{OFF}")
    print(f"  {total} scenarios | {refused} refused | {total - refused} approved")
    if failures:
        print(f"  {RED}{failures} behaved unexpectedly -- that is a finding, "
              f"not a bug to paper over{OFF}")
    else:
        print(f"  {GREEN}all scenarios matched their predicted outcome{OFF}")
    print(f"{BOLD}{'-' * 66}{OFF}")
    return 1 if failures else 0


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if "--list" in args:
        for s in SCENARIOS:
            print(f"  {s.key:<20} {s.family:<12} {s.title}")
        return 0
    verbose = "-v" in args or "--verbose" in args
    keys = [a for a in args if not a.startswith("-")]
    return run(keys, verbose)


if __name__ == "__main__":
    raise SystemExit(main())
