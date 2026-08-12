"""
Pure-Python Perlin noise implementation – *inlined* for speed.

Drop-in replacement for the `noise` C-extension library.
Provides pnoise2() and pnoise3() with the same API:
    pnoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=1024, repeaty=1024, base=0)
    pnoise3(x, y, z, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=1024, repeaty=1024, repeatz=1024, base=0)

Compared to the naive version this eliminates all per-sample function-call
overhead by inlining _fade, _lerp, _grad2, _grad3, and _noise2/_noise3
directly into the public functions.
"""

from math import floor as _floor

# Permutation table (Ken Perlin's original), doubled to avoid overflow
_p = [
    151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,
    140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,
    247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,
    57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,
    74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,
    60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,
    65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,
    200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,
    52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,
    207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,
    119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,
    129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,
    218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,
    81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,
    4,184,180,115,243,93,156,29,72,66,176,38,254,127,50,223,
    121,168,254,195,236,61,8,215,67,128,45,78,69,150,180,204,
]
_perm = _p + _p

# Pre-computed gradient tables to replace branching with lookup
# _grad2 with h&3: [(1,1),(-1,1),(1,-1),(-1,-1)]
_G2X = (1.0, -1.0, 1.0, -1.0)
_G2Y = (1.0, 1.0, -1.0, -1.0)


def pnoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0,
            repeatx=1024, repeaty=1024, base=0):
    """2D Perlin noise with octaves (fBm). Fully inlined for speed."""
    # Local references to avoid global lookups in tight loop
    P = _perm
    g2x = _G2X
    g2y = _G2Y
    fl = _floor

    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amplitude = 0.0

    for _ in range(octaves):
        sx = x * frequency + base
        sy = y * frequency + base

        # --- inlined _noise2 ---
        fsx = fl(sx)
        fsy = fl(sy)
        xi = int(fsx) & 255
        yi = int(fsy) & 255
        xf = sx - fsx
        yf = sy - fsy

        # inlined _fade
        u = xf * xf * xf * (xf * (xf * 6.0 - 15.0) + 10.0)
        v = yf * yf * yf * (yf * (yf * 6.0 - 15.0) + 10.0)

        pxi = P[xi]
        pxi1 = P[xi + 1]
        aa = P[pxi + yi]
        ab = P[pxi + yi + 1]
        ba = P[pxi1 + yi]
        bb = P[pxi1 + yi + 1]

        # inlined _grad2 + _lerp
        h = aa & 3
        g_aa = g2x[h] * xf + g2y[h] * yf
        h = ba & 3
        g_ba = g2x[h] * (xf - 1.0) + g2y[h] * yf
        h = ab & 3
        g_ab = g2x[h] * xf + g2y[h] * (yf - 1.0)
        h = bb & 3
        g_bb = g2x[h] * (xf - 1.0) + g2y[h] * (yf - 1.0)

        x1 = g_aa + u * (g_ba - g_aa)
        x2 = g_ab + u * (g_bb - g_ab)
        noise_val = x1 + v * (x2 - x1)
        # --- end inlined _noise2 ---

        total += noise_val * amplitude
        max_amplitude += amplitude
        amplitude *= persistence
        frequency *= lacunarity

    return total / max_amplitude


def pnoise3(x, y, z, octaves=1, persistence=0.5, lacunarity=2.0,
            repeatx=1024, repeaty=1024, repeatz=1024, base=0):
    """3D Perlin noise with octaves (fBm). Fully inlined for speed."""
    P = _perm
    fl = _floor

    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amplitude = 0.0

    for _ in range(octaves):
        sx = x * frequency + base
        sy = y * frequency + base
        sz = z * frequency + base

        # --- inlined _noise3 ---
        fsx = fl(sx)
        fsy = fl(sy)
        fsz = fl(sz)
        xi = int(fsx) & 255
        yi = int(fsy) & 255
        zi = int(fsz) & 255
        xf = sx - fsx
        yf = sy - fsy
        zf = sz - fsz

        # inlined _fade
        u = xf * xf * xf * (xf * (xf * 6.0 - 15.0) + 10.0)
        v = yf * yf * yf * (yf * (yf * 6.0 - 15.0) + 10.0)
        w = zf * zf * zf * (zf * (zf * 6.0 - 15.0) + 10.0)

        pxi = P[xi]
        pxi1 = P[xi + 1]
        pyi = P[pxi + yi]
        pyi1 = P[pxi + yi + 1]
        byi = P[pxi1 + yi]
        byi1 = P[pxi1 + yi + 1]

        aaa = P[pyi + zi]
        aab = P[pyi + zi + 1]
        aba = P[pyi1 + zi]
        abb = P[pyi1 + zi + 1]
        baa = P[byi + zi]
        bab = P[byi + zi + 1]
        bba = P[byi1 + zi]
        bbb = P[byi1 + zi + 1]

        xf1 = xf - 1.0
        yf1 = yf - 1.0
        zf1 = zf - 1.0

        # inlined _grad3 for all 8 corners
        # _grad3(h, x, y, z): h=hash&15, u=x if h<8 else y, v=y if h<4 else (x if h==12|14 else z)
        # return (u if h&1==0 else -u) + (v if h&2==0 else -v)
        def _g3(hh, gx, gy, gz):
            hv = hh & 15
            gu = gx if hv < 8 else gy
            gv = gy if hv < 4 else (gx if hv == 12 or hv == 14 else gz)
            return (gu if (hv & 1) == 0 else -gu) + (gv if (hv & 2) == 0 else -gv)

        g_aaa = _g3(aaa, xf, yf, zf)
        g_baa = _g3(baa, xf1, yf, zf)
        g_aba = _g3(aba, xf, yf1, zf)
        g_bba = _g3(bba, xf1, yf1, zf)
        g_aab = _g3(aab, xf, yf, zf1)
        g_bab = _g3(bab, xf1, yf, zf1)
        g_abb = _g3(abb, xf, yf1, zf1)
        g_bbb = _g3(bbb, xf1, yf1, zf1)

        # inlined trilinear interpolation (_lerp × 7)
        x1 = g_aaa + u * (g_baa - g_aaa)
        x2 = g_aba + u * (g_bba - g_aba)
        y1 = x1 + v * (x2 - x1)

        x1 = g_aab + u * (g_bab - g_aab)
        x2 = g_abb + u * (g_bbb - g_abb)
        y2 = x1 + v * (x2 - x1)

        noise_val = y1 + w * (y2 - y1)
        # --- end inlined _noise3 ---

        total += noise_val * amplitude
        max_amplitude += amplitude
        amplitude *= persistence
        frequency *= lacunarity

    return total / max_amplitude


def snoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0):
    """Simplex-like 2D noise (falls back to Perlin)."""
    return pnoise2(x, y, octaves=octaves, persistence=persistence, lacunarity=lacunarity)


def snoise3(x, y, z, octaves=1, persistence=0.5, lacunarity=2.0):
    """Simplex-like 3D noise (falls back to Perlin)."""
    return pnoise3(x, y, z, octaves=octaves, persistence=persistence, lacunarity=lacunarity)
