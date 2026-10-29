# Tools

Scripts that sit next to the Rust crates: keeping the GraphQL schema in sync with the live Morpho
API, and pulling daily history for a Vault V2 into a chartable page.

Python scripts use only the standard library. Node scripts need `npm install` in this directory
once (`graphql` for the schema tools, `jsdom` for the page check). Run Python with `-I` so a stray
file in the working directory can't shadow a standard-library module.

## Schema (`schema/`)

The API changes without notice; between January and October 2026 it removed or renamed dozens of
fields and every query in `crates/api` broke. These keep the crate honest.

| Script | What it does |
| --- | --- |
| `fetch_schema.mjs <out.graphql>` | Introspects `https://api.morpho.org/graphql` and writes SDL. `just update-schema` writes `crates/api/schema/morpho.graphql`. |
| `validate_queries.py <file.graphql> [vars-json] [Operation]` | Sends each operation to the live API and prints schema errors plus query complexity (cap: 1,000,000). `just validate-queries` checks every file in `crates/api/queries`. |
| `show_type.mjs <schema.graphql> Type[.field] ...` | Prints a type's fields and arguments compactly, without descriptions. |

Pass realistic variables when checking complexity, e.g. `'{"first": 20}'` for list queries: the
default page size is what the API scores.

## Vault history (`vault-history/`)

Builds daily history for one Vault V2, including the period when it invested through a V1
(MetaMorpho) vault, and renders it as a self-contained HTML page.

```bash
cd tools/vault-history
mkdir -p out

# 1. V2 vault: daily state, per-market positions and market state, all deposits/withdrawals
python3 -I fetch_history.py 0xbeef088055857739C12CD3765F20b7679Def0f51 1 out/history.json

# 2. Only if the vault held V1 shares through a MetaMorpho adapter: the adapter's position in the
#    V1 vault, and the V1 vault's per-market allocation (start = V2 creation timestamp)
python3 -I fetch_v1_lookthrough.py <adapter> <v1-vault> 1 <start-ts> out/v1_lookthrough.json

# 3. V1 share price and deposits/withdrawals, for the combined yield and flow charts
python3 -I fetch_v1_extra.py <v1-vault> 1 <start-ts> out/v1_extra.json

# 4. Join everything into compact daily rows (steps 2 and 3 are optional arguments)
python3 -I build_dataset.py out/history.json out/dataset.json out/v1_lookthrough.json out/v1_extra.json

# 5. Render the page, then run it headless to catch script errors
python3 -I render_page.py out/dataset.json out/page.html
node page/check_page.cjs out/page.html
```

For Steakhouse Prime USDC the V1 inputs were: adapter `0xFc98D101F6E2F7C27DB2bAEf7D803298F0e0043C`,
V1 vault `0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB`, start `1761602340` (27 Oct 2025).

### How the numbers are put together

- **Days** are UTC days keyed on the API's 00:00 points. State at 00:00 on day *d* reflects flows
  made during day *d − 1*: `assets[d] = assets[d-1] × sharePrice[d] / sharePrice[d-1] + netFlow[d-1]`.
  Both vaults reconcile to within 0.01% per day on that identity.
- **Realized APY** is `(sharePrice[d] / sharePrice[d-N]) ^ (365/N) − 1`. The API's own `avgNetApy`
  only accepts lookbacks up to 24 hours.
- **Look-through allocation.** While the V2 vault held V1 shares, its share of each market is
  `adapter position in V1 / V1 total assets × V1 supply in that market`.
- **Combined V1 + V2 figures never double-count.** V1 assets exclude the shares V2 held; combined
  allocation is all of V1's markets plus V2's direct positions; combined yield weights each vault's
  daily share-price return by those deduplicated assets; combined flows drop V1 deposits and
  withdrawals made by V2's own adapters.

### API limits the scripts work around

- `skip` is capped at 10,000, so V2 transactions are paged in 30-day windows.
- `vaultV1Transactions` is cursor-paginated.
- Deep nested lists multiply query complexity; keep nested `first` arguments small.
- The API lists only open positions for an address, but `vaultPosition` / `marketPosition`
  history still works for closed ones.

### The page template

`page/template.html` is the page published for Steakhouse Prime USDC. Its copy (vault name,
adapter switch date, findings) is written for that vault; the charts read everything else from the
embedded dataset. Edit the copy before rendering it for another vault.
