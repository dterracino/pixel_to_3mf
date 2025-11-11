"""
Compare c64ready.png colors to Bambu Lab blue/purple filaments.
"""

from color_tools import FilamentPalette, rgb_to_lab

# The two colors from c64ready.png
colors = {
    'Dark Blue (70.9%)': (66, 66, 231),
    'Light Blue (29.1%)': (165, 165, 255)
}

# Load all filaments
all_palette = FilamentPalette.load_default()

# Get Bambu Lab PLA only
bambu_pla = all_palette.filter(maker="Bambu Lab", type_name="PLA")

# Find filaments with blue or purple in the name
print("All Bambu Lab PLA filaments with 'Blue' or 'Purple' in the name:")
print("=" * 80)

blue_purple = []
for filament in bambu_pla:
    name_lower = filament.color.lower()
    if 'blue' in name_lower or 'purple' in name_lower or 'violet' in name_lower:
        blue_purple.append(filament)
        print(f"{filament.color:30} RGB{str(filament.rgb):20} {filament.finish}")

print(f"\nFound {len(blue_purple)} blue/purple filaments")
print()

# Now compare each c64ready color to each filament
for color_name, rgb in colors.items():
    print("\n" + "=" * 80)
    print(f"{color_name}: RGB{rgb}")
    print("=" * 80)
    
    # First show the actual nearest_filament() result (uses Delta E 2000)
    nearest, de2000 = all_palette.nearest_filament(
        rgb, 
        maker="Bambu Lab", 
        type_name="PLA"
    )
    print(f"\nnearest_filament() selects: {nearest.color} ({nearest.finish})")
    print(f"  RGB: {nearest.rgb}")
    print(f"  Delta E 2000: {de2000:.2f}")
    
    # Calculate Delta E for each blue/purple filament
    comparisons = []
    for filament in blue_purple:
        # Get Delta E by calling nearest_filament but we need individual comparisons
        # So we'll convert to LAB and calculate
        img_lab = rgb_to_lab(rgb)
        fil_lab = rgb_to_lab(filament.rgb)
        
        # Simple Euclidean distance in LAB (approximation of Delta E)
        de = ((img_lab[0]-fil_lab[0])**2 + 
              (img_lab[1]-fil_lab[1])**2 + 
              (img_lab[2]-fil_lab[2])**2)**0.5
        
        comparisons.append((filament.color, filament.rgb, filament.finish, de))
    
    # Sort by Delta E
    comparisons.sort(key=lambda x: x[3])
    
    # Show all blue/purple results
    print(f"\n{'Rank':<6} {'Filament':<30} {'RGB':<20} {'Finish':<10} {'~Delta E':<10}")
    print("-" * 80)
    for i, (name, fil_rgb, finish, de) in enumerate(comparisons, 1):
        marker = " ← SELECTED" if name == nearest.color and finish == nearest.finish else ""
        print(f"{i:<6} {name:<30} {str(fil_rgb):<20} {finish:<10} {de:>8.2f}{marker}")
