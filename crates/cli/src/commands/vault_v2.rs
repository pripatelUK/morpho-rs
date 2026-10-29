//! V2 vault command implementations.

use alloy_chains::NamedChain;
use anyhow::Result;
use morpho_rs_api::{ClientConfig, VaultFiltersV2, VaultQueryOptionsV2, VaultV2, VaultV2Client};

use crate::cli::{InfoArgs, ListArgs, OutputFormat};
use crate::output::{format_v2_vault_detail, format_v2_vaults_table};

/// Create a ClientConfig with a custom page size and optional API URL.
fn client_config_with_page_size(page_size: i64, api_url: Option<&str>) -> Result<ClientConfig> {
    let config = ClientConfig::new().with_page_size(page_size);
    if let Some(url) = api_url {
        Ok(config.with_api_url(url.parse()?))
    } else {
        Ok(config)
    }
}

/// Create a default ClientConfig with optional API URL.
fn client_config(api_url: Option<&str>) -> Result<ClientConfig> {
    let config = ClientConfig::new();
    if let Some(url) = api_url {
        Ok(config.with_api_url(url.parse()?))
    } else {
        Ok(config)
    }
}

pub async fn run_v2_list(args: &ListArgs, format: OutputFormat, api_url: Option<&str>) -> Result<()> {
    let config = client_config_with_page_size(args.limit as i64, api_url)?;
    let client = VaultV2Client::with_config(config);

    // All filters are applied server-side; `limit` stops pagination early.
    let mut filters = VaultFiltersV2::new();
    if args.whitelisted {
        filters = filters.listed(true);
    }
    if let Some(chain_arg) = args.chain {
        filters = filters.chain(chain_arg.0);
    }
    if let Some(curator_address) = &args.curator {
        filters = filters.curators([curator_address.as_str()]);
    }
    let options = VaultQueryOptionsV2::new()
        .filters(filters)
        .limit(args.limit as i64);

    let vaults: Vec<VaultV2> = client.get_vaults_with_options(options).await?;

    // Output
    match format {
        OutputFormat::Table => {
            println!("{}", format_v2_vaults_table(&vaults));
        }
        OutputFormat::Json => {
            let json = serde_json::to_string_pretty(&vaults)?;
            println!("{}", json);
        }
    }

    Ok(())
}

pub async fn run_v2_info(args: &InfoArgs, format: OutputFormat, api_url: Option<&str>) -> Result<()> {
    let config = client_config(api_url)?;
    let client = VaultV2Client::with_config(config);
    let chain: NamedChain = args.chain.0;

    let vault = client.get_vault(&args.address, chain).await?;

    match format {
        OutputFormat::Table => {
            println!("{}", format_v2_vault_detail(&vault));
        }
        OutputFormat::Json => {
            let json = serde_json::to_string_pretty(&vault)?;
            println!("{}", json);
        }
    }

    Ok(())
}
