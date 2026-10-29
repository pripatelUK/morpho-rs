# Changelog

## 0.9.0 — 2026-10-29

`morpho-rs-api` and `morpho-rs-cli` 0.9.0. `morpho-rs-contracts` (0.8.0) and `morpho-rs-sim` (0.6.0)
are unchanged.

The Morpho GraphQL API dropped and renamed many fields after the bundled schema was last refreshed
(January 2026). Every query in 0.8.0 now fails against `https://api.morpho.org/graphql` with
`Cannot query field ...` errors. This release refreshes the schema, rewrites the queries, and
adds support for the newer Vault V2 features.

### Breaking changes

Fields and variants the API no longer provides have been removed rather than left permanently
empty.

| Removed / changed | Replacement / migration |
| --- | --- |
| `VaultV1::whitelisted`, `VaultV2::whitelisted` | Use `listed`. The API removed `whitelisted`; `get_whitelisted_vaults()` already filtered on `listed` and keeps its name. |
| `Vault::whitelisted()` trait method | Use `Vault::listed()`. |
| `VaultV2::avg_apy` | Removed by the API. Use `avg_net_apy` or `apy`. |
| `VaultReward::yearly_supply_tokens` and the 4th argument of `VaultReward::from_gql` | Removed by the API. `supply_apr` is still available. |
| `VaultStateV1::share_price: U256` | Now `Option<f64>`: assets per share in whole asset units (API `sharePriceNumber`). The raw on-chain share price is no longer exposed by the API; read it on-chain via `convert_to_assets` if needed. |
| `VaultPositionState::roe_usd`, `UserVaultV2Position::roe_usd` | Removed by the API. `pnl`, `pnl_usd` and `roe` remain. |
| `UserState` PnL/ROE totals (`vaults_pnl_usd`, `vaults_roe_usd`, `vault_v2s_pnl_usd`, `vault_v2s_roe_usd`, `markets_*_pnl_usd`, `markets_*_roe_usd`) | Removed by the API. The six asset totals (`vaults_assets_usd`, `vault_v2s_assets_usd`, `markets_collateral_usd`, `markets_supply_assets_usd`, `markets_borrow_assets_usd`, `markets_margin_usd`) remain; `UserState::from_gql` takes only those. |
| `VaultOrderByV1::CredoraRiskScore` | Removed by the API. |
| `VaultV2::from_gql`, `VaultV1::from_gql`, `VaultStateV1::from_gql`, `VaultAdapter::from_gql`, `VaultPositionState::from_gql`, `UserVaultV2Position::from_gql` | Signatures changed to match the fields above. These are mainly internal constructors; callers building types by hand need to update their arguments. |
| `VaultQueryOptionsV2::has_client_filter()` | Now only `true` when `asset_symbols` is set, since asset-address and curator filters moved server-side. |

### Behaviour changes

- **V2 asset-address and curator filters are applied server-side.**
  `VaultQueryOptionsV2::asset_addresses` / `curator_addresses` and
  `VaultV2Client::get_vaults_by_curator` now send `assetAddress_in` / `curatorAddress_in` to the
  API instead of filtering after download. Invalid address strings are now rejected by the API
  instead of silently matching nothing.
- **V2 list queries use pages of at most 20 vaults.** Each V2 vault pulls nested adapter positions
  and market state, and a page of 100 exceeds the API's 1M query-complexity cap. A configured
  `page_size` above 20 is clamped for V2 lists, and the page limit is raised so the same total
  number of vaults (5,000) can still be fetched.
- **Nested V2 adapter data is bounded:** at most 5 adapters per vault and 50 market positions per
  `MorphoMarketV1` adapter are fetched, again to stay under the complexity cap.
- **Allocation `enabled` is derived.** The API removed it; `VaultAllocation::enabled` and
  `MetaMorphoAllocation::enabled` are now `withdraw_queue_index.is_some()`, which is how
  MetaMorpho defines an enabled market.
- **User positions without state are skipped.** The API moved V1 vault position balances and
  market position balances under `state`; a position with no state has no balances and is no
  longer returned.
- **CLI:** `morpho vaultv2 list` sends `--curator`, `--chain` and `--whitelisted` as server-side
  filters and stops paginating at `--limit` (previously `--curator` downloaded every V2 vault). The
  detail views no longer print `Whitelisted:`.

### Added

- `VaultV2` fields: `vault_type` (`MorphoVault` / `FeeWrapper`), `idle_assets`, `idle_assets_usd`,
  `max_apy`, `net_apy_excluding_rewards`, `force_deallocatable_liquidity`, `liquidity_adapter`,
  and `gates`.
- `VaultV2Gates` (re-exported from the crate root): the receive/send shares/assets gate contracts,
  with `is_gated()`.
- `VaultAdapter::force_deallocate_penalty`.
- `VaultAdapterData::MorphoVaultV2 { inner_vault }` for adapters that allocate into another V2
  vault (used by fee-wrapper vaults).
- `VaultFiltersV2::curators()`, `owners()` and `asset_addresses()` server-side filters, and
  `VaultQueryOptionsV2::server_filters()`.
- CLI `vaultv2 info` shows vault type, gates, idle assets and max APY.

### Not yet supported

- Vault V2 `MidnightAdapter` (allocation into Midnight fixed-rate markets) exists in the
  `vault-v2` contracts but is not exposed by the GraphQL API yet.
- Pending/abdicated fee and gate configuration (`performanceFeeConfig`, etc.) is not fetched; only
  current values are.
