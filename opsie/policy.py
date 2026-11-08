"""Single source of confirmed business facts and configured thresholds."""
import hashlib
import json
from .db import ROOT


def load():
    raw = (ROOT / "knowledge" / "business_policy.json").read_bytes()
    doc = json.loads(raw)
    doc["runtime_version"] = hashlib.sha256(raw).hexdigest()[:16]
    return doc


def confirmed_facts(policy):
    return {key: item["value"] for key, item in policy["policies"].items()
            if item.get("status") == "confirmed" and item.get("value") is not None}
