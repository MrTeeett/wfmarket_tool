import time
import copy
import math
from typing import List, Dict, Any, Optional
import typer
import pandas as pd
from wfmarket.analyzers import build_sets_report, riven_endo_candidates, build_mods_report
from wfmarket.config import load_config
from wfmarket.exporters import write_mods_excel, write_sets_excel
from wfmarket.constants import CATEGORY_ORDER, MODS_COLUMN_ORDER
from wfmarket.reports import prepare_mods_export
from wfmarket.i18n import get_ui_strings, normalize_language

CONFIG = load_config()
SETTINGS_SETS = CONFIG.get("sets", {})
SETTINGS_ENDO = CONFIG.get("endo", {})
SETTINGS_MODS = CONFIG.get("mods", {})
DEFAULT_PLATFORM = CONFIG.get("platform", "pc")
DEFAULT_LANGUAGE = CONFIG.get("language", "en")

UI_LANGUAGE = normalize_language(CONFIG.get("ui_language") or CONFIG.get("language"))
TEXT = get_ui_strings(UI_LANGUAGE)

app = typer.Typer(help=TEXT["app_help"])



def sets(
        out: str = typer.Option(
                SETTINGS_SETS.get("out", "warframe_market_sets.xlsx"),
                "--out",
                "-o",
                help="Output file for the sets report.",
        ),
        platform: str = typer.Option(
                DEFAULT_PLATFORM,
                "--platform",
                "-p",
                help="Game platform (pc, ps4, xbox, switch).",
        ),
        language: str = typer.Option(
                DEFAULT_LANGUAGE,
                "--language",
                "-l",
                help="Warframe Market language (en, ru, ...).",
        ),
        only_online: bool = typer.Option(
                SETTINGS_SETS.get("only_online", False),
                "--only-online/--include-offline",
                help="Consider only online/in-game sellers.",
        ),
        filter_contains: str = typer.Option(
                SETTINGS_SETS.get("filter_contains", "prime"),
                "--filter-contains",
                "-f",
                help="Substring filter applied to item names/URLs (empty string disables it).",
        ),
        limit_sets: Optional[int] = typer.Option(
                SETTINGS_SETS.get("limit_sets", 80),
                "--limit-sets",
                "-n",
                help="Maximum number of sets to process (0 or None removes the limit).",
        ),
        progress: bool = typer.Option(
                SETTINGS_SETS.get("progress", True),
                "--progress/--no-progress",
                help="Display progress and estimated time remaining.",
        ),
        fetch_part_statistics: bool = typer.Option(
                SETTINGS_SETS.get("fetch_part_statistics", True),
                "--fetch-part-statistics/--skip-part-statistics",
                help="Fetch 24h statistics for parts (slower) or skip them for speed.",
        ),
        live_price_top_n: int = typer.Option(
                SETTINGS_SETS.get("live_price_top_n", 4),
                "--live-price-top-n",
                help="Number of live orders to average for the live price (top-N).",
        ),
):
        if limit_sets is not None and limit_sets <= 0:
                limit_sets = None
        if live_price_top_n <= 0:
                raise typer.BadParameter(TEXT["errors"]["live_price_top_n_positive"])

        progress_callback = None
        if progress:
                progress_text = TEXT["progress"]
                last_report = {}
                stage_titles = progress_text["stages"]

                def _progress(stage: str, done: int, total: int, remaining_seconds: float):
                        now = time.perf_counter()
                        last = last_report.get(stage, 0.0)
                        if done == total or now - last >= 1.0:
                                label = stage_titles.get(stage, stage)
                                if done == total:
                                        message = progress_text["done_format"].format(
                                                label=label,
                                                done=done,
                                                total=total,
                                                status_done=progress_text["status_done"],
                                        )
                                else:
                                        if remaining_seconds < 1:
                                                remaining_value = progress_text["remaining_less"]
                                        else:
                                                remaining_value = progress_text["remaining_seconds"].format(seconds=remaining_seconds)
                                        message = progress_text["format"].format(
                                                label=label,
                                                done=done,
                                                total=total,
                                                remaining_label=progress_text["remaining_label"],
                                                remaining=remaining_value,
                                        )
                                typer.echo(message, err=True)
                                last_report[stage] = now

                progress_callback = _progress
        df = build_sets_report(platform=platform, language=language,
                                                   filter_contains=filter_contains,
                                                   only_online=only_online, limit_sets=limit_sets,
                                                   fetch_part_statistics=fetch_part_statistics,
                                                   live_price_top_n=live_price_top_n,
                                                   progress_callback=progress_callback)
        records = df.to_dict("records")
        if out.endswith(".xlsx"):
                write_sets_excel(records, out, TEXT, live_price_top_n, CATEGORY_ORDER)
        else:
                export_df = df.drop(columns=["row_type", "link"]).copy() if "row_type" in df else df
                export_df.to_csv(out, index=False)
        typer.echo(TEXT["saved"].format(out=out))


@app.command()
def mods(
        out: str = typer.Option(
                SETTINGS_MODS.get("out", "mod_prices.xlsx"),
                "--out",
                "-o",
                help="Output file for the mod price comparison report.",
        ),
        platform: str = typer.Option(
                DEFAULT_PLATFORM,
                "--platform",
                "-p",
                help="Game platform (pc, ps4, xbox, switch).",
        ),
        language: str = typer.Option(
                DEFAULT_LANGUAGE,
                "--language",
                "-l",
                help="Warframe Market language (en, ru, ...).",
        ),
        only_online: bool = typer.Option(
                SETTINGS_MODS.get("only_online", False),
                "--only-online/--include-offline",
                help="Consider only online/in-game sellers.",
        ),
        rarities: Optional[List[str]] = typer.Option(
                None,
                "--rarity",
                "-r",
                help="Filter by mod rarity (repeat to provide several values).",
        ),
        filter_contains: str = typer.Option(
                SETTINGS_MODS.get("filter_contains", ""),
                "--filter",
                "-f",
                help="Substring filter applied to mod names/IDs (case-insensitive).",
        ),
        limit_items: Optional[int] = typer.Option(
                SETTINGS_MODS.get("limit_items"),
                "--limit-items",
                "-n",
                help="Maximum number of mods to inspect (0 or None removes the limit).",
        ),
        progress: bool = typer.Option(
                SETTINGS_MODS.get("progress", True),
                "--progress/--no-progress",
                help="Display progress while fetching mod prices.",
        ),
        live_price_top_n: int = typer.Option(
                SETTINGS_MODS.get("live_price_top_n", 4),
                "--live-price-top-n",
                help="Number of live orders to average when comparing prices.",
        ),
):
        if live_price_top_n <= 0:
                raise typer.BadParameter(TEXT["errors"]["live_price_top_n_positive"])

        rarity_values: List[str] = []
        if rarities:
                rarity_values = [str(r).strip().lower() for r in rarities if str(r).strip()]
        else:
                default_rarities = SETTINGS_MODS.get("rarities") or []
                rarity_values = [str(r).strip().lower() for r in default_rarities if str(r).strip()]
        if limit_items is not None and limit_items <= 0:
                limit_items = None

        progress_callback = None
        if progress:
                progress_text = TEXT.get("mods_progress", {})
                label = progress_text.get("label", "Mods")
                format_text = progress_text.get("format", "[{label}] {done}/{total} • {name}")
                done_text = progress_text.get("done_format", "[{label}] {done}/{total} • {status_done}")
                status_done = progress_text.get("status_done", "done")
                last_state = {"time": 0.0, "done": 0}

                def _mods_progress(done: int, total: int, name: str) -> None:
                        if total <= 0 or done < 0:
                                return
                        now = time.perf_counter()
                        if done >= total:
                                if last_state["done"] >= total:
                                        return
                                message = done_text.format(label=label, done=total, total=total, status_done=status_done)
                        else:
                                if done == 0:
                                        return
                                if done == last_state["done"] and now - last_state["time"] < 0.5:
                                        return
                                if now - last_state["time"] < 0.5:
                                        return
                                message = format_text.format(label=label, done=done, total=total, name=name or "")
                        last_state["time"] = now
                        last_state["done"] = done if done <= total else total
                        typer.echo(message, err=True)

                progress_callback = _mods_progress

        df = build_mods_report(
                platform=platform,
                language=language,
                rarity_filter=rarity_values or None,
                only_online=only_online,
                top_n=live_price_top_n,
                filter_contains=filter_contains or None,
                limit_items=limit_items,
                progress_callback=progress_callback,
        )
        if df.empty:
                typer.echo(TEXT["no_results"])
                raise typer.Exit(code=0)

        export_df, column_order, headers = prepare_mods_export(df, TEXT, live_price_top_n)

        if out.endswith(".xlsx"):
                write_mods_excel(export_df, out, column_order, headers, TEXT)
        else:
                export_df.to_csv(out, index=False)
        typer.echo(TEXT["saved"].format(out=out))



def endo(
        out: str = typer.Option(
                SETTINGS_ENDO.get("out", "endo_candidates.xlsx"),
                "--out",
                "-o",
                help="Output file for the Endo candidates report.",
        ),
        platform: str = typer.Option(
                DEFAULT_PLATFORM,
                "--platform",
                "-p",
                help="Game platform (pc, ps4, xbox, switch).",
        ),
        language: str = typer.Option(
                DEFAULT_LANGUAGE,
                "--language",
                "-l",
                help="Warframe Market language (en, ru, ...).",
        ),
        only_online: bool = typer.Option(
                SETTINGS_ENDO.get("only_online", False),
                "--only-online/--include-offline",
                help="Consider only online/in-game sellers.",
        ),
        min_mastery: int = typer.Option(
                SETTINGS_ENDO.get("min_mastery", 8),
                "--min-mastery",
                help="Minimum mastery rank required for the item.",
        ),
        min_mod_rank: int = typer.Option(
                SETTINGS_ENDO.get("min_mod_rank", 8),
                "--min-mod-rank",
                help="Minimum mod rank to include.",
        ),
        limit_items: Optional[int] = typer.Option(
                SETTINGS_ENDO.get("limit_items", 300),
                "--limit-items",
                "-n",
                help="Maximum number of items to inspect (0 or None removes the limit).",
        ),
):
        endo_table = copy.deepcopy(CONFIG.get("endo_table", {})) or None
        if limit_items is not None and limit_items <= 0:
                limit_items = None
        df = riven_endo_candidates(platform=platform, language=language,
                                                           min_mastery=min_mastery, min_mod_rank=min_mod_rank,
                                                           only_online=only_online, limit_items=limit_items,
                                                           endo_table=endo_table)
        if df.empty:
                typer.echo(TEXT["no_results"])
                raise typer.Exit(code=0)
        if out.endswith(".xlsx"):
                with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                        df.to_excel(writer, index=False, sheet_name=TEXT.get("endo_sheet_name", "endo"))
        else:
                df.to_csv(out, index=False)
        typer.echo(TEXT["saved"].format(out=out))

if __name__ == "__main__":
        app()
