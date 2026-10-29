"""Turn the raw history dump into compact daily series for the page.

Usage: python3 -I build_dataset.py <history.json> <out.json> [v1-lookthrough.json [v1-extra.json]]

With the look-through file, days when the vault allocated through its MetaMorpho adapter
are filled with the adapter's pro-rata share of the V1 vault's per-market allocation.
"""
import collections
import datetime as dt
import json
import sys

raw = json.load(open(sys.argv[1]))
DAY = 86400


def day(ts):
    return int(ts) // DAY * DAY


def series(points, scale=1.0):
    """API timeseries come newest-first; key them by UTC day."""
    out = {}
    for p in points or []:
        if p["y"] is not None:
            out[day(p["x"])] = float(p["y"]) * scale
    return out


v = raw["vault"]
dec = raw["meta"]["asset"]["decimals"]
tvl_usd = series(v["totalAssetsUsd"])
share_price = series(v["sharePrice"])
api_apy = series(v["avgNetApy"])
supply = series(v["totalSupply"])

days = sorted(set(tvl_usd) & set(share_price))
# Drop the seed day (vault created with a 0.01 USDC dead deposit).
days = [d for d in days if tvl_usd[d] > 1000]


def realized_apy(d, window):
    prev = d - window * DAY
    if prev not in share_price or share_price[prev] <= 0:
        return None
    return (share_price[d] / share_price[prev]) ** (365 / window) - 1


deposits = collections.Counter()
withdrawals = collections.Counter()
for f in raw["flows"]:
    amt = int(f["assets"] or 0) / 10**dec
    if f["type"] == "Deposit":
        deposits[day(f["timestamp"])] += amt
    elif f["type"] == "Withdraw":
        withdrawals[day(f["timestamp"])] += amt

# Allocation by collateral family, from the current adapter's position history.
alloc = collections.defaultdict(lambda: collections.Counter())
for m in raw["markets"]:
    for d, usd in series(m["position"]["supplyAssetsUsd"]).items():
        alloc[d][m["collateral"] or "Idle"] += usd
via = {d: "direct" for d in alloc if sum(alloc[d].values()) > 0}
if len(sys.argv) > 3:
    lt = json.load(open(sys.argv[3]))
    in_v1 = series(lt["position"]["assetsUsd"])
    v1_tvl = series(lt["v1"]["historicalState"]["totalAssetsUsd"])
    for a in lt["v1"]["historicalState"]["allocation"]:
        coll = (a["market"]["collateralAsset"] or {}).get("symbol") or "Idle"
        for d, usd in series(a["supplyAssetsUsd"]).items():
            if in_v1.get(d, 0) > 1 and v1_tvl.get(d) and via.get(d) != "direct":
                alloc[d][coll] += usd * in_v1[d] / v1_tvl[d]
    for d, v in in_v1.items():
        if v > 1 and via.get(d) != "direct":
            via[d] = "v1"
alloc_days = sorted(d for d in alloc if d in tvl_usd and sum(alloc[d].values()) > 0)
families = ["cbBTC", "WBTC", "weETH", "wstETH", "WETH"]

rows = []
for d in days:
    rows.append({
        "t": d,
        "tvl": round(tvl_usd[d], 2),
        "sp": share_price[d],
        "apy1": api_apy.get(d),
        "apy7": realized_apy(d, 7),
        "apy30": realized_apy(d, 30),
        "dep": round(deposits.get(d, 0.0), 2),
        "wd": round(withdrawals.get(d, 0.0), 2),
        "alloc": {f: round(alloc[d].get(f, 0.0), 2) for f in families} if d in alloc_days else None,
        "via": via.get(d),
    })

# V1 assets excluding the V2 vault's own shares, so V1 + V2 never double-counts.
if len(sys.argv) > 3:
    for r in rows:
        if r["t"] in v1_tvl:
            r["v1"] = round(v1_tvl[r["t"]] - in_v1.get(r["t"], 0.0), 2)

    # Combined allocation: all of V1's markets plus V2's direct positions. Before the
    # switch V2's money is already inside V1's allocation, so it is not added again.
    v1_alloc = collections.defaultdict(lambda: collections.Counter())
    for a in lt["v1"]["historicalState"]["allocation"]:
        coll = (a["market"]["collateralAsset"] or {}).get("symbol") or "Idle"
        fam = coll if coll in families else "Other"
        for d, usd in series(a["supplyAssetsUsd"]).items():
            v1_alloc[d][fam] += usd
    for r in rows:
        d = r["t"]
        if d not in v1_alloc or r["alloc"] is None:
            continue
        direct = r["alloc"] if r["via"] == "direct" else {}
        r["comb"] = {f: round(v1_alloc[d].get(f, 0.0) + direct.get(f, 0.0), 2) for f in families + ["Other"]}
    gaps = [abs(sum(r["comb"].values()) - (r["v1"] + r["tvl"])) / (r["v1"] + r["tvl"]) for r in rows if "comb" in r]
    print("combined alloc days", len(gaps), "max |sum - combined tvl| / tvl", max(gaps))
    print("other max USD", max(r["comb"]["Other"] for r in rows if "comb" in r))

# Combined yield and flows need the V1 vault's share price and its own deposits/withdrawals.
if len(sys.argv) > 4:
    extra = json.load(open(sys.argv[4]))
    adapters = {a["address"].lower() for a in raw["meta"]["adapters"]["items"]}
    adapters.add(lt["adapter"].lower())  # the MetaMorpho adapter that held V1 shares
    v1_sp = series(extra["sharePrice"])
    v1_dep, v1_wd = collections.Counter(), collections.Counter()
    for f in extra["flows"]:
        if (f["data"].get("onBehalf") or "").lower() in adapters:
            continue  # V2 moving its own money in or out of V1, not a depositor
        amt = int(f["assets"] or 0) / 10**dec
        (v1_dep if f["type"] == "Deposit" else v1_wd)[day(f["timestamp"])] += amt

    # Asset-weighted daily return of both vaults, deduplicated like total assets.
    index, prev = 1.0, None
    by_day = {}
    for r in rows:
        d = r["t"]
        r["v1dep"] = round(v1_dep.get(d, 0.0), 2)
        r["v1wd"] = round(v1_wd.get(d, 0.0), 2)
        if prev and d - prev["t"] == DAY and d in v1_sp and prev["t"] in v1_sp and "v1" in prev:
            w1, w2 = prev["v1"], prev["tvl"]
            r1 = v1_sp[d] / v1_sp[prev["t"]] - 1
            r2 = r["sp"] / prev["sp"] - 1
            index *= 1 + (w1 * r1 + w2 * r2) / (w1 + w2)
        by_day[d] = index
        prev = r
    for r in rows:
        for n, key in ((7, "capy7"), (30, "capy30")):
            p = r["t"] - n * DAY
            r[key] = (by_day[r["t"]] / by_day[p]) ** (365 / n) - 1 if p in by_day else None
    last = rows[-1]
    print("combined apy7/30 last", last["capy7"], last["capy30"], "external V1 net flow", sum(v1_dep.values()) - sum(v1_wd.values()))

markets = []
for m in raw["markets"]:
    mk = m["market"]
    util = series(mk["utilization"])
    sapy = series(mk["supplyApy"])
    last = max(util) if util else None
    pos = series(m["position"]["supplyAssetsUsd"])
    markets.append({
        "id": m["marketId"],
        "collateral": m["collateral"],
        "lltv": m["lltv"],
        "days": len(sapy),
        "posDays": len(pos),
        "util": util.get(last) if last else None,
        "supplyApy": sapy.get(last) if last else None,
        "vaultUsd": pos.get(max(pos)) if pos else 0,
    })

out = {
    "vault": {
        "name": raw["meta"]["name"],
        "created": int(raw["meta"]["creationTimestamp"]),
        "fetchedAt": raw["fetchedAt"],
        "flowCount": len(raw["flows"]),
        "flowTypes": dict(collections.Counter(f["type"] for f in raw["flows"])),
        "allocStart": alloc_days[0] if alloc_days else None,
        "directFrom": min((d for d, k in via.items() if k == "direct"), default=None),
    },
    "rows": rows,
    "markets": markets,
}
json.dump(out, open(sys.argv[2], "w"), separators=(",", ":"))

fmt = lambda t: dt.datetime.fromtimestamp(t, dt.UTC).date()
print("days", len(rows), fmt(rows[0]["t"]), "->", fmt(rows[-1]["t"]))
print("alloc from", fmt(alloc_days[0]), "days", len(alloc_days), "direct from", fmt(min(d for d, k in via.items() if k == "direct")))
other = {d: sum(v for k, v in alloc[d].items() if k not in families) for d in alloc_days}
print("allocation outside the five families, max USD", max(other.values()))
gap = max(abs(sum(alloc[d].values()) - tvl_usd[d]) / tvl_usd[d] for d in alloc_days if d in tvl_usd and tvl_usd[d] > 1000)
print("max |alloc sum - tvl| / tvl", gap)
print("tvl min/max", min(r["tvl"] for r in rows), max(r["tvl"] for r in rows))
a7 = [r["apy7"] for r in rows if r["apy7"] is not None]
print("apy7 min/max", min(a7), max(a7), "apy1 last", rows[-1]["apy1"], "apy7 last", rows[-1]["apy7"], "apy30 last", rows[-1]["apy30"])
print("net flow total", sum(r["dep"] - r["wd"] for r in rows), "max dep", max(r["dep"] for r in rows), "max wd", max(r["wd"] for r in rows))
last = [r for r in rows if r["alloc"]][-1]
print("alloc last", last["alloc"], "sum", sum(last["alloc"].values()), "tvl", last["tvl"])
mid = [r for r in rows if r["alloc"]][len(alloc_days) // 2]
print("alloc mid", fmt(mid["t"]), mid["alloc"], "sum", sum(mid["alloc"].values()), "tvl", mid["tvl"])
print("size bytes", len(json.dumps(out, separators=(",", ":"))))
