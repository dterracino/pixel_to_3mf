"""
Color distance metrics for measuring perceptual color differences.

Includes multiple Delta E formulas:
- Delta E 1976 (CIE76): Simple Euclidean distance
- Delta E 1994 (CIE94): Improved with weighting
- Delta E 2000 (CIEDE2000): Current gold standard
- Delta E CMC: Textile industry standard

Also includes simpler distance functions for RGB and HSL spaces.
"""

from __future__ import annotations
from typing import Tuple
import math

from .constants import ColorConstants
from .conversions import lab_to_lch


# ============================================================================
# Basic Distance Functions
# ============================================================================

def euclidean(v1: Tuple[float, ...], v2: Tuple[float, ...]) -> float:
    """
    Simple Euclidean distance between two vectors.
    
    The classic √((x₁-x₂)² + (y₁-y₂)² + (z₁-z₂)²) formula.
    Works for any dimensionality, not just colors!
    """
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def hue_diff_deg(h1: float, h2: float) -> float:
    """
    Calculate hue difference accounting for circular nature (0° = 360°).
    
    Hue is circular (like a clock), so the difference between 359° and 1° 
    should be 2°, not 358°! This function finds the smallest angular difference.
    
    Args:
        h1, h2: Hue angles in degrees
    
    Returns:
        Smallest hue difference in degrees (0-180)
    """
    d = abs(h1 - h2) % ColorConstants.HUE_CIRCLE_DEGREES
    return min(d, ColorConstants.HUE_CIRCLE_DEGREES - d)


def hsl_euclidean(hsl1: Tuple[float, float, float], hsl2: Tuple[float, float, float]) -> float:
    """
    Euclidean distance in HSL space (accounting for hue circularity).
    
    Note: HSL distance doesn't match human perception well - LAB is better!
    This is here for compatibility with systems that work in HSL.
    """
    dh = hue_diff_deg(hsl1[0], hsl2[0])
    ds = hsl1[1] - hsl2[1]
    dl = hsl1[2] - hsl2[2]
    return math.sqrt(dh*dh + ds*ds + dl*dl)


# ============================================================================
# Delta E 1976 (CIE76) - The Original
# ============================================================================

def delta_e_76(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """
    Delta E 1976 (CIE76) - Simple Euclidean distance in LAB space.
    
    The OG color difference formula! Just treats LAB like any other 3D space
    and measures straight-line distance.
    
    **Pros:** Fast and simple
    **Cons:** Doesn't match human perception well, especially for saturated colors
    
    A ΔE of 1.0 is supposedly the "just noticeable difference" but in reality
    it varies based on the colors involved.
    
    Args:
        lab1, lab2: L*a*b* color tuples
    
    Returns:
        Delta E 1976 value (lower = more similar)
    """
    return euclidean(lab1, lab2)


# ============================================================================
# Delta E 1994 (CIE94) - The Improvement
# ============================================================================

def delta_e_94(
    lab1: Tuple[float, float, float],
    lab2: Tuple[float, float, float],
    kL: float = 1.0,
    kC: float = 1.0,
    kH: float = 1.0,
    K1: float | None = None,
    K2: float | None = None,
) -> float:
    """
    Delta E 1994 (CIE94) - Improved perceptual uniformity.
    
    CIE94 realized that humans are more sensitive to lightness differences
    than chroma differences, and more sensitive to chroma than hue. This
    formula weights things accordingly!
    
    **Better than CIE76 but still has issues with saturated colors.**
    
    Args:
        lab1, lab2: L*a*b* color tuples
        kL, kC, kH: Weighting factors (usually all 1.0)
        K1, K2: Chroma and hue weighting constants (use defaults if None)
    
    Returns:
        Delta E 1994 value (lower = more similar)
    """
    if K1 is None:
        K1 = ColorConstants.DE94_K1
    if K2 is None:
        K2 = ColorConstants.DE94_K2
        
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    
    # Calculate differences
    dL = L1 - L2
    C1 = math.hypot(a1, b1)  # Chroma of color 1
    C2 = math.hypot(a2, b2)  # Chroma of color 2
    dC = C1 - C2
    da = a1 - a2
    db = b1 - b2
    
    # Hue difference (derived from a, b differences)
    dH_sq = da*da + db*db - dC*dC
    
    # Weighting functions (make the formula perceptually uniform)
    SL = ColorConstants.NORMALIZED_MAX
    SC = ColorConstants.NORMALIZED_MAX + K1 * C1
    SH = ColorConstants.NORMALIZED_MAX + K2 * C1
    
    return math.sqrt((dL/(kL*SL))**2 + (dC/(kC*SC))**2 + (dH_sq/((kH*SH)**2)))


# ============================================================================
# Delta E 2000 (CIEDE2000) - The Gold Standard
# ============================================================================

def _atan2_deg(y: float, x: float) -> float:
    """atan2 in degrees mapped to [0,360)."""
    if x == 0.0 and y == 0.0:
        return 0.0
    ang = math.degrees(math.atan2(y, x))
    return ang + ColorConstants.HUE_CIRCLE_DEGREES if ang < 0.0 else ang


def _hp(ap: float, b: float) -> float:
    """Helper for CIEDE2000 hue prime calculation."""
    return _atan2_deg(b, ap)


def _mean_hue(h1: float, h2: float, C1p: float, C2p: float) -> float:
    """
    Helper for CIEDE2000 mean hue calculation.
    
    Handles the tricky case of averaging hues near the 0°/360° boundary.
    You can't just average 10° and 350° to get 180° - that's wrong!
    The mean should be 0° (or 360°).
    """
    if C1p * C2p == 0:
        return h1 + h2
    dh = abs(h1 - h2)
    if dh > ColorConstants.HUE_HALF_CIRCLE_DEGREES:
        sum_h = h1 + h2
        if sum_h < ColorConstants.HUE_CIRCLE_DEGREES:
            return (sum_h + ColorConstants.HUE_CIRCLE_DEGREES) / 2.0
        else:
            return (sum_h - ColorConstants.HUE_CIRCLE_DEGREES) / 2.0
    return (h1 + h2) / 2.0


def delta_e_2000(
    lab1: Tuple[float, float, float],
    lab2: Tuple[float, float, float],
    kL: float = 1.0,
    kC: float = 1.0,
    kH: float = 1.0,
) -> float:
    """
    Delta E 2000 (CIEDE2000) - Current gold standard for color difference.
    
    This is THE formula to use for color matching! After decades of research,
    CIEDE2000 finally handles all the edge cases that tripped up earlier formulas:
    - Neutral colors (low chroma)
    - Blue hues (which humans perceive differently)
    - Lightness differences at different brightness levels
    
    The formula is... complex. It's got rotation terms, weighting functions,
    and special handling for different hue regions. But it WORKS!
    
    **Fun fact:** A ΔE2000 of 1.0 is roughly the "just noticeable difference"
    for most colors. ΔE < 2 is considered imperceptible for most applications.
    
    Args:
        lab1, lab2: L*a*b* color tuples
        kL, kC, kH: Weighting factors (usually all 1.0)
            - kL for lightness
            - kC for chroma
            - kH for hue
    
    Returns:
        Delta E 2000 value (lower = more similar)
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    # Step 1: Calculate chroma and compensate for neutral colors
    # (The 25^7 term helps with very low chroma colors)
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    C_bar = (C1 + C2) / 2.0
    C_bar7 = C_bar ** 7
    pow7_term = ColorConstants.DE2000_POW7_BASE ** 7
    G = 0.5 * (1.0 - math.sqrt(C_bar7 / (C_bar7 + pow7_term)))
    
    # a' (a-prime) - adjusted a values
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2
    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)

    # Step 2: Calculate hue angles
    h1p = _hp(a1p, b1)
    h2p = _hp(a2p, b2)

    # Step 3: Calculate differences in L', C', and H'
    dLp = L2 - L1
    dCp = C2p - C1p
    
    # Hue difference (accounting for circularity)
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dh = h2p - h1p
        if dh > ColorConstants.HUE_HALF_CIRCLE_DEGREES:
            dh -= ColorConstants.HUE_CIRCLE_DEGREES
        elif dh < -ColorConstants.HUE_HALF_CIRCLE_DEGREES:
            dh += ColorConstants.HUE_CIRCLE_DEGREES
        dhp = dh
    
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp * 0.5))

    # Step 4: Calculate mean values
    Lp_bar = (L1 + L2) / 2.0
    Cp_bar = (C1p + C2p) / 2.0
    hp_bar = _mean_hue(h1p, h2p, C1p, C2p)

    # Step 5: Calculate weighting functions
    # T: Hue-dependent term (handles blue region specially)
    T = (
        ColorConstants.NORMALIZED_MAX
        - ColorConstants.DE2000_HUE_WEIGHT_1 * math.cos(math.radians(hp_bar - ColorConstants.DE2000_HUE_OFFSET_1))
        + ColorConstants.DE2000_HUE_WEIGHT_2 * math.cos(math.radians(ColorConstants.DE2000_HUE_MULT_2 * hp_bar))
        + ColorConstants.DE2000_HUE_WEIGHT_3 * math.cos(math.radians(ColorConstants.DE2000_HUE_MULT_3 * hp_bar + ColorConstants.DE2000_HUE_OFFSET_3))
        - ColorConstants.DE2000_HUE_WEIGHT_4 * math.cos(math.radians(ColorConstants.DE2000_HUE_MULT_4 * hp_bar - ColorConstants.DE2000_HUE_OFFSET_4))
    )
    
    # d_ro: Rotation term for blue region
    d_ro = ColorConstants.DE2000_DRO_MULT * math.exp(-(((hp_bar - ColorConstants.DE2000_DRO_CENTER) / ColorConstants.DE2000_DRO_DIVISOR) ** 2))
    
    # RC: Rotation function
    Cp_bar7 = Cp_bar ** 7
    RC = 2.0 * math.sqrt(Cp_bar7 / (Cp_bar7 + pow7_term))
    
    # Lightness weighting
    L_diff = Lp_bar - ColorConstants.DE2000_L_OFFSET
    SL = ColorConstants.NORMALIZED_MAX + (ColorConstants.DE2000_L_WEIGHT * (L_diff ** 2)) / math.sqrt(ColorConstants.DE2000_L_DIVISOR + (L_diff ** 2))
    
    # Chroma weighting
    SC = ColorConstants.NORMALIZED_MAX + ColorConstants.DE2000_C_WEIGHT * Cp_bar
    
    # Hue weighting
    SH = ColorConstants.NORMALIZED_MAX + ColorConstants.DE2000_H_WEIGHT * Cp_bar * T
    
    # Rotation term (interaction between chroma and hue)
    RT = -math.sin(math.radians(2.0 * d_ro)) * RC

    # Step 6: Final Delta E 2000 formula
    # This combines all the weighted differences plus the rotation term
    dE = math.sqrt(
        (dLp / (kL * SL)) ** 2
        + (dCp / (kC * SC)) ** 2
        + (dHp / (kH * SH)) ** 2
        + RT * (dCp / (kC * SC)) * (dHp / (kH * SH))
    )
    return dE


# ============================================================================
# Delta E CMC - Textile Industry Standard
# ============================================================================

def delta_e_cmc(
    lab1: Tuple[float, float, float],
    lab2: Tuple[float, float, float],
    l: float = 2.0,
    c: float = 1.0,
) -> float:
    """
    Delta E CMC(l:c) - Color difference formula used in textile industry.
    
    CMC was developed specifically for textile color matching, where the
    context matters (viewing conditions, material properties, etc.).
    
    The l:c ratio lets you tune the formula for different use cases:
    - **CMC(2:1)** - "Acceptability" → Used to judge if colors match well enough
    - **CMC(1:1)** - "Perceptibility" → More strict, for detecting differences
    
    **Why two ratios?** Turns out humans are more forgiving of color differences
    when deciding "is this acceptable?" vs "can I see a difference?"
    
    Args:
        lab1, lab2: L*a*b* color tuples
        l: Lightness weight (2.0 for acceptability, 1.0 for perceptibility)
        c: Chroma weight (usually 1.0)
    
    Returns:
        Delta E CMC value (lower = more similar)
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    # Calculate chroma
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)

    # Calculate differences
    dL = L1 - L2
    da = a1 - a2
    db = b1 - b2
    dC = C1 - C2
    dH_sq = da * da + db * db - dC * dC
    if dH_sq < 0.0:
        dH_sq = 0.0  # Numerical safety

    # Lightness weight
    if L1 < ColorConstants.CMC_L_THRESHOLD:
        SL = ColorConstants.CMC_L_LOW
    else:
        SL = (ColorConstants.CMC_L_SCALE * L1) / (ColorConstants.NORMALIZED_MAX + ColorConstants.CMC_L_DIVISOR * L1)
    
    # Chroma weight
    SC = ColorConstants.CMC_C_SCALE * C1 / (ColorConstants.NORMALIZED_MAX + ColorConstants.CMC_C_DIVISOR * C1) + ColorConstants.CMC_C_OFFSET

    # Hue weight (depends on hue angle - different for different color regions)
    h1 = _atan2_deg(b1, a1)
    if ColorConstants.CMC_HUE_MIN <= h1 <= ColorConstants.CMC_HUE_MAX:
        # Red/magenta region
        T = ColorConstants.CMC_T_IN_RANGE + abs(ColorConstants.CMC_T_COS_MULT_IN * math.cos(math.radians(h1 + ColorConstants.CMC_T_HUE_OFFSET_IN)))
    else:
        # Other regions
        T = ColorConstants.CMC_T_OUT_RANGE + abs(ColorConstants.CMC_T_COS_MULT_OUT * math.cos(math.radians(h1 + ColorConstants.CMC_T_HUE_OFFSET_OUT)))

    F = math.sqrt((C1 ** ColorConstants.CMC_F_POWER) / (C1 ** ColorConstants.CMC_F_POWER + ColorConstants.CMC_F_DIVISOR)) if C1 != 0 else 0.0
    SH = SC * (F * T + (ColorConstants.NORMALIZED_MAX - F))

    # Combine all the weighted differences
    term_L = (dL / (l * SL)) ** 2
    term_C = (dC / (c * SC)) ** 2
    term_H = (math.sqrt(dH_sq) / SH) ** 2 if SH != 0 else 0.0

    return math.sqrt(term_L + term_C + term_H)