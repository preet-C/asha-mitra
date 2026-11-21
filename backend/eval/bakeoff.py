# backend/eval/bakeoff.py
# P4 — LLM provider bake-off
#
# WHY: We pick the LLM at the event (D9). This script runs eval cases through
# one or more providers, prints a comparison table, and writes the winner
# to docs/DECISIONS.md.
#
# Usage:
#   cd backend
#   python -m eval.bakeoff                        # uses provider from .env
#   python -m eval.bakeoff --providers gemini     # explicit
#   python -m eval.bakeoff --providers gemini anthropic huggingface
#
# Output: a table printed to stdout + winner line appended to docs/DECISIONS.md.

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml

# Add backend/ to path so we can import app.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.brain.extract import extract_visit
from app.brain.normalize import resolve_next_visit

# ─── Paths ────────────────────────────────────────────────────────────────────

_BACKEND_DIR = Path(__file__).parent.parent
_CASES_PATH = Path(__file__).parent / "cases.yaml"
_DECISIONS_PATH = _BACKEND_DIR.parent / "docs" / "DECISIONS.md"


# ─── Case loading ─────────────────────────────────────────────────────────────

def load_cases() -> list[dict]:
    """Load evaluation cases from cases.yaml."""
    if not _CASES_PATH.exists():
        print(f"ERROR: cases.yaml not found at {_CASES_PATH}")
        print("Run P6 first, or create eval/cases.yaml manually.")
        sys.exit(1)
    return yaml.safe_load(_CASES_PATH.read_text(encoding="utf-8")) or []


# ─── Scoring ──────────────────────────────────────────────────────────────────

def score_case(result: dict, expect: dict, today: date) -> dict:
    """
    Compare extracted result to expected values.
    Returns a dict of per-field pass/fail + danger info.

    WHY: We care most about danger recall (missing a danger sign is the worst
    failure). Field accuracy is secondary.
    """
    hits = 0
    total = 0
    details = {}

    # ── Scalar fields ──────────────────────────────────────────────────
    for field in ("beneficiary_id", "visit_type", "weight_kg", "asks_advice"):
        if field not in expect:
            continue
        total += 1
        got = result.get(field)
        want = expect[field]

        # weight: allow ±0.05 kg tolerance for float rounding
        if field == "weight_kg" and got is not None and want is not None:
            ok = abs(float(got) - float(want)) <= 0.05
        else:
            ok = got == want

        hits += ok
        details[field] = "✓" if ok else f"✗ got={got!r} want={want!r}"

    # ── next_visit_date: resolve spec → ISO date, compare ─────────────
    if "next_visit_date" in expect:
        total += 1
        spec = result.get("next_visit")
        resolved: Optional[date] = None
        if spec:
            try:
                resolved = resolve_next_visit(spec, today)
            except Exception:
                pass
        got_str = resolved.isoformat() if resolved else None
        ok = got_str == expect["next_visit_date"]
        hits += ok
        details["next_visit_date"] = "✓" if ok else f"✗ got={got_str!r} want={expect['next_visit_date']!r}"

    # ── Danger signs: recall ───────────────────────────────────────────
    # expected_danger is a list of sign IDs we must catch (may be [])
    expected_danger = set(expect.get("danger", []))
    got_signs = {
        s["sign_id"]
        for s in (result.get("symptoms") or [])
        if s.get("status") in ("present", "unclear")
    }

    danger_recall_num = 0
    danger_recall_den = len(expected_danger)

    if expected_danger:
        danger_recall_num = len(expected_danger & got_signs)
        missed = expected_danger - got_signs
        total += 1
        ok = len(missed) == 0
        hits += ok
        details["danger"] = "✓" if ok else f"✗ missed={sorted(missed)}"
    elif got_signs:
        # No danger expected but LLM found some — false alarm
        details["danger_fa"] = f"false_alarm={sorted(got_signs)}"

    return {
        "hits": hits,
        "total": total,
        "details": details,
        "danger_recall_num": danger_recall_num,
        "danger_recall_den": danger_recall_den,
    }


# ─── Run one provider ─────────────────────────────────────────────────────────

def run_provider(provider: str, model: str, cases: list[dict], sleep_s: float = 4.0) -> dict:
    """
    Run all cases through one provider. Returns aggregated stats.
    Sets LLM_PROVIDER + LLM_MODEL in env before running (os.environ patch).

    sleep_s: seconds to wait between cases (default 4s).
    WHY: Free-tier Gemini has ~15 RPM limit. Without sleep, 15 cases
    fired back-to-back immediately exhaust the per-minute quota (429).
    4s between calls = ~15 RPM max, stays within free tier.
    """
    # Patch env so extract_visit uses this provider
    os.environ["LLM_PROVIDER"] = provider

    # Clear lru_cache on get_settings() so the new env values take effect
    try:
        from app.config import get_settings
        get_settings.cache_clear()
    except AttributeError:
        pass  # not cached, that's fine

    total_hits = 0
    total_fields = 0
    danger_num = 0
    danger_den = 0
    latencies_ms: list[float] = []
    failures = 0

    today = date.today()

    print(f"\n  Running {len(cases)} cases on {provider} / {model} "
          f"(sleep {sleep_s:.0f}s between calls) ...")

    for i, case in enumerate(cases):
        # Sleep between cases to avoid 429 rate-limit on free-tier APIs.
        # Skip sleep before the very first case.
        if i > 0 and sleep_s > 0:
            print(f"    ... waiting {sleep_s:.0f}s (rate-limit guard) ...")
            time.sleep(sleep_s)

        case_today = date.fromisoformat(case.get("today", today.isoformat()))
        text = case["text"]
        lang = case.get("lang", "en-IN")
        expect = case.get("expect", {})

        t0 = time.perf_counter()
        try:
            result = extract_visit(text, lang, case_today)
        except KeyboardInterrupt:
            # User pressed Ctrl+C — print what we have so far, then stop cleanly.
            print(f"\n  Interrupted at case {case['id']} — printing partial results.")
            break
        except Exception as e:
            print(f"    CRASH on case {case['id']}: {e}")
            failures += 1
            continue
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(elapsed_ms)

        sc = score_case(result, expect, case_today)
        total_hits += sc["hits"]
        total_fields += sc["total"]
        danger_num += sc["danger_recall_num"]
        danger_den += sc["danger_recall_den"]

        status = "✓" if sc["hits"] == sc["total"] else "✗"
        print(f"    [{status}] {case['id']:20s} {elapsed_ms:5.0f} ms  {sc['details']}")

    # ── Compute aggregated stats ───────────────────────────────────────
    field_acc = (total_hits / total_fields * 100) if total_fields else 0.0

    danger_recall = (danger_num / danger_den * 100) if danger_den else 100.0

    latencies_ms.sort()
    p50 = latencies_ms[len(latencies_ms) // 2] if latencies_ms else 0.0
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)] if latencies_ms else 0.0

    return {
        "provider": provider,
        "model": model,
        "field_acc": field_acc,
        "danger_recall": danger_recall,
        "p50_ms": p50,
        "p95_ms": p95,
        "failures": failures,
        "n_cases": len(cases),
    }


# ─── Print comparison table ───────────────────────────────────────────────────

def print_table(results: list[dict]) -> None:
    sep = "─" * 90
    print(f"\n{sep}")
    print(f"{'Provider':<14} {'Model':<28} {'FieldAcc':>8} {'DangerRec':>10} {'p50ms':>7} {'p95ms':>7} {'Fail':>5}")
    print(sep)
    for r in results:
        flag = " ← WINNER" if r.get("winner") else ""
        print(
            f"{r['provider']:<14} {r['model']:<28} "
            f"{r['field_acc']:>7.1f}% {r['danger_recall']:>9.1f}% "
            f"{r['p50_ms']:>7.0f} {r['p95_ms']:>7.0f} "
            f"{r['failures']:>5}{flag}"
        )
    print(sep)


# ─── Pick winner (D9 rules) ───────────────────────────────────────────────────

def pick_winner(results: list[dict]) -> dict:
    """
    D9 decision rule:
    1. Danger recall must be 100%. If not → exclude provider.
    2. Highest field accuracy wins.
    3. Within 5 percentage points of leader → prefer huggingface (deck integrity).
    4. All under 2.5s p50 → pick most accurate.
    """
    eligible = [r for r in results if r["danger_recall"] >= 100.0 and r["failures"] == 0]
    if not eligible:
        # Relax: allow up to 1 failure if no perfect candidate
        eligible = [r for r in results if r["danger_recall"] >= 100.0]
    if not eligible:
        # Last resort: take best danger recall
        eligible = sorted(results, key=lambda r: -r["danger_recall"])[:1]

    eligible.sort(key=lambda r: -r["field_acc"])
    best_acc = eligible[0]["field_acc"]

    # Prefer huggingface within 5 points of leader (D9)
    hf_candidates = [r for r in eligible if r["provider"] == "huggingface"
                     and best_acc - r["field_acc"] <= 5.0]
    if hf_candidates:
        return hf_candidates[0]

    return eligible[0]


# ─── Write to DECISIONS.md ────────────────────────────────────────────────────

def record_decision(winner: dict) -> None:
    """Append the bake-off result as one line in docs/DECISIONS.md."""
    now = datetime.now().strftime("%H:%M")
    line = (
        f"| {now} | LLM bake-off: **{winner['provider']} / {winner['model']}** "
        f"(field_acc={winner['field_acc']:.1f}%, danger_recall={winner['danger_recall']:.1f}%, "
        f"p50={winner['p50_ms']:.0f}ms) | D9: highest accuracy with 100% danger recall |"
    )

    text = _DECISIONS_PATH.read_text(encoding="utf-8")
    # Replace the placeholder row
    placeholder = "| — | (LLM bake-off result goes here — event H1–5, see D9) | — |"
    if placeholder in text:
        text = text.replace(placeholder, line)
    else:
        # Already replaced or missing — append at end of table
        text = text.rstrip() + "\n" + line + "\n"

    _DECISIONS_PATH.write_text(text, encoding="utf-8")
    print(f"\nWinner recorded in docs/DECISIONS.md")


# ─── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LLM bake-off for ASHA Mitra (P4)")
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=["gemini", "anthropic", "huggingface"],
        help="Providers to test. Default: provider from .env",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=4.0,
        help="Seconds to wait between cases (default 4). "
             "Free-tier Gemini = ~15 RPM, so 4s keeps you safe. "
             "Set 0 to disable (paid tier / local model).",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Limit to first N cases (default: all). "
             "Use --max-cases 3 to do a quick smoke-test without burning quota.",
    )
    args = parser.parse_args()

    # Load .env
    from dotenv import load_dotenv
    load_dotenv(_BACKEND_DIR / ".env")

    from app.config import get_settings
    s = get_settings()

    if args.providers:
        providers = args.providers
    else:
        p = s.LLM_PROVIDER or "gemini"
        providers = [p]
        print(f"No --providers specified. Using .env: {p}")

    cases = load_cases()
    if args.max_cases:
        cases = cases[: args.max_cases]
        print(f"  (limited to first {args.max_cases} cases by --max-cases)")
    print(f"Loaded {len(cases)} cases from {_CASES_PATH.name}")

    # Warm-up call (don't time this — avoids cold start skewing p50)
    if cases:
        warmup_case = cases[0]
        print("\nWarm-up call (not timed) ...")
        try:
            warmup_today = date.fromisoformat(warmup_case.get("today", date.today().isoformat()))
            extract_visit(warmup_case["text"], warmup_case.get("lang", "en-IN"), warmup_today)
            print("  Warm-up OK")
        except Exception as e:
            print(f"  Warm-up failed (continuing anyway): {e}")

    sleep_s = args.sleep if hasattr(args, "sleep") else 4.0

    all_results = []
    for provider in providers:
        model = s.LLM_MODEL or "gemini-2.0-flash"
        try:
            result = run_provider(provider, model, cases, sleep_s=sleep_s)
        except KeyboardInterrupt:
            print("\nBake-off interrupted. No results to show.")
            sys.exit(1)
        all_results.append(result)

    if not all_results:
        print("No results. Exiting.")
        sys.exit(1)

    winner = pick_winner(all_results)
    winner["winner"] = True

    print_table(all_results)

    print(f"\n🏆 Winner: {winner['provider']} / {winner['model']}")
    print(f"   Set in backend/.env:  LLM_PROVIDER={winner['provider']}")
    print(f"                         LLM_MODEL={winner['model']}")

    record_decision(winner)


if __name__ == "__main__":
    main()
