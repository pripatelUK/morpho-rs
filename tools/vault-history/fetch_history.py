"""Pull daily history for one Vault V2 from the Morpho API into a JSON file.

Usage: python3 -I fetch_history.py <vault-address> <chain-id> <out.json>
"""
import json
import sys
import time
import urllib.request

API = "https://api.morpho.org/graphql"
ADDRESS, CHAIN_ID, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]


def gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API, body, {"content-type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        r = json.load(e)
    if r.get("errors"):
        raise RuntimeError(json.dumps(r["errors"])[:800])
    return r["data"]


meta = gql(
    """query($a: String!, $c: Int!) { vaultV2ByAddress(address: $a, chainId: $c) {
        name creationTimestamp asset { symbol decimals }
        adapters { items { address type ... on MorphoMarketV1Adapter {
          positions(first: 50) { items { market { marketId lltv collateralAsset { symbol } } } } } } }
    } }""",
    {"a": ADDRESS, "c": CHAIN_ID},
)["vaultV2ByAddress"]

start = int(meta["creationTimestamp"])
end = int(time.time())
opts = {"startTimestamp": start, "endTimestamp": end, "interval": "DAY"}

vault_hist = gql(
    """query($a: String!, $c: Int!, $o: TimeseriesOptions) { vaultV2ByAddress(address: $a, chainId: $c) {
        historicalState {
          totalAssets(options: $o) { x y }
          totalAssetsUsd(options: $o) { x y }
          totalSupply(options: $o) { x y }
          realAssets(options: $o) { x y }
          idleAssets(options: $o) { x y }
          sharePrice(options: $o) { x y }
          avgNetApy(options: $o, lookbackHours: 24) { x y }
        }
    } }""",
    {"a": ADDRESS, "c": CHAIN_ID, "o": opts},
)["vaultV2ByAddress"]["historicalState"]

# Per-market: the adapter's own position history (= the vault's allocation) plus market state.
markets = []
for adapter in meta["adapters"]["items"]:
    for pos in (adapter.get("positions") or {}).get("items") or []:
        m = pos["market"]
        hist = gql(
            """query($a: String!, $m: String!, $c: Int!, $o: TimeseriesOptions) {
                marketPosition(userAddress: $a, marketUniqueKey: $m, chainId: $c) {
                  historicalState { supplyAssets(options: $o) { x y } supplyAssetsUsd(options: $o) { x y } }
                }
                marketById(marketId: $m, chainId: $c) {
                  historicalState {
                    supplyApy(options: $o) { x y }
                    borrowApy(options: $o) { x y }
                    utilization(options: $o) { x y }
                    supplyAssetsUsd(options: $o) { x y }
                    liquidityAssetsUsd(options: $o) { x y }
                  }
                }
            }""",
            {"a": adapter["address"], "m": m["marketId"], "c": CHAIN_ID, "o": opts},
        )
        markets.append({
            "marketId": m["marketId"],
            "collateral": (m["collateralAsset"] or {}).get("symbol"),
            "lltv": int(m["lltv"]) / 1e18,
            "position": hist["marketPosition"]["historicalState"],
            "market": hist["marketById"]["historicalState"],
        })

# The API caps `skip` at 10,000, so page through flows in 30-day windows.
flows = []
window = 30 * 86400
for lo in range(start, end + 1, window):
    hi = min(lo + window - 1, end)
    skip = 0
    while True:
        page = gql(
            """query($a: [String!], $c: [Int!], $s: Int, $lo: Int, $hi: Int) { vaultV2transactions(
                first: 1000, skip: $s, where: { vaultAddress_in: $a, chainId_in: $c,
                timestamp_gte: $lo, timestamp_lte: $hi }) {
                items { timestamp type assets shares } pageInfo { countTotal } } }""",
            {"a": [ADDRESS], "c": [CHAIN_ID], "s": skip, "lo": lo, "hi": hi},
        )["vaultV2transactions"]
        flows += page["items"]
        skip += len(page["items"])
        if not page["items"] or skip >= page["pageInfo"]["countTotal"]:
            break

json.dump({"meta": meta, "vault": vault_hist, "markets": markets, "flows": flows,
           "fetchedAt": end}, open(OUT, "w"))
print("days", len(vault_hist["totalAssets"]), "markets", len(markets), "flows", len(flows))
