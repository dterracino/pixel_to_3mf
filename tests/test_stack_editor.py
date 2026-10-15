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
from pixel_to_3mf.stack_editor import (
    ImageCanvas,
    ImageViewSettings,
    SelectionMode,
    SelectionTool,
    StackEditorWindow,
    load_stack_editor_state,
    pixel_data_to_qimage,
)
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


def test_assigned_view_filters_change_only_display_pixels(tmp_path, qapp):
    _, _, pixels = _state(tmp_path)
    assigned = {(0, pixels.height - 1)}
    image = pixel_data_to_qimage(
        pixels,
        assigned,
        ImageViewSettings(
            show_assigned=True,
            show_unassigned=False,
            assigned_opacity=0.5,
            assigned_saturation=0.0,
            invert_assigned=True,
        ),
    )

    assigned_color = image.pixelColor(0, 0)
    assert assigned_color.alpha() in {127, 128}
    assert assigned_color.red() == assigned_color.green() == assigned_color.blue()
    assert image.pixelColor(1, 0).alpha() == 0


def test_canvas_draws_and_animates_selection_outline(tmp_path, qapp):
    _, _, pixels = _state(tmp_path)
    canvas = ImageCanvas(pixels)
    canvas.resize(320, 240)
    canvas.set_selection({(0, pixels.height - 1), (1, pixels.height - 1)})
    canvas.show()
    qapp.processEvents()

    assert canvas._selection_outline.active
    assert len(canvas._selection_edges) == 6
    assert not canvas.grab().isNull()

    canvas.set_selection(set())
    assert not canvas._selection_outline.active
    canvas.close()


def test_fill_modifiers_and_manifest_save(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    manifest_path = tmp_path / "scene.manifest.json"
    window = StackEditorWindow(source, manifest_path, pixels, config)
    red_model_y = pixels.height - 1

    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y)}
    window._select_at(2, 0, Qt.KeyboardModifier.ShiftModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y), (2, 0)}
    window._select_at(0, red_model_y, Qt.KeyboardModifier.AltModifier)
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


def test_existing_stack_defaults_to_add_mode_and_can_be_extended(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    window = StackEditorWindow(source, tmp_path / "scene.manifest.json", pixels, config)
    red_model_y = pixels.height - 1
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    window.name_edit.setText("Extended stack")
    window._save_stack()

    assert window.selection_mode is SelectionMode.ADD
    assert window.add_mode_button.isChecked()
    window._select_at(2, 0, Qt.KeyboardModifier.NoModifier)
    window._save_stack()

    assert len(window.stacks) == 1
    assert window.stacks[0].pixels == frozenset(
        {(0, red_model_y), (1, red_model_y), (2, 0)}
    )
    window.dirty = False
    window.close()


def test_persistent_selection_modes_and_modifier_overrides(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    window = StackEditorWindow(source, tmp_path / "scene.manifest.json", pixels, config)
    red_model_y = pixels.height - 1

    window._set_selection_mode(SelectionMode.ADD)
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    window._select_at(2, 0, Qt.KeyboardModifier.NoModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y), (2, 0)}

    window._set_selection_mode(SelectionMode.SUBTRACT)
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    assert window.selection == {(2, 0)}

    window._set_selection_mode(SelectionMode.REPLACE)
    window._select_at(0, red_model_y, Qt.KeyboardModifier.ShiftModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y), (2, 0)}
    window._select_at(2, 0, Qt.KeyboardModifier.AltModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y)}
    window.dirty = False
    window.close()


def test_saving_stack_reassigns_pixels_exclusively(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    window = StackEditorWindow(source, tmp_path / "scene.manifest.json", pixels, config)
    red_model_y = pixels.height - 1
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
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


def test_magic_wand_contiguous_option_and_tool_icons(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    window = StackEditorWindow(source, tmp_path / "scene.manifest.json", pixels, config)
    red_model_y = pixels.height - 1

    assert not window.fill_button.icon().isNull()
    assert not window.magic_wand_button.icon().isNull()
    window.magic_wand_button.click()
    assert window.active_tool is SelectionTool.MAGIC_WAND
    assert window.tool_options.currentIndex() == 1

    window.magic_wand_contiguous.setChecked(True)
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y)}

    window.magic_wand_contiguous.setChecked(False)
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y)}
    # This fixture has one connected red area; add a disconnected red pixel to
    # the processed map to prove non-contiguous selection behavior in the UI.
    pixels.pixels[(2, 0)] = (255, 0, 0, 255)
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    assert window.selection == {(0, red_model_y), (1, red_model_y), (2, 0)}
    window.dirty = False
    window.close()


def test_view_menu_tracks_saved_assignment_visibility(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    window = StackEditorWindow(source, tmp_path / "scene.manifest.json", pixels, config)
    red_model_y = pixels.height - 1
    window._select_at(0, red_model_y, Qt.KeyboardModifier.NoModifier)
    window.name_edit.setText("Red")
    window._save_stack()

    window.show_assigned_action.setChecked(False)
    assert not window.view_settings.show_assigned
    window.show_unassigned_action.setChecked(False)
    assert not window.view_settings.show_unassigned
    window._set_assigned_opacity(0.25)
    window._set_assigned_saturation(0.0)
    window.invert_assigned_action.setChecked(True)
    assert window.view_settings.assigned_opacity == 0.25
    assert window.view_settings.assigned_saturation == 0.0
    assert window.view_settings.invert_assigned
    window.dirty = False
    window.close()


def test_resume_loads_saved_stacks_and_manifest_settings(tmp_path, qapp):
    source, config, pixels = _state(tmp_path)
    manifest_path = tmp_path / "scene.manifest.json"
    window = StackEditorWindow(source, manifest_path, pixels, config)
    window._select_at(0, pixels.height - 1, Qt.KeyboardModifier.NoModifier)
    window.name_edit.setText("Saved red")
    window._save_stack()
    assert window.save_manifest()
    window.close()

    resumed_config = ConversionConfig()
    resumed_pixels, resumed_stacks = load_stack_editor_state(
        source, manifest_path, resumed_config, resume=True
    )

    assert resumed_pixels.width == pixels.width
    assert [stack.name for stack in resumed_stacks] == ["Saved red"]
    assert resumed_config.base_height_mm == 2.0
