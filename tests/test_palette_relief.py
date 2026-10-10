"""Focused tests for palette-relief manifests and geometry."""

from __future__ import annotations

import json
import zipfile
import sys
from copy import deepcopy
from typing import Any

from PIL import Image
import pytest

from pixel_to_3mf.config import ConversionConfig
from pixel_to_3mf.cli import main
from pixel_to_3mf.pixel_to_3mf import convert_image_to_3mf
from pixel_to_3mf.palette_relief import build_palette_relief_meshes
from pixel_to_3mf.image_processor import PixelData
from pixel_to_3mf.mesh_generator import check_mesh_manifold, generate_region_mesh_shell
from pixel_to_3mf.region_merger import Region
from pixel_to_3mf.relief_plan import create_palette_relief_plan
from pixel_to_3mf.relief_manifest import (
    build_relief_manifest,
    load_relief_manifest,
    validate_relief_manifest,
    write_relief_manifest,
)
from pixel_to_3mf.relief_workflow import (
    color_at_image_coordinate,
    generate_relief_manifest_file,
    generate_relief_section_images,
    prepare_relief_image,
)


def _make_image(path):
    image = Image.new("RGB", (4, 2), (0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((3, 1), (255, 0, 0))
    image.putpixel((1, 0), (255, 255, 255))
    image.save(path)


def _config(**overrides: Any):
    config = ConversionConfig(
        scale_mm_per_pixel=1.0,
        max_colors=8,
        backing_color=(0, 0, 0),
        relief_background_color=(0, 0, 0),
        color_naming_mode="hex",
        trim_disconnected=False,
        skip_checks=True,
    )
    for name, value in overrides.items():
        setattr(config, name, value)
    return config


def _completed_manifest(tmp_path):
    image_path = tmp_path / "palette.png"
    _make_image(image_path)
    config = _config()
    pixels, regions = prepare_relief_image(image_path, config)
    data = build_relief_manifest(image_path, pixels, regions, config)
    for section in data["sections"]:
        section["height_mm"] = 2.0
    return image_path, config, pixels, regions, data


def test_manifest_orders_by_pixel_count_and_omits_background(tmp_path):
    image_path = tmp_path / "palette.png"
    _make_image(image_path)
    config = _config()
    pixels, regions = prepare_relief_image(image_path, config)

    data = build_relief_manifest(image_path, pixels, regions, config)

    assert data["model"]["height_reference"] == "backing_top"
    assert [section["color"]["rgb"] for section in data["sections"]] == [
        [255, 0, 0],
        [255, 255, 255],
    ]
    assert data["sections"][0]["pixel_count"] == 2
    assert data["sections"][0]["component_count"] == 2
    assert [section["section_number"] for section in data["sections"]] == [1, 2]
    assert [section["section_name"] for section in data["sections"]] == [
        "palette.section_01",
        "palette.section_02",
    ]
    assert [section["section_image"] for section in data["sections"]] == [
        "palette.section_01.png",
        "palette.section_02.png",
    ]
    assert all(section["height_mm"] is None for section in data["sections"])


def test_manifest_generation_writes_full_canvas_section_images(tmp_path):
    image_path = tmp_path / "palette.png"
    manifest_path = tmp_path / "palette.manifest.json"
    _make_image(image_path)

    written = generate_relief_manifest_file(image_path, manifest_path, _config())

    assert written == manifest_path
    data = load_relief_manifest(manifest_path)
    assert [section["section_image"] for section in data["sections"]] == [
        "palette.section_01.png",
        "palette.section_02.png",
    ]

    red = Image.open(tmp_path / "palette.section_01.png")
    assert red.mode == "RGB"
    assert red.size == (4, 2)
    assert red.getpixel((0, 0)) == (255, 0, 0)
    assert red.getpixel((3, 1)) == (255, 0, 0)
    assert red.getpixel((1, 0)) == (0, 0, 0)
    assert red.getpixel((2, 1)) == (0, 0, 0)

    white = Image.open(tmp_path / "palette.section_02.png")
    assert white.mode == "RGB"
    assert white.size == (4, 2)
    assert white.getpixel((1, 0)) == (255, 255, 255)
    assert white.getpixel((0, 0)) == (0, 0, 0)
    assert white.getpixel((3, 1)) == (0, 0, 0)


def test_section_images_use_processed_canvas_and_palette(tmp_path):
    pixels = PixelData(
        2,
        3,
        1.0,
        {
            (0, 2): (10, 20, 30, 255),
            (1, 0): (10, 20, 30, 255),
        },
    )
    data = {
        "model": {"background_color": [1, 2, 3]},
        "sections": [
            {
                "section_image": "processed.section_01.png",
                "color": {"rgb": [10, 20, 30]},
            }
        ],
    }

    paths = generate_relief_section_images(pixels, data, tmp_path)

    assert paths == [tmp_path / "processed.section_01.png"]
    image = Image.open(paths[0])
    assert image.size == (2, 3)
    assert image.getpixel((0, 0)) == (10, 20, 30)
    assert image.getpixel((1, 2)) == (10, 20, 30)
    assert image.getpixel((0, 2)) == (1, 2, 3)


def test_manifest_generation_is_deterministic_and_round_trips(tmp_path):
    image_path = tmp_path / "palette.png"
    manifest_path = tmp_path / "palette.relief.json"
    _make_image(image_path)
    config = _config()
    pixels, regions = prepare_relief_image(image_path, config)

    first = build_relief_manifest(image_path, pixels, regions, config)
    second = build_relief_manifest(image_path, pixels, regions, config)
    assert first == second

    write_relief_manifest(manifest_path, first)
    assert load_relief_manifest(manifest_path) == first


def test_ten_colors_with_one_background_produces_nine_sections(tmp_path):
    image_path = tmp_path / "ten.png"
    colors = [(0, 0, 0)] + [(index * 20, 10, 255 - index * 20) for index in range(1, 10)]
    image = Image.new("RGB", (10, 1))
    for x, color in enumerate(colors):
        image.putpixel((x, 0), color)
    image.save(image_path)
    config = _config(max_colors=10, no_backing_color=True)
    pixels, regions = prepare_relief_image(image_path, config)

    data = build_relief_manifest(image_path, pixels, regions, config)

    assert data["processed_image"]["color_count"] == 10
    assert len(data["sections"]) == 9


def test_manifest_records_exact_pre_quantization_contributions(tmp_path):
    image_path = tmp_path / "source.png"
    Image.new("RGB", (3, 1), (0, 0, 0)).save(image_path)
    final = PixelData(
        3,
        1,
        1.0,
        {
            (0, 0): (0, 0, 0, 255),
            (1, 0): (255, 0, 0, 255),
            (2, 0): (255, 0, 0, 255),
        },
    )
    before = PixelData(
        3,
        1,
        1.0,
        {
            (0, 0): (0, 0, 0, 255),
            (1, 0): (250, 0, 0, 255),
            (2, 0): (255, 20, 20, 255),
        },
    )
    regions = [Region((0, 0, 0), {(0, 0)}), Region((255, 0, 0), {(1, 0), (2, 0)})]

    data = build_relief_manifest(
        image_path, final, regions, _config(), pre_quantization_pixels=before
    )

    assert data["sections"][0]["pre_quantization_colors"] == [
        {"rgb": [250, 0, 0], "hex": "#FA0000", "pixel_count": 1},
        {"rgb": [255, 20, 20], "hex": "#FF1414", "pixel_count": 1},
    ]


def test_manifest_validation_rejects_unset_and_degenerate_heights(tmp_path):
    image_path = tmp_path / "palette.png"
    _make_image(image_path)
    config = _config()
    pixels, regions = prepare_relief_image(image_path, config)
    data = build_relief_manifest(image_path, pixels, regions, config)

    _, errors, _ = validate_relief_manifest(data, pixels, regions)
    assert any("height_mm must be a number" in error for error in errors)

    for section in data["sections"]:
        section["height_mm"] = 1.0
    _, errors, _ = validate_relief_manifest(data, pixels, regions)
    assert any("greater than interface_depth_mm" in error for error in errors)

    data["sections"][0]["height_mm"] = -1.0
    data["sections"][0]["color_depth_mode"] = "unknown"
    _, errors, _ = validate_relief_manifest(data, pixels, regions)
    assert any("height_mm must be greater than zero" in error for error in errors)
    assert any("color_depth_mode" in error for error in errors)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_manifest_validation_rejects_non_finite_numbers(tmp_path, value):
    _, _, pixels, regions, data = _completed_manifest(tmp_path)
    data["sections"][0]["height_mm"] = value

    manifest, errors, _ = validate_relief_manifest(data, pixels, regions)

    assert manifest is None
    assert any("height_mm must be finite" in error for error in errors)


def test_manifest_validation_rejects_bad_schema_hashes_and_processing(tmp_path):
    _, _, pixels, regions, valid = _completed_manifest(tmp_path)
    cases = []
    for mutate in (
        lambda data: data.update(schema_version=999),
        lambda data: data.update(mode="unknown"),
        lambda data: data["source"].update(sha256="z" * 64),
        lambda data: data["processed_image"].update(pixel_sha256="x" * 64),
        lambda data: data["processing"].update(connectivity=6),
        lambda data: data["processing"].update(max_size_mm=float("inf")),
        lambda data: data["processing"].update(quantize="yes"),
    ):
        candidate = deepcopy(valid)
        mutate(candidate)
        cases.append(candidate)

    for candidate in cases:
        manifest, errors, _ = validate_relief_manifest(candidate, pixels, regions)
        assert manifest is None
        assert errors


def test_manifest_validation_rejects_missing_duplicate_and_modified_sections(tmp_path):
    _, _, pixels, regions, valid = _completed_manifest(tmp_path)

    missing = deepcopy(valid)
    missing["sections"].pop()
    _, missing_errors, _ = validate_relief_manifest(missing, pixels, regions)
    assert any("section colors" in error for error in missing_errors)

    duplicate = deepcopy(valid)
    duplicate["sections"][1]["color"]["rgb"] = duplicate["sections"][0]["color"]["rgb"]
    _, duplicate_errors, _ = validate_relief_manifest(duplicate, pixels, regions)
    assert any("duplicates" in error for error in duplicate_errors)

    modified = deepcopy(valid)
    modified["sections"][0]["pixel_count"] += 1
    _, modified_errors, _ = validate_relief_manifest(modified, pixels, regions)
    assert any("pixel_count" in error for error in modified_errors)


def test_manifest_validation_rejects_modified_section_identity(tmp_path):
    _, _, pixels, regions, valid = _completed_manifest(tmp_path)
    invalid = deepcopy(valid)
    invalid["sections"][0]["section_number"] = 2
    invalid["sections"][0]["section_name"] = "wrong"
    invalid["sections"][0]["section_image"] = "wrong.png"

    _, errors, _ = validate_relief_manifest(invalid, pixels, regions)

    assert any("section_number" in error for error in errors)
    assert any("section_name" in error for error in errors)
    assert any("section_image" in error for error in errors)


def test_palette_relief_conversion_aggregates_material_objects(tmp_path):
    image_path = tmp_path / "palette.png"
    manifest_path = tmp_path / "palette.relief.json"
    output_path = tmp_path / "palette.3mf"
    _make_image(image_path)
    config = _config()
    pixels, regions = prepare_relief_image(image_path, config)
    data = build_relief_manifest(image_path, pixels, regions, config)
    for section in data["sections"]:
        section["height_mm"] = 3.0 if section["color"]["rgb"] == [255, 0, 0] else 2.0
    write_relief_manifest(manifest_path, data)

    result = convert_image_to_3mf(
        str(image_path),
        str(output_path),
        _config(
            relief_manifest_path=str(manifest_path),
            generate_summary=True,
            generate_swatches=True,
            generate_preview=True,
            render_model=True,
        ),
    )

    assert output_path.exists()
    # Black backing/fill + red + white: disconnected red pixels remain one
    # aggregate material object rather than separate slicer entries.
    assert result["num_colors"] == 3
    assert result["summary_path"]
    assert result["swatches_path"]
    assert result["render_path"]
    assert result["preview_path"]
    assert (tmp_path / "palette_render.png").exists()
    assert (tmp_path / "palette_preview.png").exists()
    with zipfile.ZipFile(output_path) as archive:
        model = archive.read("3D/Objects/object_1.model").decode("utf-8")
    assert model.count("<object ") == 3


def test_depth_modes_create_the_expected_z_partitions(tmp_path):
    image_path = tmp_path / "palette.png"
    _make_image(image_path)
    config = _config()
    pixels, regions = prepare_relief_image(image_path, config)
    data = build_relief_manifest(image_path, pixels, regions, config)
    for section in data["sections"]:
        if section["color"]["rgb"] == [255, 0, 0]:
            section["height_mm"] = 3.0
            section["color_depth_mode"] = "deep_color"
        else:
            section["height_mm"] = 2.0
            section["color_depth_mode"] = "top_cap"
    manifest, errors, _ = validate_relief_manifest(data, pixels, regions)
    assert errors == []
    assert manifest is not None

    plan = create_palette_relief_plan(manifest, regions)
    meshes, colors = build_palette_relief_meshes(plan, pixels, config)
    by_color = {color: mesh for (mesh, _), color in zip(meshes, colors)}
    red_z = {vertex[2] for vertex in by_color[(255, 0, 0)].vertices}
    white_z = {vertex[2] for vertex in by_color[(255, 255, 255)].vertices}
    backing_z = {vertex[2] for vertex in by_color[(0, 0, 0)].vertices}

    assert red_z == {1.0, 3.0}
    assert white_z == {1.0, 2.0}
    assert min(backing_z) == -1.0
    assert max(backing_z) == 1.0

    roles = [span.role for span in plan.spans]
    assert roles.count("background") == 1
    assert roles.count("section_backing_fill") == 2
    assert roles.count("section_color") == 2


def test_palette_relief_rejects_unsupported_geometry_modes(tmp_path):
    image_path = tmp_path / "palette.png"
    _make_image(image_path)
    pixels, regions = prepare_relief_image(image_path, _config())

    for config, expected in (
        (_config(optimize_mesh=True), "optimized mesh"),
        (_config(smooth_boundaries=True), "boundary smoothing"),
        (_config(solid_core=True, base_height_mm=0.0), "physical backing"),
        (_config(no_backing_plate=True), "physical backing"),
    ):
        with pytest.raises(ValueError, match=expected):
            build_relief_manifest(image_path, pixels, regions, config)


def test_explicit_height_shell_splits_saddle_corners():
    # Both pixels at the diagonal contact have another edge neighbor. The old
    # coarse diagonal-only test missed this and created a four-face edge.
    region = Region((255, 0, 0), {(0, 0), (1, 0), (2, 1), (2, 2)})
    pixels = PixelData(
        3,
        3,
        1.0,
        {coord: (255, 0, 0, 255) for coord in region.pixels},
    )
    mesh = generate_region_mesh_shell(region, pixels, _config(), 0.0, 2.0)

    result = check_mesh_manifold(mesh)
    assert result["boundary_edges"] == 0
    assert result["non_manifold_edges"] == 0
    assert result["is_valid"] is True


def test_processed_fingerprint_detects_stale_manifest(tmp_path):
    image_path = tmp_path / "palette.png"
    _make_image(image_path)
    config = _config()
    pixels, regions = prepare_relief_image(image_path, config)
    data = build_relief_manifest(image_path, pixels, regions, config)
    for section in data["sections"]:
        section["height_mm"] = 2.0

    image = Image.open(image_path)
    image.putpixel((2, 0), (0, 255, 0))
    image.save(image_path)
    changed_pixels, changed_regions = prepare_relief_image(image_path, _config())

    _, errors, _ = validate_relief_manifest(data, changed_pixels, changed_regions)
    assert any("pixel_sha256" in error for error in errors)


def test_cli_generate_validate_and_sample_color(tmp_path, monkeypatch, capsys):
    image_path = tmp_path / "palette.png"
    manifest_path = tmp_path / "custom.relief.json"
    _make_image(image_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixel-to-3mf",
            str(image_path),
            "--background-color",
            "0,0,0",
            "--backing-color",
            "0,0,0",
            "--generate-relief-manifest",
            str(manifest_path),
        ],
    )
    main()
    assert manifest_path.exists()

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for section in data["sections"]:
        section["height_mm"] = 2.0
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["pixel-to-3mf", "--validate-relief-manifest", str(manifest_path)],
    )
    main()
    assert "Relief manifest is valid" in capsys.readouterr().out

    monkeypatch.setattr(
        sys,
        "argv",
        ["pixel-to-3mf", str(image_path), "--color-at", "0,0"],
    )
    main()
    assert "RGB(255, 0, 0)" in capsys.readouterr().out


def test_cli_default_manifest_and_section_image_names(tmp_path, monkeypatch):
    image_path = tmp_path / "arcade-scene.png"
    _make_image(image_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixel-to-3mf",
            str(image_path),
            "--background-color",
            "0,0,0",
            "--backing-color",
            "0,0,0",
            "--generate-relief-manifest",
        ],
    )

    main()

    manifest_path = tmp_path / "arcade-scene.manifest.json"
    assert manifest_path.exists()
    data = load_relief_manifest(manifest_path)
    assert [section["section_image"] for section in data["sections"]] == [
        "arcade-scene.section_01.png",
        "arcade-scene.section_02.png",
    ]
    assert (tmp_path / "arcade-scene.section_01.png").exists()
    assert (tmp_path / "arcade-scene.section_02.png").exists()


def test_cli_validation_rejects_changed_source_file(tmp_path, monkeypatch):
    image_path, _, _, _, data = _completed_manifest(tmp_path)
    manifest_path = tmp_path / "stale.relief.json"
    write_relief_manifest(manifest_path, data)
    image = Image.open(image_path)
    image.putpixel((2, 0), (0, 255, 0))
    image.save(image_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["pixel-to-3mf", "--validate-relief-manifest", str(manifest_path)],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_cli_validation_runs_geometry_dry_run(tmp_path, monkeypatch):
    _, _, _, _, data = _completed_manifest(tmp_path)
    manifest_path = tmp_path / "geometry.relief.json"
    write_relief_manifest(manifest_path, data)
    monkeypatch.setattr(
        "pixel_to_3mf.palette_relief.validate_palette_relief_geometry",
        lambda *args, **kwargs: ["synthetic geometry failure"],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["pixel-to-3mf", "--validate-relief-manifest", str(manifest_path)],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_processed_coordinate_sampling_rejects_transparency_and_bounds(tmp_path):
    image_path = tmp_path / "transparent.png"
    image = Image.new("RGBA", (3, 2), (0, 0, 0, 0))
    image.putpixel((1, 0), (10, 20, 30, 255))
    image.save(image_path)
    pixels, _ = prepare_relief_image(image_path, _config(no_backing_color=True))

    assert color_at_image_coordinate(pixels, 1, 0) == (10, 20, 30, 255)
    with pytest.raises(ValueError, match="transparent"):
        color_at_image_coordinate(pixels, 0, 0)
    with pytest.raises(ValueError, match="outside processed image bounds"):
        color_at_image_coordinate(pixels, 3, 0)


def test_coordinate_sampling_uses_post_crop_dimensions(tmp_path):
    image_path = tmp_path / "cropped.png"
    image = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
    image.putpixel((2, 2), (1, 2, 3, 255))
    image.save(image_path)
    pixels, _ = prepare_relief_image(
        image_path,
        _config(auto_crop=True, no_backing_color=True),
    )

    assert (pixels.width, pixels.height) == (1, 1)
    assert color_at_image_coordinate(pixels, 0, 0) == (1, 2, 3, 255)
    with pytest.raises(ValueError, match="outside processed image bounds"):
        color_at_image_coordinate(pixels, 2, 2)


def test_coordinate_sampling_reports_quantized_color(tmp_path):
    image_path = tmp_path / "quantized.png"
    image = Image.new("RGB", (2, 1))
    image.putpixel((0, 0), (250, 0, 0))
    image.putpixel((1, 0), (255, 20, 20))
    image.save(image_path)
    pixels, _ = prepare_relief_image(
        image_path,
        _config(
            no_backing_color=True,
            quantize=True,
            quantize_colors=1,
        ),
    )

    assert color_at_image_coordinate(pixels, 0, 0) == color_at_image_coordinate(pixels, 1, 0)


def test_cli_rejects_conflicting_backing_selectors(tmp_path, monkeypatch):
    image_path = tmp_path / "palette.png"
    _make_image(image_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixel-to-3mf",
            str(image_path),
            "--backing-color",
            "0,0,0",
            "--backing-color-at",
            "0,0",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_backing_color_at_is_recorded_in_generated_manifest(tmp_path, monkeypatch):
    image_path = tmp_path / "palette.png"
    manifest_path = tmp_path / "sampled.relief.json"
    _make_image(image_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixel-to-3mf",
            str(image_path),
            "--background-color",
            "0,0,0",
            "--backing-color-at",
            "0,0",
            "--generate-relief-manifest",
            str(manifest_path),
        ],
    )

    main()

    data = load_relief_manifest(manifest_path)
    assert data["model"]["backing_color"] == [255, 0, 0]
    assert data["model"]["backing_color_selection"] == "coordinate"
    assert data["model"]["backing_color_coordinate"] == [0, 0]


def test_cli_rejects_optimized_palette_relief(tmp_path, monkeypatch):
    image_path, _, _, _, data = _completed_manifest(tmp_path)
    manifest_path = tmp_path / "palette.relief.json"
    write_relief_manifest(manifest_path, data)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixel-to-3mf",
            str(image_path),
            "--relief-manifest",
            str(manifest_path),
            "--optimize-mesh",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_quantized_artifact_is_independent_from_matched_preview(tmp_path):
    image_path = tmp_path / "many-colors.png"
    output_path = tmp_path / "many-colors.3mf"
    image = Image.new("RGB", (4, 1))
    for x, color in enumerate(((0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255))):
        image.putpixel((x, 0), color)
    image.save(image_path)

    result = convert_image_to_3mf(
        str(image_path),
        str(output_path),
        _config(
            quantize=True,
            quantize_colors=2,
            generate_quantized_preview=True,
            generate_preview=False,
        ),
    )

    assert result["preview_paths"] == [str(tmp_path / "many-colors_quantized.png")]
    assert (tmp_path / "many-colors_quantized.png").exists()
    assert not (tmp_path / "many-colors_preview.png").exists()


def test_manifest_generation_supports_iterative_quantization(tmp_path):
    image_path = tmp_path / "iterative.png"
    manifest_path = tmp_path / "iterative.relief.json"
    colors = (
        [(0, 0, 0)] * 6
        + [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    )
    image = Image.new("RGB", (len(colors), 1))
    for x, color in enumerate(colors):
        image.putpixel((x, 0), color)
    image.save(image_path)

    config = _config(
        quantize=True,
        quantize_colors=5,
        iterate_quantize=True,
        max_colors=3,
        no_backing_color=True,
        merge_similar_colors=False,
        relief_background_color=(0, 0, 36),
    )
    generate_relief_manifest_file(image_path, manifest_path, config)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert 3 <= data["processing"]["quantize_colors"] <= 5
    assert data["processing"]["iterate_quantize"] is True
    assert data["processed_image"]["pre_quantization_color_count"] == 5
    assert data["processed_image"]["color_count"] <= 3

    for section in data["sections"]:
        assert sum(
            contribution["pixel_count"]
            for contribution in section["pre_quantization_colors"]
        ) == section["pixel_count"]
        section_image = Image.open(tmp_path / section["section_image"])
        section_pixels = [
            section_image.getpixel((x, y))
            for y in range(section_image.height)
            for x in range(section_image.width)
        ]
        section_rgb = tuple(section["color"]["rgb"])
        background_rgb = tuple(data["model"]["background_color"])
        assert set(section_pixels) <= {background_rgb, section_rgb}
        assert section_pixels.count(section_rgb) == section["pixel_count"]
