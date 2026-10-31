"""20×16 HUD and item palette sample using ROM tiles at B0800.

Layout follows the inventory tilemap's first two rows, with representative
shield/sword L-1, 006 rupees, and two full hearts plus one empty heart.
This is a palette preview, not a preview of saved player equipment or health.
"""
from PIL import Image
from windfish.rendering.windfish_sprite_oam import decode_2bpp
from windfish.rendering.windfish_sprite_palettes import palette_record_offset, gbc_rgb

HUD_TILES_OFFSET = 0xB0800
# VRAM tile IDs 80–FF map to the equipment graphics at the supplied offset.
# 7F is the blank HUD background tile; render it as color zero.
HUD_TILES = (
    (0xBD,0x86,0x7F,0x7F,0xBE,0xBB,0x84,0x7F,0x7F,0xBE,0xCF,0x7F,0x7F,0xA9,0xA9,0xCD,0x7F,0x7F,0x7F,0x7F),
    (0xBC,0x87,0xBA,0xB1,0xBF,0xBC,0x85,0xBA,0xB1,0xBF,0xB0,0xB0,0xB6,0x7F,0x7F,0x7F,0x7F,0x7F,0x7F,0x7F),
)
# First two rows from inventory.attrmap: the rupee digits use BG 1 too.
HUD_PALETTES = ((1,)*10+(2,)*10, (1,)*13+(2,)*7)


# InventoryItemTiles / InventoryItemPaletteIndexes from the game. Each icon
# has top/bottom 8×8 tiles; palettes may differ between those two halves.
ITEM_SAMPLES = (
    ('Sword', 0x84, 0x85, 1, 1, 'level'),
    ('Bombs', 0x80, 0x81, 1, 1, 'count'),
    ('Bracelet', 0x82, 0x83, 1, 1, 'level'),
    ('Shield', 0x86, 0x87, 1, 1, 'level'),
    ('Bow', 0x88, 0x89, 3, 3, 'count'),
    ('Hookshot', 0x8A, 0x8B, 1, 2, ''),
    ('Magic Rod', 0x8C, 0x8D, 2, 1, ''),
    ('Boots', 0x98, 0x99, 3, 3, ''),
    ('Ocarina', 0x90, 0x91, 2, 2, ''),
    ('Feather', 0x92, 0x93, 3, 3, ''),
    ('Shovel', 0x96, 0x97, 3, 1, ''),
    ('Magic Powder', 0x8E, 0x8F, 3, 3, 'count'),
    ('Boomerang', 0xA4, 0xA5, 2, 2, ''),
)


def preview_tilemap():
    """20×16 cells: HUD at top, usable inventory below, blanks elsewhere."""
    tiles = [[0x7F] * 20 for _ in range(16)]
    attributes = [[1] * 20 for _ in range(16)]
    for y in range(2):
        tiles[y][:] = HUD_TILES[y]
        attributes[y][:] = HUD_PALETTES[y]
    for index, (_, top, bottom, top_pal, bottom_pal, annotation) in enumerate(ITEM_SAMPLES):
        x, y = 1 + (index % 5) * 4, 4 + (index // 5) * 3
        tiles[y][x], tiles[y+1][x] = top, bottom
        attributes[y][x], attributes[y+1][x] = top_pal, bottom_pal
        if annotation == 'level':
            tiles[y+1][x+1:x+3] = [0xBA, 0xB1]
        elif annotation == 'count':
            tiles[y+1][x+1:x+3] = [0xB2, 0xB0]
    return tiles, attributes


def render_hud_preview(rom, room, scale=2):
    if not isinstance(scale, int) or scale < 1:
        raise ValueError('Palette preview scale must be a positive integer')
    if not 0 <= room <= 255:
        raise ValueError('Room must be 00–FF')
    if len(rom) < HUD_TILES_OFFSET+0x800:
        raise ValueError('ROM does not contain the HUD and item graphics')
    record = palette_record_offset(rom, rom[0x842EF+room])
    colors = {}
    for palette in (1, 2, 3):
        colors[palette] = tuple(gbc_rgb(int.from_bytes(rom[at:at+2], 'little'))
                                for at in range(record+palette*8, record+palette*8+8, 2))
    tiles, attributes = preview_tilemap()
    image = Image.new('RGB', (160,128))
    for y, row in enumerate(tiles):
        for x, tile_id in enumerate(row):
            palette = colors[attributes[y][x]]
            tile = Image.new('RGB', (8,8), palette[0])
            if tile_id != 0x7F:
                offset = HUD_TILES_OFFSET+(tile_id-0x80)*16
                indices = decode_2bpp(rom[offset:offset+16])
                tile.putdata([palette[indices.getpixel((xx, yy))]
                              for yy in range(8) for xx in range(8)])
            image.paste(tile, (x*8,y*8))
    return image.resize((160*scale,128*scale), Image.Resampling.NEAREST)
