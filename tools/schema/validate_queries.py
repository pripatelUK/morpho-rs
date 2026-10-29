"""Send each operation in a .graphql file to the live Morpho API and print schema errors and complexity.

Usage: python3 -I validate_queries.py <queries.graphql> ['{"first": 20}'] [OperationName]
"""
import json, re, sys, urllib.request

src = open(sys.argv[1]).read()
variables = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
only = sys.argv[3] if len(sys.argv) > 3 else None
for op in re.findall(r'^query\s+(\w+)', src, re.M):
    if only and op != only:
        continue
    body = json.dumps({"query": src, "operationName": op, "variables": variables}).encode()
    req = urllib.request.Request("https://api.morpho.org/graphql", body, {"content-type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        r = json.load(e)
    # drop "variable X of required type was not provided" noise; keep schema validation errors
    errs = sorted({e["message"] for e in r.get("errors", []) if "was not provided" not in e["message"]})
    ext = r.get("extensions") or {}
    print(f"[{op}]", "OK" if not errs else "", ext.get("complexity", ""), ext.get("maximumComplexity", ""))
    for e in errs:
        print("   ", e)
