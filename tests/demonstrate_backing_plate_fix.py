"""
Demonstration script showing the backing plate synchronization fix.

This script demonstrates the issue that was fixed and how the solution works.
"""

from pixel_to_3mf.pixel_to_3mf import _create_filtered_pixel_data
from pixel_to_3mf.region_merger import Region
from pixel_to_3mf.image_processor import PixelData


def print_section(title):
    """Print a section header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demonstrate_issue():
    """Demonstrate the backing plate synchronization issue and fix."""
    
    print_section("BACKING PLATE SYNCHRONIZATION FIX DEMONSTRATION")
    
    # Scenario: Image with main region + isolated pixels
    print("\n📊 SCENARIO: Image with disconnected pixels")
    print("-" * 70)
    print("Original image has 10 pixels:")
    print("  - Main region: 7 connected pixels (0,0) to (6,0)")
    print("  - Isolated pixel 1: (10,10)")
    print("  - Isolated pixel 2: (15,15)")
    print("  - Isolated pixel 3: (20,20)")
    
    # Create the original pixel data
    pixels = {
        (0, 0): (255, 0, 0, 255),
        (1, 0): (255, 0, 0, 255),
        (2, 0): (255, 0, 0, 255),
        (3, 0): (255, 0, 0, 255),
        (4, 0): (255, 0, 0, 255),
        (5, 0): (255, 0, 0, 255),
        (6, 0): (255, 0, 0, 255),
        (10, 10): (255, 0, 0, 255),  # Isolated
        (15, 15): (255, 0, 0, 255),  # Isolated
        (20, 20): (255, 0, 0, 255),  # Isolated
    }
    original_pixel_data = PixelData(width=21, height=21, pixel_size_mm=1.0, pixels=pixels)
    
    print(f"\n✓ Original pixel_data created: {len(original_pixel_data.pixels)} pixels")
    
    # Simulate region filtering (e.g., --trim removes isolated pixels)
    print("\n🔧 FILTERING: Remove isolated pixels (simulating --trim)")
    print("-" * 70)
    print("After filtering, only main connected region remains")
    
    main_region = Region(
        color=(255, 0, 0), 
        pixels={(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0)}
    )
    filtered_regions = [main_region]
    
    print(f"✓ Regions after filtering: {len(filtered_regions)}")
    print(f"✓ Total pixels in regions: {sum(len(r.pixels) for r in filtered_regions)}")
    
    # Show the problem (before fix)
    print_section("BEFORE FIX: Backing plate uses original pixel_data")
    print()
    print("❌ PROBLEM:")
    print(f"  - Colored regions: {sum(len(r.pixels) for r in filtered_regions)} pixels")
    print(f"  - Backing plate: {len(original_pixel_data.pixels)} pixels")
    print()
    print("  Result: 3 isolated pixels appear ONLY in backing plate!")
    print("  These create floating islands of unprintable geometry.")
    
    # Show the solution (after fix)
    print_section("AFTER FIX: Backing plate uses filtered pixel_data")
    print()
    filtered_pixel_data = _create_filtered_pixel_data(filtered_regions, original_pixel_data)
    
    print("✅ SOLUTION:")
    print(f"  - Colored regions: {sum(len(r.pixels) for r in filtered_regions)} pixels")
    print(f"  - Backing plate: {len(filtered_pixel_data.pixels)} pixels")
    print()
    print("  Result: Backing plate matches colored regions exactly!")
    print("  No floating islands, clean printable geometry.")
    
    # Verify the fix
    print_section("VERIFICATION")
    print()
    
    # Check that all region pixels are in filtered data
    all_region_pixels = set()
    for region in filtered_regions:
        all_region_pixels.update(region.pixels)
    
    filtered_coords = set(filtered_pixel_data.pixels.keys())
    
    assert filtered_coords == all_region_pixels, "Mismatch between regions and filtered data!"
    
    print("✓ All region pixels are in filtered pixel_data")
    print("✓ No extra pixels in filtered pixel_data")
    print("✓ Backing plate will match colored regions exactly")
    
    # Show which pixels were excluded
    excluded_pixels = set(original_pixel_data.pixels.keys()) - filtered_coords
    print(f"\n📌 Excluded pixels (not in backing plate): {sorted(excluded_pixels)}")
    print(f"   These were isolated/disconnected pixels that were filtered out")
    
    print_section("SUMMARY")
    print()
    print("✅ Fix successfully synchronizes backing plate with colored regions")
    print("✅ Isolated pixels correctly excluded from backing plate")
    print("✅ System is now resilient to any pixel filtering operations")
    print()


if __name__ == '__main__':
    demonstrate_issue()
