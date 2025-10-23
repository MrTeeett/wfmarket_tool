# wfmarket_tool

A compact utility for pulling Warframe Market analytics.

1. **Sets vs parts report** - compares complete sets with the sum of their components, including live-market deltas.
2. **Endo candidates scan** - finds inexpensive high-rank mods and rivens worth dissolving for Endo.
3. **Mod rank profitability** - contrasts unranked and fully ranked mod prices, factoring in Endo costs to evaluate upgrades.

## Installation

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Quick start

```bash
python cli.py sets --out warframe_market_sets.xlsx
python cli.py endo --out endo_candidates.xlsx
python cli.py mods --out mod_prices.xlsx
python gui.py  # launches the Qt6 desktop interface
```

The GUI mirrors the CLI features while adding:

- Live language switching between English and Russian.
- Persistent configuration for the UI language, rate delay, and default export paths.
- A unified progress bar and log console while reports are being generated.
- A "Generate all" workflow that writes the sets, mods, and Endo data into a single workbook with dedicated sheets.

## Configuration

Every CLI option can be defined in `config.toml`; command-line flags override the file when needed.

- `platform` / `language` – global defaults for both commands (e.g., `platform = "pc"`, `language = "en"`).
- `ui_language` – language for CLI output (`"en"` or `"ru"`).
- `[limits].rate_delay` – throttle between API calls to avoid 429 responses.
- `[sets]` – defaults for the sets report: output file (`out`), substring filter (`filter_contains`),
  maximum number of sets (`limit_sets`, 0 or `null` disables the limit), seller status filter (`only_online`),
  progress output (`progress`), optional 24h statistics for parts (`fetch_part_statistics`) and
  `live_price_top_n` – how many current sell orders to average for the live price.
- `[endo]` – defaults for the Endo candidates report: output file, seller filter, minimum mastery/mod rank and
  the item limit.
- `[mods]` – defaults for the mod profitability report: output file, seller filter, rarity filter (`rarities` list),
  substring filter, item limit and `live_price_top_n` that controls the order averaging window.
- `[endo_table]` – optional rarity/rank → Endo mapping for precise calculations (placeholders by default).
- `[cache]` – filesystem cache controls (directory and TTLs for statistics, orders and `item_full` responses).

Changing `config.toml` requires no extra steps – adjustments are picked up on the next run.

The sets report (`cli.py sets`) provides:

- 24-hour average prices from Warframe Market statistics.
- Live-market prices averaged across the top-N orders (with deviation showing half of the spread).
- Pre-calculated sums of component prices (24h and live top-N).
- Absolute and percentage differences between the set and the sum of its parts (for both price sources).
- Excel output split into category sheets (Warframes, Primary, Secondary, Melee, Archwing, Companions, Other).
- `--skip-part-statistics` (or `fetch_part_statistics = false`) to skip 24h statistics and keep only the live prices for a faster run.

## Mod profitability (`cli.py mods`)

- Compares the cheapest unranked (`mod_rank = 0`) and fully ranked sell orders using a configurable top-N window.
- Lists the Endo required to reach max rank (using rarity-based fusion formulas) and highlights the platinum delta.
- Reports Endo-per-platinum and platinum-per-Endo ratios to help decide whether upgrading before selling is worth it.
- Supports rarity and name filters, online-only sellers, and CSV/Excel exports with localized column headers.

## Project structure

- `wfmarket/api.py` - lightweight client for the warframe.market API.
- `wfmarket/analyzers/sets_vs_parts.py` - logic behind the sets-versus-parts report.
- `wfmarket/analyzers/riven_endo_hunt.py` - heuristic scan for profitable Endo dissolves.
- `wfmarket/analyzers/mods_price_tracker.py` - mod price comparison and Endo efficiency calculations.
- `wfmarket/gui_app.py` - PyQt6 desktop application with combined report generation and settings persistence.
- `cli.py` - Typer-based command-line interface.
- `config.toml` - user configuration and optional Endo conversion tables.

## Building standalone binaries

PyInstaller scripts are provided for both Linux and Windows:

```bash
./scripts/build_linux.sh
```

```bat
scripts\build_windows.bat
```

Each script produces `wfmarket-cli` and `wfmarket-gui` single-file executables in the `dist/` directory.

## Notes

- Do not hammer the API faster than ~3 requests per second - the code enforces a delay, but be kind.
- For accurate Endo calculations, populate `endo_table` in `config.toml` with real values.
- Mod profitability depends on live market liquidity; tweak `live_price_top_n` or `rarities` when results look sparse.
- The tool only reads public data; it does not place orders or interact with your account.
