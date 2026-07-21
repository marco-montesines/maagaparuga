#!/usr/bin/env python3
"""cost-guard — FinOps guardrail for MaagapAruga's OpenTofu/Terraform plans.

Subcommands:
  refresh   Fetch live Hetzner Cloud prices (requires HCLOUD_TOKEN) into prices.json.
  check     Price a plan JSON against infra/budget.json; non-zero exit on breach.

The check runs offline from the committed prices.json snapshot, so pull-request
pipelines need no cloud credentials (FinOps "Operate" without widening access).

Typical pipeline wiring:
  terragrunt plan -out=tf.plan && terragrunt show -json tf.plan > plan.json
  python3 tools/cost-guard/cost_guard.py check --plan plan.json --env staging
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRICES_FILE = HERE / "prices.json"
BUDGET_FILE = HERE.parent.parent / "infra" / "budget.json"
HETZNER_PRICING_URL = "https://api.hetzner.cloud/v1/pricing"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        sys.exit(f"cost-guard: missing {path} — run the 'refresh' subcommand first")
    except json.JSONDecodeError as exc:
        sys.exit(f"cost-guard: {path} is not valid JSON: {exc}")


def refresh(args: argparse.Namespace) -> int:
    token = os.environ.get("HCLOUD_TOKEN")
    if not token:
        sys.exit("cost-guard: refresh needs the HCLOUD_TOKEN environment variable")

    req = urllib.request.Request(
        HETZNER_PRICING_URL, headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        pricing = json.load(resp)["pricing"]

    # Keep only what the plan checker prices; monthly gross covers the whole VAT story.
    snapshot = {
        "snapshot_date": args.date,
        "currency": pricing["currency"],
        "server_types": {
            st["name"]: float(st["prices"][0]["price_monthly"]["gross"])
            for st in pricing["server_types"]
            if st.get("prices")
        },
        "volume_per_gb_month": float(pricing["volume"]["price_per_gb_month"]["gross"]),
        "primary_ip_month": float(
            pricing["primary_ips"][0]["prices"][0]["price_monthly"]["gross"]
        )
        if pricing.get("primary_ips")
        else 0.0,
    }
    PRICES_FILE.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(f"cost-guard: wrote {PRICES_FILE} ({len(snapshot['server_types'])} server types)")
    return 0


def planned_resources(plan: dict) -> list[dict]:
    """Resources the plan will create or keep (deletes don't cost anything)."""
    keep = []
    for rc in plan.get("resource_changes", []):
        actions = rc.get("change", {}).get("actions", [])
        if actions in (["create"], ["update"], ["no-op"]) or actions == ["create", "delete"]:
            keep.append(rc)
        elif actions == ["delete", "create"]:  # replacement still exists afterwards
            keep.append(rc)
    return keep


def check(args: argparse.Namespace) -> int:
    prices = load_json(Path(args.prices))
    budget = load_json(Path(args.budget))
    plan = load_json(Path(args.plan))

    env_budget = budget["monthly_budget"].get(args.env)
    if env_budget is None:
        sys.exit(f"cost-guard: no monthly_budget entry for environment '{args.env}'")

    allowed_types = set(budget.get("allowed_server_types", []))
    required_labels = budget.get("required_labels", [])
    warn_pct = float(budget.get("warn_at_percent", 80))

    lines: list[tuple[str, float]] = []
    violations: list[str] = []
    total = 0.0

    for rc in planned_resources(plan):
        values = rc.get("change", {}).get("after") or {}
        addr = rc.get("address", rc.get("type", "?"))

        if rc.get("type") == "hcloud_server":
            labels = values.get("labels") or {}
            missing = [lb for lb in required_labels if not labels.get(lb)]
            if missing:
                violations.append(
                    f"{addr}: missing required cost-attribution labels {missing}"
                )
            server_type = values.get("server_type", "?")
            if allowed_types and server_type not in allowed_types:
                violations.append(
                    f"{addr}: server_type '{server_type}' is not in "
                    f"allowed_server_types {sorted(allowed_types)}"
                )
            price = prices["server_types"].get(server_type)
            if price is None:
                violations.append(
                    f"{addr}: no price known for server_type '{server_type}' "
                    f"— run 'refresh'"
                )
                continue
            lines.append((f"{addr} ({server_type})", price))
            total += price

        elif rc.get("type") == "hcloud_volume":
            size = float(values.get("size", 0))
            price = size * prices["volume_per_gb_month"]
            lines.append((f"{addr} ({size:g} GB volume)", price))
            total += price

        elif rc.get("type") == "hcloud_primary_ip":
            price = prices.get("primary_ip_month", 0.0)
            lines.append((f"{addr} (primary IP)", price))
            total += price

    currency = prices.get("currency", budget.get("currency", "EUR"))
    print(f"cost-guard: projected monthly cost for '{args.env}'")
    for label, price in lines:
        print(f"  {label:<58} {price:>8.2f} {currency}")
    print(f"  {'TOTAL':<58} {total:>8.2f} {currency}  (budget {env_budget:.2f})")

    status = 0
    if violations:
        for v in violations:
            print(f"::error::cost-guard: {v}")
        status = 1
    if total > env_budget:
        print(
            f"::error::cost-guard: projected {total:.2f} {currency}/month exceeds the "
            f"'{args.env}' budget of {env_budget:.2f} — plan blocked"
        )
        status = 1
    elif total > env_budget * warn_pct / 100:
        print(
            f"::warning::cost-guard: projected {total:.2f} {currency}/month is above "
            f"{warn_pct:.0f}% of the '{args.env}' budget ({env_budget:.2f})"
        )
    else:
        print("cost-guard: within budget")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(prog="cost-guard", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_refresh = sub.add_parser("refresh", help="fetch live Hetzner prices into prices.json")
    p_refresh.add_argument("--date", default="", help="snapshot label, e.g. 2026-07-20")
    p_refresh.set_defaults(func=refresh)

    p_check = sub.add_parser("check", help="price a plan JSON against the budget")
    p_check.add_argument("--plan", required=True, help="output of: terragrunt show -json")
    p_check.add_argument("--env", required=True, help="environment key in budget.json")
    p_check.add_argument("--budget", default=str(BUDGET_FILE))
    p_check.add_argument("--prices", default=str(PRICES_FILE))
    p_check.set_defaults(func=check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
