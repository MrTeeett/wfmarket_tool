from __future__ import annotations

import math
from collections import OrderedDict
from numbers import Number
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import pandas as pd


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


def _unique_sheet_name(base: str, used_names: Set[str]) -> str:
        trimmed = (base or "Report")[:31] or "Sheet"
        name = trimmed
        counter = 2
        while name in used_names:
                suffix = f" {counter}"
                name = f"{trimmed[:31 - len(suffix)]}{suffix}"
                counter += 1
        used_names.add(name)
        return name


def append_sets_sheets(
        workbook,
        records: Iterable[Dict[str, Any]],
        ui_text: Dict[str, Any],
        live_price_top_n: int,
        category_order: Sequence[str],
        used_sheet_names: Optional[Set[str]] = None,
) -> None:
        if used_sheet_names is None:
                used_sheet_names = set()

        headers = [header.format(n=live_price_top_n) for header in ui_text["headers"]]
        notes = [note.format(n=live_price_top_n) for note in ui_text["notes"]]

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

        category_titles = ui_text.get("category_titles", {})
        category_map = OrderedDict((key, []) for key in category_order)

        for record in records:
                category = record.get("category") or "other"
                category_map.setdefault(category, [])
                category_map[category].append(record)

        any_sheet_written = False
        for category_key, cat_records in category_map.items():
                if not cat_records:
                        continue
                any_sheet_written = True
                sheet_title = category_titles.get(category_key, category_key.title())
                sheet_name = _unique_sheet_name(sheet_title, used_sheet_names)
                worksheet = workbook.add_worksheet(sheet_name)

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
                for record in cat_records:
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

        if not any_sheet_written:
                sheet_name = _unique_sheet_name(ui_text.get("empty_sheet", "Report"), used_sheet_names)
                worksheet = workbook.add_worksheet(sheet_name)
                worksheet.write(0, 0, ui_text.get("empty_sheet", "No data"), header_fmt)


def write_sets_excel(
        records: List[Dict[str, Any]],
        out_path: str,
        ui_text: Dict[str, Any],
        live_price_top_n: int,
        category_order: Sequence[str],
) -> None:
        import xlsxwriter

        workbook = xlsxwriter.Workbook(out_path)
        try:
                append_sets_sheets(workbook, records, ui_text, live_price_top_n, category_order)
        finally:
                workbook.close()


def _format_mods_sheet(
        workbook,
        worksheet,
        df: pd.DataFrame,
        column_order: List[str],
        headers: List[str],
        ui_text: Dict[str, Any],
) -> None:
        from xlsxwriter.utility import xl_col_to_name

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

        key_header_pairs = list(zip(column_order, headers))

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

        open_label = ui_text["open_label"]
        for row_idx, link in enumerate(df.iloc[:, 0], start=1):
                if isinstance(link, str) and link:
                        worksheet.write_url(row_idx, 0, link, link_fmt, open_label)

        if row_count > 0:
                price_diff_idx = column_order.index("price_diff")
                price_diff_percent_idx = column_order.index("price_diff_percent")
                endo_per_platinum_idx = column_order.index("endo_per_platinum")
                platinum_per_endo_idx = column_order.index("platinum_per_endo")
                unranked_min_idx = column_order.index("unranked_min")
                maxed_min_idx = column_order.index("maxed_min")

                worksheet.conditional_format(
                        1,
                        price_diff_idx,
                        last_row,
                        price_diff_idx,
                        {"type": "cell", "criteria": ">", "value": 0, "format": good_fmt},
                )
                worksheet.conditional_format(
                        1,
                        price_diff_idx,
                        last_row,
                        price_diff_idx,
                        {"type": "cell", "criteria": "<", "value": 0, "format": bad_fmt},
                )
                worksheet.conditional_format(
                        1,
                        price_diff_percent_idx,
                        last_row,
                        price_diff_percent_idx,
                        {"type": "cell", "criteria": ">", "value": 0, "format": good_fmt},
                )
                worksheet.conditional_format(
                        1,
                        price_diff_percent_idx,
                        last_row,
                        price_diff_percent_idx,
                        {"type": "cell", "criteria": "<", "value": 0, "format": bad_fmt},
                )
                worksheet.conditional_format(
                        1,
                        platinum_per_endo_idx,
                        last_row,
                        platinum_per_endo_idx,
                        {
                                "type": "3_color_scale",
                                "min_color": "#FFC7CE",
                                "mid_color": "#FFEB9C",
                                "max_color": "#C6EFCE",
                        },
                )
                worksheet.conditional_format(
                        1,
                        endo_per_platinum_idx,
                        last_row,
                        endo_per_platinum_idx,
                        {
                                "type": "3_color_scale",
                                "min_color": "#C6EFCE",
                                "mid_color": "#FFEB9C",
                                "max_color": "#FFC7CE",
                        },
                )

                col_letter = xl_col_to_name(unranked_min_idx)
                worksheet.conditional_format(
                        1,
                        unranked_min_idx,
                        last_row,
                        unranked_min_idx,
                        {
                                "type": "formula",
                                "criteria": f"=${col_letter}2=MIN(${col_letter}2:${col_letter}{row_count + 1})",
                                "format": min_price_fmt,
                        },
                )

                col_letter = xl_col_to_name(maxed_min_idx)
                worksheet.conditional_format(
                        1,
                        maxed_min_idx,
                        last_row,
                        maxed_min_idx,
                        {
                                "type": "formula",
                                "criteria": f"=${col_letter}2=MIN(${col_letter}2:${col_letter}{row_count + 1})",
                                "format": max_column_fmt,
                        },
                )


def write_mods_excel(
        df: pd.DataFrame,
        out_path: str,
        column_order: List[str],
        headers: List[str],
        ui_text: Dict[str, Any],
) -> None:
        if df.empty:
                df.to_excel(out_path, index=False)
                return

        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
                sheet_name = ui_text.get("mods_sheet_name", "mods")
                df.to_excel(writer, index=False, sheet_name=sheet_name)
                workbook = writer.book
                worksheet = writer.sheets[sheet_name]
                _format_mods_sheet(workbook, worksheet, df, column_order, headers, ui_text)


def append_mods_sheet(
        writer: pd.ExcelWriter,
        df: pd.DataFrame,
        column_order: List[str],
        headers: List[str],
        ui_text: Dict[str, Any],
        used_sheet_names: Set[str],
) -> Optional[str]:
        sheet_name = ui_text.get("mods_sheet_name", "mods")
        sheet_name = _unique_sheet_name(sheet_name, used_sheet_names)
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        _format_mods_sheet(workbook, worksheet, df, column_order, headers, ui_text)
        return sheet_name


def append_endo_sheet(
        writer: pd.ExcelWriter,
        df: pd.DataFrame,
        ui_text: Dict[str, Any],
        used_sheet_names: Set[str],
) -> Optional[str]:
        sheet_name = ui_text.get("endo_sheet_name", "endo")
        sheet_name = _unique_sheet_name(sheet_name, used_sheet_names)
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        return sheet_name


def write_combined_excel(
        out_path: str,
        sets_records: List[Dict[str, Any]],
        mods_df: Optional[pd.DataFrame],
        endo_df: Optional[pd.DataFrame],
        ui_text: Dict[str, Any],
        live_price_top_n: int,
        category_order: Sequence[str],
        column_order: List[str],
        headers: List[str],
) -> None:
        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
                workbook = writer.book
                used_sheet_names: Set[str] = set()
                append_sets_sheets(workbook, sets_records, ui_text, live_price_top_n, category_order, used_sheet_names)

                if mods_df is not None and not mods_df.empty:
                        append_mods_sheet(writer, mods_df, column_order, headers, ui_text, used_sheet_names)
                elif mods_df is not None:
                        # still create an empty sheet to keep structure predictable
                        sheet_name = ui_text.get("mods_sheet_name", "mods")
                        sheet_name = _unique_sheet_name(sheet_name, used_sheet_names)
                        mods_df.to_excel(writer, index=False, sheet_name=sheet_name)

                if endo_df is not None and not endo_df.empty:
                        append_endo_sheet(writer, endo_df, ui_text, used_sheet_names)
                elif endo_df is not None:
                        sheet_name = ui_text.get("endo_sheet_name", "endo")
                        sheet_name = _unique_sheet_name(sheet_name, used_sheet_names)
                        endo_df.to_excel(writer, index=False, sheet_name=sheet_name)
