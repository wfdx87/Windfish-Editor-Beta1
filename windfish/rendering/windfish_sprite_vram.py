"""Map room-specific 16-tile sprite sheets into a *declared* VRAM tile layout.

The four room spritesheet slots are verified at VRAM $8400,$8500,$8600,$8700
(bank0.asm 00:0E21, interrupts.asm 00:0721 and 00:078F). The provider refuses reads from
unmapped VRAM locations instead of silently showing incorrect graphics.
"""
from dataclasses import dataclass
from windfish.rendering.windfish_sprite_graphics import load_room_sprite_graphics, graphics_source_offset

VERIFIED_OVERWORLD_SLOT_BASES = (0x40, 0x50, 0x60, 0x70)

@dataclass(frozen=True)
class SpriteSlot:
    slot: int
    selector: int
    rom_offset: int | None
    tile_base: int


def room_vram_provider(rom: bytes, room: int, slot_tile_bases: tuple[int, int, int, int] = VERIFIED_OVERWORLD_SLOT_BASES, *, graphics_overrides=(), graphics_sources=()):
    """Return (fetch, slots) where fetch(tile_index, bank) returns 16 bytes.

    tile bases refer to *absolute* 8x8 tile indices in Game Boy OBJ VRAM,
    not indices in the room graphics preview. No guessed mappings are used.
    """
    loaded = load_room_sprite_graphics(rom, room)
    return loaded_vram_provider(rom, loaded, slot_tile_bases, graphics_overrides=graphics_overrides, graphics_sources=graphics_sources)


def loaded_vram_provider(rom, loaded, slot_tile_bases=VERIFIED_OVERWORLD_SLOT_BASES, *, graphics_overrides=(), graphics_sources=()):
    """Use the same verified slot mapping for overworld or indoor graphics."""
    if len(slot_tile_bases) != 4:
        raise ValueError('Exactly four slot base tile indices required')
    for base in slot_tile_bases:
        if not isinstance(base, int) or not 0 <= base <= 240 or base % 16:
            raise ValueError('Slot bases must be 16-aligned tile indices in 0..240')
    if len(set(slot_tile_bases)) != 4:
        raise ValueError('Sprite slots must occupy distinct tile ranges')
    selectors, offsets, graphics = loaded.selectors, loaded.offsets, loaded.graphics
    if graphics_overrides or graphics_sources:
        selectors, offsets = list(selectors), list(offsets)
        graphics = bytearray(graphics)
    seen = set()
    for slot, selector in graphics_overrides:
        if slot not in range(4) or slot in seen or selector not in range(1,255):
            raise ValueError('Invalid graphics override')
        seen.add(slot)
        offset = graphics_source_offset(rom, selector)
        selectors[slot], offsets[slot] = selector, offset
        graphics[slot*0x100:(slot+1)*0x100] = rom[offset:offset+0x100]
    for slot, offset in graphics_sources:
        if (slot not in range(4) or slot in seen or not isinstance(offset, int)
                or offset < 0 or offset % 0x100 or offset+0x100 > len(rom)):
            raise ValueError('Invalid direct graphics source')
        seen.add(slot)
        # Runtime uploads have no encoded room selector. Offset, not selector,
        # determines availability; retain all other room slots as loaded.
        selectors[slot], offsets[slot] = 0, offset
        graphics[slot*0x100:(slot+1)*0x100] = rom[offset:offset+0x100]
    slots = tuple(SpriteSlot(i, selectors[i], offsets[i], slot_tile_bases[i]) for i in range(4))
    def fetch(index: int, bank: int) -> bytes:
        if bank != 0:
            raise ValueError('VRAM bank 1 graphics are not yet mapped')
        if not isinstance(index, int) or not 0 <= index < 256:
            raise ValueError('Invalid tile index')
        for s in slots:
            if s.tile_base <= index < s.tile_base + 16:
                if s.rom_offset is None:
                    raise ValueError('Requested tile belongs to an empty graphics slot')
                start = (s.slot * 16 + index - s.tile_base) * 16
                return bytes(graphics[start:start + 16])
        raise ValueError('Tile index outside the four mapped sprite graphics slots')
    return fetch, slots


def shared_item_tile(rom, index, bank, *, overworld=True):
    """Read verified base CGB OBJ uploads, without changing room slot mappings.

    bank0.asm func_2D50 uploads LinkCharacterTiles+$200 to $8200 and
    InventoryEquipmentItemsTiles to $8800. LoadBaseOverworldTiles uploads
    InventoryOverworldItemsTiles to $8C00. Native and original VWF retain the
    same graphics addresses. This is the default item state, before runtime
    inventory substitutions (for example a Golden Leaf replacing the Slime Key).
    """
    if bank != 0:
        raise ValueError('Shared item graphics require VRAM bank 0')
    if 0x20 <= index < 0x30:
        at = 0xB0200 + (index - 0x20) * 16
    elif 0x3E <= index < 0x40:
        # LoadBaseTiles copies LinkCharacterTiles[0:400] to VRAM 8000-83FF;
        # these two tiles are the overworld warp's particle and blank lower half.
        at = 0xB0000 + index * 16
    elif 0xC0 <= index <= 0xFF and not overworld:
        # Indoor C0-FF uploads depend on dungeon/map ID; the caller must not
        # accidentally substitute the overworld key graphics for that context.
        raise ValueError('Indoor high item tiles require a map-specific mapping')
    elif 0x80 <= index <= 0xFF:
        at = 0xB0800 + (index - 0x80) * 16
    else:
        raise ValueError('Tile is outside verified shared item graphics')
    raw = bytes(rom[at:at+16])
    if len(raw) != 16:
        raise ValueError('Missing shared item graphics')
    return raw
