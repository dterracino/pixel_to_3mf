"""Focused tests for stack selection, persistence, and material planning."""

from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image

from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.relief_workflow import prepare_relief_image
from pixel_to_3mf.stack_manifest import (
    StackDefinition,
    build_stack_manifest_data,
    connected_color_component,
    decode_row_runs,
    encode_row_runs,
    validate_stack_manifest,
    write_stack_manifest,
)
from pixel_to_3mf.stack_plan import create_stack_relief_plan
from pixel_to_3mf.pixel_to_3mf import convert_image_to_3mf
from pixel_to_3mf.cli import main


def _image(path: Path) -> None:
    image = Image.new("RGB", (4, 3), (0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (255, 0, 0))
    image.putpixel((3, 0), (255, 0, 0))
    image.putpixel((0, 2), (0, 0, 255))
    image.save(path)


def _config() -> ConversionConfig:
    return ConversionConfig(
        scale_mm_per_pixel=1.0,
        max_colors=8,
        backing_color=(0, 0, 0),
        relief_background_color=(0, 0, 0),
        base_height_mm=2.0,
        color_naming_mode="hex",
        skip_checks=True,
    )


def test_fill_is_exact_color_and_four_connected(tmp_path):
    path = tmp_path / "scene.png"
    _image(path)
    pixels, _ = prepare_relief_image(path, _config())

    top_left = (0, pixels.height - 1)
    component = connected_color_component(pixels, top_left)

    assert component == frozenset({(0, 2), (1, 2)})
    assert (3, 2) not in component
    assert connected_color_component(pixels, (99, 99)) == frozenset()


def test_row_runs_round_trip_top_left_coordinates():
    pixels = frozenset({(0, 2), (1, 2), (3, 2), (2, 0)})

    runs = encode_row_runs(pixels, height=3)

    assert runs == [[0, 0, 1], [0, 3, 3], [2, 2, 2]]
    assert decode_row_runs(runs, width=4, height=3) == pixels


def test_manifest_allows_multicolor_stack_and_exempts_background(tmp_path):
    path = tmp_path / "scene.png"
    _image(path)
    config = _config()
    pixels, _ = prepare_relief_image(path, config)
    required = frozenset(
        coordinate for coordinate, rgba in pixels.pixels.items() if rgba[:3] != (0, 0, 0)
    )
    stack = StackDefinition("stack_01", "Artwork", required, 4.0, 1.0)
    data = build_stack_manifest_data(path, pixels, config, [stack])

    manifest, errors, warnings = validate_stack_manifest(data, pixels)

    assert errors == []
    assert warnings == []
    assert manifest is not None
    assert manifest.stacks[0].pixels == required


def test_manifest_reports_unassigned_non_background_but_not_background(tmp_path):
    path = tmp_path / "scene.png"
    _image(path)
    config = _config()
    pixels, _ = prepare_relief_image(path, config)
    data = build_stack_manifest_data(path, pixels, config, [])

    manifest, errors, _ = validate_stack_manifest(data, pixels)
    draft, draft_errors, warnings = validate_stack_manifest(
        data, pixels, require_complete=False
    )

    assert manifest is None
    assert any("4 non-background pixel(s) are unassigned" in error for error in errors)
    assert draft is not None
    assert draft_errors == []
    assert warnings == ["4 non-background pixel(s) are unassigned"]


def test_manifest_validates_frozen_processing_settings(tmp_path):
    path = tmp_path / "scene.png"
    _image(path)
    config = _config()
    pixels, _ = prepare_relief_image(path, config)
    data = build_stack_manifest_data(path, pixels, config, [])
    data["processing"]["connectivity"] = 7
    data["processed_image"]["pixel_sha256"] = "z" * 64

    manifest, errors, _ = validate_stack_manifest(
        data, pixels, require_complete=False
    )

    assert manifest is None
    assert "processing.connectivity must be 0, 4, or 8" in errors
    assert any("pixel_sha256" in error for error in errors)


def test_plan_uses_background_fill_and_preserves_each_pixel_color(tmp_path):
    path = tmp_path / "scene.png"
    _image(path)
    config = _config()
    pixels, _ = prepare_relief_image(path, config)
    required = frozenset(
        coordinate for coordinate, rgba in pixels.pixels.items() if rgba[:3] != (0, 0, 0)
    )
    data = build_stack_manifest_data(
        path,
        pixels,
        config,
        [StackDefinition("stack_01", "Mixed", required, 3.0, 1.0)],
    )
    manifest, errors, _ = validate_stack_manifest(data, pixels)
    assert errors == []
    assert manifest is not None

    plan = create_stack_relief_plan(manifest, pixels)

    fill = [span for span in plan.spans if span.role == "background_fill"]
    colors = [span for span in plan.spans if span.role == "pixel_color"]
    assert len(fill) == 1
    assert fill[0].rgb == (0, 0, 0)
    assert (fill[0].z_bottom, fill[0].z_top) == (0.0, 2.0)
    assert {(span.rgb, span.z_bottom, span.z_top) for span in colors} == {
        ((255, 0, 0), 2.0, 3.0),
        ((0, 0, 255), 2.0, 3.0),
    }


def test_solid_color_stack_omits_zero_depth_fill(tmp_path):
    path = tmp_path / "scene.png"
    _image(path)
    config = _config()
    pixels, _ = prepare_relief_image(path, config)
    red = frozenset(
        coordinate for coordinate, rgba in pixels.pixels.items() if rgba[:3] == (255, 0, 0)
    )
    blue = frozenset(
        coordinate for coordinate, rgba in pixels.pixels.items() if rgba[:3] == (0, 0, 255)
    )
    data = build_stack_manifest_data(
        path,
        pixels,
        config,
        [
            StackDefinition("stack_01", "Red", red, 5.0, 5.0),
            StackDefinition("stack_02", "Blue", blue, 1.0, 1.0),
        ],
    )
    manifest, errors, _ = validate_stack_manifest(data, pixels)
    assert errors == []
    assert manifest is not None

    plan = create_stack_relief_plan(manifest, pixels)

    assert all(span.role != "background_fill" for span in plan.spans)
    assert {(span.rgb, span.z_bottom, span.z_top) for span in plan.spans} == {
        ((255, 0, 0), 0.0, 5.0),
        ((0, 0, 255), 0.0, 1.0),
    }


def test_stack_manifest_converts_to_3mf_and_render(tmp_path):
    path = tmp_path / "scene.png"
    output = tmp_path / "scene.3mf"
    manifest_path = tmp_path / "scene.manifest.json"
    _image(path)
    config = _config()
    pixels, _ = prepare_relief_image(path, config)
    red = frozenset(
        coordinate for coordinate, rgba in pixels.pixels.items() if rgba[:3] == (255, 0, 0)
    )
    blue = frozenset(
        coordinate for coordinate, rgba in pixels.pixels.items() if rgba[:3] == (0, 0, 255)
    )
    data = build_stack_manifest_data(
        path,
        pixels,
        config,
        [
            StackDefinition("stack_01", "Maze", red, 4.0, 1.0),
            StackDefinition("stack_02", "Character", blue, 2.0, 2.0),
        ],
    )
    write_stack_manifest(manifest_path, data)

    conversion_config = _config()
    conversion_config.relief_manifest_path = str(manifest_path)
    conversion_config.render_model = True
    result = convert_image_to_3mf(
        str(path),
        str(output),
        conversion_config,
    )

    assert output.exists()
    assert result["num_colors"] == 3
    assert result["render_path"]
    assert (tmp_path / "scene_render.png").exists()


def test_cli_manifest_opens_editor_with_default_path(tmp_path, monkeypatch):
    path = tmp_path / "scene.png"
    _image(path)
    captured = {}

    def fake_launch(source, manifest, config):
        captured["source"] = Path(source)
        captured["manifest"] = Path(manifest)
        return 0

    monkeypatch.setattr("pixel_to_3mf.stack_editor.launch_stack_editor", fake_launch)
    monkeypatch.setattr(sys, "argv", ["pixel-to-3mf", str(path), "--manifest"])

    main()

    assert captured == {
        "source": path,
        "manifest": tmp_path / "scene.manifest.json",
    }


def test_cli_validate_manifest_alias_accepts_complete_stack_manifest(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "scene.png"
    manifest_path = tmp_path / "scene.manifest.json"
    _image(path)
    config = _config()
    pixels, _ = prepare_relief_image(path, config)
    required = frozenset(
        coordinate for coordinate, rgba in pixels.pixels.items() if rgba[:3] != (0, 0, 0)
    )
    write_stack_manifest(
        manifest_path,
        build_stack_manifest_data(
            path,
            pixels,
            config,
            [StackDefinition("stack_01", "Artwork", required, 2.0, 1.0)],
        ),
    )
    monkeypatch.setattr(
        sys, "argv", ["pixel-to-3mf", "--validate-manifest", str(manifest_path)]
    )

    main()

    assert "Relief manifest is valid" in capsys.readouterr().out
