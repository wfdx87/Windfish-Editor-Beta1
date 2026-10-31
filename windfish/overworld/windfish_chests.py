"""Overworld room chest rewards for English LADX Rev 2.

The A0 room object is the chest. Sprite 07 is spawned by the game on opening.
Alternate layouts share the same reward byte and saved room-status bit.
"""
CHEST_TABLE = 0x50560
CHEST_ITEMS = {
    0x00: 'Power Bracelet', 0x01: 'Shield', 0x02: 'Bow',
    0x03: 'Hookshot', 0x04: 'Magic Rod', 0x05: 'Pegasus Boots',
    0x06: 'Ocarina', 0x07: "Roc’s Feather", 0x08: 'Shovel',
    0x09: 'Magic Powder', 0x0A: 'Bomb', 0x0B: 'Sword',
    0x0C: 'Flippers', 0x0D: 'Magnifying Lens', 0x10: 'Secret Medicine',
    0x11: 'Tail Key', 0x12: 'Angler Key', 0x13: 'Face Key',
    0x14: 'Bird Key', 0x15: 'Gold Leaf', 0x16: 'Dungeon Map',
    0x17: 'Compass', 0x18: 'Stone Beak', 0x19: 'Nightmare Key',
    0x1A: 'Small Key', 0x1B: '50 Rupees', 0x1C: '20 Rupees',
    0x1D: '100 Rupees', 0x1E: '200 Rupees', 0x1F: '500 Rupees',
    0x20: 'Secret Seashell', 0x21: 'Message', 0x22: 'Zol trap',
}


def chest_offset(data, room):
    if not isinstance(room, int) or not 0 <= room <= 255:
        raise ValueError('Room must be 00–FF')
    if len(data) < CHEST_TABLE + 256:
        raise ValueError('Missing overworld chest contents table')
    return CHEST_TABLE + room


def read_chest_item(data, room):
    return data[chest_offset(data, room)]


def chest_item_label(item):
    return f'{item:02X} — {CHEST_ITEMS.get(item, "Unknown (preserved)")}'


def set_chest_item(data, room, item):
    """Change exactly one byte; return its history change, or None for a no-op."""
    offset = chest_offset(data, room)
    if item not in CHEST_ITEMS:
        raise ValueError('Unsupported chest item')
    before = data[offset]
    if before == item:
        return None
    data[offset] = item
    return offset, before, item
