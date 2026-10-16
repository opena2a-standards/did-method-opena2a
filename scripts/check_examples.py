#!/usr/bin/env python3
"""Check the DID Documents under examples/ against the 0.2 shape.

examples/ holds one document per resource type the reference deployment
serves, plus the registry self-DID. examples/conformance/ holds identifiers
that the conformance suites carry and the deployment does not serve. Offline,
this checks the file set, the 0.2 shape (Section 5) and the service endpoint
encoding the deployment emits. `--live` also resolves each DID against the
reference deployment. A top-level document must answer 200 with the same
`id` and `service`, and its keys must have the layout the Implementation
status notes of Sections 5.1 and 5.3 record for the deployment, each
registry-controlled Ed25519 key carrying the registry's `#signing-key` value.
A conformance document must answer 404. python3 standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
CONFORMANCE = EXAMPLES / "conformance"
RESOURCE_TYPES = ROOT / "registries" / "resource-types.json"
BASE = "https://api.oa2a.org"
REGISTRY_DID = "did:opena2a:registry:opena2a.org"
CONTEXT = ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/suites/ed25519-2020/v1"]
# Registered types the reference deployment resolves (measured 2026-10-11;
# authority and publisher DIDs answer 404).
SERVED = ("agent", "mcp_server", "ai_tool", "llm", "skill")
# The deployment catalogues agents under the deprecated alias a2a_agent
# (Section 3.2) and puts that type in trust-lookup and badge URLs; its trust
# lookup answers 404 for type=agent.
CATALOG_TYPE = {"agent": "a2a_agent"}
DID_RE = re.compile(r"^did:opena2a:([a-z][a-z_]*):([A-Za-z0-9._/@:-]+)$")
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ED25519 = "Ed25519VerificationKey2020"
JWK_CONTEXT = "https://w3id.org/security/jwk/v1"


def deployment_keys(did: str) -> dict:
    """The key layout the reference deployment serves for `did`, as key_layout() reads it.

    Spec Section 5.1 (Implementation status) records the resource layout: one
    registry key, under both relationships. Section 5.3 records the registry
    layout: #signing-key and #key-v1 with the same Ed25519 key material,
    #pqc-v1 an ML-DSA-65 JsonWebKey, the jwk/v1 context, #signing-key alone
    under authentication and all three under assertionMethod.
    """
    if did == REGISTRY_DID:
        return {
            "@context": CONTEXT + [JWK_CONTEXT],
            "verificationMethod": [
                ("#signing-key", ED25519, did),
                ("#key-v1", ED25519, did),
                ("#pqc-v1", "JsonWebKey", did, "AKP", "ML-DSA-65"),
            ],
            "authentication": ["#signing-key"],
            "assertionMethod": ["#signing-key", "#key-v1", "#pqc-v1"],
        }
    return {
        "@context": CONTEXT,
        "verificationMethod": [("#registry-key", ED25519, REGISTRY_DID)],
        "authentication": ["#registry-key"],
        "assertionMethod": ["#registry-key"],
    }


def key_layout(doc: dict) -> dict:
    """The contexts, each verification method's fragment, type and controller
    (and a JWK's kty and alg), and each relationship's fragments; no key values."""
    did = doc.get("id", "")

    def fragment(ref):
        return ref[len(did):] if isinstance(ref, str) and ref.startswith(did + "#") else ref

    def entry(vm):
        if not isinstance(vm, dict):
            return vm
        found = (fragment(vm.get("id")), vm.get("type"), vm.get("controller"))
        jwk = vm.get("publicKeyJwk")
        return found + (jwk.get("kty"), jwk.get("alg")) if isinstance(jwk, dict) else found

    def each(field, read):
        value = doc.get(field, [])
        return [read(v) for v in value] if isinstance(value, list) else value

    return {
        "@context": doc.get("@context"),
        "verificationMethod": each("verificationMethod", entry),
        "authentication": each("authentication", fragment),
        "assertionMethod": each("assertionMethod", fragment),
    }


def describe(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(describe(v) for v in value) + "]"
    if isinstance(value, tuple):
        return " ".join(str(v) for v in value)
    return str(value)


def check_live_keys(name: str, live: dict) -> list:
    did = live.get("id", "")
    section = "5.3" if did == REGISTRY_DID else "5.1"
    got, want = key_layout(live), deployment_keys(did)
    return [f"{name}: live {field} {describe(got[field])} differs from the layout spec Section {section} "
            f"records for the deployment, {describe(want[field])}"
            for field in want if got[field] != want[field]]


def check_live_key_values(live_docs: list) -> list:
    """Each registry-controlled Ed25519 key must carry the registry's #signing-key value.

    A verificationMethod that is not a list of objects is left to check_live_keys.
    """
    def methods(doc):
        value = doc.get("verificationMethod", [])
        return [vm for vm in value if isinstance(vm, dict)] if isinstance(value, list) else []

    registry = next((live for _, live in live_docs if live.get("id") == REGISTRY_DID), None)
    if registry is None:
        return []
    signing_id = f"{REGISTRY_DID}#signing-key"
    signing = next((vm.get("publicKeyMultibase") for vm in methods(registry) if vm.get("id") == signing_id), None)
    if not signing:
        return []
    problems = []
    for name, live in live_docs:
        section = "5.3" if live.get("id") == REGISTRY_DID else "5.1"
        for vm in methods(live):
            if vm.get("id") == signing_id:
                continue
            if vm.get("controller") == REGISTRY_DID and vm.get("type") == ED25519 \
                    and vm.get("publicKeyMultibase") != signing:
                problems.append(f"{name}: {vm.get('id')} does not carry the key {signing_id} carries "
                                f"(spec Section {section})")
    return problems


def service_endpoints(did: str, rtype: str, rid: str) -> list:
    # Query values are fully escaped; the badge path segment keeps "@" and ":"
    # and escapes "/", as the deployment emits them.
    return [
        {"id": f"{did}#trust-lookup", "type": "TrustLookup",
         "serviceEndpoint": f"{BASE}/api/v1/trust/query?name={quote(rid, safe='')}&type={rtype}"},
        {"id": f"{did}#trust-proof", "type": "TrustProof",
         "serviceEndpoint": f"{BASE}/api/v1/trust/proof?did={quote(did, safe='')}"},
        {"id": f"{did}#badge", "type": "TrustBadge",
         "serviceEndpoint": f"{BASE}/badge/{rtype}/{quote(rid, safe='@:')}"},
    ]


def check_doc(name: str, doc: dict, registered: set, expect_type: str | None, served: bool) -> list:
    problems = []
    did = doc.get("id", "")
    m = DID_RE.match(did)
    if not m:
        return [f"{name}: id {did!r} is not a did:opena2a DID (Section 3.1)"]
    rtype, rid = m.groups()
    if expect_type and rtype != expect_type:
        problems.append(f"{name}: id {did} has resource type {rtype}, expected {expect_type}")
    if rtype not in registered:
        problems.append(f"{name}: resource type {rtype} is not registered (Section 3.2)")
    if doc.get("@context") != CONTEXT:
        problems.append(f"{name}: @context differs from the Section 5 contexts")
    for field in ("created", "updated"):
        if not TIME_RE.match(str(doc.get(field, ""))):
            problems.append(f"{name}: {field} is not an RFC 3339 UTC timestamp")

    vms = {}
    for vm in doc.get("verificationMethod", []):
        vid = vm.get("id", "")
        vms[vid] = vm
        if not vid.startswith(did + "#"):
            problems.append(f"{name}: verification method {vid} is not a fragment of {did}")
        if vm.get("type") != "Ed25519VerificationKey2020":
            problems.append(f"{name}: {vid} type is {vm.get('type')}, expected Ed25519VerificationKey2020")
        if not str(vm.get("publicKeyMultibase", "")).startswith("z6Mk"):
            problems.append(f"{name}: {vid} publicKeyMultibase does not begin z6Mk (Section 5.1)")
    auth = doc.get("authentication", [])
    assertion = doc.get("assertionMethod", [])

    if rtype == "registry":
        key = f"{did}#signing-key"
        if list(vms) != [key] or vms[key].get("controller") != did:
            problems.append(f"{name}: expected one key {key} controlled by {did} (Section 5.3)")
        if auth != [key] or assertion != [key]:
            problems.append(f"{name}: {key} must be the only authentication and assertionMethod entry")
        return problems

    key = f"{did}#registry-key"
    if assertion != [key] or vms.get(key, {}).get("controller") != REGISTRY_DID:
        problems.append(f"{name}: assertionMethod must list only {key}, controlled by {REGISTRY_DID}")
    for ref in auth:
        if ref == key or vms.get(ref, {}).get("controller") != did:
            problems.append(f"{name}: authentication entry {ref} is not a subject key controlled by {did}")
    for vid, vm in vms.items():
        if vid != key and vid not in auth:
            problems.append(f"{name}: verification method {vid} is under neither relationship")
    catalog = CATALOG_TYPE.get(rtype, rtype) if served else rtype
    if doc.get("service") != service_endpoints(did, catalog, rid):
        problems.append(f"{name}: service endpoints differ from the deployment's encoding")
    return problems


def resolve(did: str) -> tuple:
    """Return (status, document, error); error is set when no HTTP status was received.

    document is None when the body is not JSON (an HTML error page, for example).
    """
    req = urllib.request.Request(f"{BASE}/api/v1/did/{did}",
                                 headers={"User-Agent": "did-method-opena2a/check-examples"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            try:
                document = json.load(resp)
            except ValueError:
                # JSONDecodeError, and UnicodeDecodeError for a body that is not UTF-8.
                document = None
            return resp.status, document, None
    except urllib.error.HTTPError as err:
        # The error is also the response; close it so its body is released.
        err.close()
        return err.code, None, None
    except OSError as err:
        # URLError (DNS failure, refused connection), TimeoutError and other
        # socket errors: report the reason instead of a traceback.
        return None, None, f"request failed: {getattr(err, 'reason', err)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="also resolve each DID against the reference deployment")
    args = ap.parse_args()
    registered = {row["Resource type"] for row in json.loads(RESOURCE_TYPES.read_text(encoding="utf-8"))["rows"]}
    problems = []

    want = {f"{t}.json" for t in ("registry",) + SERVED}
    have = {p.name for p in EXAMPLES.glob("*.json")}
    for missing in sorted(want - have):
        problems.append(f"examples/{missing}: missing (one example per served resource type)")
    for extra in sorted(have - want):
        problems.append(f"examples/{extra}: not a served resource type; move it to examples/conformance/")

    docs = []
    for path in sorted(EXAMPLES.glob("*.json")):
        docs.append((path, json.loads(path.read_text(encoding="utf-8")), True))
    for path in sorted(CONFORMANCE.glob("*.json")):
        docs.append((path, json.loads(path.read_text(encoding="utf-8")), False))
    for path, doc, served in docs:
        name = str(path.relative_to(ROOT))
        problems += check_doc(name, doc, registered, path.stem if served else None, served)

    if args.live:
        live_docs = []
        for path, doc, served in docs:
            name = str(path.relative_to(ROOT))
            status, live, error = resolve(doc["id"])
            if error:
                problems.append(f"{name}: {doc['id']}: {error}")
                continue
            if not served:
                if status != 404:
                    problems.append(f"{name}: {doc['id']} answered {status}; it is served, move it to examples/")
                continue
            if status != 200:
                problems.append(f"{name}: {doc['id']} answered {status}, expected 200")
            elif not isinstance(live, dict):
                problems.append(f"{name}: {doc['id']} answered 200 with a body that is not a JSON object")
            elif live.get("id") != doc["id"]:
                problems.append(f"{name}: resolved id {live.get('id')} differs from {doc['id']}")
            else:
                if live.get("service") != doc.get("service"):
                    problems.append(f"{name}: service endpoints differ from the live document")
                problems += check_live_keys(name, live)
                live_docs.append((name, live))
        problems += check_live_key_values(live_docs)

    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        return 1
    served_n = sum(1 for _, _, s in docs if s)
    print(f"examples match: {served_n} served, {len(docs) - served_n} conformance"
          + (", resolved against the reference deployment" if args.live else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
