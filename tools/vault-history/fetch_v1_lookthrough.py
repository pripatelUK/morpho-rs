"""Fetch the V2 vault's history inside a V1 (MetaMorpho) vault via its MetaMorpho adapter.

Usage: python3 -I fetch_v1_lookthrough.py <adapter> <v1-vault> <chain-id> <start-ts> <out.json>
"""
import json
import sys
import time
import urllib.request

API = "https://api.morpho.org/graphql"
ADAPTER, V1, CHAIN, START, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API, body, {"content-type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=90))
    except urllib.error.HTTPError as e:
        r = json.load(e)
    if r.get("errors"):
        raise RuntimeError(json.dumps(r["errors"])[:800])
    return r["data"]


opts = {"startTimestamp": START, "endTimestamp": int(time.time()), "interval": "DAY"}

position = gql(
    """query($u: String!, $v: String!, $c: Int, $o: TimeseriesOptions) {
        vaultPosition(userAddress: $u, vaultAddress: $v, chainId: $c) {
          historicalState { assets(options: $o) { x y } assetsUsd(options: $o) { x y } shares(options: $o) { x y } }
        } }""",
    {"u": ADAPTER, "v": V1, "c": CHAIN, "o": opts},
)["vaultPosition"]["historicalState"]

v1 = gql(
    """query($v: String!, $c: Int, $o: TimeseriesOptions) {
        vaultByAddress(address: $v, chainId: $c) {
          name
          historicalState {
            totalAssets(options: $o) { x y }
            totalAssetsUsd(options: $o) { x y }
            allocation {
              market { marketId lltv collateralAsset { symbol } }
              supplyAssetsUsd(options: $o) { x y }
            }
          }
        } }""",
    {"v": V1, "c": CHAIN, "o": opts},
)["vaultByAddress"]

json.dump({"adapter": ADAPTER, "position": position, "v1": v1}, open(OUT, "w"))
nz = [p for p in position["assetsUsd"] if p["y"]]
print("position points", len(position["assetsUsd"]), "nonzero", len(nz))
print("v1", v1["name"], "points", len(v1["historicalState"]["totalAssetsUsd"]), "markets", len(v1["historicalState"]["allocation"]))
