"""Main window: sidebar navigation, menus, shortcuts, and the glue between views and services."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, QThreadPool, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from umr.app import ReviewService
from umr.checks import CheckRegistry
from umr.domain import Journey, ReviewRun
from umr.gui import integrations
from umr.gui.compare_view import CompareView
from umr.gui.dashboard_view import DashboardView
from umr.gui.eval_view import EvaluateView, LeaderboardView
from umr.gui.findings_view import FindingsView
from umr.gui.integrations import ProviderCatalog
from umr.gui.setup_view import SetupView
from umr.gui.viewmodels import check_infos, friendly_error, progress_line
from umr.gui.workers import Task, split_progress_args, start_task
from umr.ingest import load_journey
from umr.scoring import ScoringConfig
from umr.storage import RunStore

APP_TITLE = "User Manual Reviewer"
VIEWS = ["Setup", "Dashboard", "Findings", "Compare", "Evaluate", "Leaderboard"]
DEFAULT_JOURNEY = Path("samples/shopflow/journey.yaml")
SCORING_FILE = Path("config/scoring.yaml")
RECENT_RUNS = 10


class MainWindow(QMainWindow):
    review_finished = Signal(object)  # ReviewRun
    comparison_finished = Signal(object)  # Comparison
    eval_finished = Signal(object)  # EvalResult
    task_ended = Signal(str)  # "finished" | "cancelled" | "failed"

    def __init__(self, *, settings: QSettings | None = None, run_store: RunStore | None = None,
                 review_service: ReviewService | None = None, providers: ProviderCatalog | None = None,
                 check_classes: Callable[[], list[Any]] | None = None,
                 compare_service: Callable[[ReviewService], Any] | None = None,
                 eval_service: Any = None, eval_store: Any = None, pool: QThreadPool | None = None):
        super().__init__()
        self.settings = settings or QSettings("UserManualReviewer", "umr")
        self.run_store = run_store or RunStore()
        self.review_service = review_service or ReviewService(ScoringConfig.load(SCORING_FILE))
        self.providers = providers if providers is not None else ProviderCatalog.load()
        self._check_classes = check_classes or CheckRegistry.all
        self._compare_factory = compare_service or integrations.make_compare_service
        self.eval_service = eval_service if eval_service is not None else integrations.make_eval_service()
        if eval_store is None:  # the store EvalService saves into, so the leaderboard shows its results
            eval_store = getattr(self.eval_service, "store", None) or integrations.make_eval_store()
        self.eval_store = eval_store
        self.pool = pool or QThreadPool.globalInstance()
        self.dialogs_enabled = True
        self.last_error: tuple[str, str] | None = None

        self.journey: Journey | None = None
        self.journey_path: Path | None = None
        self.run: ReviewRun | None = None
        self.run_journey: Journey | None = None
        self.comparison: Any = None
        self.task: Task | None = None
        self.eval_task: Task | None = None
        self.last_saved: list[Path] = []
        self._progress: dict[str, tuple[int, int]] = {}

        self.setup = SetupView()
        self.dashboard = DashboardView()
        self.findings = FindingsView()
        self.compare = CompareView()
        self.evaluate = EvaluateView()
        self.leaderboard = LeaderboardView()
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.addItems(VIEWS)
        self.nav.setFixedWidth(150)
        self.stack = QStackedWidget()
        for w in (self.setup, self.dashboard, self.findings, self.compare, self.evaluate, self.leaderboard):
            self.stack.addWidget(w)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.nav.setStyleSheet("QListWidget#nav { border: none; } QListWidget#nav::item { padding: 9px 12px; }")
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._build_menus()
        self.setup.open_file_requested.connect(self.choose_journey_file)
        self.setup.open_folder_requested.connect(self.choose_journey_folder)
        self.setup.start_requested.connect(self.start_review)
        self.setup.cancel_requested.connect(self.cancel)
        self.evaluate.run_requested.connect(self.start_evaluation)
        self.evaluate.cancel_requested.connect(self.cancel_evaluation)
        self.leaderboard.refresh_btn.clicked.connect(self.refresh_leaderboard)

        self.setup.set_checks(check_infos(self._check_classes()))
        self.setup.set_providers(self.providers.names(), self.providers.notice)
        benchmarks = self._benchmarks()
        self.evaluate.set_options(self.providers.names(), benchmarks, self._eval_notice())
        self.refresh_leaderboard()
        self.update_title()
        self.resize(1360, 860)
        self.statusBar().showMessage("Open a journey to start (Ctrl+O).")

    # ---------------- menus ----------------
    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.act_open = self._action("Open &journey…", QKeySequence.StandardKey.Open, self.choose_journey_file)
        self.act_open_folder = self._action("Open journey &folder…", None, self.choose_journey_folder)
        self.act_open_run = self._action("Open &run…", "Ctrl+Shift+O", self.choose_run_file)
        self.recent_menu = QMenu("Recent &runs", self)
        self.recent_menu.aboutToShow.connect(self.populate_recent_runs)
        self.act_compare_runs = self._action("&Compare two runs…", None, self.choose_runs_to_compare)
        self.act_quit = self._action("&Quit", QKeySequence.StandardKey.Quit, self.close)
        for a in (self.act_open, self.act_open_folder, self.act_open_run):
            file_menu.addAction(a)
        file_menu.addMenu(self.recent_menu)
        file_menu.addAction(self.act_compare_runs)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)
        review_menu = self.menuBar().addMenu("&Review")
        self.act_start = self._action("&Start", "Ctrl+R", self.start_review)
        self.act_cancel = self._action("&Cancel", "Esc", self.cancel)
        review_menu.addAction(self.act_start)
        review_menu.addAction(self.act_cancel)
        view_menu = self.menuBar().addMenu("&View")
        for i, name in enumerate(VIEWS):
            view_menu.addAction(self._action(name, f"Ctrl+{i + 1}", partial(self.nav.setCurrentRow, i)))

    def _action(self, text: str, shortcut: Any, slot: Callable[[], Any]) -> QAction:
        act = QAction(text, self)
        if shortcut is not None:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(lambda *_: slot())
        self.addAction(act)  # shortcuts work even while the menu bar is hidden
        return act

    def show_view(self, name: str) -> None:
        self.nav.setCurrentRow(VIEWS.index(name))

    def current_view(self) -> str:
        return VIEWS[self.stack.currentIndex()]

    def update_title(self) -> None:
        name = self.journey.name if self.journey else self.run.journey_name if self.run else ""
        self.setWindowTitle(f"{APP_TITLE} — {name}" if name else APP_TITLE)

    # ---------------- errors ----------------
    def show_error(self, title: str, text: str) -> None:
        self.last_error = (title, text)
        self.statusBar().showMessage(f"{title}: {text.splitlines()[0] if text else ''}", 10000)
        if self.dialogs_enabled:
            box = QMessageBox(QMessageBox.Icon.Critical, title, title, QMessageBox.StandardButton.Ok, self)
            box.setInformativeText(text)
            box.exec()

    def show_exception(self, exc: BaseException) -> None:
        self.show_error(*friendly_error(exc))

    # ---------------- journey ----------------
    def open_initial_journey(self) -> None:
        last = self.settings.value("last_journey", "")
        for candidate in (Path(str(last)) if last else None, DEFAULT_JOURNEY):
            if candidate is not None and candidate.exists():
                self.open_journey(candidate, quiet=True)
                if self.journey is not None:
                    return

    def _start_dir(self) -> str:
        last = self.settings.value("last_journey", "")
        if last:
            return str(Path(str(last)).parent)
        return str(DEFAULT_JOURNEY.parent if DEFAULT_JOURNEY.exists() else Path.cwd())

    def choose_journey_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open journey", self._start_dir(),
                                              "Journey (journey.yaml *.yaml *.yml);;All files (*)")
        if path:
            self.open_journey(Path(path))

    def choose_journey_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open journey or manual folder", self._start_dir())
        if path:
            self.open_journey(Path(path))

    def open_journey(self, path: Path, quiet: bool = False) -> bool:
        try:
            journey = load_journey(path)
        except Exception as e:
            if quiet:
                self.statusBar().showMessage(f"Could not open {path}: {e}", 10000)
            else:
                self.show_exception(e)
            return False
        self.journey, self.journey_path = journey, path
        self.setup.set_journey(journey, str(path.resolve()))
        self.settings.setValue("last_journey", str(path.resolve()))
        self.update_title()
        self.statusBar().showMessage(
            f"Opened {journey.name}: {len(journey.manuals)} manuals, {len(journey.pages)} pages, "
            f"{journey.word_count:,} words.", 8000)
        return True

    # ---------------- review ----------------
    def is_running(self) -> bool:
        return self.task is not None

    def start_review(self) -> None:
        if self.task is not None:
            return
        if self.journey is None:
            self.show_error("No journey open", "Open a journey first (File → Open journey…, Ctrl+O).")
            return
        check_ids = self.setup.selected_check_ids()
        if not check_ids:
            self.show_error("No checks selected", "Tick at least one check, or click All.")
            return
        name_a, name_b = self.setup.model_a_name(), self.setup.model_b_name()
        try:
            provider_a = self.providers.make(name_a) if name_a else None
            provider_b = self.providers.make(name_b) if name_b else None
        except Exception as e:
            self.show_exception(e)
            return
        journey, jpath = self.journey, self.journey_path
        if name_b:
            service = self._compare_factory(self.review_service)
            if service is None:
                self.show_error("Comparison not available",
                                "This build has no comparison service (umr.app.compare).")
                return

            def compare_fn(progress: Callable[..., None], cancel: Any) -> Any:
                return service.run_and_compare(journey, check_ids, provider_a, provider_b,
                                               progress=progress, cancel=cancel)
            fn: Callable[..., Any] = compare_fn
            labels: tuple[str, ...] = (name_a or "rules", name_b)
        else:
            def review_fn(progress: Callable[..., None], cancel: Any) -> Any:
                return self.review_service.review(journey, check_ids, provider_a, progress=progress,
                                                  cancel=cancel, journey_path=jpath)
            fn = review_fn
            labels = ()
        self._progress = {}
        self.setup.log.clear()
        what = f"comparison of {labels[0]} and {labels[1]}" if labels else \
            f"review with {name_a or 'rule checks only'}"
        self.setup.append_log(f"Starting {what} on {journey.name} ({len(check_ids)} checks selected)")
        self.setup.progress.setValue(0)
        self.setup.set_running(True)
        self.statusBar().showMessage("Review running… (Esc to cancel)")
        task = Task(fn)
        task.signals.progress.connect(self._on_progress)
        task.signals.finished.connect(lambda result: self._on_review_done(result, bool(labels)))
        task.signals.failed.connect(self._on_task_failed)
        task.signals.cancelled.connect(self._on_task_cancelled)
        self.task = task
        start_task(task, self.pool)

    def cancel(self) -> None:
        if self.task is not None:
            self.task.cancel()
            self.setup.append_log("Cancelling…")
            self.statusBar().showMessage("Cancelling…")
        if self.eval_task is not None:
            self.cancel_evaluation()

    def _on_progress(self, args: tuple[Any, ...]) -> None:
        label, event = split_progress_args(args)
        if event is None:
            return
        line = progress_line(event, label)
        if line:
            self.setup.append_log(line)
        total = getattr(event, "total", 0)
        if total:
            self._progress[label or ""] = (getattr(event, "done", 0), total)
            done = sum(d for d, _ in self._progress.values())
            tot = sum(t for _, t in self._progress.values())
            self.setup.progress.setValue(int(round(100 * done / tot)) if tot else 0)

    def _end_task(self) -> None:
        self.task = None
        self.setup.set_running(False)

    def _save_run(self, run: ReviewRun) -> Path | None:
        try:
            path = self.run_store.save(run)
        except OSError as e:
            self.setup.append_log(f"Could not save the run: {e}")
            return None
        self.last_saved.append(path)
        return path

    def _on_review_done(self, result: Any, is_comparison: bool) -> None:
        self._end_task()
        self.setup.progress.setValue(100)
        if is_comparison:
            runs = [result.run_a, result.run_b]
            paths = [self._save_run(r) for r in runs]
            self.show_run(result.run_a, self.journey)
            self.show_comparison(result, self.journey)
            self.setup.append_log(f"Comparison done: {len(result.both)} found by both, "
                                  f"{len(result.only_a)} only A, {len(result.only_b)} only B.")
            saved = ", ".join(str(p) for p in paths if p)
            self.statusBar().showMessage(f"Comparison finished. Runs saved to {saved}", 15000)
            self.show_view("Compare")
            self.comparison_finished.emit(result)
        else:
            run: ReviewRun = result
            path = self._save_run(run)
            self.show_run(run, self.journey)
            score = run.score_for("set")
            self.setup.append_log(f"Done: {len(run.findings)} findings, set score "
                                  f"{score.value if score else '–'}, {len(run.errors)} errors. "
                                  f"Saved to {path}")
            self.statusBar().showMessage(f"Review finished. Saved to {path}", 15000)
            self.show_view("Dashboard")
        self.task_ended.emit("finished")
        if not is_comparison:
            self.review_finished.emit(result)

    def _on_task_failed(self, exc: BaseException) -> None:
        self._end_task()
        self.setup.append_log(f"Review failed: {type(exc).__name__}: {exc}")
        self.task_ended.emit("failed")
        self.show_exception(exc)

    def _on_task_cancelled(self) -> None:
        self._end_task()
        self.setup.append_log("Review cancelled.")
        self.statusBar().showMessage("Review cancelled.", 8000)
        self.task_ended.emit("cancelled")

    # ---------------- results ----------------
    def show_run(self, run: ReviewRun, journey: Journey | None = None) -> None:
        self.run = run
        self.run_journey = journey
        self.dashboard.set_run(run, journey)
        self.findings.set_findings(run.findings, journey)
        self.update_title()

    def show_comparison(self, comparison: Any, journey: Journey | None = None) -> None:
        self.comparison = comparison
        self.compare.set_comparison(comparison, journey)

    def _journey_for_run(self, run: ReviewRun) -> Journey | None:
        if self.journey is not None and self.journey_path is not None and \
                Path(run.journey_path).resolve() == self.journey_path.resolve():
            return self.journey
        try:
            return load_journey(Path(run.journey_path))
        except Exception:
            return None  # passages show "source not available"

    def choose_run_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open review run", str(self.run_store.root),
                                              "Review runs (*.json);;All files (*)")
        if path:
            self.open_run(Path(path))

    def open_run(self, path: Path) -> ReviewRun | None:
        try:
            run = self.run_store.load(path)
        except Exception as e:
            self.show_error("Could not open the run", f"{path}\n\n{e}")
            return None
        journey = self._journey_for_run(run)
        self.show_run(run, journey)
        self._remember_run(path)
        note = "" if journey else " (manual sources not found, passages unavailable)"
        self.statusBar().showMessage(f"Opened run {path.name}{note}", 10000)
        self.show_view("Dashboard")
        return run

    def _remember_run(self, path: Path) -> None:
        recent = [p for p in self.recent_run_paths() if p != str(path)]
        self.settings.setValue("recent_runs", [str(path), *recent][:RECENT_RUNS])

    def recent_run_paths(self) -> list[str]:
        value: Any = self.settings.value("recent_runs", [])
        if isinstance(value, str):
            value = [value]
        opened = [str(v) for v in (value or [])]
        saved = [str(p) for p in self.run_store.list()]
        out = list(dict.fromkeys(opened + saved))
        return [p for p in out if Path(p).exists()][:RECENT_RUNS]

    def populate_recent_runs(self) -> None:
        self.recent_menu.clear()
        paths = self.recent_run_paths()
        if not paths:
            act = self.recent_menu.addAction("No saved runs yet")
            act.setEnabled(False)
            return
        for p in paths:
            act = self.recent_menu.addAction(Path(p).stem)
            act.setToolTip(p)
            act.triggered.connect(lambda *_, p=p: self.open_run(Path(p)))

    def choose_runs_to_compare(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose two review runs", str(self.run_store.root),
                                                "Review runs (*.json)")
        if paths:
            self.compare_run_files([Path(p) for p in paths])

    def compare_run_files(self, paths: list[Path]) -> Any:
        if len(paths) != 2:
            self.show_error("Choose two runs", "Select exactly two run files to compare.")
            return None
        service = self._compare_factory(self.review_service)
        if service is None:
            self.show_error("Comparison not available", "This build has no comparison service (umr.app.compare).")
            return None
        try:
            run_a, run_b = self.run_store.load(paths[0]), self.run_store.load(paths[1])
            comparison = service.compare_runs(run_a, run_b)
        except Exception as e:
            self.show_exception(e)
            return None
        self.show_comparison(comparison, self._journey_for_run(run_a))
        self.show_view("Compare")
        return comparison

    # ---------------- evaluation ----------------
    def _benchmarks(self) -> list[str]:
        if self.eval_service is None:
            return []
        try:
            return list(self.eval_service.benchmarks())
        except Exception:
            return []

    def _eval_notice(self) -> str:
        if self.eval_service is None:
            return "Evaluation is not available in this build (umr.app.evaluation)."
        return self.providers.notice

    def start_evaluation(self) -> None:
        if self.eval_task is not None or self.eval_service is None:
            return
        name = self.evaluate.provider.currentData()
        benchmark = self.evaluate.benchmark.currentData()
        if not name or not benchmark:
            self.show_error("Nothing to evaluate", "Choose a model and a benchmark.")
            return
        try:
            provider = self.providers.make(str(name))
        except Exception as e:
            self.show_exception(e)
            return
        repeat, include_rules = self.evaluate.repeat.value(), self.evaluate.include_rules.isChecked()
        service = self.eval_service

        def fn(progress: Callable[..., None], cancel: Any) -> Any:
            return service.evaluate(provider, benchmark=str(benchmark), repeat=repeat,
                                    include_rules=include_rules, progress=progress, cancel=cancel)
        task = Task(fn)
        task.signals.progress.connect(self._on_eval_progress)
        task.signals.finished.connect(self._on_eval_done)
        task.signals.failed.connect(self._on_eval_failed)
        task.signals.cancelled.connect(self._on_eval_cancelled)
        self.eval_task = task
        self._eval_progress: dict[str, tuple[int, int]] = {}
        self.evaluate.set_running(True)
        self.evaluate.status.setText(f"Evaluating {name} on {benchmark}…")
        self.statusBar().showMessage(f"Evaluating {name} on {benchmark}…")
        start_task(task, self.pool)

    def cancel_evaluation(self) -> None:
        if self.eval_task is not None:
            self.eval_task.cancel()
            self.evaluate.status.setText("Cancelling…")

    def _on_eval_progress(self, args: tuple[Any, ...]) -> None:
        label, event = split_progress_args(args)
        if event is None:
            return
        line = progress_line(event, label)
        if line:
            self.evaluate.status.setText(line)
        total = getattr(event, "total", 0)
        if total:
            self._eval_progress[label or ""] = (getattr(event, "done", 0), total)
            done = sum(d for d, _ in self._eval_progress.values())
            tot = sum(t for _, t in self._eval_progress.values())
            self.evaluate.progress.setValue(int(round(100 * done / tot)))

    def _on_eval_done(self, result: Any) -> None:
        self.eval_task = None
        self.evaluate.set_running(False)
        self.evaluate.progress.setValue(100)
        self.evaluate.set_result(result)
        # EvalService.evaluate saves the result (and its review runs) itself
        root = getattr(self.eval_store, "root", None)
        saved = f" Saved to {root}." if root else ""
        self.evaluate.status.setText(f"Evaluation finished.{saved}")
        self.statusBar().showMessage(f"Evaluation finished.{saved}", 15000)
        self.refresh_leaderboard()
        self.eval_finished.emit(result)

    def _on_eval_failed(self, exc: BaseException) -> None:
        self.eval_task = None
        self.evaluate.set_running(False)
        self.evaluate.status.setText(f"Evaluation failed: {exc}")
        self.show_exception(exc)

    def _on_eval_cancelled(self) -> None:
        self.eval_task = None
        self.evaluate.set_running(False)
        self.evaluate.status.setText("Evaluation cancelled.")

    def refresh_leaderboard(self) -> None:
        results: list[Any] = []
        if self.eval_store is not None:
            try:
                results = list(self.eval_store.load_all())
            except Exception as e:
                self.statusBar().showMessage(f"Could not read evaluation results: {e}", 10000)
        self.leaderboard.set_results(integrations.leaderboard(results))

    # ---------------- lifecycle ----------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        for task in (self.task, self.eval_task):
            if task is not None:
                task.cancel()
        self.pool.waitForDone(3000)
        super().closeEvent(event)

