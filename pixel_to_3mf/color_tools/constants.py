"""
Immutable color science constants from international standards.

These values are defined by CIE (International Commission on Illumination),
sRGB specification, and various color difference formulas. They should
never be modified as they represent fundamental color science.
"""

import json
import hashlib


class ColorConstants:
    """
    Immutable color science constants from international standards.
    
    These values are defined by CIE (International Commission on Illumination),
    sRGB specification, and various color difference formulas. They should
    never be modified as they represent fundamental color science.
    """
    
    # ===== D65 Standard Illuminant (CIE XYZ Reference White Point) =====
    # D65 represents average daylight with correlated color temperature of 6504K
    D65_WHITE_X = 95.047
    D65_WHITE_Y = 100.000
    D65_WHITE_Z = 108.883
    
    # ===== sRGB to XYZ Transformation Matrix (D65 Illuminant) =====
    # Linear RGB to XYZ conversion coefficients
    SRGB_TO_XYZ_R = (0.4124564, 0.3575761, 0.1804375)
    SRGB_TO_XYZ_G = (0.2126729, 0.7151522, 0.0721750)
    SRGB_TO_XYZ_B = (0.0193339, 0.1191920, 0.9503041)
    
    # ===== XYZ to sRGB Transformation Matrix (Inverse) =====
    XYZ_TO_SRGB_X = (3.2404542, -1.5371385, -0.4985314)
    XYZ_TO_SRGB_Y = (-0.9692660, 1.8760108, 0.0415560)
    XYZ_TO_SRGB_Z = (0.0556434, -0.2040259, 1.0572252)
    
    # ===== sRGB Gamma Correction (Companding) =====
    # sRGB uses a piecewise function for gamma encoding/decoding
    SRGB_GAMMA_THRESHOLD = 0.04045      # Crossover point for piecewise function
    SRGB_GAMMA_LINEAR_SCALE = 12.92     # Scale factor for linear segment
    SRGB_GAMMA_OFFSET = 0.055           # Offset for power function
    SRGB_GAMMA_DIVISOR = 1.055          # Divisor for power function
    SRGB_GAMMA_POWER = 2.4              # Gamma exponent
    
    # ===== Inverse sRGB Gamma (Linearization) =====
    SRGB_INV_GAMMA_THRESHOLD = 0.0031308  # Different threshold for inverse
    # Other constants same as forward direction
    
    # ===== CIE L*a*b* Color Space Constants =====
    LAB_DELTA = 6.0 / 29.0              # Delta constant (≈ 0.206897)
    LAB_KAPPA = 116.0                   # L* scale factor
    LAB_OFFSET = 16.0                   # L* offset
    LAB_A_SCALE = 500.0                 # a* scale factor
    LAB_B_SCALE = 200.0                 # b* scale factor
    
    # ===== Delta E 1994 (CIE94) Constants =====
    DE94_K1 = 0.045                     # Chroma weighting
    DE94_K2 = 0.015                     # Hue weighting
    
    # ===== Delta E 2000 (CIEDE2000) Constants =====
    # These are empirically derived for perceptual uniformity
    DE2000_POW7_BASE = 25.0             # Base for 25^7 calculation
    DE2000_HUE_OFFSET_1 = 30.0
    DE2000_HUE_WEIGHT_1 = 0.17
    DE2000_HUE_MULT_2 = 2.0
    DE2000_HUE_WEIGHT_2 = 0.24
    DE2000_HUE_MULT_3 = 3.0
    DE2000_HUE_OFFSET_3 = 6.0
    DE2000_HUE_WEIGHT_3 = 0.32
    DE2000_HUE_MULT_4 = 4.0
    DE2000_HUE_OFFSET_4 = 63.0
    DE2000_HUE_WEIGHT_4 = 0.20
    DE2000_DRO_MULT = 30.0
    DE2000_DRO_CENTER = 275.0
    DE2000_DRO_DIVISOR = 25.0
    DE2000_L_WEIGHT = 0.015
    DE2000_L_OFFSET = 50.0
    DE2000_L_DIVISOR = 20.0
    DE2000_C_WEIGHT = 0.045
    DE2000_H_WEIGHT = 0.015
    
    # ===== Delta E CMC Constants =====
    # Used in textile industry for color difference
    CMC_L_THRESHOLD = 16.0
    CMC_L_LOW = 0.511
    CMC_L_SCALE = 0.040975
    CMC_L_DIVISOR = 0.01765
    CMC_C_SCALE = 0.0638
    CMC_C_DIVISOR = 0.0131
    CMC_C_OFFSET = 0.638
    CMC_HUE_MIN = 164.0
    CMC_HUE_MAX = 345.0
    CMC_T_IN_RANGE = 0.56
    CMC_T_COS_MULT_IN = 0.2
    CMC_T_HUE_OFFSET_IN = 168.0
    CMC_T_OUT_RANGE = 0.36
    CMC_T_COS_MULT_OUT = 0.4
    CMC_T_HUE_OFFSET_OUT = 35.0
    CMC_F_POWER = 4.0
    CMC_F_DIVISOR = 1900.0
    
    # Default l:c ratios for CMC (2:1 for acceptability, 1:1 for perceptibility)
    CMC_L_DEFAULT = 2.0
    CMC_C_DEFAULT = 1.0
    
    # ===== Angle and Range Constants =====
    HUE_CIRCLE_DEGREES = 360.0          # Full circle for hue
    HUE_HALF_CIRCLE_DEGREES = 180.0     # Half circle
    RGB_MIN = 0                         # Minimum RGB value
    RGB_MAX = 255                       # Maximum RGB value (8-bit)
    NORMALIZED_MIN = 0.0                # Minimum normalized value
    NORMALIZED_MAX = 1.0                # Maximum normalized value
    XYZ_SCALE_FACTOR = 100.0            # XYZ typically scaled 0-100
    WIN_HSL_MAX = 240.0                 # Windows uses 0-240 for HSL
    
    # Computed values (derived from above constants)
    LAB_DELTA_CUBED = LAB_DELTA ** 3
    LAB_F_SCALE = 3.0 * (LAB_DELTA ** 2)
    LAB_F_OFFSET = 4.0 / 29.0
    
    @classmethod
    def _compute_hash(cls) -> str:
        """
        Compute SHA-256 hash of all constant values for integrity checking.
        
        This creates a fingerprint of all the color science constants. If any
        constant is accidentally (or maliciously) modified, the hash won't match.
        """
        # Collect all UPPERCASE attributes (our constant naming convention)
        constants = {}
        for name in dir(cls):
            if name.isupper() and not name.startswith('_'):
                value = getattr(cls, name)
                # Convert tuples to lists for JSON serialization
                if isinstance(value, tuple):
                    value = list(value)
                constants[name] = value
        
        # Create stable JSON representation (sorted keys for consistency)
        data = json.dumps(constants, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()
    
    @classmethod
    def verify_integrity(cls) -> bool:
        """
        Verify that constants haven't been modified.
        
        Returns:
            True if all constants match expected values, False if tampered with.
        """
        return cls._compute_hash() == cls._EXPECTED_HASH
    
    # This hash is computed once when the constants are known to be correct
    # Computed hash of all color science constants (SHA-256)
    _EXPECTED_HASH = "879f819a84b516e5510a93af8cfaed6c430cbed72e14bcc91e48b7ffd5cd5f21"

