from .color_tools import FilamentPalette

# Hex codes and their RGB conversions
colors = [
    ("#000000", (0, 0, 0)),
    ("#e0f8f8", (224, 248, 248)),
    ("#e0e0d0", (224, 224, 208)),
    ("#705040", (112, 80, 64)),
    ("#604038", (96, 64, 56)),
    ("#002870", (0, 40, 112)),
    ("#c0b098", (192, 176, 152)),
    ("#3060c0", (48, 96, 192)),
    ("#987060", (152, 112, 96)),
    ("#382820", (56, 40, 32)),
    ("#1088e0", (16, 136, 224)),
    ("#304098", (48, 64, 152)),
    ("#c06030", (192, 96, 48)),
]

# Load the filament palette
palette = FilamentPalette.load_default()

# Filter to just Bambu Lab PLA Basic/Matte filaments
filtered = palette.filter(maker="Bambu Lab", type_name="PLA", finish=["Basic", "Matte"])

print(f"Searching {len(filtered)} Bambu Lab PLA (Basic/Matte) filaments...\n")

for hex_code, rgb in colors:
    result, delta_e = palette.nearest_filament(
        rgb, 
        maker="Bambu Lab", 
        type_name="PLA", 
        finish=["Basic", "Matte"]
    )
    print(f"{hex_code} → {result.color}")
    print(f"  RGB: {result.rgb}")
    print(f"  Maker: {result.maker}, Type: {result.type}, Finish: {result.finish}")
    print(f"  Delta E: {delta_e:.2f}\n")