"""Offscreen tests for the thin PySide6 stack-manifest editor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import pytest

from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.stack_editor import StackEditorWindow, pixel_data_to_qimage
from pixel_to_3mf.stack_manifest import load_stack_manifest, validate_stack_manifest
from pixel_to_3mf.relief_workflow import prepare_relief_image


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return cast(QApplication, existing) if existing is not None else QApplication([])


def _state(tmp_path: Path):
    source = tmp_path / "scene.png"
    image = Image.new("RGB", (3, 2), (0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (255, 0, 0))
    image.putpixel((2, 1), (0, 0, 255))
    image.save(source)
    config = ConversionConfig(
        scale_mm_per_pixel=1.0,
        max_colors=8,
        backing_color=(0, 0, 0),
        relief_background_color=(0, 0, 0),
        base_height_mm=2.0,
        skip_checks=True,
    )
    pixels, _ = prepare_relief_image(source, config)
    return source, config, pixels


def test_qimage_preserves_top_left_image_orientation(tmp_path, qapp):
    _, _, pixels = _state(tmp_path)

    image = pixel_data_to_qimage(pixels)

    assert image.pixelColor(0, 0).getRgb() == (255, 0, 0, 255)
    assert image.pixelColor(2, 1).getRgb() == (0, 0, 255, 255)


def test_fill_modifiers_and_manifest_save(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    manifest_path = tmp_path / "scene.manifest.json"
    window = StackEditorWindow(source, manifest_path, pixels, config)
    red_model_y = pixels.height - 1

    window._fill_clicked(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y)}
    window._fill_clicked(2, 0, Qt.KeyboardModifier.ShiftModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y), (2, 0)}
    window._fill_clicked(0, red_model_y, Qt.KeyboardModifier.AltModifier)
    assert window.selection == {(2, 0)}

    window.name_edit.setText("Blue ghost")
    window.stack_height.setValue(3.0)
    window.color_height.setValue(1.0)
    window._save_stack()
    assert window.save_manifest()

    data = load_stack_manifest(manifest_path)
    manifest, errors, warnings = validate_stack_manifest(
        data, pixels, require_complete=False
    )
    assert errors == []
    assert warnings == ["2 non-background pixel(s) are unassigned"]
    assert manifest is not None
    assert manifest.stacks[0].name == "Blue ghost"
    assert manifest.stacks[0].stack_height_mm == 3.0
    assert manifest.stacks[0].color_height_mm == 1.0
    window.dirty = False
    window.close()


def test_saving_stack_reassigns_pixels_exclusively(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    window = StackEditorWindow(source, tmp_path / "scene.manifest.json", pixels, config)
    red_model_y = pixels.height - 1
    window._fill_clicked(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    window.name_edit.setText("Red")
    window._save_stack()

    window._new_stack()
    window.selection = {(1, red_model_y), (2, 0)}
    window.name_edit.setText("Mixed")
    window._save_stack()

    ownership = [stack.pixels for stack in window.stacks]
    assert ownership == [frozenset({(0, red_model_y)}), frozenset({(1, red_model_y), (2, 0)})]
    window.dirty = False
    window.close()
