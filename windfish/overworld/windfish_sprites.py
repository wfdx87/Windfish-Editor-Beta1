"""Read-only LADX DX overworld sprite records, following LALE Sprites.loadObjects.

Pointer table: bank 0x16 at file offset 0x58000; 256 little-endian
bank-local addresses. Entries: packed YX byte, sprite ID byte; FF terminates.
"""
from dataclasses import dataclass

TABLE = 0x58000
BANK = 0x58000
BANK_END = 0x5C000

@dataclass(frozen=True)
class Sprite:
    x: int
    y: int
    id: int
    offset: int


def read_room_sprites(data, room):
    if not 0 <= room < 256:
        raise ValueError('Room must be between 00 and FF')
    if len(data) < BANK_END:
        raise ValueError('ROM too small for overworld sprite bank')
    from windfish.rom.windfish_sprite_storage import enabled, EXTENDED, storage_end
    bank = EXTENDED if enabled(data) else BANK
    bank_end = storage_end(data) if enabled(data) else BANK_END
    table_offset = bank + room * 2
    pointer = data[table_offset] | (data[table_offset + 1] << 8)
    if not 0x4000 <= pointer < 0x8000:
        raise ValueError(f'Invalid sprite pointer {pointer:04X} for room {room:02X}')
    start = bank + pointer - (0x4000)
    sprites = []
    cursor = start
    while cursor < bank_end:
        xy = data[cursor]
        if xy == 0xFF:
            return {'room':room, 'pointer_offset':table_offset, 'start':start,
                    'end':cursor+1, 'sprites':sprites}
        if cursor + 1 >= bank_end:
            break
        sprites.append(Sprite(xy & 15, xy >> 4, data[cursor+1], cursor))
        cursor += 2
    raise ValueError(f'Unterminated sprite list for room {room:02X}')
