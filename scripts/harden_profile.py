#!/usr/bin/env python3
"""Apply the hardened privacy / approval profile to this Hermes install.

Every key below is one Hermes already supports; this script only pins each one to its
most conservative value and writes it EXPLICITLY into your config. Writing it explicitly
is the point: if a later release loosens one of these defaults, your install stays where
you put it instead of silently following.

Two properties matter here, so the script keeps them:

* **Nothing changes without you.** It is a dry run by default and only prints what it
  would change. ``--apply`` is required to write anything.
* **Your config file stays yours.** Values are written through ``set_config_value`` — the
  same function behind ``hermes config set`` — so the comment-preserving config backend
  is used and comments and unrelated keys are untouched.

Usage:
    python scripts/harden_profile.py            # show current → hardened (no writes)
    python scripts/harden_profile.py --apply    # write the settings
    python scripts/harden_profile.py --apply --only approvals,telemetry
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# (dotted key, hardened value, section, why)
SETTINGS: list[tuple[str, object, str, str]] = [
    (
        "approvals.mode",
        "manual",
        "approvals",
        "smart mode lets a guardian model approve or deny risky commands; manual makes "
        "every one of them your decision",
    ),
    ("approvals.cron_mode", "deny", "approvals", "no human is present in a cron run: deny, never approve"),
    (
        "approvals.single_query_mode",
        "deny",
        "approvals",
        "hermes -q has nobody to answer an approval prompt: deny, never approve",
    ),
    (
        "approvals.unattended_mode",
        "deny",
        "approvals",
        "unattended platforms (cron, relays) deny instead of waiting out the timeout",
    ),
    (
        "memory.write_approval",
        True,
        "approvals",
        "the agent never rewrites MEMORY.md / USER.md without you",
    ),
    (
        "skills.write_approval",
        True,
        "approvals",
        "the agent never creates or edits a SKILL.md without you",
    ),
    (
        "delegation.subagent_auto_approve",
        False,
        "approvals",
        "subagents auto-deny risky commands instead of auto-approving them",
    ),
    (
        "telemetry.shared_metrics.enabled",
        False,
        "privacy",
        "no local collection of usage metrics",
    ),
    (
        "telemetry.shared_metrics.send",
        False,
        "privacy",
        "no metrics upload (the only Hermes-operated ingest endpoint)",
    ),
    (
        "updates.check",
        False,
        "privacy",
        "passive update checks reach out to GitHub on every start; run "
        "`hermes update --check` yourself instead",
    ),
    (
        "plugins.auto_apply",
        False,
        "supply-chain",
        "plugin updates are applied only when you ask, never on a background tick",
    ),
    (
        "security.protected_instruction_files",
        True,
        "prompt-injection",
        "writes to AGENTS.md / CLAUDE.md / SOUL.md always ask, even under --yolo",
    ),
    (
        "security.allow_private_urls",
        False,
        "network",
        "web/vision/media fetches may not reach private or internal addresses",
    ),
    ("security.redact_secrets", True, "privacy", "secrets are redacted from output"),
    (
        "security.redact_phone_numbers",
        True,
        "privacy",
        "phone numbers are redacted from output",
    ),
]

SECTIONS = ("approvals", "privacy", "supply-chain", "prompt-injection", "network")


def _load_current() -> dict[str, object]:
    """Effective values for the dotted keys, read through the project's own loader."""
    from hermes_cli.config import cfg_get, load_config

    cfg = load_config()
    return {".".join(path): cfg_get(cfg, *path, default="(unset)") for path in
            (key.split(".") for key, _, _, _ in SETTINGS)}


def _yaml_literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _apply(key: str, value: object) -> None:
    """Write one key through the CLI's own setter (comment-preserving, schema-validated)."""
    from hermes_cli.config import set_config_value

    set_config_value(key, _yaml_literal(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the settings (default: dry run)")
    parser.add_argument(
        "--only",
        default="",
        help=f"comma-separated sections to include ({', '.join(SECTIONS)}); default all",
    )
    args = parser.parse_args(argv)

    wanted = {s.strip() for s in args.only.split(",") if s.strip()} or set(SECTIONS)
    unknown = wanted - set(SECTIONS)
    if unknown:
        parser.error(f"unknown section(s): {', '.join(sorted(unknown))}")

    selected = [row for row in SETTINGS if row[2] in wanted]
    current = _load_current()

    changes = []
    for key, target, section, why in selected:
        now = current.get(key, "(unset)")
        if now == target:
            print(f"  ok      {key} = {_yaml_literal(target)}")
            continue
        changes.append((key, target, now, why))
        print(f"  CHANGE  {key}: {now} → {_yaml_literal(target)}   ({why})")

    if not changes:
        print("\nAlready hardened — nothing to write.")
        return 0

    if not args.apply:
        print(f"\n{len(changes)} change(s) pending. Dry run — nothing written. Re-run with --apply.")
        return 0

    print()
    for key, target, _now, _why in changes:
        _apply(key, target)
        print(f"  wrote   {key} = {_yaml_literal(target)}")

    after = _load_current()
    missed = [key for key, target, _n, _w in changes if after.get(key) != target]
    if missed:
        print(f"\nNot applied: {', '.join(missed)}")
        return 1
    print(f"\n{len(changes)} setting(s) written and read back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
