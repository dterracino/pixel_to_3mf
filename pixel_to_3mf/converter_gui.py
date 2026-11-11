"""Desktop front end for the existing converter command-line contract."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .cli import build_parser


GROUPS = {
    "Files and batch": {
        "image_file", "--output", "--batch", "--batch-input", "--batch-output",
        "--skip-checks", "--recurse", "--check-batch", "--check-batch-folder",
        "--log-file",
    },
    "Size and geometry": {
        "--max-size", "--scale", "--scale-to", "--line-width",
        "--color-height", "--base-height", "--max-colors", "--connectivity",
        "--trim", "--optimize-mesh", "--validate-mesh", "--smooth",
        "--smooth-tolerance", "--smooth-iterations", "--no-backing-plate",
        "--solid-core", "--core-height",
    },
    "Colors and filaments": {
        "--backing-color", "--auto-backing-color", "--no-backing-color",
        "--backing-color-at", "--color-mode", "--filament-maker",
        "--filament-type", "--filament-finish", "--no-merge-colors",
        "--prefer-hue", "--no-prefer-hue", "--ams-count",
    },
    "Image processing": {
        "--auto-crop", "--padding-size", "--padding-color", "--padding-type",
        "--denoise", "--denoise-type", "--blob-min-size",
        "--preprocess-filter", "--preprocess-filter-size", "--quantize",
        "--quantize-algo", "--quantize-colors", "--iterate-quantize",
    },
    "Relief and manifests": {
        "--relief", "--background-color", "--relief-height",
        "--generate-relief-manifest", "--create-manifest", "--resume-manifest",
        "--validate-relief-manifest", "--relief-manifest", "--color-at",
    },
    "Output images": {"--summary", "--preview", "--quantized", "--swatches", "--render"},
}

FILE_OPTIONS = {
    "image_file", "--output", "--batch-input", "--batch-output", "--scale-to",
    "--generate-relief-manifest", "--create-manifest", "--resume-manifest",
    "--validate-relief-manifest", "--relief-manifest", "--log-file",
    "--check-batch-folder",
}
DIRECTORIES = {"--batch-input", "--batch-output", "--check-batch-folder"}
SAVE_FILES = {"--output", "--generate-relief-manifest", "--create-manifest", "--log-file"}


def option_name(action: argparse.Action) -> str:
    """Use the first long spelling, keeping aliases tied to one control."""
    return next((name for name in action.option_strings if name.startswith("--")), action.dest)


class ConverterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.parser = build_parser()
        self.actions: dict[str, argparse.Action] = {}
        self.option_widgets: dict[str, QWidget] = {}
        self.process: QProcess | None = None
        self.setWindowTitle("Pixel Art to 3MF")
        self.resize(1050, 800)

        root = QWidget()
        layout = QVBoxLayout(root)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        forms = {name: self._add_tab(name) for name in GROUPS}

        for action in self.parser._actions:
            name = option_name(action)
            if name in {"--help", "--version"}:
                continue
            group = next((title for title, names in GROUPS.items() if name in names), None)
            if group is None:
                raise ValueError(f"CLI option has no UI group: {name}")
            widget = self._make_control(name, action)
            self.actions[name] = action
            self.option_widgets[name] = widget
            forms[group].addRow(name.removeprefix("--").replace("-", " ").title() + ":", widget)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run converter")
        self.run_button.clicked.connect(self.run_conversion)
        buttons.addWidget(self.run_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_conversion)
        buttons.addWidget(self.stop_button)
        for answer, label in (("y", "Answer Yes"), ("n", "Answer No")):
            button = QPushButton(label)
            button.setEnabled(False)
            button.clicked.connect(lambda _checked=False, value=answer: self._answer(value))
            buttons.addWidget(button)
            if answer == "y":
                self.yes_button = button
            else:
                self.no_button = button
        help_button = QPushButton("CLI help")
        help_button.clicked.connect(lambda: QMessageBox.information(self, "CLI help", self.parser.format_help()))
        buttons.addWidget(help_button)
        version_button = QPushButton("Version")
        version_button.clicked.connect(lambda: self._start(["--version"]))
        buttons.addWidget(version_button)
        layout.addLayout(buttons)

        layout.addWidget(QLabel("Command"))
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        layout.addWidget(self.command_preview)
        layout.addWidget(QLabel("Output"))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, stretch=1)
        self.setCentralWidget(root)
        self._update_command()

    def _add_tab(self, title: str) -> QFormLayout:
        content = QWidget()
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.tabs.addTab(scroll, title)
        return form

    def _make_control(self, name: str, action: argparse.Action) -> QWidget:
        if isinstance(action, argparse._StoreTrueAction):
            control = QCheckBox()
            control.setToolTip(action.help or "")
            control.toggled.connect(self._update_command)
            return control
        if action.choices:
            control = QComboBox()
            control.addItem(f"Default ({action.default})", None)
            for choice in action.choices:
                control.addItem(str(choice), str(choice))
            control.setToolTip(action.help or "")
            control.currentIndexChanged.connect(self._update_command)
            return control

        row = QWidget()
        horizontal = QHBoxLayout(row)
        horizontal.setContentsMargins(0, 0, 0, 0)
        if action.nargs == "?" and action.option_strings:
            enabled = QCheckBox("Use")
            enabled.setObjectName("enabled")
            enabled.toggled.connect(self._update_command)
            horizontal.addWidget(enabled)
        if action.nargs == "+":
            field: QWidget = QPlainTextEdit()
            field.setPlaceholderText("One model path per line")
            field.setFixedHeight(75)
            field.textChanged.connect(self._update_command)
        else:
            field = QLineEdit()
            if action.default is not None and action.default != "":
                field.setPlaceholderText(f"Default: {action.default}")
            field.textChanged.connect(self._update_command)
        field.setObjectName("value")
        field.setToolTip(action.help or "")
        horizontal.addWidget(field, stretch=1)
        if name in FILE_OPTIONS:
            browse = QPushButton("Browse…")
            browse.clicked.connect(lambda: self._browse(name, field))
            horizontal.addWidget(browse)
        return row

    def _browse(self, name: str, field: QWidget) -> None:
        if name in DIRECTORIES:
            path = QFileDialog.getExistingDirectory(self, "Select folder")
        elif name in SAVE_FILES:
            path, _ = QFileDialog.getSaveFileName(self, "Select output file")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path and isinstance(field, QLineEdit):
            field.setText(path)

    def arguments(self) -> list[str]:
        args: list[str] = []
        for name, action in self.actions.items():
            widget = self.option_widgets[name]
            if isinstance(widget, QCheckBox):
                if widget.isChecked():
                    args.append(name)
            elif isinstance(widget, QComboBox):
                if widget.currentData() is not None:
                    args.extend((name, str(widget.currentData())))
            else:
                field = widget.findChild(QWidget, "value")
                if isinstance(field, QPlainTextEdit):
                    values = [line.strip() for line in field.toPlainText().splitlines() if line.strip()]
                else:
                    assert isinstance(field, QLineEdit)
                    values = [field.text().strip()] if field.text().strip() else []
                enabled = widget.findChild(QCheckBox, "enabled")
                if enabled is not None and enabled.isChecked():
                    args.append(name)
                    args.extend(values)
                elif values:
                    if name != "image_file":
                        args.append(name)
                    args.extend(values)
        return args

    def _update_command(self, *_: object) -> None:
        if not hasattr(self, "command_preview"):
            return
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "run_converter.py"), *self.arguments()]
        self.command_preview.setText(subprocess.list2cmdline(command))

    def run_conversion(self) -> None:
        args = self.arguments()
        try:
            self.parser.parse_args(args)
        except SystemExit:
            QMessageBox.warning(self, "Invalid options", "Check the selected options and paths.")
            return
        image = self.option_widgets["image_file"].findChild(QLineEdit, "value")
        assert image is not None
        if not image.text().strip() and not any(item in args for item in (
            "--batch", "--resume-manifest", "--check-batch", "--check-batch-folder"
        )):
            QMessageBox.warning(self, "Input needed", "Select an image or a batch operation.")
            return
        self._start(args)

    def _start(self, args: list[str]) -> None:
        if self.process is not None:
            return
        self.output.clear()
        process = QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments([str(Path(__file__).resolve().parents[1] / "run_converter.py"), *args])
        process.setWorkingDirectory(str(Path.cwd()))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self.process = process
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.yes_button.setEnabled(True)
        self.no_button.setEnabled(True)
        process.start()

    def _answer(self, value: str) -> None:
        if self.process is not None:
            self.process.write((value + "\n").encode())
            self.output.appendPlainText(f"\n> {value}")

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if self.process is None:
            return
        self._read_output()
        self.output.appendPlainText(f"\nProcess error: {self.process.errorString()}")
        if error == QProcess.ProcessError.FailedToStart:
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _read_output(self) -> None:
        if self.process is not None:
            self.output.insertPlainText(bytes(self.process.readAllStandardOutput()).decode(errors="replace"))
            self.output.ensureCursorVisible()

    def _finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        self._read_output()
        self.output.appendPlainText(f"\nProcess finished with exit code {code}.")
        if self.process is not None:
            self.process.deleteLater()
        self.process = None
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.yes_button.setEnabled(False)
        self.no_button.setEnabled(False)

    def stop_conversion(self) -> None:
        if self.process is not None:
            self.process.terminate()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(3000)
        super().closeEvent(event)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = ConverterWindow()
    window.show()
    return app.exec()
