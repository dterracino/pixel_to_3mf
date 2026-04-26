test_colors = [
    ((0, 0, 255), "Pure blue", "Should → Blue"),
    ((104, 108, 232), "#686CE8 DECAPATTACK title", "Should → Purple"),
    ((128, 0, 255), "Pure purple/magenta", "Should → Purple"),
    ((94, 67, 183), "Bambu Purple filament", "Reference"),
]

for rgb, description, expected in test_colors:
    r, g, b = rgb
    print(f"{description}:")
    print(f"  RGB{rgb} = #{r:02X}{g:02X}{b:02X}")
    print(f"  R={r:3}, G={g:3}, B={b:3}")
    print(f"  B - R = {b - r:4}")
    print(f"  B - (R + G)/2 = {b - (r + g) / 2:.1f}")
    print(f"  (R + G) vs B: {(r + g) / 2:.1f} vs {b}")
    print(f"  {expected}")
    print()
