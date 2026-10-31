"""Room-aware LADX Rev 2 OBJ palettes, before transient gameplay effects."""
OBJ_PALETTES_OFFSET = 0x85518
ROOM_PALETTE_MAP = 0x842EF
ROOM_PALETTE_POINTERS = 0x842B1


def palette_record_offset(rom, palette_id):
    from windfish.rom.windfish_palette_patch import is_installed
    maximum = 0x3F if is_installed(rom) else 0x1E
    if not 0 <= palette_id <= maximum:
        raise ValueError('Palette ID is not available in this ROM')
    if palette_id >= 0x1F:
        offset = 0x1D2C00 + (palette_id-0x1F)*0x50
    else:
        at = ROOM_PALETTE_POINTERS + palette_id*2
        pointer = int.from_bytes(rom[at:at+2], 'little')
        if not 0x4000 <= pointer <= 0x7FFF:
            raise ValueError(f'Invalid original palette pointer {pointer:04X}')
        offset = 0x84000 + pointer-0x4000
    if offset+80 > len(rom):
        raise ValueError('Room palette record extends outside the ROM')
    return offset


def object_palette_offsets(rom, room):
    """Source offset for each of 32 OBJ colors, including known room overrides.

    The six shared palettes occupy 48 bytes; the final 16 bytes come from
    the selected room record. The game also overrides OBJ 5 in 0E and OBJ 7
    in 92 after loading that record (palettes are zero-based here).
    """
    if not 0 <= room <= 255:
        raise ValueError('Room must be 00–FF')
    if len(rom) < ROOM_PALETTE_MAP+256:
        raise ValueError('ROM does not contain the overworld palette map')
    offset = palette_record_offset(rom, rom[ROOM_PALETTE_MAP+room])
    offsets = [OBJ_PALETTES_OFFSET+i*2 for i in range(24)]
    offsets.extend(offset+64+i*2 for i in range(8))
    if room == 0x0E:
        offsets[20:24] = list(range(0x85548, 0x85550, 2))
    if room == 0x92:
        offsets[29:32] = [0x856CE, 0x856CA, 0x856C8]
    return tuple(offsets)


def gbc_rgb(value):
    return ((value & 31) << 3, ((value >> 5) & 31) << 3,
            ((value >> 10) & 31) << 3)


def object_palettes(rom, room=0):
    offsets = object_palette_offsets(rom, room)
    colors = tuple(gbc_rgb(int.from_bytes(rom[at:at+2], 'little')) for at in offsets)
    return tuple(colors[i:i+4] for i in range(0, 32, 4))
