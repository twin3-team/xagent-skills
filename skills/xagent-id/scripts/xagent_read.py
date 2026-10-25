import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description="Read public xAgent ID APIs without credentials or writes")
    parser.add_argument("command", choices=["health", "pricing", "billing", "card", "company", "install-status", "checkout-link"])
    parser.add_argument("--registration-id")
    parser.add_argument("--domain")
    parser.add_argument("--plan")
    parser.add_argument("--source")
    args = parser.parse_args()
    if args.command == "company":
        if not re.fullmatch(r"[0-9]{8}", args.registration_id or ""):
            parser.error("company requires an eight-digit --registration-id")
    elif args.registration_id is not None:
        parser.error("--registration-id is only valid for company")
    if args.command in ("card", "checkout-link"):
        domain = (args.domain or "").lower()
        labels = domain.split(".")
        if len(domain) > 253 or len(labels) < 2 or all(label.isdigit() for label in labels) or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
            parser.error(args.command + " requires a DNS hostname in --domain, without a URL, port or path")
    elif args.domain is not None:
        parser.error("--domain is only valid for card and checkout-link")
    if args.command == "checkout-link":
        if not re.fullmatch(r"[a-z]{1,32}", args.plan or ""):
            parser.error("checkout-link requires --plan with a plan id from pricing")
        if args.source is not None and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", args.source):
            parser.error("--source must be a short lowercase client name such as claude-code")
    elif args.plan is not None or args.source is not None:
        parser.error("--plan and --source are only valid for checkout-link")
    routes = {
        "health": "/agent/health.json",
        "pricing": "/api/agent/pricing",
        "billing": "/api/agent/billing_guide",
        "company": "/api/company-card/resolve",
        "card": "/" + (args.domain or "").lower() + ".json",
        "install-status": "/agent/mcp.json",
        "checkout-link": "/api/agent/pricing",
    }
    path = routes[args.command]
    if args.command == "company":
        path += "?" + urllib.parse.urlencode({"registration_id": args.registration_id})
    request = urllib.request.Request("https://xagent.id" + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            raw = response.read(2097153)
            if len(raw) > 2097152:
                raise ValueError("response exceeds 2 MiB")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("expected a JSON object")
    except urllib.error.HTTPError as error:
        error.close()
        print(json.dumps({"ok": False, "http_status": error.code}), file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        print(json.dumps({"ok": False, "error": "request_or_response_failed"}), file=sys.stderr)
        return 1
    if args.command == "install-status":
        result = {key: result.get(key) for key in ("release", "invocation")}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        release = result.get("release")
        invocation = result.get("invocation")
        ready = isinstance(release, dict) and release.get("ready") is True and bool(release.get("version"))
        configured = isinstance(invocation, dict) and invocation.get("status") != "release_not_ready" and isinstance(invocation.get("mcp_servers"), dict) and bool(invocation["mcp_servers"].get("xagent-id"))
        return 0 if ready and configured else 2
    if args.command == "checkout-link":
        return checkout_link(result, args.domain.lower(), args.plan, args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def checkout_link(pricing, domain, plan_id, source):
    sellable = pricing.get("sellable_plan_ids")
    plans = pricing.get("plans")
    plan = next((item for item in plans if isinstance(item, dict) and item.get("id") == plan_id), None) if isinstance(plans, list) else None
    if not isinstance(sellable, list) or plan_id not in sellable or plan is None:
        print(json.dumps({"ok": False, "error": "plan_not_sellable", "plan": plan_id, "sellable_plan_ids": sellable if isinstance(sellable, list) else []}), file=sys.stderr)
        return 2
    query = {"host": domain, "plan": plan_id, "src": "skill-" + (source or "unknown")}
    print(json.dumps({
        "ok": True,
        "domain": domain,
        "plan": plan_id,
        "plan_name": plan.get("name"),
        "price": plan.get("price"),
        "currency": pricing.get("currency"),
        "billing_period": pricing.get("billing_period"),
        "checkout_url": "https://xagent.id/claim?" + urllib.parse.urlencode(query),
        "buyer_steps": [
            "Open checkout_url in a browser",
            "Prove control of the domain with a mailbox at that domain or a DNS record",
            "Pay in Stripe Checkout",
        ],
        "not_done": ["no_claim_started", "no_payment_made", "no_entitlement_granted"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
