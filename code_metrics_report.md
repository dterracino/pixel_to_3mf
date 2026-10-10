# Code Metrics Refactoring Report

## Scope and configuration

- Target: `.`
- Configuration: `E:/pixel_to_3mf/tools/code_metrics.json`
- Default exclusions enabled: `true`
- Custom exclusions: none
- Thresholds: lines 500, code lines 500, classes 1, definition lines 100
- Reproduce: `python tools/code_metrics.py . --report`

## Executive summary

- Files scanned: 77
- Files with unresolved findings: 40
- Line findings: 25
- Class findings: 21
- Long-definition findings: 24
- Analysis errors: 0

## Refactoring candidates

### `pixel_to_3mf/polygon_optimizer.py`

- Physical lines: 1045 (limit 500, over by 545)
- Code lines: 522 (limit 500, over by 22)
- Long definition: 162 (limit 100, over by 62); function triangulate_polygon_2d, lines 297-458
- Long definition: 202 (limit 100, over by 102); function extrude_polygon_to_mesh, lines 543-744
- Long definition: 112 (limit 100, over by 12); function generate_region_mesh_optimized, lines 748-859

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/cli.py`

- Physical lines: 1940 (limit 500, over by 1440)
- Code lines: 1533 (limit 500, over by 1033)
- Long definition: 169 (limit 100, over by 69); function process_batch, lines 190-358
- Long definition: 1576 (limit 100, over by 1476); function main, lines 361-1936

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/relief_manifest.py`

- Physical lines: 578 (limit 500, over by 78)
- Code lines: 501 (limit 500, over by 1)
- Classes: 2 (limit 1, over by 1); ReliefSection (line 30), ReliefManifest (line 42)
- Long definition: 132 (limit 100, over by 32); function build_relief_manifest, lines 73-204
- Long definition: 227 (limit 100, over by 127); function validate_relief_manifest, lines 352-578

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Check whether the classes are cohesive and intentionally colocated.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/threemf_core.py`

- Physical lines: 990 (limit 500, over by 490)
- Classes: 3 (limit 1, over by 2); ThreeMFMesh (line 73), ThreeMFObject (line 97), ThreeMFWriter (line 826)
- Long definition: 103 (limit 100, over by 3); function _generate_main_model_xml, lines 558-660
- Long definition: 103 (limit 100, over by 3); method ThreeMFWriter.write, lines 888-990

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Check whether the classes are cohesive and intentionally colocated.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/pixel_to_3mf.py`

- Physical lines: 650 (limit 500, over by 150)
- Long definition: 545 (limit 100, over by 445); function convert_image_to_3mf, lines 106-650

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/batch_checker.py`

- Long definition: 439 (limit 100, over by 339); function check_batch_compatibility, lines 56-494

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/threemf_writer.py`

- Physical lines: 1120 (limit 500, over by 620)
- Code lines: 587 (limit 500, over by 87)
- Long definition: 366 (limit 100, over by 266); function write_3mf, lines 755-1120

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/image_processor.py`

- Physical lines: 608 (limit 500, over by 108)
- Long definition: 202 (limit 100, over by 102); function load_image, lines 318-519

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `test_region_reduction.py`

- Physical lines: 724 (limit 500, over by 224)
- Long definition: 192 (limit 100, over by 92); function main, lines 529-720

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `smooth_preview.py`

- Long definition: 189 (limit 100, over by 89); function main, lines 93-281

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `debug_render_coords.py`

- Long definition: 160 (limit 100, over by 60); function create_multi_view_renders, lines 134-293

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/mesh_postprocessor.py`

- Long definition: 155 (limit 100, over by 55); function fix_mesh_issues, lines 126-280

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/summary_writer.py`

- Long definition: 154 (limit 100, over by 54); function write_summary_file, lines 87-240

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/padding_processor.py`

- Long definition: 146 (limit 100, over by 46); function add_padding, lines 19-164

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/morph_smoother.py`

- Long definition: 135 (limit 100, over by 35); function smooth_pixel_regions, lines 39-173

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/rectangle_optimizer.py`

- Physical lines: 533 (limit 500, over by 33)
- Long definition: 131 (limit 100, over by 31); function generate_triangles, lines 279-409

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/mesh_generator.py`

- Physical lines: 573 (limit 500, over by 73)
- Long definition: 118 (limit 100, over by 18); function _generate_region_mesh_original, lines 95-212

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/config.py`

- Long definition: 116 (limit 100, over by 16); method ConversionConfig.__post_init__, lines 263-378

Suggested investigation:

- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `pixel_to_3mf/region_merger.py`

- Physical lines: 509 (limit 500, over by 9)
- Long definition: 114 (limit 100, over by 14); function denoise_blob_pixels, lines 396-509

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Look for cohesive phases or helpers that can be extracted without changing behavior.

### `tests/test_threemf_core.py`

- Physical lines: 914 (limit 500, over by 414)
- Code lines: 579 (limit 500, over by 79)
- Classes: 11 (limit 1, over by 10); TestFormatFloat (line 99), TestThreeMFMesh (line 143), TestThreeMFObject (line 180), TestCountMeshStats (line 216), TestValidateTriangleWinding (line 255), TestCalculateModelBounds (line 297), TestCalculateModelCenter (line 364), TestCreateCenteringTransform (line 403), TestPrettifyXml (line 442), TestThreeMFWriter (line 480), TestThreeMFWriterEdgeCases (line 830)

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Check whether the classes are cohesive and intentionally colocated.

### `pixel_to_3mf/mesh_new.py`

- Physical lines: 836 (limit 500, over by 336)
- Code lines: 537 (limit 500, over by 37)

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.

### `tests/test_cli.py`

- Physical lines: 815 (limit 500, over by 315)
- Code lines: 529 (limit 500, over by 29)
- Classes: 6 (limit 1, over by 5); TestIsImageFile (line 41), TestParseRgbColor (line 95), TestProcessBatch (line 113), TestGenerateBatchSummary (line 551), TestConversionConfigBatchFlags (line 732), TestFilamentFilters (line 762)

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Check whether the classes are cohesive and intentionally colocated.

### `pixel_to_3mf/boundary_smoother.py`

- Physical lines: 737 (limit 500, over by 237)
- Classes: 3 (limit 1, over by 2); SmoothedRegion (line 34), _BoundarySegment (line 50), _BoundaryPath (line 57)

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_palette_relief.py`

- Physical lines: 607 (limit 500, over by 107)

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.

### `tests/test_pixel_to_3mf.py`

- Physical lines: 605 (limit 500, over by 105)
- Classes: 6 (limit 1, over by 5); TestConvertImageTo3MF (line 29), TestConvertImageTo3MFErrors (line 238), TestConvertImageTo3MFWithRealSamples (line 327), TestFormatFilesize (line 365), TestConvertWithPadding (line 406), TestConvertImageTo3MFSolidCore (line 477)

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_polygon_optimizer.py`

- Physical lines: 598 (limit 500, over by 98)
- Classes: 7 (limit 1, over by 6); TestPixelsToPolygon (line 28), TestTriangulatePolygon (line 96), TestExtrudePolygonToMesh (line 172), TestOptimizedMeshGeneration (line 217), TestOptimizationComparison (line 363), TestBackingPlateOptimized (line 448), TestManifoldProperties (line 489)

Suggested investigation:

- Examine whether the file contains separable responsibilities before splitting it.
- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_mesh_generator.py`

- Classes: 6 (limit 1, over by 5); TestMesh (line 27), TestGenerateRegionMesh (line 51), TestGenerateBackingPlate (line 185), TestMeshValidity (line 265), TestGenerateSolidCore (line 298), TestGenerateRegionMeshShell (line 383)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_config.py`

- Classes: 4 (limit 1, over by 3); TestFormatTitleFromFilename (line 12), TestConversionConfigTitleGeneration (line 212), TestConversionConfigSolidCore (line 287), TestConversionConfigRelief (line 368)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_image_processor.py`

- Classes: 4 (limit 1, over by 3); TestPixelData (line 31), TestCalculatePixelSize (line 90), TestLoadImage (line 137), TestGetPixelBoundsMm (line 289)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_region_merger.py`

- Classes: 4 (limit 1, over by 3); TestRegion (line 32), TestFloodFill (line 56), TestMergeRegions (line 148), TestGetRegionBounds (line 232)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_diagonal_connectivity.py`

- Classes: 3 (limit 1, over by 2); TestDiagonalConnectivityDetection (line 32), TestDiagonalRegionFallback (line 86), TestRealWorldDiagonalPatterns (line 147)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_mesh_stats.py`

- Classes: 3 (limit 1, over by 2); TestMeshStatistics (line 32), TestTriangleWinding (line 128), TestCountMeshStats (line 180)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_quantization.py`

- Classes: 3 (limit 1, over by 2); TestQuantizeImage (line 24), TestLoadImageWithQuantization (line 129), TestConfigQuantizationValidation (line 284)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_render.py`

- Classes: 3 (limit 1, over by 2); TestRenderPath (line 31), TestRenderOutput (line 53), TestRenderIntegration (line 70)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_summary_writer.py`

- Classes: 3 (limit 1, over by 2); TestWriteSummaryFile (line 17), TestExtruderToAmsLocation (line 215), TestSummaryWithAmsLocation (line 289)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_threemf_writer.py`

- Classes: 3 (limit 1, over by 2); TestFormatFloat (line 27), TestWrite3MF (line 56), TestWrite3MFIntegration (line 364)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `pixel_to_3mf/relief_plan.py`

- Classes: 2 (limit 1, over by 1); ReliefMaterialSpan (line 13), PaletteReliefPlan (line 24)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_backing_plate_sync.py`

- Classes: 2 (limit 1, over by 1); TestFilteredPixelData (line 24), TestBackingPlateSynchronization (line 105)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_padding.py`

- Classes: 2 (limit 1, over by 1); TestShouldApplyPadding (line 30), TestAddPadding (line 49)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

### `tests/test_trim_disconnected.py`

- Classes: 2 (limit 1, over by 1); TestIsPixelDisconnected (line 21), TestTrimDisconnectedPixels (line 115)

Suggested investigation:

- Check whether the classes are cohesive and intentionally colocated.

## Analysis errors

None.

## Accepted findings

- `tools/code_metrics.py`: classes 14 (limit 1); ConfigError (line 93), ScanConfig (line 98), Thresholds (line 107), TerminalConfig (line 115), MarkdownReportConfig (line 123), EffectiveConfig (line 130), ClassMetric (line 139), DefinitionMetric (line 145), FileMetrics (line 154), Finding (line 182), FileReport (line 193), Summary (line 207), MetricsReport (line 226), _StructureVisitor (line 537)
- `tools/code_metrics.py`: code_lines 751 (limit 500)
- `tools/code_metrics.py`: lines 890 (limit 500)

## Agent handoff constraints

- Inspect existing behavior and tests before modifying a candidate.
- Preserve public APIs and observable behavior unless separately authorized.
- Treat these metrics as signals, not automatic proof of poor design.
- Apply separation of concerns and DRY without introducing needless abstractions.
- Run relevant tests and static checks after each coherent refactor.
