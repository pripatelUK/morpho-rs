"""Fetch a V1 vault's daily share price and its deposits/withdrawals, for combining with V2.

Usage: python3 -I fetch_v1_extra.py <v1-vault> <chain-id> <start-ts> <out.json>
"""
import json
import sys
import time
import urllib.request

API = "https://api.morpho.org/graphql"
V1, CHAIN, START, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
END = int(time.time())


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


share_price = gql(
    """query($v: String!, $c: Int, $o: TimeseriesOptions) { vaultByAddress(address: $v, chainId: $c) {
        historicalState { sharePriceNumber(options: $o) { x y } } } }""",
    {"v": V1, "c": CHAIN, "o": {"startTimestamp": START, "endTimestamp": END, "interval": "DAY"}},
)["vaultByAddress"]["historicalState"]["sharePriceNumber"]

# vaultV1Transactions is cursor-paginated.
flows, cursor = [], None
while True:
    where = {"vaultAddress_in": [V1], "chainId_in": [CHAIN], "type_in": ["Deposit", "Withdraw"],
             "timestamp_gte": START, "timestamp_lte": END}
    if cursor:
        where["cursor"] = cursor
    page = gql(
        """query($w: VaultV1TransactionFilters) { vaultV1Transactions(first: 1000, orderBy: Time,
            orderDirection: Asc, where: $w) {
            items { timestamp type assets data {
              ... on VaultV1DepositData { onBehalf }
              ... on VaultV1WithdrawData { onBehalf } } }
            pageInfo { hasNextPage endCursor { txHash logIndex } } } }""",
        {"w": where},
    )["vaultV1Transactions"]
    flows += page["items"] or []
    info = page["pageInfo"]
    if not info["hasNextPage"]:
        break
    cursor = info["endCursor"]

json.dump({"sharePrice": share_price, "flows": flows}, open(OUT, "w"))
print("share price points", len(share_price), "flows", len(flows))
