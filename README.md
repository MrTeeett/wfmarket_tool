# wfmarket_tool

A compact utility for pulling Warframe Market analytics.

1. **Sets vs parts report** – compares complete sets with the sum of their components, including live-market deltas.
2. **Endo candidates scan** – finds inexpensive high-rank mods and rivens worth dissolving for Endo.

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
```

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

## Project structure

- `wfmarket/api.py` – lightweight client for the warframe.market API.
- `wfmarket/analyzers/sets_vs_parts.py` – logic behind the sets-versus-parts report.
- `wfmarket/analyzers/riven_endo_hunt.py` – heuristic scan for profitable Endo dissolves.
- `cli.py` – Typer-based command-line interface.
- `config.toml` – user configuration and optional Endo conversion tables.

## Notes

- Do not hammer the API faster than ~3 requests per second – the code enforces a delay, but be kind.
- For accurate Endo calculations, populate `endo_table` in `config.toml` with real values.
- The tool only reads public data; it does not place orders or interact with your account.
