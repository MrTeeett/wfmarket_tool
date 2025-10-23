from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets

from wfmarket.analyzers import build_mods_report, build_sets_report, riven_endo_candidates
from wfmarket.config import CONFIG_PATH, load_config, save_config
from wfmarket.constants import CATEGORY_ORDER, MODS_COLUMN_ORDER
from wfmarket.exporters import write_combined_excel, write_mods_excel, write_sets_excel
from wfmarket.i18n import available_languages, get_ui_strings, normalize_language
from wfmarket.reports import prepare_mods_export
from wfmarket.util import set_rate_delay


@dataclass
class ReportOptions:
        platform: str
        language: str
        only_online: bool
        live_price_top_n: int
        filter_contains: Optional[str] = None
        limit_items: Optional[int] = None
        fetch_part_statistics: bool = True
        rarities: Optional[list[str]] = None
        min_mastery: Optional[int] = None
        min_mod_rank: Optional[int] = None


class ReportWorker(QtCore.QObject):
        progress = QtCore.pyqtSignal(float)
        message = QtCore.pyqtSignal(str)
        finished = QtCore.pyqtSignal(bool, str)
        error = QtCore.pyqtSignal(str)

        def __init__(self, job: str, options: Dict[str, Any], ui_text: Dict[str, Any]):
                super().__init__()
                self.job = job
                self.options = options
                self.ui_text = ui_text

        def run(self) -> None:
                try:
                        if self.job == "sets":
                                self._run_sets()
                        elif self.job == "mods":
                                self._run_mods()
                        elif self.job == "endo":
                                self._run_endo()
                        elif self.job == "all":
                                self._run_all()
                        else:
                                raise ValueError(f"Unknown job: {self.job}")
                except Exception as exc:  # pragma: no cover - run in UI
                        self.error.emit(str(exc))
                        self.finished.emit(False, "")

        # Helpers -----------------------------------------------------------------

        def _sets_progress(self, stage: str, done: int, total: int, _remaining: float, *, base: float = 0.0, weight: float = 1.0) -> None:
                if total <= 0:
                        return
                stages = ["scan", "calc"]
                try:
                        stage_index = stages.index(stage)
                except ValueError:
                        stage_index = 0
                fraction = (stage_index + min(max(done / total, 0.0), 1.0)) / len(stages)
                overall = base + fraction * weight
                self.progress.emit(min(max(overall, 0.0), 1.0))

        def _run_sets(self) -> None:
                opts: ReportOptions = self.options["sets"]
                out_path: Path = Path(self.options["out"])

                def callback(stage: str, done: int, total: int, remaining: float) -> None:
                        self._sets_progress(stage, done, total, remaining)

                df = build_sets_report(
                        platform=opts.platform,
                        language=opts.language,
                        filter_contains=opts.filter_contains,
                        only_online=opts.only_online,
                        limit_sets=opts.limit_items,
                        fetch_part_statistics=opts.fetch_part_statistics,
                        live_price_top_n=opts.live_price_top_n,
                        progress_callback=callback,
                )
                records = df.to_dict("records")
                if not records:
                        self.message.emit(self.ui_text["no_results"])
                        self.finished.emit(False, "")
                        return

                if out_path.suffix.lower() == ".xlsx":
                        write_sets_excel(records, str(out_path), self.ui_text, opts.live_price_top_n, CATEGORY_ORDER)
                else:
                        export_df = df.drop(columns=["row_type", "link"]).copy() if "row_type" in df else df
                        export_df.to_csv(out_path, index=False)
                self.finished.emit(True, str(out_path))

        def _run_mods(self) -> None:
                opts: ReportOptions = self.options["mods"]
                out_path: Path = Path(self.options["out"])

                def callback(done: int, total: int, _name: str) -> None:
                        if total > 0:
                                self.progress.emit(min(max(done / total, 0.0), 1.0))

                df = build_mods_report(
                        platform=opts.platform,
                        language=opts.language,
                        rarity_filter=opts.rarities,
                        only_online=opts.only_online,
                        top_n=opts.live_price_top_n,
                        filter_contains=opts.filter_contains,
                        limit_items=opts.limit_items,
                        progress_callback=callback,
                )
                if df.empty:
                        self.message.emit(self.ui_text["no_results"])
                        self.finished.emit(False, "")
                        return

                export_df, column_order, headers = prepare_mods_export(df, self.ui_text, opts.live_price_top_n)
                if out_path.suffix.lower() == ".xlsx":
                        write_mods_excel(export_df, str(out_path), column_order, headers, self.ui_text)
                else:
                        export_df.to_csv(out_path, index=False)
                self.finished.emit(True, str(out_path))

        def _run_endo(self) -> None:
                opts: ReportOptions = self.options["endo"]
                out_path: Path = Path(self.options["out"])
                df = riven_endo_candidates(
                        platform=opts.platform,
                        language=opts.language,
                        min_mastery=opts.min_mastery or 0,
                        min_mod_rank=opts.min_mod_rank or 0,
                        only_online=opts.only_online,
                        limit_items=opts.limit_items,
                        endo_table=self.options.get("endo_table"),
                )
                if df.empty:
                        self.message.emit(self.ui_text["no_results"])
                        self.finished.emit(False, "")
                        return
                if out_path.suffix.lower() == ".xlsx":
                        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
                                df.to_excel(writer, index=False, sheet_name=self.ui_text.get("endo_sheet_name", "endo"))
                else:
                        df.to_csv(out_path, index=False)
                self.finished.emit(True, str(out_path))

        def _run_all(self) -> None:
                sets_opts: ReportOptions = self.options["sets"]
                mods_opts: ReportOptions = self.options["mods"]
                endo_opts: ReportOptions = self.options["endo"]
                out_path: Path = Path(self.options["out"])

                sets_weight = 0.5
                mods_weight = 0.3
                endo_weight = 0.2

                def sets_callback(stage: str, done: int, total: int, remaining: float) -> None:
                        self._sets_progress(stage, done, total, remaining, base=0.0, weight=sets_weight)

                df_sets = build_sets_report(
                        platform=sets_opts.platform,
                        language=sets_opts.language,
                        filter_contains=sets_opts.filter_contains,
                        only_online=sets_opts.only_online,
                        limit_sets=sets_opts.limit_items,
                        fetch_part_statistics=sets_opts.fetch_part_statistics,
                        live_price_top_n=sets_opts.live_price_top_n,
                        progress_callback=sets_callback,
                )
                set_records = df_sets.to_dict("records")
                if not set_records:
                        self.message.emit(self.ui_text["no_results"])
                        self.finished.emit(False, "")
                        return

                def mods_callback(done: int, total: int, _name: str) -> None:
                        if total > 0:
                                fraction = min(max(done / total, 0.0), 1.0)
                                self.progress.emit(sets_weight + fraction * mods_weight)

                df_mods = build_mods_report(
                        platform=mods_opts.platform,
                        language=mods_opts.language,
                        rarity_filter=mods_opts.rarities,
                        only_online=mods_opts.only_online,
                        top_n=mods_opts.live_price_top_n,
                        filter_contains=mods_opts.filter_contains,
                        limit_items=mods_opts.limit_items,
                        progress_callback=mods_callback,
                )
                if df_mods.empty:
                        self.message.emit(self.ui_text["no_results"])
                        self.finished.emit(False, "")
                        return
                export_mods, column_order, headers = prepare_mods_export(df_mods, self.ui_text, mods_opts.live_price_top_n)

                self.progress.emit(sets_weight + mods_weight)

                df_endo = riven_endo_candidates(
                        platform=endo_opts.platform,
                        language=endo_opts.language,
                        min_mastery=endo_opts.min_mastery or 0,
                        min_mod_rank=endo_opts.min_mod_rank or 0,
                        only_online=endo_opts.only_online,
                        limit_items=endo_opts.limit_items,
                        endo_table=self.options.get("endo_table"),
                )

                self.progress.emit(sets_weight + mods_weight + endo_weight * 0.5)

                write_combined_excel(
                        str(out_path),
                        set_records,
                        export_mods,
                        df_endo,
                        self.ui_text,
                        sets_opts.live_price_top_n,
                        CATEGORY_ORDER,
                        column_order,
                        headers,
                )
                self.progress.emit(1.0)
                self.finished.emit(True, str(out_path))


class MainWindow(QtWidgets.QWidget):
        def __init__(self) -> None:
                super().__init__()
                self.setWindowTitle("Warframe Market Toolkit")
                self.config = load_config(CONFIG_PATH)
                self.available_langs = available_languages()
                self.current_language = normalize_language(
                        self.config.get("ui_language") or self.config.get("language")
                )
                self.ui_text = get_ui_strings(self.current_language)

                self.sets_path_edit: QtWidgets.QLineEdit
                self.mods_path_edit: QtWidgets.QLineEdit
                self.endo_path_edit: QtWidgets.QLineEdit
                self.all_path_edit: QtWidgets.QLineEdit
                self.progress_bar: QtWidgets.QProgressBar
                self.log_output: QtWidgets.QPlainTextEdit
                self.status_label: QtWidgets.QLabel
                self.language_combo: QtWidgets.QComboBox
                self.rate_spin: QtWidgets.QDoubleSpinBox
                self.platform_combo: QtWidgets.QComboBox
                self.platform_label: QtWidgets.QLabel

                self.sets_group: QtWidgets.QGroupBox
                self.mods_group: QtWidgets.QGroupBox
                self.endo_group: QtWidgets.QGroupBox
                self.general_group: QtWidgets.QGroupBox
                self.paths_group: QtWidgets.QGroupBox

                self.sets_only_online_check: QtWidgets.QCheckBox
                self.sets_filter_edit: QtWidgets.QLineEdit
                self.sets_limit_spin: QtWidgets.QSpinBox
                self.sets_live_spin: QtWidgets.QSpinBox
                self.sets_fetch_stats_check: QtWidgets.QCheckBox
                self.sets_filter_label: QtWidgets.QLabel
                self.sets_limit_label: QtWidgets.QLabel
                self.sets_live_label: QtWidgets.QLabel

                self.mods_only_online_check: QtWidgets.QCheckBox
                self.mods_filter_edit: QtWidgets.QLineEdit
                self.mods_limit_spin: QtWidgets.QSpinBox
                self.mods_live_spin: QtWidgets.QSpinBox
                self.mods_rarity_edit: QtWidgets.QLineEdit
                self.mods_filter_label: QtWidgets.QLabel
                self.mods_limit_label: QtWidgets.QLabel
                self.mods_live_label: QtWidgets.QLabel
                self.mods_rarity_label: QtWidgets.QLabel

                self.endo_only_online_check: QtWidgets.QCheckBox
                self.endo_limit_spin: QtWidgets.QSpinBox
                self.endo_min_mastery_spin: QtWidgets.QSpinBox
                self.endo_min_rank_spin: QtWidgets.QSpinBox
                self.endo_limit_label: QtWidgets.QLabel
                self.endo_min_mastery_label: QtWidgets.QLabel
                self.endo_min_rank_label: QtWidgets.QLabel

                self._thread: Optional[QtCore.QThread] = None
                self._worker: Optional[ReportWorker] = None

                self._build_ui()
                self._apply_texts()
                self._apply_runtime_settings()

        # UI Construction -------------------------------------------------------

        def _build_ui(self) -> None:
                layout = QtWidgets.QVBoxLayout(self)

                limits_cfg = self.config.get("limits", {})
                sets_cfg = self.config.get("sets", {})
                mods_cfg = self.config.get("mods", {})
                endo_cfg = self.config.get("endo", {})
                gui_cfg = self.config.get("gui", {})

                self.tab_widget = QtWidgets.QTabWidget()
                layout.addWidget(self.tab_widget)

                # General settings -------------------------------------------------
                self.general_group = QtWidgets.QGroupBox()
                general_layout = QtWidgets.QGridLayout(self.general_group)

                self.language_label = QtWidgets.QLabel("language_label")
                self.language_label.setObjectName("language_label")
                self.language_combo = QtWidgets.QComboBox()
                for code, data in self.available_langs.items():
                        label = data.get("gui", {}).get("language_label", code)
                        display = "English" if code == "en" else "Русский" if code == "ru" else code.upper()
                        self.language_combo.addItem(display, code)
                        if code == self.current_language:
                                self.language_combo.setCurrentIndex(self.language_combo.count() - 1)
                self.language_combo.currentIndexChanged.connect(self._on_language_changed)

                general_layout.addWidget(self.language_label, 0, 0)
                general_layout.addWidget(self.language_combo, 0, 1)

                self.platform_label = QtWidgets.QLabel("platform_label")
                self.platform_label.setObjectName("platform_label")
                self.platform_combo = QtWidgets.QComboBox()
                platform_options = [
                        ("pc", "PC"),
                        ("ps4", "PS4"),
                        ("xbox", "Xbox"),
                        ("switch", "Switch"),
                ]
                current_platform = str(self.config.get("platform", "pc")).lower()
                for code, display in platform_options:
                        self.platform_combo.addItem(display, code)
                        if code == current_platform:
                                self.platform_combo.setCurrentIndex(self.platform_combo.count() - 1)

                general_layout.addWidget(self.platform_label, 1, 0)
                general_layout.addWidget(self.platform_combo, 1, 1)

                self.rate_label = QtWidgets.QLabel("rate_delay_label")
                self.rate_label.setObjectName("rate_delay_label")
                self.rate_spin = QtWidgets.QDoubleSpinBox()
                self.rate_spin.setMinimum(0.0)
                self.rate_spin.setMaximum(5.0)
                self.rate_spin.setSingleStep(0.05)
                self.rate_spin.setValue(float(limits_cfg.get("rate_delay", 0.35)))
                self.rate_spin.valueChanged.connect(lambda _value: self._apply_runtime_settings())
                general_layout.addWidget(self.rate_label, 2, 0)
                general_layout.addWidget(self.rate_spin, 2, 1)

                general_tab = QtWidgets.QWidget()
                general_tab_layout = QtWidgets.QVBoxLayout(general_tab)
                general_tab_layout.addWidget(self.general_group)
                general_tab_layout.addStretch(1)
                self.general_tab_index = self.tab_widget.addTab(general_tab, "")

                # Sets report settings ---------------------------------------------
                self.sets_group = QtWidgets.QGroupBox()
                sets_layout = QtWidgets.QFormLayout(self.sets_group)
                self.sets_only_online_check = QtWidgets.QCheckBox()
                self.sets_only_online_check.setChecked(bool(sets_cfg.get("only_online", False)))
                sets_layout.addRow(self.sets_only_online_check)

                self.sets_filter_label = QtWidgets.QLabel("sets_filter")
                self.sets_filter_edit = QtWidgets.QLineEdit(str(sets_cfg.get("filter_contains", "")))
                sets_layout.addRow(self.sets_filter_label, self.sets_filter_edit)

                self.sets_limit_label = QtWidgets.QLabel("sets_limit")
                self.sets_limit_spin = QtWidgets.QSpinBox()
                self.sets_limit_spin.setMinimum(0)
                self.sets_limit_spin.setMaximum(10000)
                limit_sets = sets_cfg.get("limit_sets")
                self.sets_limit_spin.setValue(int(limit_sets) if isinstance(limit_sets, int) and limit_sets > 0 else 0)
                sets_layout.addRow(self.sets_limit_label, self.sets_limit_spin)

                self.sets_fetch_stats_check = QtWidgets.QCheckBox()
                self.sets_fetch_stats_check.setChecked(bool(sets_cfg.get("fetch_part_statistics", True)))
                sets_layout.addRow(self.sets_fetch_stats_check)

                self.sets_live_label = QtWidgets.QLabel("sets_live_top")
                self.sets_live_spin = QtWidgets.QSpinBox()
                self.sets_live_spin.setMinimum(1)
                self.sets_live_spin.setMaximum(10)
                self.sets_live_spin.setValue(int(sets_cfg.get("live_price_top_n", 4) or 1))
                sets_layout.addRow(self.sets_live_label, self.sets_live_spin)

                sets_tab = QtWidgets.QWidget()
                sets_tab_layout = QtWidgets.QVBoxLayout(sets_tab)
                sets_tab_layout.addWidget(self.sets_group)
                sets_tab_layout.addStretch(1)
                self.sets_tab_index = self.tab_widget.addTab(sets_tab, "")

                # Mods report settings ---------------------------------------------
                self.mods_group = QtWidgets.QGroupBox()
                mods_layout = QtWidgets.QFormLayout(self.mods_group)
                self.mods_only_online_check = QtWidgets.QCheckBox()
                self.mods_only_online_check.setChecked(bool(mods_cfg.get("only_online", False)))
                mods_layout.addRow(self.mods_only_online_check)

                self.mods_filter_label = QtWidgets.QLabel("mods_filter")
                self.mods_filter_edit = QtWidgets.QLineEdit(str(mods_cfg.get("filter_contains", "")))
                mods_layout.addRow(self.mods_filter_label, self.mods_filter_edit)

                self.mods_limit_label = QtWidgets.QLabel("mods_limit")
                self.mods_limit_spin = QtWidgets.QSpinBox()
                self.mods_limit_spin.setMinimum(0)
                self.mods_limit_spin.setMaximum(10000)
                limit_mods = mods_cfg.get("limit_items")
                self.mods_limit_spin.setValue(int(limit_mods) if isinstance(limit_mods, int) and limit_mods > 0 else 0)
                mods_layout.addRow(self.mods_limit_label, self.mods_limit_spin)

                self.mods_live_label = QtWidgets.QLabel("mods_live_top")
                self.mods_live_spin = QtWidgets.QSpinBox()
                self.mods_live_spin.setMinimum(1)
                self.mods_live_spin.setMaximum(10)
                self.mods_live_spin.setValue(int(mods_cfg.get("live_price_top_n", 3) or 1))
                mods_layout.addRow(self.mods_live_label, self.mods_live_spin)

                self.mods_rarity_label = QtWidgets.QLabel("mods_rarities")
                rarities = mods_cfg.get("rarities")
                rarity_text = ", ".join(str(r) for r in rarities) if isinstance(rarities, list) else ""
                self.mods_rarity_edit = QtWidgets.QLineEdit(rarity_text)
                mods_layout.addRow(self.mods_rarity_label, self.mods_rarity_edit)

                mods_tab = QtWidgets.QWidget()
                mods_tab_layout = QtWidgets.QVBoxLayout(mods_tab)
                mods_tab_layout.addWidget(self.mods_group)
                mods_tab_layout.addStretch(1)
                self.mods_tab_index = self.tab_widget.addTab(mods_tab, "")

                # Endo report settings ---------------------------------------------
                self.endo_group = QtWidgets.QGroupBox()
                endo_layout = QtWidgets.QFormLayout(self.endo_group)
                self.endo_only_online_check = QtWidgets.QCheckBox()
                self.endo_only_online_check.setChecked(bool(endo_cfg.get("only_online", False)))
                endo_layout.addRow(self.endo_only_online_check)

                self.endo_limit_label = QtWidgets.QLabel("endo_limit")
                self.endo_limit_spin = QtWidgets.QSpinBox()
                self.endo_limit_spin.setMinimum(0)
                self.endo_limit_spin.setMaximum(10000)
                limit_endo = endo_cfg.get("limit_items")
                self.endo_limit_spin.setValue(int(limit_endo) if isinstance(limit_endo, int) and limit_endo > 0 else 0)
                endo_layout.addRow(self.endo_limit_label, self.endo_limit_spin)

                self.endo_min_mastery_label = QtWidgets.QLabel("endo_min_mastery")
                self.endo_min_mastery_spin = QtWidgets.QSpinBox()
                self.endo_min_mastery_spin.setMinimum(0)
                self.endo_min_mastery_spin.setMaximum(30)
                self.endo_min_mastery_spin.setValue(int(endo_cfg.get("min_mastery", 8)))
                endo_layout.addRow(self.endo_min_mastery_label, self.endo_min_mastery_spin)

                self.endo_min_rank_label = QtWidgets.QLabel("endo_min_rank")
                self.endo_min_rank_spin = QtWidgets.QSpinBox()
                self.endo_min_rank_spin.setMinimum(0)
                self.endo_min_rank_spin.setMaximum(10)
                self.endo_min_rank_spin.setValue(int(endo_cfg.get("min_mod_rank", 8)))
                endo_layout.addRow(self.endo_min_rank_label, self.endo_min_rank_spin)

                endo_tab = QtWidgets.QWidget()
                endo_tab_layout = QtWidgets.QVBoxLayout(endo_tab)
                endo_tab_layout.addWidget(self.endo_group)
                endo_tab_layout.addStretch(1)
                self.endo_tab_index = self.tab_widget.addTab(endo_tab, "")

                # Output paths -----------------------------------------------------
                self.paths_group = QtWidgets.QGroupBox()
                paths_layout = QtWidgets.QGridLayout(self.paths_group)

                self.sets_path_edit = QtWidgets.QLineEdit(str(Path(sets_cfg.get("out", "warframe_market_sets.xlsx"))))
                self.mods_path_edit = QtWidgets.QLineEdit(str(Path(mods_cfg.get("out", "mod_prices.xlsx"))))
                self.endo_path_edit = QtWidgets.QLineEdit(str(Path(endo_cfg.get("out", "endo_candidates.xlsx"))))
                self.all_path_edit = QtWidgets.QLineEdit(str(gui_cfg.get("all_out", "warframe_market_reports.xlsx")))

                self._add_path_row(paths_layout, 0, "sets_output", self.sets_path_edit, self._choose_sets_path)
                self._add_path_row(paths_layout, 1, "mods_output", self.mods_path_edit, self._choose_mods_path)
                self._add_path_row(paths_layout, 2, "endo_output", self.endo_path_edit, self._choose_endo_path)
                self._add_path_row(paths_layout, 3, "all_output", self.all_path_edit, self._choose_all_path)

                paths_tab = QtWidgets.QWidget()
                paths_tab_layout = QtWidgets.QVBoxLayout(paths_tab)
                paths_tab_layout.addWidget(self.paths_group)
                paths_tab_layout.addStretch(1)
                self.paths_tab_index = self.tab_widget.addTab(paths_tab, "")

                buttons_layout = QtWidgets.QGridLayout()
                self.generate_sets_btn = QtWidgets.QPushButton()
                self.generate_sets_btn.clicked.connect(self._on_generate_sets)
                buttons_layout.addWidget(self.generate_sets_btn, 0, 0)

                self.generate_mods_btn = QtWidgets.QPushButton()
                self.generate_mods_btn.clicked.connect(self._on_generate_mods)
                buttons_layout.addWidget(self.generate_mods_btn, 0, 1)

                self.generate_endo_btn = QtWidgets.QPushButton()
                self.generate_endo_btn.clicked.connect(self._on_generate_endo)
                buttons_layout.addWidget(self.generate_endo_btn, 1, 0)

                self.generate_all_btn = QtWidgets.QPushButton()
                self.generate_all_btn.clicked.connect(self._on_generate_all)
                buttons_layout.addWidget(self.generate_all_btn, 1, 1)

                layout.addLayout(buttons_layout)

                self.progress_bar = QtWidgets.QProgressBar()
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(0)
                layout.addWidget(self.progress_bar)

                self.status_label = QtWidgets.QLabel()
                layout.addWidget(self.status_label)

                self.log_output = QtWidgets.QPlainTextEdit()
                self.log_output.setReadOnly(True)
                layout.addWidget(self.log_output)

                self.setLayout(layout)

        def _add_path_row(self, layout: QtWidgets.QGridLayout, row: int, label_key: str, edit: QtWidgets.QLineEdit, handler) -> None:
                label = QtWidgets.QLabel(label_key)
                label.setObjectName(label_key)
                button = QtWidgets.QPushButton("...")
                button.clicked.connect(handler)
                layout.addWidget(label, row, 0)
                layout.addWidget(edit, row, 1)
                layout.addWidget(button, row, 2)

        # Event handlers --------------------------------------------------------

        def _on_language_changed(self) -> None:
                code = self.language_combo.currentData()
                self.current_language = normalize_language(code)
                self.ui_text = get_ui_strings(self.current_language)
                self.config["language"] = self.current_language
                self.config["ui_language"] = self.current_language
                self._apply_texts()

        def _choose_sets_path(self) -> None:
                self._choose_path(self.sets_path_edit)

        def _choose_mods_path(self) -> None:
                self._choose_path(self.mods_path_edit)

        def _choose_endo_path(self) -> None:
                self._choose_path(self.endo_path_edit)

        def _choose_all_path(self) -> None:
                self._choose_path(self.all_path_edit)

        def _choose_path(self, edit: QtWidgets.QLineEdit) -> None:
                dialog_title = self.ui_text.get("gui", {}).get("dialog_title", "Select output file")
                filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, dialog_title, edit.text())
                if filename:
                        edit.setText(filename)

        def _apply_texts(self) -> None:
                gui_text = self.ui_text.get("gui", {})
                self.setWindowTitle(gui_text.get("title", "Warframe Market Toolkit"))

                self.general_group.setTitle(gui_text.get("general_settings", "General settings"))
                self.paths_group.setTitle(gui_text.get("paths_settings", "Output files"))
                self.sets_group.setTitle(gui_text.get("sets_settings", "Prime sets"))
                self.mods_group.setTitle(gui_text.get("mods_settings", "Mods"))
                self.endo_group.setTitle(gui_text.get("endo_settings", "Endo candidates"))

                if hasattr(self, "tab_widget"):
                        self.tab_widget.setTabText(self.general_tab_index, self.general_group.title())
                        self.tab_widget.setTabText(self.sets_tab_index, self.sets_group.title())
                        self.tab_widget.setTabText(self.mods_tab_index, self.mods_group.title())
                        self.tab_widget.setTabText(self.endo_tab_index, self.endo_group.title())
                        self.tab_widget.setTabText(self.paths_tab_index, self.paths_group.title())

                self.language_label.setText(gui_text.get("language_label", "Interface language"))
                self.rate_label.setText(gui_text.get("rate_delay_label", "Rate delay"))
                self.platform_label.setText(gui_text.get("platform_label", "Platform"))

                filter_placeholder = gui_text.get("filter_placeholder", "")
                rarities_placeholder = gui_text.get("rarities_placeholder", "")
                unlimited_text = gui_text.get("limit_unlimited", "Unlimited")

                self.sets_only_online_check.setText(gui_text.get("only_online", "Only online sellers"))
                self.sets_filter_label.setText(gui_text.get("filter_contains", "Name filter"))
                self.sets_filter_edit.setPlaceholderText(filter_placeholder)
                self.sets_limit_label.setText(gui_text.get("limit_sets", "Set limit"))
                self.sets_limit_spin.setSpecialValueText(unlimited_text)
                self.sets_fetch_stats_check.setText(gui_text.get("fetch_part_statistics", "Fetch part statistics"))
                self.sets_live_label.setText(gui_text.get("live_price_top_n", "Live price top-N"))

                self.mods_only_online_check.setText(gui_text.get("only_online", "Only online sellers"))
                self.mods_filter_label.setText(gui_text.get("filter_contains", "Name filter"))
                self.mods_filter_edit.setPlaceholderText(filter_placeholder)
                self.mods_limit_label.setText(gui_text.get("limit_items", "Item limit"))
                self.mods_limit_spin.setSpecialValueText(unlimited_text)
                self.mods_live_label.setText(gui_text.get("live_price_top_n", "Live price top-N"))
                self.mods_rarity_label.setText(gui_text.get("rarities", "Rarities"))
                self.mods_rarity_edit.setPlaceholderText(rarities_placeholder)

                self.endo_only_online_check.setText(gui_text.get("only_online", "Only online sellers"))
                self.endo_limit_label.setText(gui_text.get("limit_items", "Item limit"))
                self.endo_limit_spin.setSpecialValueText(unlimited_text)
                self.endo_min_mastery_label.setText(gui_text.get("min_mastery", "Min. mastery rank"))
                self.endo_min_rank_label.setText(gui_text.get("min_mod_rank", "Min. mod rank"))

                for key in ("sets_output", "mods_output", "endo_output", "all_output"):
                        label = self.findChild(QtWidgets.QLabel, key)
                        if label is not None:
                                label.setText(gui_text.get(key, key))

                self.generate_sets_btn.setText(gui_text.get("generate_sets", "Generate sets report"))
                self.generate_mods_btn.setText(gui_text.get("generate_mods", "Generate mods report"))
                self.generate_endo_btn.setText(gui_text.get("generate_endo", "Generate Endo report"))
                self.generate_all_btn.setText(gui_text.get("generate_all", "Generate all reports"))

                self.status_label.setText(gui_text.get("progress_idle", "Idle"))
                if not self.log_output.toPlainText():
                        self.log_output.setPlaceholderText(gui_text.get("log_placeholder", "Messages will appear here."))

        def _apply_runtime_settings(self) -> None:
                try:
                        set_rate_delay(float(self.rate_spin.value()))
                except (TypeError, ValueError):
                        pass

        # Logging and progress --------------------------------------------------

        def _log(self, message: str) -> None:
                self.log_output.appendPlainText(message)

        def _on_worker_progress(self, value: float) -> None:
                self.progress_bar.setValue(int(max(0.0, min(1.0, value)) * 100))

        def _on_worker_error(self, message: str) -> None:
                gui_text = self.ui_text.get("gui", {})
                formatted = gui_text.get("status_error", "Error: {error}").format(error=message)
                self._log(formatted)
                QtWidgets.QMessageBox.critical(self, gui_text.get("title", "Warframe Market Toolkit"), formatted)

        def _on_worker_finished(self, success: bool, path: str) -> None:
                gui_text = self.ui_text.get("gui", {})
                self._thread = None
                self._worker = None
                self._set_controls_enabled(True)
                if success and path:
                                self.progress_bar.setValue(100)
                                status = gui_text.get("status_saved", "Saved to {path}").format(path=path)
                                self.status_label.setText(status)
                                self._log(status)
                else:
                        self.status_label.setText(gui_text.get("progress_idle", "Idle"))

        # Generate handlers -----------------------------------------------------

        def _on_generate_sets(self) -> None:
                options = self._build_sets_options()
                self._start_worker("sets", {"sets": options, "out": self.sets_path_edit.text()})

        def _on_generate_mods(self) -> None:
                options = self._build_mods_options()
                self._start_worker("mods", {"mods": options, "out": self.mods_path_edit.text()})

        def _on_generate_endo(self) -> None:
                options = self._build_endo_options()
                payload = {
                        "endo": options,
                        "out": self.endo_path_edit.text(),
                        "endo_table": self.config.get("endo_table"),
                }
                self._start_worker("endo", payload)

        def _on_generate_all(self) -> None:
                payload = {
                        "sets": self._build_sets_options(),
                        "mods": self._build_mods_options(),
                        "endo": self._build_endo_options(),
                        "endo_table": self.config.get("endo_table"),
                        "out": self.all_path_edit.text(),
                }
                self._start_worker("all", payload)

        # Worker orchestration --------------------------------------------------

        def _start_worker(self, job: str, payload: Dict[str, Any]) -> None:
                if self._thread is not None:
                        return
                self._persist_settings()
                self._set_controls_enabled(False)
                self.progress_bar.setValue(0)
                self.status_label.setText(self.ui_text.get("gui", {}).get("progress_working", "Working…"))

                worker = ReportWorker(job, payload, self.ui_text)
                thread = QtCore.QThread(self)
                worker.moveToThread(thread)
                thread.started.connect(worker.run)
                worker.progress.connect(self._on_worker_progress)
                worker.message.connect(self._log)
                worker.error.connect(self._on_worker_error)
                worker.finished.connect(self._on_worker_finished)
                worker.finished.connect(thread.quit)
                worker.finished.connect(worker.deleteLater)
                thread.finished.connect(thread.deleteLater)
                thread.start()
                self._thread = thread
                self._worker = worker

        def _set_controls_enabled(self, enabled: bool) -> None:
                for widget in (
                        self.generate_sets_btn,
                        self.generate_mods_btn,
                        self.generate_endo_btn,
                        self.generate_all_btn,
                        self.language_combo,
                        self.platform_combo,
                        self.rate_spin,
                        self.sets_path_edit,
                        self.mods_path_edit,
                        self.endo_path_edit,
                        self.all_path_edit,
                        self.sets_only_online_check,
                        self.sets_filter_edit,
                        self.sets_limit_spin,
                        self.sets_live_spin,
                        self.sets_fetch_stats_check,
                        self.mods_only_online_check,
                        self.mods_filter_edit,
                        self.mods_limit_spin,
                        self.mods_live_spin,
                        self.mods_rarity_edit,
                        self.endo_only_online_check,
                        self.endo_limit_spin,
                        self.endo_min_mastery_spin,
                        self.endo_min_rank_spin,
                ):
                        widget.setEnabled(enabled)

        # Option builders -------------------------------------------------------

        def _build_sets_options(self) -> ReportOptions:
                filter_text = self.sets_filter_edit.text().strip()
                limit_value = int(self.sets_limit_spin.value())
                return ReportOptions(
                        platform=str(self.platform_combo.currentData() or "pc"),
                        language=self.current_language,
                        only_online=self.sets_only_online_check.isChecked(),
                        live_price_top_n=int(self.sets_live_spin.value()),
                        filter_contains=filter_text or None,
                        limit_items=limit_value if limit_value > 0 else None,
                        fetch_part_statistics=self.sets_fetch_stats_check.isChecked(),
                )

        def _build_mods_options(self) -> ReportOptions:
                filter_text = self.mods_filter_edit.text().strip()
                limit_value = int(self.mods_limit_spin.value())
                raw_rarities = [part.strip().lower() for part in self.mods_rarity_edit.text().split(",") if part.strip()]
                rarities = raw_rarities if raw_rarities else None
                return ReportOptions(
                        platform=str(self.platform_combo.currentData() or "pc"),
                        language=self.current_language,
                        only_online=self.mods_only_online_check.isChecked(),
                        live_price_top_n=int(self.mods_live_spin.value()),
                        filter_contains=filter_text or None,
                        limit_items=limit_value if limit_value > 0 else None,
                        rarities=rarities,
                )

        def _build_endo_options(self) -> ReportOptions:
                limit_value = int(self.endo_limit_spin.value())
                return ReportOptions(
                        platform=str(self.platform_combo.currentData() or "pc"),
                        language=self.current_language,
                        only_online=self.endo_only_online_check.isChecked(),
                        live_price_top_n=0,
                        limit_items=limit_value if limit_value > 0 else None,
                        min_mastery=int(self.endo_min_mastery_spin.value()),
                        min_mod_rank=int(self.endo_min_rank_spin.value()),
                )

        # Cleanup ----------------------------------------------------------------

        def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore
                self._persist_settings()
                super().closeEvent(event)

        def _collect_config_updates(self) -> Dict[str, Any]:
                ui_lang = self.current_language
                rate_delay = float(self.rate_spin.value())
                platform = str(self.platform_combo.currentData() or "pc")
                sets_filter = self.sets_filter_edit.text().strip()
                mods_filter = self.mods_filter_edit.text().strip()
                rarities = [part.strip().lower() for part in self.mods_rarity_edit.text().split(",") if part.strip()]

                updates: Dict[str, Any] = {
                        "platform": platform,
                        "language": ui_lang,
                        "ui_language": ui_lang,
                        "limits": {"rate_delay": rate_delay},
                        "sets": {
                                "out": self.sets_path_edit.text(),
                                "only_online": self.sets_only_online_check.isChecked(),
                                "filter_contains": sets_filter,
                                "limit_sets": int(self.sets_limit_spin.value()),
                                "fetch_part_statistics": self.sets_fetch_stats_check.isChecked(),
                                "live_price_top_n": int(self.sets_live_spin.value()),
                        },
                        "mods": {
                                "out": self.mods_path_edit.text(),
                                "only_online": self.mods_only_online_check.isChecked(),
                                "filter_contains": mods_filter,
                                "limit_items": int(self.mods_limit_spin.value()),
                                "live_price_top_n": int(self.mods_live_spin.value()),
                                "rarities": rarities,
                        },
                        "endo": {
                                "out": self.endo_path_edit.text(),
                                "only_online": self.endo_only_online_check.isChecked(),
                                "limit_items": int(self.endo_limit_spin.value()),
                                "min_mastery": int(self.endo_min_mastery_spin.value()),
                                "min_mod_rank": int(self.endo_min_rank_spin.value()),
                        },
                        "gui": {
                                "all_out": self.all_path_edit.text(),
                        },
                }

                # Ensure empty strings/lists are stored consistently
                updates["sets"]["filter_contains"] = updates["sets"]["filter_contains"] or ""
                updates["mods"]["filter_contains"] = updates["mods"]["filter_contains"] or ""
                if not updates["mods"]["rarities"]:
                        updates["mods"]["rarities"] = []

                return updates

        def _persist_settings(self) -> None:
                updates = self._collect_config_updates()
                saved = save_config(updates, CONFIG_PATH)
                self.config = saved
                self._apply_runtime_settings()


def run() -> None:
        app = QtWidgets.QApplication([])
        window = MainWindow()
        window.show()
        app.exec()


__all__ = ["MainWindow", "run"]
