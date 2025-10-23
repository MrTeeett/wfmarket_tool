import time
import copy
import math
from collections import OrderedDict
from numbers import Number
from typing import List, Dict, Any, Optional
import typer
import pandas as pd
from wfmarket.analyzers import build_sets_report, riven_endo_candidates, build_mods_report
from wfmarket.config import load_config

CONFIG = load_config()
SETTINGS_SETS = CONFIG.get("sets", {})
SETTINGS_ENDO = CONFIG.get("endo", {})
SETTINGS_MODS = CONFIG.get("mods", {})
DEFAULT_PLATFORM = CONFIG.get("platform", "pc")
DEFAULT_LANGUAGE = CONFIG.get("language", "en")

UI_LANGUAGE = (CONFIG.get("ui_language") or CONFIG.get("language") or "en").lower()
if UI_LANGUAGE not in ("en", "ru"):
	UI_LANGUAGE = "en"

UI_STRINGS = {
	"en": {
		"app_help": "Warframe Market analytics without tears.",
		"progress": {
			"stages": {"scan": "Scanning prime sets", "calc": "Calculating prices"},
			"format": "[{label}] {done}/{total} • {remaining_label} {remaining}",
			"done_format": "[{label}] {done}/{total} • {status_done}",
			"remaining_label": "Remaining",
			"remaining_less": "less than a second",
			"remaining_seconds": "{seconds:.1f} s",
			"status_done": "done",
		},
		"saved": "Saved: {out}",
		"no_results": "Nothing suitable was found.",
		"open_label": "Open",
		"sheet_title_template": "{title} — Warframe Market Profit Overview",
		"empty_sheet": "No data",
		"headers": [
			"Open",
			"Warframe Market ID",
			"Item name",
			"24h volume",
			"Average price (24h)",
			"Live price (top-{n})",
			"Deviation",
			"Sum of parts (24h)",
			"Sum of parts (top-{n})",
			"Difference (24h)",
			"Difference % (24h)",
			"Difference (top-{n})",
			"Difference % (top-{n})",
		],
		"notes": [
			"Use the Warframe Market ID filter \"_set\" to jump to a set quickly.",
			"The average price (24h) comes from the Warframe Market statistics for the last 24 hours.",
			"The live price averages the top-{n} current sell orders; the deviation is half of their spread.",
			"Sum of parts is calculated with component quantities (24h statistics or the top-{n} orders).",
			"Difference (24h) shows platinum: parts sum − set price. Positive values mean the parts are more expensive.",
			"Difference % equals (parts sum / set price − 1).",
		],
		"mods_headers": [
			"Open",
			"Warframe Market ID",
			"Mod name",
			"Rarity",
			"Max rank",
			"Endo to max",
			"Unranked min",
			"Unranked avg (top-{n})",
			"Unranked deviation",
			"Unranked orders",
			"Maxed min",
			"Maxed avg (top-{n})",
			"Maxed deviation",
			"Maxed orders",
			"Price diff",
			"Price diff %",
			"Endo per platinum diff",
			"Platinum per Endo",
		],
		"mods_notes": [
			"Unranked columns use sell orders with mod rank 0; maxed columns use the maximum mod rank available.",
			"Deviation equals half of the spread between the cheapest and the priciest order within the top-{n} selection.",
			"Endo per platinum diff shows how much Endo is required for each extra platinum earned by ranking the mod.",
		],
		"mods_sheet_name": "mods",
		"mods_rarity_labels": {
			"common": "Common",
			"uncommon": "Uncommon",
			"rare": "Rare",
			"legendary": "Legendary",
		},
		"mods_progress": {
			"label": "Mods",
			"format": "[{label}] {done}/{total} • {name}",
			"done_format": "[{label}] {done}/{total} • {status_done}",
			"status_done": "done",
		},
		"category_titles": {
			"warframes": "Warframes",
			"primary": "Primary weapons",
			"secondary": "Secondary weapons",
			"melee": "Melee weapons",
			"archwing": "Archwing & Space",
			"companions": "Companions",
			"other": "Other",
		},
		"endo_sheet_name": "endo",
		"errors": {
			"live_price_top_n_positive": "live_price_top_n must be positive",
		},
	},
	"ru": {
		"app_help": "Warframe Market аналитика без лишних слез.",
		"progress": {
			"stages": {"scan": "Поиск прайм-наборов", "calc": "Расчёт цен"},
			"format": "[{label}] {done}/{total} • {remaining_label} {remaining}",
			"done_format": "[{label}] {done}/{total} • {status_done}",
			"remaining_label": "Осталось",
			"remaining_less": "меньше секунды",
			"remaining_seconds": "{seconds:.1f} с",
			"status_done": "готово",
		},
		"saved": "Сохранено: {out}",
		"no_results": "Ничего подходящего не найдено.",
		"open_label": "Открыть",
		"sheet_title_template": "{title} — аналитика Warframe Market",
		"empty_sheet": "Нет данных",
		"headers": [
			"Открыть",
			"Warframe Market ID",
			"Название в игре",
			"Объём продаж 24 часа",
			"Средняя цена (24ч)",
			"Реальная цена (топ-{n})",
			"Погрешность",
			"Сумма частей (24ч)",
			"Сумма частей (топ-{n})",
			"Разница (24ч)",
			"Разница % (24ч)",
			"Разница (топ-{n})",
			"Разница % (топ-{n})",
		],
		"notes": [
			"Используйте фильтр Warframe Market ID \"_set\" для быстрого перехода к комплекту.",
			"Средняя цена (24ч) берётся из статистики Warframe Market за последние 24 часа.",
			"Реальная цена усредняется по топ-{n} актуальным ордерам; погрешность — половина разброса.",
			"Сумма частей рассчитывается с учётом количества деталей (по статистике 24ч или по топ-{n} ордерам).",
			"Разница (24ч) показана в платине: сумма деталей − цена комплекта (положительное значение ⇒ детали дороже).",
			"Разница % вычисляется как (сумма деталей / цена комплекта − 1).",
		],

		"mods_headers": [
			"Открыть",
			"Warframe Market ID",
			"Название мода",
			"Редкость",
			"Макс. ранг",
			"Эндо до максимума",
			"Мин. цена (0 ранг)",
			"Средняя цена (top-{n}, 0 ранг)",
			"Отклонение (0 ранг)",
			"Количество ордеров (0 ранг)",
			"Мин. цена (макс. ранг)",
			"Средняя цена (top-{n}, макс. ранг)",
			"Отклонение (макс. ранг)",
			"Количество ордеров (макс. ранг)",
			"Разница в цене",
			"Разница в цене %",
			"Эндо / разница в платине",
			"Платина / эндо",
		],
		"mods_notes": [
			"Столбцы для ранга 0 используют ордера с mod_rank = 0; столбцы для максимального ранга берут ордера с максимальным mod_rank.",
			"Отклонение равняется половине разброса между минимальной и максимальной ценой внутри выборки top-{n}.",
			"Эндо / разница в платине показывает, сколько эндо требуется для дополнительной платины после прокачки.",
		],
		"mods_sheet_name": "моды",
		"mods_rarity_labels": {
			"common": "Обычный",
			"uncommon": "Необычный",
			"rare": "Редкий",
			"legendary": "Легендарный",
		},
		"mods_progress": {
			"label": "Моды",
			"format": "[{label}] {done}/{total} • {name}",
			"done_format": "[{label}] {done}/{total} • {status_done}",
			"status_done": "готово",
		},
		"category_titles": {
			"warframes": "Варфреймы",
			"primary": "Основное оружие",
			"secondary": "Вторичное оружие",
			"melee": "Ближнее оружие",
			"archwing": "Арч и космос",
			"companions": "Компаньоны",
			"other": "Прочее",
		},
		"endo_sheet_name": "Эндо",
		"errors": {
			"live_price_top_n_positive": "live_price_top_n должно быть положительным",
		},
	},
}

TEXT = UI_STRINGS[UI_LANGUAGE]

_CATEGORY_ORDER = [
	"warframes",
	"primary",
	"secondary",
	"melee",
	"archwing",
	"companions",
	"other",
]

app = typer.Typer(help=TEXT["app_help"])



def _write_sets_excel(records: List[Dict[str, Any]], out_path: str, language: str, live_price_top_n: int) -> None:
	import xlsxwriter

	def _sanitize_number(value: Any) -> Optional[float]:
		if not isinstance(value, Number):
			return None
		try:
			numeric = float(value)
		except (TypeError, ValueError):
			return None
		if math.isnan(numeric) or math.isinf(numeric):
			return None
		return numeric

	ui_text = TEXT
	headers = [header.format(n=live_price_top_n) for header in ui_text["headers"]]
	notes = [note.format(n=live_price_top_n) for note in ui_text["notes"]]

	used_sheet_names: set[str] = set()

	def _unique_sheet_name(title: str) -> str:
		base = title or "Report"
		trimmed = base[:31] or "Sheet"
		name = trimmed
		counter = 2
		while name in used_sheet_names:
			suffix = f" {counter}"
			name = f"{trimmed[:31 - len(suffix)]}{suffix}"
			counter += 1
		used_sheet_names.add(name)
		return name

	workbook = xlsxwriter.Workbook(out_path)

	title_fmt = workbook.add_format({
		"bold": True,
		"font_size": 24,
		"align": "center",
		"valign": "vcenter",
		"bg_color": "#d8d8d8",
		"border": 2,
	})
	header_fmt = workbook.add_format({
		"bold": True,
		"bg_color": "#d9d9d9",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	set_text_fmt = workbook.add_format({
		"bold": True,
		"bg_color": "#d9d9d9",
		"align": "left",
		"valign": "vcenter",
		"border": 1,
	})
	part_text_fmt = workbook.add_format({
		"bg_color": "#ffffff",
		"align": "left",
		"valign": "vcenter",
		"border": 1,
	})
	set_link_fmt = workbook.add_format({
		"bold": True,
		"bg_color": "#d9d9d9",
		"font_color": "#1155cc",
		"underline": True,
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	part_link_fmt = workbook.add_format({
		"font_color": "#1155cc",
		"underline": True,
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	set_number_fmt = workbook.add_format({
		"bg_color": "#d9d9d9",
		"num_format": "#,##0",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	part_number_fmt = workbook.add_format({
		"bg_color": "#ffffff",
		"num_format": "#,##0",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	set_price_fmt = workbook.add_format({
		"bg_color": "#d9d9d9",
		"num_format": "#,##0.0",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	part_price_fmt = workbook.add_format({
		"bg_color": "#ffffff",
		"num_format": "#,##0.0",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	set_percent_fmt = workbook.add_format({
		"bg_color": "#d9d9d9",
		"num_format": "0.0%",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	part_percent_fmt = workbook.add_format({
		"bg_color": "#ffffff",
		"num_format": "0.0%",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	diff_positive_fmt = workbook.add_format({
		"bg_color": "#c6efce",
		"font_color": "#006100",
		"num_format": "#,##0.0",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	diff_negative_fmt = workbook.add_format({
		"bg_color": "#ffc7ce",
		"font_color": "#9c0006",
		"num_format": "#,##0.0",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	diff_neutral_fmt = workbook.add_format({
		"bg_color": "#d9d9d9",
		"num_format": "#,##0.0",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	part_diff_blank_fmt = workbook.add_format({
		"bg_color": "#ffffff",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	diff_positive_percent_fmt = workbook.add_format({
		"bg_color": "#c6efce",
		"font_color": "#006100",
		"num_format": "0.0%",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	diff_negative_percent_fmt = workbook.add_format({
		"bg_color": "#ffc7ce",
		"font_color": "#9c0006",
		"num_format": "0.0%",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	diff_neutral_percent_fmt = workbook.add_format({
		"bg_color": "#d9d9d9",
		"num_format": "0.0%",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	part_percent_blank_fmt = workbook.add_format({
		"bg_color": "#ffffff",
		"align": "center",
		"valign": "vcenter",
		"border": 1,
	})
	note_fmt = workbook.add_format({"italic": True, "font_color": "#555555"})

	def _write_category_sheet(worksheet, sheet_title: str, rows: List[Dict[str, Any]]) -> None:
		worksheet.freeze_panes(2, 1)
		worksheet.set_zoom(120)
		worksheet.merge_range("B1:N1", ui_text["sheet_title_template"].format(title=sheet_title), title_fmt)
		for col, header in enumerate(headers, start=1):
			worksheet.write(1, col, header, header_fmt)
		worksheet.set_column("B:B", 10)
		worksheet.set_column("C:C", 26)
		worksheet.set_column("D:D", 42)
		worksheet.set_column("E:E", 18)
		worksheet.set_column("F:F", 18)
		worksheet.set_column("G:G", 18)
		worksheet.set_column("H:H", 18)
		worksheet.set_column("I:I", 18)
		worksheet.set_column("J:J", 18)
		worksheet.set_column("K:K", 18)
		worksheet.set_column("L:L", 18)
		worksheet.set_column("M:M", 18)
		worksheet.set_column("N:N", 18)

		row_idx = 2
		for record in rows:
			row_type = record.get("row_type")
			link = record.get("link")
			url_name = record.get("url_name")
			item_name = record.get("item_name")
			volume_val = _sanitize_number(record.get("volume_24h"))
			avg_price_val = _sanitize_number(record.get("avg_price_24h"))
			live_price_val = _sanitize_number(record.get("live_price_avg_top"))
			live_error_val = _sanitize_number(record.get("live_price_err_top"))
			sum_avg_val = _sanitize_number(record.get("sum_parts_avg_24h"))
			sum_live_val = _sanitize_number(record.get("sum_parts_live_top"))
			diff_avg_val = _sanitize_number(record.get("price_diff"))
			pct_avg_val = _sanitize_number(record.get("pct_diff_avg_24h"))
			diff_live_val = _sanitize_number(record.get("live_price_diff"))
			pct_live_val = _sanitize_number(record.get("pct_diff_live_top"))

			text_fmt = set_text_fmt if row_type == "set" else part_text_fmt
			link_fmt = set_link_fmt if row_type == "set" else part_link_fmt
			number_fmt = set_number_fmt if row_type == "set" else part_number_fmt
			price_fmt = set_price_fmt if row_type == "set" else part_price_fmt
			percent_fmt = set_percent_fmt if row_type == "set" else part_percent_fmt

			if link:
				worksheet.write_url(row_idx, 1, link, link_fmt, ui_text["open_label"])
			else:
				worksheet.write_blank(row_idx, 1, None, link_fmt)

			worksheet.write(row_idx, 2, url_name or "", text_fmt)
			worksheet.write(row_idx, 3, item_name or "", text_fmt)

			if volume_val is not None:
				worksheet.write_number(row_idx, 4, volume_val, number_fmt)
			else:
				worksheet.write_blank(row_idx, 4, None, number_fmt)

			if avg_price_val is not None:
				worksheet.write_number(row_idx, 5, avg_price_val, price_fmt)
			else:
				worksheet.write_blank(row_idx, 5, None, price_fmt)

			if live_price_val is not None:
				worksheet.write_number(row_idx, 6, live_price_val, price_fmt)
			else:
				worksheet.write_blank(row_idx, 6, None, price_fmt)

			if live_error_val is not None:
				worksheet.write_number(row_idx, 7, live_error_val, price_fmt)
			else:
				worksheet.write_blank(row_idx, 7, None, price_fmt)

			if sum_avg_val is not None:
				worksheet.write_number(row_idx, 8, sum_avg_val, price_fmt)
			else:
				worksheet.write_blank(row_idx, 8, None, price_fmt)

			if sum_live_val is not None:
				worksheet.write_number(row_idx, 9, sum_live_val, price_fmt)
			else:
				worksheet.write_blank(row_idx, 9, None, price_fmt)

			if row_type == "set" and diff_avg_val is not None:
				diff_fmt = diff_positive_fmt if diff_avg_val >= 0 else diff_negative_fmt
				worksheet.write_number(row_idx, 10, diff_avg_val, diff_fmt)
			else:
				base_fmt = diff_neutral_fmt if row_type == "set" else part_diff_blank_fmt
				worksheet.write_blank(row_idx, 10, None, base_fmt)

			if row_type == "set" and pct_avg_val is not None:
				diff_fmt = diff_positive_percent_fmt if pct_avg_val >= 0 else diff_negative_percent_fmt
				worksheet.write_number(row_idx, 11, pct_avg_val, diff_fmt)
			else:
				base_fmt = diff_neutral_percent_fmt if row_type == "set" else part_percent_blank_fmt
				worksheet.write_blank(row_idx, 11, None, base_fmt)

			if row_type == "set" and diff_live_val is not None:
				diff_fmt = diff_positive_fmt if diff_live_val >= 0 else diff_negative_fmt
				worksheet.write_number(row_idx, 12, diff_live_val, diff_fmt)
			else:
				base_fmt = diff_neutral_fmt if row_type == "set" else part_diff_blank_fmt
				worksheet.write_blank(row_idx, 12, None, base_fmt)

			if row_type == "set" and pct_live_val is not None:
				diff_fmt = diff_positive_percent_fmt if pct_live_val >= 0 else diff_negative_percent_fmt
				worksheet.write_number(row_idx, 13, pct_live_val, diff_fmt)
			else:
				base_fmt = diff_neutral_percent_fmt if row_type == "set" else part_percent_blank_fmt
				worksheet.write_blank(row_idx, 13, None, base_fmt)

			row_idx += 1

		notes_start = row_idx + 1
		for offset, note in enumerate(notes):
			worksheet.write(notes_start + offset, 1, note, note_fmt)

	category_map = OrderedDict((key, []) for key in _CATEGORY_ORDER)
	for record in records:
		category = record.get("category") or "other"
		if category not in category_map:
			category_map[category] = []
		category_map[category].append(record)

	any_sheet_written = False
	for category_key, cat_records in category_map.items():
		if not cat_records:
			continue
		any_sheet_written = True
		sheet_title = ui_text["category_titles"].get(category_key, category_key.title())
		sheet_name = _unique_sheet_name(sheet_title)
		worksheet = workbook.add_worksheet(sheet_name)
		_write_category_sheet(worksheet, sheet_title, cat_records)

	if not any_sheet_written:
		worksheet = workbook.add_worksheet(_unique_sheet_name(ui_text.get("empty_sheet", "Report")))
		worksheet.write(0, 0, ui_text["empty_sheet"], header_fmt)

	workbook.close()

@app.command()
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
		_write_sets_excel(records, out, language=language, live_price_top_n=live_price_top_n)
	else:
		export_df = df.drop(columns=["row_type", "link"]).copy() if "row_type" in df else df
		export_df.to_csv(out, index=False)
	typer.echo(TEXT["saved"].format(out=out))


def _write_mods_excel(
	df: pd.DataFrame,
	out_path: str,
	column_order: List[str],
	headers: List[str],
) -> None:
	import xlsxwriter
	from xlsxwriter.utility import xl_col_to_name

	if df.empty:
		df.to_excel(out_path, index=False)
		return

	key_header_pairs = list(zip(column_order, headers))

	workbook: xlsxwriter.Workbook
	with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
		sheet_name = TEXT.get("mods_sheet_name", "mods")
		df.to_excel(writer, index=False, sheet_name=sheet_name)
		workbook = writer.book
		worksheet = writer.sheets[sheet_name]

		header_fmt = workbook.add_format({
			"bold": True,
			"bg_color": "#1f4e78",
			"font_color": "#ffffff",
			"align": "center",
			"valign": "vcenter",
			"text_wrap": True,
			"bottom": 2,
		})
		worksheet.set_row(0, 24, header_fmt)

		link_fmt = workbook.add_format({"font_color": "#1155CC", "underline": 1})
		number_fmt = workbook.add_format({"num_format": "#,##0.00"})
		int_fmt = workbook.add_format({"num_format": "#,##0"})
		percent_fmt = workbook.add_format({"num_format": '0.00"%"'})

		good_fmt = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"})
		bad_fmt = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})
		min_column_fmt = workbook.add_format({"bg_color": "#FFF5CC", "num_format": "#,##0.00"})
		max_column_fmt = workbook.add_format({"bg_color": "#FDE9D9", "num_format": "#,##0.00"})
		min_price_fmt = workbook.add_format({
			"bg_color": "#F9CB9C",
			"font_color": "#7F6000",
			"bold": True,
			"num_format": "#,##0.00",
		})

		row_count = len(df)
		last_row = row_count
		last_col = len(df.columns) - 1

		worksheet.freeze_panes(1, 2)
		worksheet.autofilter(0, 0, last_row, last_col)
		worksheet.hide_gridlines(0)

		width_map = {
			"link": 9,
			"url_name": 28,
			"item_name": 34,
			"rarity": 14,
			"max_rank": 10,
			"endo_to_max": 16,
			"unranked_min": 14,
			"unranked_avg": 18,
			"unranked_error": 16,
			"unranked_orders": 16,
			"maxed_min": 14,
			"maxed_avg": 18,
			"maxed_error": 16,
			"maxed_orders": 16,
			"price_diff": 16,
			"price_diff_percent": 18,
			"endo_per_platinum": 20,
			"platinum_per_endo": 18,
		}

		currency_columns = {
			"unranked_min",
			"unranked_avg",
			"unranked_error",
			"maxed_min",
			"maxed_avg",
			"maxed_error",
			"price_diff",
			"endo_per_platinum",
			"platinum_per_endo",
		}
		integer_columns = {"endo_to_max", "unranked_orders", "maxed_orders", "max_rank"}
		percent_columns = {"price_diff_percent"}
		highlight_columns = {
			"unranked_min": min_column_fmt,
			"maxed_min": max_column_fmt,
		}

		for col_idx, (key, _) in enumerate(key_header_pairs):
			width = width_map.get(key, 14)
			if key == "link":
				worksheet.set_column(col_idx, col_idx, width)
				continue
			column_format = None
			if key in highlight_columns:
				column_format = highlight_columns[key]
			elif key in percent_columns:
				column_format = percent_fmt
			elif key in integer_columns:
				column_format = int_fmt
			elif key in currency_columns:
				column_format = number_fmt
			worksheet.set_column(col_idx, col_idx, width, column_format)

		open_label = TEXT["open_label"]
		for row_idx, link in enumerate(df.iloc[:, 0], start=1):
			if isinstance(link, str) and link:
				worksheet.write_url(row_idx, 0, link, link_fmt, open_label)

		price_diff_idx = column_order.index("price_diff")
		price_diff_percent_idx = column_order.index("price_diff_percent")
		endo_per_platinum_idx = column_order.index("endo_per_platinum")
		platinum_per_endo_idx = column_order.index("platinum_per_endo")
		unranked_min_idx = column_order.index("unranked_min")
		maxed_min_idx = column_order.index("maxed_min")

		if row_count > 0:
			worksheet.conditional_format(
				1, price_diff_idx, last_row, price_diff_idx,
				{"type": "cell", "criteria": ">", "value": 0, "format": good_fmt},
			)
			worksheet.conditional_format(
				1, price_diff_idx, last_row, price_diff_idx,
				{"type": "cell", "criteria": "<", "value": 0, "format": bad_fmt},
			)
			worksheet.conditional_format(
				1, price_diff_percent_idx, last_row, price_diff_percent_idx,
				{"type": "cell", "criteria": ">", "value": 0, "format": good_fmt},
			)
			worksheet.conditional_format(
				1, price_diff_percent_idx, last_row, price_diff_percent_idx,
				{"type": "cell", "criteria": "<", "value": 0, "format": bad_fmt},
			)
			worksheet.conditional_format(
				1, platinum_per_endo_idx, last_row, platinum_per_endo_idx,
				{
					"type": "3_color_scale",
					"min_color": "#FFC7CE",
					"mid_color": "#FFEB9C",
					"max_color": "#C6EFCE",
				},
			)
			worksheet.conditional_format(
				1, endo_per_platinum_idx, last_row, endo_per_platinum_idx,
				{
					"type": "3_color_scale",
					"min_color": "#C6EFCE",
					"mid_color": "#FFEB9C",
					"max_color": "#FFC7CE",
				},
			)
			min_range_start = 2
			min_range_end = row_count + 1
			for col_idx in (unranked_min_idx, maxed_min_idx):
				col_letter = xl_col_to_name(col_idx)
				worksheet.conditional_format(
					1, col_idx, last_row, col_idx,
					{
						"type": "formula",
						"criteria": f"=${col_letter}{min_range_start}=MIN(${col_letter}${min_range_start}:${col_letter}${min_range_end})",
						"format": min_price_fmt,
					},
				)
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

	column_order = [
		"link",
		"url_name",
		"item_name",
		"rarity",
		"max_rank",
		"endo_to_max",
		"unranked_min",
		"unranked_avg",
		"unranked_error",
		"unranked_orders",
		"maxed_min",
		"maxed_avg",
		"maxed_error",
		"maxed_orders",
		"price_diff",
		"price_diff_percent",
		"endo_per_platinum",
		"platinum_per_endo",
	]

	for column in column_order:
		if column not in df.columns:
			df[column] = None

	rarity_labels = TEXT.get("mods_rarity_labels", {})
	if rarity_labels:
		def _map_rarity(value: Any) -> Any:
			if isinstance(value, str):
				lower = value.lower()
				if lower in rarity_labels:
					return rarity_labels[lower]
				return value.title()
			return value
		df["rarity"] = df["rarity"].apply(_map_rarity)

	headers_template = TEXT.get("mods_headers", [])
	headers = [header.format(n=live_price_top_n) for header in headers_template]
	rename_map = {key: headers[idx] for idx, key in enumerate(column_order) if idx < len(headers)}

	export_df = df[column_order].rename(columns=rename_map)

	if out.endswith(".xlsx"):
		_write_mods_excel(export_df, out, column_order, headers)
	else:
		export_df.to_csv(out, index=False)
	typer.echo(TEXT["saved"].format(out=out))

@app.command()
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
