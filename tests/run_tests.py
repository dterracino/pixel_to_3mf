#!/usr/bin/env python3
"""
Test runner for pixel_to_3mf test suite.

Runs all unit tests and displays results.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import all test modules
from tests import (
    test_image_processor,
    test_region_merger,
    test_mesh_generator,
    test_threemf_writer,
    test_pixel_to_3mf,
    test_cli,
    test_quantization,
    test_padding,
    test_operation_order,
    test_trim_disconnected,
    test_trim_integration,
    test_render_model
)


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test modules
    suite.addTests(loader.loadTestsFromModule(test_image_processor))
    suite.addTests(loader.loadTestsFromModule(test_region_merger))
    suite.addTests(loader.loadTestsFromModule(test_mesh_generator))
    suite.addTests(loader.loadTestsFromModule(test_threemf_writer))
    suite.addTests(loader.loadTestsFromModule(test_pixel_to_3mf))
    suite.addTests(loader.loadTestsFromModule(test_cli))
    suite.addTests(loader.loadTestsFromModule(test_quantization))
    suite.addTests(loader.loadTestsFromModule(test_padding))
    suite.addTests(loader.loadTestsFromModule(test_operation_order))
    suite.addTests(loader.loadTestsFromModule(test_trim_disconnected))
    suite.addTests(loader.loadTestsFromModule(test_trim_integration))
    suite.addTests(loader.loadTestsFromModule(test_render_model))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
