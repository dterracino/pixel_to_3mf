"""
Color space conversion functions.

Handles conversions between:
- sRGB (0-255) ↔ XYZ ↔ LAB ↔ LCH
- sRGB ↔ HSL (various formats)
- Gamma correction (sRGB companding)

All conversions use D65 illuminant and proper color science math.
"""

from __future__ import annotations
from typing import Optional, Tuple
import math
import colorsys

from .constants import ColorConstants


# ============================================================================
# General Helpers
# ============================================================================

def hex_to_rgb(hex_code: str) -> Optional[Tuple[int, int, int]]:
    """
    Converts a hex color string to an RGB tuple.

    Args:
        hex_code: Hex color string in the format "#RRGGBB" or "RRGGBB".

    Returns:
        rgb: Tuple of (R, G, B) where each component is 0-255.
        None if the hex code is invalid.
    """
    hex_clean = hex_code.lstrip('#')
    if len(hex_clean) == 6:
        try:
            return (
                int(hex_clean[0:2], 16),
                int(hex_clean[2:4], 16),
                int(hex_clean[4:6], 16)
            )
        except ValueError:
            return None
    return None
    
def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """
    Converts an RGB tuple to a hex color string.
    
    Args:
        rgb: Tuple of (R, G, B) where each component is 0-255.
    
    Returns:
        Hex color string in the format "#RRGGBB".
    """
    r, g, b = rgb
    return "#{:02X}{:02X}{:02X}".format(
        max(ColorConstants.RGB_MIN, min(ColorConstants.RGB_MAX, r)),
        max(ColorConstants.RGB_MIN, min(ColorConstants.RGB_MAX, g)),
        max(ColorConstants.RGB_MIN, min(ColorConstants.RGB_MAX, b))
    )    

# ============================================================================
# Forward Conversions (RGB → LAB)
# ============================================================================

def srgb_to_linear(c: float) -> float:
    """
    Convert sRGB value to linear RGB (gamma correction removal).
    
    sRGB uses a piecewise function to approximate gamma 2.2 encoding.
    This function reverses that to get linear light values.
    """
    if c <= ColorConstants.SRGB_GAMMA_THRESHOLD:
        return c / ColorConstants.SRGB_GAMMA_LINEAR_SCALE
    return ((c + ColorConstants.SRGB_GAMMA_OFFSET) / ColorConstants.SRGB_GAMMA_DIVISOR) ** ColorConstants.SRGB_GAMMA_POWER


def rgb_to_xyz(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    Convert sRGB (0-255) to CIE XYZ using D65 illuminant.
    
    XYZ is a device-independent color space that represents how the human
    eye responds to light. It's the bridge between RGB and LAB.
    """
    # Normalize to 0-1 range
    r, g, b = [v / ColorConstants.RGB_MAX for v in rgb]
    
    # Remove gamma correction (linearize)
    r_lin, g_lin, b_lin = srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)
    
    # Matrix multiplication using sRGB → XYZ coefficients
    X = r_lin * ColorConstants.SRGB_TO_XYZ_R[0] + g_lin * ColorConstants.SRGB_TO_XYZ_R[1] + b_lin * ColorConstants.SRGB_TO_XYZ_R[2]
    Y = r_lin * ColorConstants.SRGB_TO_XYZ_G[0] + g_lin * ColorConstants.SRGB_TO_XYZ_G[1] + b_lin * ColorConstants.SRGB_TO_XYZ_G[2]
    Z = r_lin * ColorConstants.SRGB_TO_XYZ_B[0] + g_lin * ColorConstants.SRGB_TO_XYZ_B[1] + b_lin * ColorConstants.SRGB_TO_XYZ_B[2]
    
    # Scale to 0-100 range (standard for XYZ)
    return (X * ColorConstants.XYZ_SCALE_FACTOR, Y * ColorConstants.XYZ_SCALE_FACTOR, Z * ColorConstants.XYZ_SCALE_FACTOR)


def _f_lab(t: float) -> float:
    """
    LAB conversion helper function.
    
    This piecewise function handles the nonlinear transformation from XYZ to LAB.
    The cube root section makes LAB perceptually uniform.
    """
    if t > ColorConstants.LAB_DELTA_CUBED:
        return t ** (1.0 / 3.0)
    return t / ColorConstants.LAB_F_SCALE + ColorConstants.LAB_F_OFFSET


def xyz_to_lab(xyz: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Convert CIE XYZ to L*a*b* using D65 illuminant.
    
    LAB is perceptually uniform - equal distances in LAB space correspond
    to roughly equal perceived color differences. Perfect for color matching!
    
    - L*: Lightness (0=black, 100=white)
    - a*: Green←→Red axis
    - b*: Blue←→Yellow axis
    """
    X, Y, Z = xyz
    
    # Normalize by D65 white point and apply nonlinear transformation
    fx = _f_lab(X / ColorConstants.D65_WHITE_X)
    fy = _f_lab(Y / ColorConstants.D65_WHITE_Y)
    fz = _f_lab(Z / ColorConstants.D65_WHITE_Z)
    
    # Calculate LAB components
    L = ColorConstants.LAB_KAPPA * fy - ColorConstants.LAB_OFFSET
    a = ColorConstants.LAB_A_SCALE * (fx - fy)
    b = ColorConstants.LAB_B_SCALE * (fy - fz)
    return (L, a, b)


def rgb_to_lab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    Convert sRGB (0-255) to CIE L*a*b*.
    
    This is the main conversion you'll use for color matching!
    Goes RGB → XYZ → LAB in one shot.
    """
    return xyz_to_lab(rgb_to_xyz(rgb))


# ============================================================================
# Reverse Conversions (LAB → RGB)
# ============================================================================

def _f_lab_inverse(t: float) -> float:
    """
    Inverse of the f function used in LAB conversion.
    
    This reverses the nonlinear transformation to go from LAB back to XYZ.
    """
    if t > ColorConstants.LAB_DELTA:
        return t ** 3
    return ColorConstants.LAB_F_SCALE * (t - ColorConstants.LAB_F_OFFSET)


def lab_to_xyz(lab: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Convert CIE L*a*b* to XYZ using D65 illuminant.
    
    Reverses the LAB → XYZ transformation.
    """
    L, a, b = lab
    
    # Calculate intermediate values
    fy = (L + ColorConstants.LAB_OFFSET) / ColorConstants.LAB_KAPPA
    fx = a / ColorConstants.LAB_A_SCALE + fy
    fz = fy - b / ColorConstants.LAB_B_SCALE
    
    # Apply inverse transformation and scale by D65 white point
    X = ColorConstants.D65_WHITE_X * _f_lab_inverse(fx)
    Y = ColorConstants.D65_WHITE_Y * _f_lab_inverse(fy)
    Z = ColorConstants.D65_WHITE_Z * _f_lab_inverse(fz)
    
    return (X, Y, Z)


def linear_to_srgb(c: float) -> float:
    """
    Convert linear RGB to sRGB (inverse gamma correction).
    
    This applies the sRGB gamma curve to convert from linear light
    back to the nonlinear sRGB encoding.
    """
    if c <= ColorConstants.SRGB_INV_GAMMA_THRESHOLD:
        return ColorConstants.SRGB_GAMMA_LINEAR_SCALE * c
    return ColorConstants.SRGB_GAMMA_DIVISOR * (c ** (1.0 / ColorConstants.SRGB_GAMMA_POWER)) - ColorConstants.SRGB_GAMMA_OFFSET


def xyz_to_rgb(xyz: Tuple[float, float, float], clamp: bool = True) -> Tuple[int, int, int]:
    """
    Convert CIE XYZ to sRGB (0-255).
    
    Args:
        xyz: XYZ color tuple
        clamp: If True, clamp out-of-gamut values to 0-255. If False, may return
               values outside valid range (useful for gamut checking).
    
    Returns:
        RGB tuple (0-255)
    """
    # Scale from 0-100 to 0-1 range
    X, Y, Z = [v / ColorConstants.XYZ_SCALE_FACTOR for v in xyz]
    
    # Matrix multiplication using XYZ → sRGB coefficients
    r_lin = X * ColorConstants.XYZ_TO_SRGB_X[0] + Y * ColorConstants.XYZ_TO_SRGB_X[1] + Z * ColorConstants.XYZ_TO_SRGB_X[2]
    g_lin = X * ColorConstants.XYZ_TO_SRGB_Y[0] + Y * ColorConstants.XYZ_TO_SRGB_Y[1] + Z * ColorConstants.XYZ_TO_SRGB_Y[2]
    b_lin = X * ColorConstants.XYZ_TO_SRGB_Z[0] + Y * ColorConstants.XYZ_TO_SRGB_Z[1] + Z * ColorConstants.XYZ_TO_SRGB_Z[2]
    
    # Apply gamma correction
    r = linear_to_srgb(r_lin)
    g = linear_to_srgb(g_lin)
    b = linear_to_srgb(b_lin)
    
    # Convert to 0-255 range
    r_255 = r * ColorConstants.RGB_MAX
    g_255 = g * ColorConstants.RGB_MAX
    b_255 = b * ColorConstants.RGB_MAX
    
    if clamp:
        # Clamp to valid range
        r_255 = max(ColorConstants.RGB_MIN, min(ColorConstants.RGB_MAX, r_255))
        g_255 = max(ColorConstants.RGB_MIN, min(ColorConstants.RGB_MAX, g_255))
        b_255 = max(ColorConstants.RGB_MIN, min(ColorConstants.RGB_MAX, b_255))
    
    return (int(round(r_255)), int(round(g_255)), int(round(b_255)))


def lab_to_rgb(lab: Tuple[float, float, float], clamp: bool = True) -> Tuple[int, int, int]:
    """
    Convert CIE L*a*b* to sRGB (0-255).
    
    Args:
        lab: L*a*b* color tuple
        clamp: If True, clamp out-of-gamut colors to valid RGB range
    
    Returns:
        RGB tuple (0-255)
    """
    return xyz_to_rgb(lab_to_xyz(lab), clamp=clamp)


# ============================================================================
# LCH Color Space (Cylindrical LAB)
# ============================================================================

def lab_to_lch(lab: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Convert L*a*b* to L*C*h° (cylindrical LAB).
    
    LCH is more intuitive than LAB for certain operations:
    - L* (Lightness): Same as LAB, 0-100
    - C* (Chroma): Color intensity/saturation, sqrt(a² + b²)
    - h° (Hue): Hue angle in degrees, 0-360
    
    Returns:
        (L*, C*, h°) tuple
    """
    L, a, b = lab
    C = math.sqrt(a*a + b*b)  # Chroma (color intensity)
    h = math.degrees(math.atan2(b, a))  # Hue angle
    if h < 0:
        h += ColorConstants.HUE_CIRCLE_DEGREES  # Normalize to 0-360
    return (L, C, h)


def lch_to_lab(lch: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Convert L*C*h° to L*a*b*.
    
    Args:
        lch: (L*, C*, h°) tuple
    
    Returns:
        (L*, a*, b*) tuple
    """
    L, C, h = lch
    h_rad = math.radians(h)
    a = C * math.cos(h_rad)
    b = C * math.sin(h_rad)
    return (L, a, b)


def lch_to_rgb(lch: Tuple[float, float, float], clamp: bool = True) -> Tuple[int, int, int]:
    """Convert L*C*h° directly to sRGB (0-255)."""
    return lab_to_rgb(lch_to_lab(lch), clamp=clamp)


def rgb_to_lch(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """Convert sRGB (0-255) directly to L*C*h°."""
    return lab_to_lch(rgb_to_lab(rgb))


# ============================================================================
# HSL Conversions
# ============================================================================

def rgb_to_rawhsl(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    Convert RGB to raw HSL (all values 0-1).
    
    Uses Python's colorsys module for the conversion.
    """
    r, g, b = [v / ColorConstants.RGB_MAX for v in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (h, s, l)


def rgb_to_hsl(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """
    Convert RGB (0-255) to HSL (H: 0-360, S: 0-100, L: 0-100).
    
    This is the standard HSL representation:
    - H: Hue in degrees (0° = red, 120° = green, 240° = blue)
    - S: Saturation as percentage (0% = gray, 100% = pure color)
    - L: Lightness as percentage (0% = black, 50% = pure color, 100% = white)
    """
    h, s, l = rgb_to_rawhsl(rgb)
    return (h * ColorConstants.HUE_CIRCLE_DEGREES, s * ColorConstants.XYZ_SCALE_FACTOR, l * ColorConstants.XYZ_SCALE_FACTOR)


def rgb_to_winhsl(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """
    Convert RGB (0-255) to Windows HSL (all components 0-240).
    
    Windows HSL is used in Win32 COLORREF and some GDI APIs.
    Each component is scaled to the 0-240 range instead of the usual
    H:0-360, S:0-100, L:0-100 representation.
    """
    h, s, l = rgb_to_rawhsl(rgb)
    win_h = int(round(h * ColorConstants.WIN_HSL_MAX))
    win_s = int(round(s * ColorConstants.WIN_HSL_MAX))
    win_l = int(round(l * ColorConstants.WIN_HSL_MAX))
    return (win_h, win_s, win_l)


def hsl_to_rgb(hsl: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """
    Convert HSL (H: 0-360, S: 0-100, L: 0-100) to RGB (0-255).
    
    This is the inverse of rgb_to_hsl(), converting from the standard
    HSL representation back to 8-bit RGB values.
    
    Args:
        hsl: HSL tuple (Hue 0-360°, Saturation 0-100%, Lightness 0-100%)
        
    Returns:
        RGB tuple (0-255 for each component)
    """
    h, s, l = hsl
    # Normalize to 0-1 range
    h_norm = h / 360.0
    s_norm = s / 100.0
    l_norm = l / 100.0
    
    # Use the standard HSL to RGB algorithm
    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1/6:
            return p + (q - p) * 6 * t
        if t < 1/2:
            return q
        if t < 2/3:
            return p + (q - p) * (2/3 - t) * 6
        return p
    
    if s_norm == 0:
        # Achromatic (gray)
        r = g = b = l_norm
    else:
        q = l_norm * (1 + s_norm) if l_norm < 0.5 else l_norm + s_norm - l_norm * s_norm
        p = 2 * l_norm - q
        r = hue_to_rgb(p, q, h_norm + 1/3)
        g = hue_to_rgb(p, q, h_norm)
        b = hue_to_rgb(p, q, h_norm - 1/3)
    
    # Convert to 0-255 range and clamp
    return (
        max(0, min(255, int(round(r * 255)))),
        max(0, min(255, int(round(g * 255)))),
        max(0, min(255, int(round(b * 255))))
    )