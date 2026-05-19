"""
How Smoothing Works in Image-to-Keychain Conversion

When MakerLab turns an image into a keychain, the smoothing stage is designed to remove jagged pixel edges and produce a clean, printable outline.
A typical workflow looks like this:

1. Image Cleanup

Convert to grayscale.
Apply thresholding to get a binary silhouette.
Remove small specks using morphological operations.

2. Outline Extraction

Trace the silhouette into vector paths (e.g., OpenCV findContours or Potrace).

3. Smoothing / Rounding

Instead of just reducing points, apply a curve-based smoothing method like Chaikin’s algorithm to round corners.
This produces a more natural, flowing outline compared to polygon simplification.

4. Final Adjustments

Offset the path slightly to ensure smoothness.
Remove tiny holes or artifacts.
Prepare for extrusion into a 3D model.
"""

import cv2
import numpy as np

def chaikin_curve(points, iterations=2):
    """Apply Chaikin's corner-cutting algorithm to smooth a polygon."""
    for _ in range(iterations):
        new_points = []
        for i in range(len(points)):
            p0 = points[i]
            p1 = points[(i + 1) % len(points)]
            Q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            R = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            new_points.extend([Q, R])
        points = new_points
    return np.array(points, dtype=np.int32)

# Load and preprocess image
img = cv2.imread("keychain_image.png", cv2.IMREAD_GRAYSCALE)
_, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)

# Find contours
contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

# Create output image
output = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

for cnt in contours:
    # Convert contour to list of tuples
    pts = [(int(p[0][0]), int(p[0][1])) for p in cnt]
    
    # Smooth using Chaikin's algorithm
    smoothed_pts = chaikin_curve(pts, iterations=3)
    
    # Draw smoothed contour
    cv2.polylines(output, [smoothed_pts], isClosed=True, color=(0, 255, 0), thickness=2)

cv2.imwrite("smoothed_keychain.png", output)
print("Smoothed keychain outline saved as smoothed_keychain.png")
