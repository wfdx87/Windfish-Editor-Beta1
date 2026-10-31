"""Shared sprite decoding and OAM composition."""
from dataclasses import dataclass
from PIL import Image

@dataclass(frozen=True)
class Piece:
    x: int
    y: int
    tile: int
    attributes: int = 0


def decode_2bpp(tile_bytes):
    if len(tile_bytes) != 16:
        raise ValueError('A Game Boy 8x8 tile must contain 16 bytes')
    result = Image.new('L', (8, 8))
    pixels = result.load()
    for y in range(8):
        low, high = tile_bytes[2*y:2*y+2]
        for x in range(8):
            bit = 7-x
            pixels[x,y] = ((low >> bit)&1) | (((high >> bit)&1)<<1)
    return result


def compose(pieces, get_tile, palettes=None):
    """Compose 8x8 OAM parts; transparency is color index 0.

    get_tile(tile_number, vram_bank) -> 16-byte 2bpp tile.
    Attributes: bit 3 VRAM bank; bit 5 X flip; bit 6 Y flip;
    bits 0..2 GBC OBJ palette. Ordering follows provided draw order.
    Returns an RGBA image and its bounding box relative to sprite origin.
    """
    pieces = tuple(pieces)
    if not pieces:
        return Image.new('RGBA', (1, 1)), (0, 0, 0, 0)
    x0 = min(p.x for p in pieces)
    y0 = min(p.y for p in pieces)
    x1 = max(p.x+8 for p in pieces)
    y1 = max(p.y+8 for p in pieces)
    canvas = Image.new('RGBA', (x1-x0, y1-y0))
    default = [(238,247,220), (160,194,147), (76,129,102), (25,55,58)]
    for p in pieces:
        tile = decode_2bpp(get_tile(p.tile, (p.attributes >> 3)&1))
        if p.attributes & 0x20:
            tile = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if p.attributes & 0x40:
            tile = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        palette = default if palettes is None else palettes[p.attributes & 7]
        rgba = Image.new('RGBA',(8,8))
        src, dst = tile.load(), rgba.load()
        for yy in range(8):
            for xx in range(8):
                n=src[xx,yy]
                if n: dst[xx,yy] = (*palette[n],255)
        canvas.alpha_composite(rgba, (p.x-x0,p.y-y0))
    return canvas, (x0,y0,x1,y1)


@dataclass(frozen=True)
class OAMSprite:
    x: int
    y: int
    tile: int
    attributes: int = 0


def expand_oam(sprites, *, height=16):
    """Expand hardware OBJ records to 8x8 pieces for compose()."""
    if height not in (8, 16):
        raise ValueError('Game Boy OBJ height must be 8 or 16')
    result = []
    for s in sprites:
        if not 0 <= s.tile <= 255 or not 0 <= s.attributes <= 255:
            raise ValueError('Invalid OAM tile or attribute byte')
        if height == 8:
            result.append(Piece(s.x, s.y, s.tile, s.attributes))
        else:
            base = s.tile & 0xFE
            # In 8x16 mode, Y flip changes the ordering of the two tiles.
            tiles = (base + 1, base) if s.attributes & 0x40 else (base, base + 1)
            for i, tile in enumerate(tiles):
                result.append(Piece(s.x, s.y + 8*i, tile, s.attributes))
    return tuple(result)


def compose_oam(sprites, get_tile, *, height=16, palettes=None):
    """Render a known OAM record list using Windfish's 8x8 tile composer."""
    return compose(expand_oam(sprites, height=height), get_tile, palettes)
