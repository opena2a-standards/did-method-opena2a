#!/usr/bin/env python3
"""A did:opena2a resolver written from the specification (spec Section 8.6).

Its source is public, so a reader can see how a resolver carries out each
rule of the specification. It is not the registry source of Section 8.1 and
does not serve the reference deployment. It covers:

- parsing (Sections 3.1, 3.1.2 and 3.3): parse_did() reads the Section 3.1
  grammar, decodes the resource-id once and lowercases nothing; for an
  invalid DID it raises DidSyntaxError naming the defect;
- multibase (Section 5.1): ed25519_multibase() writes an Ed25519 public key
  as "z" followed by the base58btc encoding of the multicodec prefix 0xed01
  and the 32 key bytes, and ed25519_key() reads one back;
- document construction (Sections 5, 5.1, 5.1.1, 5.2 and 5.3):
  Registry.document() builds a resource's DID Document, the subject's keys
  under authentication and the registry's current key under assertionMethod,
  and Registry.registry_document() builds the registry's own;
- handlers (Sections 3.5, 4.2, 4.4 and 8.3): Registry.respond() answers an
  HTTP request with a status, headers and a body, and serve() answers HTTP.

Resolution. For GET /api/v1/did/<did>, the reference deployment's path
(Section 8.4), the resolver URL-decodes the path once, as a transport does,
and the decoding step of Section 3.1.2 follows. A registered DID is answered
200 with Content-Type
application/did+ld+json, Cache-Control public, max-age=300 and a DID
resolution result whose didDocumentMetadata names this registry under
issuingRegistry (Section 3.5). For a record whose status is suspended,
revoked or deprecated it also carries deactivated: true, and the document
lists no services (Section 4.4). A DID with no record, including a registry
DID other than this registry's own, is answered 404. An invalid DID, and a
DID carrying a fragment, whose document id could not equal the requested DID
(Section 4.2), are answered 400. Both error bodies are JSON naming the DID
and the reason, sent with Cache-Control no-store. HEAD gets the status and
headers of GET. GET /.well-known/opena2a returns a discovery document
(Section 8.3) with the members registryDid, supportedMethods, publicKeys and
endpoints.didResolve, named as in the reference deployment's discovery
document (read 2026-10-21). Each publicKeys entry carries algorithm, the key
as publicKey (base64, as the deployment writes it) and as publicKeyMultibase.

An a2a_agent DID, the deprecated alias of Section 3.2, is answered 400 like
any DID outside the Section 3.1 grammar, which admits no digit in a
resource-type.

Records. The registry and its records are read from a JSON file:

    {
      "authority": "registry.example",
      "baseUrl": "https://registry.example",
      "signingKeys": ["z6Mk..."],
      "created": "2026-02-15T00:00:00Z",
      "updated": "2026-09-08T00:00:00Z",
      "resources": [
        {
          "did": "did:opena2a:agent:agent_conformance_test_001",
          "subjectKeys": ["z6Mk..."],
          "status": "active",
          "created": "2026-04-12T00:00:00Z",
          "updated": "2026-09-08T00:00:00Z"
        }
      ]
    }

The registry names itself did:opena2a:registry:<authority> (Section 3.4).
signingKeys holds every currently valid registry key, the current one first;
the DID Documents carry the current one (Section 5.1). Service endpoints are
written under baseUrl, which must be an https URL (Section 6.2). resources,
subjectKeys and status are optional. Loading the file applies the rules of
Sections 3.4 and 4.1: each DID is in canonical form with no fragment, no two
records share a DID, and no record takes the registry's self-identifier.
Each key must be an Ed25519 publicKeyMultibase value.

resolve prints the reply to a resolution request for DID, which it takes as
a DID string rather than a URL path, so only the Section 3.1.2 step decodes
it, and exits 0 when the status is 200, 1 otherwise. serve answers HTTP on
127.0.0.1:8080 unless told otherwise (--port takes 0 to 65535); it serves
plain HTTP, and Section 6.2 requires TLS in front of it. Both exit 2 when
the records file does not load, and serve exits 2, after one line naming
the address and the reason, when it cannot listen on the address; a --host
holding a character other than visible ASCII appears there as Python's
ascii() of it. python3 standard library only.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import json
import re
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

PREFIX = "did:opena2a:"
# Section 3.1. ALPHA and DIGIT are US-ASCII ranges, so these sets are too.
ALPHA_LOWER = frozenset("abcdefghijklmnopqrstuvwxyz")
ALPHA = ALPHA_LOWER | frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
DIGIT = frozenset("0123456789")
HEXDIG = DIGIT | frozenset("ABCDEFabcdef")
UNRESERVED = ALPHA | DIGIT | frozenset("._-/@")
# The characters a resource-id holds unescaped, before and after decoding.
RESOURCE_ID = UNRESERVED | {":"}

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
# The multicodec code of ed25519-pub, 0xed, as an unsigned varint (Section 5.1).
ED25519_PUB = b"\xed\x01"
ED25519_KEY_BYTES = 32

CONTEXT = ("https://www.w3.org/ns/did/v1", "https://w3id.org/security/suites/ed25519-2020/v1")
KEY_TYPE = "Ed25519VerificationKey2020"
MEDIA_TYPE = "application/did+ld+json"
CACHE_CONTROL = "public, max-age=300"
# Section 4.4: a record in one of these statuses is deactivated.
DEACTIVATED = frozenset({"suspended", "revoked", "deprecated"})
RESOLVE_PATH = "/api/v1/did/"
DISCOVERY_PATH = "/.well-known/opena2a"
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
DNS_LABEL = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
AUTHORITY = re.compile(rf"{DNS_LABEL}(?:\.{DNS_LABEL})*")


class DidSyntaxError(ValueError):
    """A DID that does not conform to Section 3.1 or does not decode under Section 3.1.2."""


@dataclass(frozen=True)
class Did:
    """A parsed did:opena2a DID, its resource-id decoded (Section 3.1.2)."""

    resource_type: str
    resource_id: str
    fragment: str | None = None

    @property
    def did(self) -> str:
        """The canonical form of the DID, without a fragment."""
        return f"{PREFIX}{self.resource_type}:{self.resource_id}"

    @property
    def canonical(self) -> str:
        """The canonical form of the string parsed, its fragment included."""
        return self.did if self.fragment is None else f"{self.did}#{self.fragment}"


def parse_did(text: str) -> Did:
    """Parse a did:opena2a DID and decode its resource-id exactly once.

    Nothing is lowercased: the prefix and the resource-type are lowercase or
    the DID is invalid, and the resource-id keeps its case (Section 3.3).
    """
    if not text.startswith(PREFIX):
        raise DidSyntaxError("the DID does not begin with did:opena2a:, which is lowercase (Sections 2 and 3.3)")
    rtype, colon, tail = text[len(PREFIX):].partition(":")
    if not colon:
        raise DidSyntaxError("no ':' separates a resource-type from a resource-id (Section 3.1)")
    if not rtype or rtype[0] not in ALPHA_LOWER or not set(rtype) <= ALPHA_LOWER | {"_"}:
        raise DidSyntaxError(f"the resource-type {rtype!r} is not a lowercase letter followed by "
                             "lowercase letters and underscores (Section 3.1)")
    rid, hash_mark, fragment = tail.partition("#")
    if hash_mark and (not fragment or not set(fragment) <= UNRESERVED):
        raise DidSyntaxError("the fragment is empty or holds a character outside unreserved (Section 3.1)")
    if not rid:
        raise DidSyntaxError("the resource-id is empty (Section 3.1)")
    decoded = []
    i = 0
    while i < len(rid):
        ch = rid[i]
        if ch == "%":
            digits = rid[i + 1:i + 3]
            if len(digits) < 2 or not set(digits) <= HEXDIG:
                raise DidSyntaxError(f"the '%' at offset {i} of the resource-id is not followed by "
                                     "two hexadecimal digits (Section 3.1)")
            ch = chr(int(digits, 16))
            if ch not in RESOURCE_ID:
                raise DidSyntaxError(f"%{digits} in the resource-id decodes to a character the resource-id "
                                     "does not admit unescaped (Section 3.1.2)")
            i += 3
        elif ch in RESOURCE_ID:
            i += 1
        else:
            raise DidSyntaxError(f"the resource-id holds {ch!r} at offset {i}, which Section 3.1 does not admit")
        decoded.append(ch)
    return Did(rtype, "".join(decoded), fragment if hash_mark else None)


def base58btc_encode(data: bytes) -> str:
    """The base58btc encoding of `data`; each leading zero byte is written as "1"."""
    number = int.from_bytes(data, "big")
    digits = []
    while number:
        number, digit = divmod(number, 58)
        digits.append(BASE58_ALPHABET[digit])
    zeros = len(data) - len(data.lstrip(b"\0"))
    return "1" * zeros + "".join(reversed(digits))


def base58btc_decode(text: str) -> bytes:
    number = 0
    for ch in text:
        digit = BASE58_ALPHABET.find(ch)
        if digit < 0:
            raise ValueError(f"{ch!r} is not a base58btc character")
        number = number * 58 + digit
    zeros = len(text) - len(text.lstrip("1"))
    return b"\0" * zeros + number.to_bytes((number.bit_length() + 7) // 8, "big")


def ed25519_multibase(key: bytes) -> str:
    """The publicKeyMultibase value of an Ed25519 public key (Section 5.1), the z6Mk... form."""
    if len(key) != ED25519_KEY_BYTES:
        raise ValueError(f"an Ed25519 public key is {ED25519_KEY_BYTES} bytes, not {len(key)}")
    return "z" + base58btc_encode(ED25519_PUB + key)


def ed25519_key(value: str) -> bytes:
    """The 32 key bytes of an Ed25519 publicKeyMultibase value (Section 5.1)."""
    if not isinstance(value, str) or not value.startswith("z"):
        raise ValueError("an Ed25519 publicKeyMultibase value begins with z, the base58btc prefix (Section 5.1)")
    data = base58btc_decode(value[1:])
    if len(data) != len(ED25519_PUB) + ED25519_KEY_BYTES or not data.startswith(ED25519_PUB):
        raise ValueError("an Ed25519 publicKeyMultibase value holds the multicodec prefix 0xed01 "
                         "followed by 32 key bytes (Section 5.1)")
    return data[len(ED25519_PUB):]


def _members(obj, where: str, required: tuple, optional: tuple = ()) -> None:
    if not isinstance(obj, dict):
        raise ValueError(f"{where} is not a JSON object")
    unknown = sorted(set(obj) - set(required) - set(optional))
    if unknown:
        raise ValueError(f"{where}: unknown member {unknown[0]!r}")
    missing = [name for name in required if name not in obj]
    if missing:
        raise ValueError(f"{where}: missing member {missing[0]!r}")


def _timestamp(value, where: str) -> str:
    try:
        if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
            raise ValueError
        datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValueError(f"{where} is not a UTC time written as 2026-02-15T00:00:00Z") from None
    return value


def _keys(value, where: str, allow_empty: bool) -> tuple:
    if not isinstance(value, list) or not (value or allow_empty):
        raise ValueError(f"{where} is not a list of publicKeyMultibase values"
                         + ("" if allow_empty else " with one or more entries"))
    for n, key in enumerate(value):
        try:
            ed25519_key(key)
        except ValueError as exc:
            raise ValueError(f"{where}[{n}]: {exc}") from None
    if len(set(value)) != len(value):
        raise ValueError(f"{where} lists a key twice")
    return tuple(value)


@dataclass(frozen=True)
class Record:
    """One registered resource: its DID, its own keys and its status."""

    did: Did
    subject_keys: tuple
    status: str
    created: str
    updated: str

    @property
    def deactivated(self) -> bool:
        return self.status in DEACTIVATED

    @classmethod
    def from_json(cls, entry, where: str = "record") -> "Record":
        _members(entry, where, ("did", "created", "updated"), ("subjectKeys", "status"))
        text = entry["did"]
        if not isinstance(text, str):
            raise ValueError(f"{where}.did is not a string")
        try:
            did = parse_did(text)
        except DidSyntaxError as exc:
            raise ValueError(f"{where}.did: {exc}") from None
        if did.fragment is not None or did.did != text:
            raise ValueError(f"{where}.did is not in canonical form without a fragment (Sections 3.1.2 and 4.1)")
        status = entry.get("status", "active")
        if not isinstance(status, str) or not status:
            raise ValueError(f"{where}.status is not a non-empty string")
        return cls(did, _keys(entry.get("subjectKeys", []), f"{where}.subjectKeys", allow_empty=True), status,
                   _timestamp(entry["created"], f"{where}.created"), _timestamp(entry["updated"], f"{where}.updated"))


class Registry:
    """A registry's records and the replies a resolver gives for them. Build one with from_json()."""

    def __init__(self, authority: str, base_url: str, signing_keys: tuple, created: str, updated: str):
        self.did = f"{PREFIX}registry:{authority}"
        self.base_url = base_url
        self.signing_keys = signing_keys
        self.created = created
        self.updated = updated
        self.records: dict = {}

    @classmethod
    def from_json(cls, data) -> "Registry":
        _members(data, "records file", ("authority", "baseUrl", "signingKeys", "created", "updated"), ("resources",))
        authority = data["authority"]
        if not isinstance(authority, str) or not AUTHORITY.fullmatch(authority):
            raise ValueError("authority is not a lowercase DNS name (Section 3.4)")
        base_url = data["baseUrl"]
        if (not isinstance(base_url, str) or not re.fullmatch(r"https://[!-~]+", base_url)
                or "?" in base_url or "#" in base_url or not urlsplit(base_url).hostname):
            raise ValueError("baseUrl is not an https URL without a query or a fragment (Section 6.2)")
        registry = cls(authority, base_url.rstrip("/"), _keys(data["signingKeys"], "signingKeys", allow_empty=False),
                       _timestamp(data["created"], "created"), _timestamp(data["updated"], "updated"))
        resources = data.get("resources", [])
        if not isinstance(resources, list):
            raise ValueError("resources is not a list")
        for n, entry in enumerate(resources):
            registry.add(Record.from_json(entry, f"resources[{n}]"))
        return registry

    def add(self, record: Record) -> None:
        """Admit a record under the rules of Sections 3.4 and 4.1."""
        did = record.did.did
        if did == self.did:
            raise ValueError(f"{did} is the registry's self-identifier, which it assigns to no other resource "
                             "(Section 3.4)")
        if did in self.records:
            raise ValueError(f"{did} is registered twice (Section 4.1)")
        self.records[did] = record

    def services(self, did: Did) -> list:
        """The TrustLookup, TrustProof and TrustBadge endpoints of a resource (Section 5.2)."""
        rid, rtype = did.resource_id, did.resource_type
        return [
            {"id": f"{did.did}#trust-lookup", "type": "TrustLookup",
             "serviceEndpoint": f"{self.base_url}/api/v1/trust/query?name={quote(rid, safe='')}&type={rtype}"},
            {"id": f"{did.did}#trust-proof", "type": "TrustProof",
             "serviceEndpoint": f"{self.base_url}/api/v1/trust/proof?did={quote(did.did, safe='')}"},
            {"id": f"{did.did}#badge", "type": "TrustBadge",
             "serviceEndpoint": f"{self.base_url}/badge/{rtype}/{quote(rid, safe='@:')}"},
        ]

    def document(self, record: Record) -> dict:
        """A resource's DID Document (Sections 5, 5.1 and 5.1.1)."""
        did = record.did.did
        subject = [f"{did}#key-{n}" for n in range(1, len(record.subject_keys) + 1)]
        registry_key = f"{did}#registry-key"
        methods = [{"id": vid, "type": KEY_TYPE, "controller": did, "publicKeyMultibase": key}
                   for vid, key in zip(subject, record.subject_keys)]
        methods.append({"id": registry_key, "type": KEY_TYPE, "controller": self.did,
                        "publicKeyMultibase": self.signing_keys[0]})
        doc = {"@context": list(CONTEXT), "id": did, "verificationMethod": methods}
        if subject:
            doc["authentication"] = subject
        doc["assertionMethod"] = [registry_key]
        if not record.deactivated:
            doc["service"] = self.services(record.did)
        doc["created"] = record.created
        doc["updated"] = record.updated
        return doc

    def registry_document(self) -> dict:
        """The DID Document of the registry's self-identifier (Section 5.3)."""
        key = f"{self.did}#signing-key"
        return {
            "@context": list(CONTEXT),
            "id": self.did,
            "verificationMethod": [{"id": key, "type": KEY_TYPE, "controller": self.did,
                                    "publicKeyMultibase": self.signing_keys[0]}],
            "authentication": [key],
            "assertionMethod": [key],
            "service": [
                {"id": f"{self.did}#trust-api", "type": "TrustAPI",
                 "serviceEndpoint": f"{self.base_url}/api/v1/trust/query"},
                {"id": f"{self.did}#did-resolver", "type": "DIDResolver",
                 "serviceEndpoint": f"{self.base_url}{RESOLVE_PATH}"},
                {"id": f"{self.did}#federation", "type": "Federation",
                 "serviceEndpoint": f"{self.base_url}/api/v1/federation/proposals"},
            ],
            "created": self.created,
            "updated": self.updated,
        }

    def resolve(self, text: str) -> tuple:
        """Return (status, JSON body) for a request for the DID `text` (Sections 3.5, 4.2 and 4.4)."""
        try:
            did = parse_did(text)
        except DidSyntaxError as exc:
            return 400, {"error": "invalidDid", "message": str(exc), "did": text}
        if did.fragment is not None:
            return 400, {"error": "invalidDid", "did": text,
                         "message": "the request carries a fragment: a DID Document's id carries none, so it could "
                                    "not equal the requested DID as Section 4.2 requires; request the DID without it"}
        if did.did == self.did:
            return 200, self.result(self.registry_document())
        record = self.records.get(did.did)
        if record is None:
            return 404, {"error": "notFound", "message": f"no resource is registered under {did.did}", "did": did.did}
        return 200, self.result(self.document(record), record.deactivated)

    def result(self, document: dict, deactivated: bool = False) -> dict:
        """A DID resolution result (DID Core Section 7.1) carrying issuingRegistry (Section 3.5)."""
        metadata = {"issuingRegistry": self.did}
        if deactivated:
            metadata["deactivated"] = True
        return {"didDocument": document, "didResolutionMetadata": {"contentType": MEDIA_TYPE},
                "didDocumentMetadata": metadata}

    def discovery(self) -> dict:
        """The discovery document (Section 8.3), with every currently valid signing key."""
        return {
            "registryDid": self.did,
            "supportedMethods": ["did:opena2a"],
            "publicKeys": [{"algorithm": "Ed25519", "publicKey": base64.b64encode(ed25519_key(key)).decode("ascii"),
                            "publicKeyMultibase": key} for key in self.signing_keys],
            "endpoints": {"didResolve": RESOLVE_PATH + "{did}"},
        }

    def resolution_reply(self, did: str) -> tuple:
        """Return (status, headers, body) answering a request for the DID string `did` (Section 4.2)."""
        status, body = self.resolve(did)
        if status == 200:
            return _reply(status, body, MEDIA_TYPE, CACHE_CONTROL)
        return _reply(status, body, "application/json", "no-store")

    def respond(self, method: str, target: str) -> tuple:
        """Return (status, headers, body) answering `method` on the request-target `target`.

        For HEAD the caller sends the status and headers and not the body.
        """
        if method not in ("GET", "HEAD"):
            return _reply(405, {"error": "methodNotAllowed", "message": "this resolver answers GET and HEAD"},
                          "application/json", "no-store", [("Allow", "GET, HEAD")])
        path = target.partition("?")[0]
        if path == DISCOVERY_PATH:
            return _reply(200, self.discovery(), "application/json")
        if path.startswith(RESOLVE_PATH):
            # The transport's URL decoding; the DID's own decoding step follows in resolve().
            return self.resolution_reply(unquote(path[len(RESOLVE_PATH):]))
        return _reply(404, {"error": "notFound", "message": f"this resolver answers {RESOLVE_PATH}<did> "
                                                            f"and {DISCOVERY_PATH}"}, "application/json", "no-store")


def _reply(status: int, body: dict, content_type: str, cache_control: str | None = None, extra: list = ()) -> tuple:
    data = (json.dumps(body, indent=2) + "\n").encode("utf-8")
    headers = [("Content-Type", content_type), ("Content-Length", str(len(data)))]
    if cache_control:
        headers.append(("Cache-Control", cache_control))
    headers.append(("X-Content-Type-Options", "nosniff"))
    return status, headers + list(extra), data


def handler_for(registry: Registry, log: bool = True) -> type:
    """A request handler class for http.server that answers with registry.respond()."""

    class Handler(BaseHTTPRequestHandler):
        def answer(self) -> None:
            status, headers, body = registry.respond(self.command, self.path)
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = answer

        def version_string(self) -> str:
            return "did-opena2a-reference-resolver"

        def log_message(self, format: str, *args) -> None:
            if log:
                super().log_message(format, *args)

    return Handler


def shown_host(host: str) -> str:
    """host as given when it is visible ASCII, otherwise its ascii(), which escapes the characters a reader cannot see."""
    if host and all("!" <= ch <= "~" for ch in host):
        return host
    return ascii(host)


def serve(registry: Registry, host: str, port: int) -> int:
    """Answer HTTP on host:port until interrupted; 0, or 2 after one line on stderr when it cannot listen there."""
    handler = handler_for(registry)
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except (OSError, OverflowError, TypeError) as exc:
        # OSError: the port is taken or the host is not an address of this machine. OverflowError: a port
        # outside 0-65535, which the command line refuses before this. TypeError: a host the IDNA codec cannot
        # encode, such as one carrying an invisible character.
        print(f"cannot listen on {shown_host(host)}:{port}: {exc}", file=sys.stderr)
        return 2
    print(f"resolving for {registry.did} at http://{host}:{server.server_port}{RESOLVE_PATH}<did>", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def port_number(text: str) -> int:
    """The --port value: an integer from 0 to 65535."""
    try:
        port = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from None
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"{port} is outside 0-65535")
    return port


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", required=True, type=Path, metavar="FILE",
                    help="the JSON file holding the registry and its records")
    commands = ap.add_subparsers(dest="command", required=True, metavar="command")
    resolve = commands.add_parser("resolve", help="print the reply to a resolution request for the DID string DID")
    resolve.add_argument("did", metavar="DID")
    listen = commands.add_parser("serve", help="answer HTTP requests until interrupted")
    listen.add_argument("--host", default="127.0.0.1", help="the IPv4 address to listen on (default: 127.0.0.1)")
    listen.add_argument("--port", type=port_number, default=8080, metavar="PORT",
                        help="the port to listen on, 0 to 65535 (default: 8080)")
    args = ap.parse_args(argv)
    try:
        registry = Registry.from_json(json.loads(args.records.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"{args.records}: {exc}", file=sys.stderr)
        return 2
    if args.command == "serve":
        return serve(registry, args.host, args.port)
    status, headers, body = registry.resolution_reply(args.did)
    print(f"{status} {HTTPStatus(status).phrase}")
    for name, value in headers:
        print(f"{name}: {value}")
    print()
    sys.stdout.write(body.decode("utf-8"))
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
