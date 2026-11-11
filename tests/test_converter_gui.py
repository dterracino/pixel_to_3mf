"""Desktop controls must retain the CLI contract and launch real conversions."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QLineEdit

from pixel_to_3mf.converter_gui import ConverterWindow, option_name


def _app():
    return QApplication.instance() or QApplication([])


def _set_text(window: ConverterWindow, name: str, value: str) -> None:
    field = window.option_widgets[name].findChild(QLineEdit, "value")
    assert field is not None
    field.setText(value)


def test_every_cli_option_has_a_control():
    _app()
    window = ConverterWindow()
    expected = {
        option_name(action)
        for action in window.parser._actions
        if option_name(action) not in {"--help", "--version"}
    }
    assert set(window.option_widgets) == expected
    window.close()


def test_gui_runs_filament_conversion(tmp_path):
    _app()
    window = ConverterWindow()
    source = Path(__file__).resolve().parents[1] / "samples/input/sprites/santa-mario-8bit.png"
    output = tmp_path / "santa.3mf"
    _set_text(window, "image_file", str(source))
    _set_text(window, "--output", str(output))
    _set_text(window, "--filament-maker", "Bambu Lab")
    _set_text(window, "--filament-type", "PLA")
    _set_text(window, "--filament-finish", "Basic,Matte,Pure")
    window.option_widgets["--summary"].setChecked(True)
    assert window.parser.parse_args(window.arguments()).filament_finish == "Basic,Matte,Pure"

    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    window.run_conversion()
    assert window.process is not None
    window.process.finished.connect(loop.quit)
    timer.start(30000)
    loop.exec()
    assert timer.isActive(), window.output.toPlainText()
    assert output.exists(), window.output.toPlainText()
    assert (tmp_path / "santa.summary.txt").exists()
    assert "exit code 0" in window.output.toPlainText()
    window.close()
