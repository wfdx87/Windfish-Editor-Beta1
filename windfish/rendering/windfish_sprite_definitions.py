"""ID-ordered sprite frames. Change display_frame to choose ONE static preview.

Frame numbers are zero-based. All frames are initialized as ROM-backed metadata;
images are assembled on demand using the selected room's graphics. None keeps the
ROM-loaded placeholder. Alternate gameplay tables are labeled explicitly.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SpriteFrame:
    offset: int
    expected: bytes
    label: str
    layout: str = 'pair'
    tile_offset: int = 0


@dataclass(frozen=True)
class SpritePart:
    """Additional ROM-backed component at a fixed editor-preview position."""
    frame: SpriteFrame
    x: int = 0
    y: int = 0


@dataclass(frozen=True)
class SpriteDefinition:
    frames: tuple[SpriteFrame, ...]
    display_frame: int = 0
    tile_offset: int = 0
    required_slot: int | None = None
    required_selector: int | None = None
    fallback_palette: int = 0
    room_fallback: tuple[int, int] | None = None
    canvas_size: tuple[int, int] | None = None
    draw_offset: tuple[int, int] = (0, 0)
    graphics_overrides: tuple[tuple[int, int], ...] = ()
    graphics_sources: tuple[tuple[int, int], ...] = ()
    shared_graphics: bool = False
    overworld_only: bool = False
    parts: tuple[SpritePart, ...] = ()

    def __post_init__(self):
        if not self.frames or not 0 <= self.display_frame < len(self.frames):
            raise ValueError('Display frame must index an initialized sprite frame')
        for frame in (*self.frames, *(part.frame for part in self.parts)):
            if not isinstance(frame.tile_offset, int) or not 0 <= frame.tile_offset <= 255 or frame.tile_offset % 2:
                raise ValueError('Frame tile offset must be an even byte value')
            if frame.layout == 'single':
                valid = len(frame.expected) == 2
            elif frame.layout == 'pair':
                valid = len(frame.expected) == 4
            elif frame.layout == 'rect':
                valid = bool(frame.expected) and len(frame.expected) % 4 == 0
            else:
                valid = False
            if not valid:
                raise ValueError('Invalid sprite frame layout or record length')
        if self.canvas_size and any(side <= 0 for side in self.canvas_size):
            raise ValueError('Sprite canvas dimensions must be positive')
        if (len({slot for slot, _ in self.graphics_overrides}) != len(self.graphics_overrides)
                or any(slot not in range(4) or selector not in range(1,255)
                       for slot, selector in self.graphics_overrides)):
            raise ValueError('Graphics overrides must name distinct slots and valid selectors')
        source_slots = [slot for slot, _ in self.graphics_sources]
        if (len(set(source_slots)) != len(source_slots)
                or set(source_slots) & {slot for slot, _ in self.graphics_overrides}
                or any(slot not in range(4) or not isinstance(offset, int)
                       or offset < 0 or offset % 0x100
                       for slot, offset in self.graphics_sources)):
            raise ValueError('Direct graphics sources must name distinct slots and aligned ROM offsets')


# Replace deferred None entries as sprites are added. Keep IDs in order.
SPRITE_DEFINITIONS = {
    0x00: None,  # Arrow
    0x01: None,  # Boomerang
    0x02: None,  # Bomb
    0x03: None,  # Hookshot Chain
    0x04: None,  # Magic Rod Fireball
    0x05: None,  # Liftable Rock
    0x06: SpriteDefinition(  # Pushed Block
        frames=(
            SpriteFrame(0x0D232, bytes.fromhex('6E 07 6E 27'), 'Unknown011SpriteVariants / 0'),
            SpriteFrame(0x0D236, bytes.fromhex('F8 17 FA 17'), 'Unknown011SpriteVariants / 1'),
            SpriteFrame(0x0D242, bytes.fromhex('7E 07 7E 27'), 'Unknown010SpriteVariants / 0'),
        ),
        display_frame=0,  # Change this zero-based frame number.
    ),
    0x07: None,  # Chest With Item
    0x08: None,  # Magic Powder Sprinkle
    0x09: SpriteDefinition(  # Octorok
        frames=(
            SpriteFrame(0x0D7F2, bytes.fromhex('30 02 30 22'), 'normal / 0'),
            SpriteFrame(0x0D7F6, bytes.fromhex('32 02 32 22'), 'normal / 1'),
            SpriteFrame(0x0D7FA, bytes.fromhex('30 42 30 62'), 'normal / 2'),
            SpriteFrame(0x0D7FE, bytes.fromhex('32 42 32 62'), 'normal / 3'),
            SpriteFrame(0x0D802, bytes.fromhex('34 02 36 02'), 'normal / 4'),
            SpriteFrame(0x0D806, bytes.fromhex('38 02 3A 02'), 'normal / 5'),
            SpriteFrame(0x0D80A, bytes.fromhex('36 22 34 22'), 'normal / 6'),
            SpriteFrame(0x0D80E, bytes.fromhex('3A 22 38 22'), 'normal / 7'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        tile_offset=48,
        required_slot=2,
        required_selector=227,
    ),
    0x0A: None,  # Octorok Rock
    0x0B: SpriteDefinition(  # Moblin
        frames=(
            SpriteFrame(0x0D90E, bytes.fromhex('60 03 62 03'), 'normal / 0'),
            SpriteFrame(0x0D912, bytes.fromhex('62 23 60 23'), 'normal / 1'),
            SpriteFrame(0x0D916, bytes.fromhex('64 03 66 03'), 'normal / 2'),
            SpriteFrame(0x0D91A, bytes.fromhex('66 23 64 23'), 'normal / 3'),
            SpriteFrame(0x0D91E, bytes.fromhex('68 03 6A 03'), 'normal / 4'),
            SpriteFrame(0x0D922, bytes.fromhex('6C 03 6E 03'), 'normal / 5'),
            SpriteFrame(0x0D926, bytes.fromhex('6A 23 68 23'), 'normal / 6'),
            SpriteFrame(0x0D92A, bytes.fromhex('6E 23 6C 23'), 'normal / 7'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        required_slot=2,
        fallback_palette=3,
    ),
    0x0C: None,  # Moblin Arrow
    0x0D: SpriteDefinition(  # Tektite
        frames=(
            SpriteFrame(0x1B8B3, bytes.fromhex('58 02 58 22'), 'normal / 0'),
            SpriteFrame(0x1B8B7, bytes.fromhex('5A 02 5A 22'), 'normal / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        required_slot=1,
        fallback_palette=2,
    ),
    0x0E: SpriteDefinition(  # Leever
        frames=(
            SpriteFrame(0x13EF1, bytes.fromhex('56 02 56 22'), 'normal / 0'),
            SpriteFrame(0x13EF5, bytes.fromhex('54 02 54 22'), 'normal / 1'),
            SpriteFrame(0x13EF9, bytes.fromhex('52 02 52 22'), 'normal / 2'),
            SpriteFrame(0x13EFD, bytes.fromhex('50 02 50 22'), 'normal / 3'),
        ),
        display_frame=2,  # Change this zero-based frame number.
        required_slot=1,
        fallback_palette=2,
        room_fallback=(226, 225),
    ),
    0x0F: SpriteDefinition(  # Armos Statue
        frames=(
            SpriteFrame(0x1B442, bytes.fromhex('60 07 62 07'), 'ArmosStatueSpriteVariants / 0'),
            SpriteFrame(0x1B446, bytes.fromhex('64 07 66 07'), 'ArmosStatueSpriteVariants / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        fallback_palette=7,
    ),
    0x10: SpriteDefinition(  # Hiding Ghini: show its revealed form.
        frames=(
            SpriteFrame(0x11BFC, bytes.fromhex('58 02 5A 02'), 'Ghini / 0', layout='pair'),
            SpriteFrame(0x11C00, bytes.fromhex('5C 02 5E 02'), 'Ghini / 1', layout='pair'),
        ), required_slot=1, fallback_palette=2,
    ),
    0x11: SpriteDefinition(  # Giant Ghini, eight 8x16 pieces.
        frames=(
            SpriteFrame(0x11D26, bytes.fromhex('F8 F8 60 02 F8 00 62 02 F8 08 62 22 F8 10 60 22 08 F8 64 02 08 00 66 02 08 08 68 02 08 10 6A 02'), 'Giant Ghini / 0', layout='rect'),
            SpriteFrame(0x11D46, bytes.fromhex('F8 F8 60 02 F8 00 62 02 F8 08 62 22 F8 10 60 22 08 F8 64 02 08 00 6C 02 08 08 6E 02 08 10 6A 02'), 'Giant Ghini / 1', layout='rect'),
            SpriteFrame(0x11D66, bytes.fromhex('F8 F8 60 02 F8 00 62 02 F8 08 62 22 F8 10 60 22 08 F8 6A 22 08 00 68 22 08 08 66 22 08 10 64 22'), 'Giant Ghini / 2', layout='rect'),
            SpriteFrame(0x11D86, bytes.fromhex('F8 F8 60 02 F8 00 62 02 F8 08 62 22 F8 10 60 22 08 F8 6A 22 08 00 6E 22 08 08 6C 22 08 10 64 22'), 'Giant Ghini / 3', layout='rect'),
        ), required_slot=2, fallback_palette=2, draw_offset=(-8, -8),
    ),
    0x12: SpriteDefinition(  # Ghini
        frames=(
            SpriteFrame(0x11BFC, bytes.fromhex('58 02 5A 02'), 'GhiniSpriteVariants / 0'),
            SpriteFrame(0x11C00, bytes.fromhex('5C 02 5E 02'), 'GhiniSpriteVariants / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        fallback_palette=2,
    ),
    0x13: None,  # Sprite 13
    0x14: SpriteDefinition(  # Moblin Sword
        frames=(
            SpriteFrame(0x1FAD1, bytes.fromhex('60 03 62 03'), 'Unknown042SpriteVariants / 0'),
            SpriteFrame(0x1FAD5, bytes.fromhex('62 23 60 23'), 'Unknown042SpriteVariants / 1'),
            SpriteFrame(0x1FAD9, bytes.fromhex('64 03 66 03'), 'Unknown042SpriteVariants / 2'),
            SpriteFrame(0x1FADD, bytes.fromhex('66 23 64 23'), 'Unknown042SpriteVariants / 3'),
            SpriteFrame(0x1FAE1, bytes.fromhex('68 03 6A 03'), 'Unknown042SpriteVariants / 4'),
            SpriteFrame(0x1FAE5, bytes.fromhex('6C 03 6E 03'), 'Unknown042SpriteVariants / 5'),
            SpriteFrame(0x1FAE9, bytes.fromhex('6A 23 68 23'), 'Unknown042SpriteVariants / 6'),
            SpriteFrame(0x1FAED, bytes.fromhex('6E 23 6C 23'), 'Unknown042SpriteVariants / 7'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        fallback_palette=3,
    ),
    0x15: None,  # Anti Fairy
    0x16: None,  # Spark Counter Clockwise
    0x17: None,  # Spark Clockwise
    0x18: SpriteDefinition(  # Pols Voice
        frames=(
            SpriteFrame(0x1B36F, bytes.fromhex('70 01 70 21'), 'PolsVoiceSpriteVariants / 0'),
            SpriteFrame(0x1B373, bytes.fromhex('72 01 72 21'), 'PolsVoiceSpriteVariants / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        fallback_palette=1,
    ),
    0x19: SpriteDefinition(  # Keese
        frames=(
            SpriteFrame(0x1A70A, bytes.fromhex('42 00 42 20'), 'KeeseSpriteVariants / 0'),
            SpriteFrame(0x1A70E, bytes.fromhex('40 00 40 20'), 'KeeseSpriteVariants / 1'),
            SpriteFrame(0x1A712, bytes.fromhex('62 00 62 20'), 'KeeseCaveBSpriteVariants / 0'),
            SpriteFrame(0x1A716, bytes.fromhex('60 00 60 20'), 'KeeseCaveBSpriteVariants / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
    ),
    0x1A: SpriteDefinition(  # Stalfos Aggressive
        frames=(
            SpriteFrame(0x18AA8, bytes.fromhex('4A 00 4C 00'), 'StalfosAggressiveSpriteVariants / 0'),
            SpriteFrame(0x18AAC, bytes.fromhex('4C 20 4A 20'), 'StalfosAggressiveSpriteVariants / 1'),
            SpriteFrame(0x18AB0, bytes.fromhex('4E 00 4E 20'), 'StalfosAggressiveSpriteVariants / 2'),
        ),
        display_frame=0,  # Change this zero-based frame number.
    ),
    0x1B: SpriteDefinition(  # Zol
        frames=(
            SpriteFrame(0x1BC05, bytes.fromhex('52 02 52 22'), 'ZolSpriteVariants / 0'),
            SpriteFrame(0x1BC09, bytes.fromhex('54 02 54 22'), 'ZolSpriteVariants / 1'),
            SpriteFrame(0x1BC0D, bytes.fromhex('52 00 52 20'), 'ZolSlimeEyeSpriteVariants / 0'),
            SpriteFrame(0x1BC11, bytes.fromhex('54 00 54 20'), 'ZolSlimeEyeSpriteVariants / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
        fallback_palette=2,
    ),
    0x1C: None,  # Gel
    0x1D: None,  # Unknown entity
    0x1E: SpriteDefinition(  # Stalfos Evasive
        frames=(
            SpriteFrame(0x54E7D, bytes.fromhex('4A 01 4C 01'), 'StalfosEvasive2SpriteVariants / 0'),
            SpriteFrame(0x54E81, bytes.fromhex('4C 21 4A 21'), 'StalfosEvasive2SpriteVariants / 1'),
            SpriteFrame(0x54E85, bytes.fromhex('4E 01 4E 21'), 'StalfosEvasive2SpriteVariants / 2'),
            SpriteFrame(0x54E8E, bytes.fromhex('48 01 48 61'), 'StalfosEvasive1SpriteVariants / 0'),
            SpriteFrame(0x54E92, bytes.fromhex('48 41 48 21'), 'StalfosEvasive1SpriteVariants / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
    ),
    0x1F: SpriteDefinition(  # Gibdo
        frames=(
            SpriteFrame(0x1BE6B, bytes.fromhex('74 02 76 02'), 'GibdoSpriteVariants / 0'),
            SpriteFrame(0x1BE6F, bytes.fromhex('76 22 74 22'), 'GibdoSpriteVariants / 1'),
            SpriteFrame(0x1BE73, bytes.fromhex('44 02 46 02'), 'GibdoTurtleRockSpriteVariants / 0'),
            SpriteFrame(0x1BE77, bytes.fromhex('46 22 44 22'), 'GibdoTurtleRockSpriteVariants / 1'),
        ),
        display_frame=0,  # Change this zero-based frame number.
    ),
    0x20: SpriteDefinition(  # Hardhat Beetle
        frames=(
            SpriteFrame(0x18F2C, bytes.fromhex('44 01 44 21'), 'HardHatBeetleSpriteVariants / 0'),
            SpriteFrame(0x18F30, bytes.fromhex('46 01 46 21'), 'HardHatBeetleSpriteVariants / 1'),
            SpriteFrame(0x18F34, bytes.fromhex('64 01 64 21'), 'HardHatBeetleCaveBSpriteVariants / 0'),
            SpriteFrame(0x18F38, bytes.fromhex('66 01 66 21'), 'HardHatBeetleCaveBSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x21: SpriteDefinition(  # Wizrobe
        frames=(
            SpriteFrame(0x1B600, bytes.fromhex('6E 00 6E 20'), 'WizrobeSpriteVariants / 0'),
            SpriteFrame(0x1B604, bytes.fromhex('66 20 64 20'), 'WizrobeSpriteVariants / 1'),
            SpriteFrame(0x1B608, bytes.fromhex('64 00 66 00'), 'WizrobeSpriteVariants / 2'),
            SpriteFrame(0x1B60C, bytes.fromhex('62 00 62 20'), 'WizrobeSpriteVariants / 3'),
            SpriteFrame(0x1B610, bytes.fromhex('60 00 60 20'), 'WizrobeSpriteVariants / 4'),
        ),
        display_frame=0,
        fallback_palette=0,
    ),
    0x22: SpriteDefinition(  # Wizrobe Projectile
        frames=(
            SpriteFrame(0x1A5E3, bytes.fromhex('6A 23 68 23'), 'WizrobeProjectileSpriteVariants / 0'),
            SpriteFrame(0x1A5E7, bytes.fromhex('68 03 6A 03'), 'WizrobeProjectileSpriteVariants / 1'),
            SpriteFrame(0x1A5EB, bytes.fromhex('6C 43 6C 63'), 'WizrobeProjectileSpriteVariants / 2'),
            SpriteFrame(0x1A5EF, bytes.fromhex('6C 03 6C 23'), 'WizrobeProjectileSpriteVariants / 3'),
        ),
        display_frame=0,
        fallback_palette=3,
    ),
    0x23: SpriteDefinition(  # Like Like
        frames=(
            SpriteFrame(0x1BDD0, bytes.fromhex('7C 01 7C 21'), 'LikeLikeSpriteVariants / 0'),
            SpriteFrame(0x1BDD4, bytes.fromhex('7E 01 7E 21'), 'LikeLikeSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x24: SpriteDefinition(  # Iron Mask
        frames=(
            SpriteFrame(0x0CFCC, bytes.fromhex('60 02 62 02'), 'MaskedIronMaskSpriteVariants / 0'),
            SpriteFrame(0x0CFD0, bytes.fromhex('62 22 60 22'), 'MaskedIronMaskSpriteVariants / 1'),
            SpriteFrame(0x0CFD4, bytes.fromhex('64 02 66 02'), 'MaskedIronMaskSpriteVariants / 2'),
            SpriteFrame(0x0CFD8, bytes.fromhex('66 22 64 22'), 'MaskedIronMaskSpriteVariants / 3'),
            SpriteFrame(0x0CFDC, bytes.fromhex('68 02 6A 02'), 'MaskedIronMaskSpriteVariants / 4'),
            SpriteFrame(0x0CFE0, bytes.fromhex('6C 02 6E 02'), 'MaskedIronMaskSpriteVariants / 5'),
            SpriteFrame(0x0CFE4, bytes.fromhex('6A 22 68 22'), 'MaskedIronMaskSpriteVariants / 6'),
            SpriteFrame(0x0CFE8, bytes.fromhex('6E 22 6C 22'), 'MaskedIronMaskSpriteVariants / 7'),
            SpriteFrame(0x0CFEC, bytes.fromhex('70 02 72 02'), 'UnmaskedIronMaskSpriteVariants / 0'),
            SpriteFrame(0x0CFF0, bytes.fromhex('72 22 70 22'), 'UnmaskedIronMaskSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=2,
    ),
    0x25: None,  # Sprite 25 — Unused handler
    0x26: None,  # Sprite 26 — Unused handler
    0x27: SpriteDefinition(  # Spike Trap
        frames=(
            SpriteFrame(0x1B4F6, bytes.fromhex('50 02 50 22'), 'SpikeTrapSpriteVariants / 0'),
        ),
        display_frame=0,
        fallback_palette=2,
    ),
    0x28: SpriteDefinition(  # Mimic
        frames=(
            SpriteFrame(0x66A93, bytes.fromhex('60 01 62 01'), 'MimicSpriteVariants / 0'),
            SpriteFrame(0x66A97, bytes.fromhex('62 21 60 21'), 'MimicSpriteVariants / 1'),
            SpriteFrame(0x66A9B, bytes.fromhex('64 01 66 01'), 'MimicSpriteVariants / 2'),
            SpriteFrame(0x66A9F, bytes.fromhex('66 21 64 21'), 'MimicSpriteVariants / 3'),
            SpriteFrame(0x66AA3, bytes.fromhex('68 01 6A 01'), 'MimicSpriteVariants / 4'),
            SpriteFrame(0x66AA7, bytes.fromhex('6C 01 6E 01'), 'MimicSpriteVariants / 5'),
            SpriteFrame(0x66AAB, bytes.fromhex('6A 21 68 21'), 'MimicSpriteVariants / 6'),
            SpriteFrame(0x66AAF, bytes.fromhex('6E 21 6C 21'), 'MimicSpriteVariants / 7'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x29: SpriteDefinition(  # Fixed downward pose; gameplay tail follows position history.
        frames=(
            SpriteFrame(0x11A49, bytes.fromhex('70 00 70 20'), 'Mini Moldorm head / 0', layout='pair'),
        ), required_slot=3, draw_offset=(0, -22),
        parts=(
            SpritePart(SpriteFrame(0x11A69, bytes.fromhex('7A 00 7A 20'), 'Mini Moldorm middle', layout='pair'), 0, -12),
            SpritePart(SpriteFrame(0x11A6D, bytes.fromhex('7C 00 7C 20'), 'Mini Moldorm tail', layout='pair'), 0, -22),
        ),
    ),
    0x2A: SpriteDefinition(  # Laser
        frames=(
            SpriteFrame(0x12C2D, bytes.fromhex('70 03 70 23'), 'LaserSpriteVariants / 0'),
            SpriteFrame(0x12C31, bytes.fromhex('78 03 7A 03'), 'LaserSpriteVariants / 1'),
            SpriteFrame(0x12C35, bytes.fromhex('74 03 76 03'), 'LaserSpriteVariants / 2'),
            SpriteFrame(0x12C39, bytes.fromhex('7C 03 7E 03'), 'LaserSpriteVariants / 3'),
            SpriteFrame(0x12C3D, bytes.fromhex('72 03 72 23'), 'LaserSpriteVariants / 4'),
            SpriteFrame(0x12C41, bytes.fromhex('7E 23 7C 23'), 'LaserSpriteVariants / 5'),
            SpriteFrame(0x12C45, bytes.fromhex('76 23 74 23'), 'LaserSpriteVariants / 6'),
            SpriteFrame(0x12C49, bytes.fromhex('7A 23 78 23'), 'LaserSpriteVariants / 7'),
        ),
        display_frame=0,
        fallback_palette=3,
    ),
    0x2B: None,  # Laser Beam — Beam layout; deferred
    0x2C: SpriteDefinition(  # Spiked Beetle
        frames=(
            SpriteFrame(0x1F7C0, bytes.fromhex('70 00 70 20'), 'SpikedBeetle1SpriteVariants / 0'),
            SpriteFrame(0x1F7C4, bytes.fromhex('72 00 72 20'), 'SpikedBeetle1SpriteVariants / 1'),
            SpriteFrame(0x1F7C8, bytes.fromhex('74 00 74 20'), 'SpikedBeetle1SpriteVariants / 2'),
            SpriteFrame(0x1F7CC, bytes.fromhex('76 00 76 20'), 'SpikedBeetle1SpriteVariants / 3'),
            SpriteFrame(0x1F7D0, bytes.fromhex('60 00 60 20'), 'SpikedBeetle2SpriteVariants / 0'),
            SpriteFrame(0x1F7D4, bytes.fromhex('62 00 62 20'), 'SpikedBeetle2SpriteVariants / 1'),
            SpriteFrame(0x1F7D8, bytes.fromhex('64 00 64 20'), 'SpikedBeetle2SpriteVariants / 2'),
            SpriteFrame(0x1F7DC, bytes.fromhex('66 00 66 20'), 'SpikedBeetle2SpriteVariants / 3'),
        ),
        display_frame=0,
        fallback_palette=0,
    ),
    0x2D: SpriteDefinition(
        frames=(
            SpriteFrame(0x0DD28, bytes.fromhex('A8 14'), 'Heart', layout='single'),
        ), shared_graphics=True,
    ),
    0x2E: None,  # Droppable Rupee — Shared pickup graphics; deferred
    0x2F: SpriteDefinition(
        frames=(
            SpriteFrame(0x0E153, bytes.fromhex('20 21'), 'Fairy / left', layout='single'),
            SpriteFrame(0x0E155, bytes.fromhex('20 01'), 'Fairy / right', layout='single'),
        ), shared_graphics=True,
    ),
    0x30: None,  # Key Drop Point — Invisible spawn point
    0x31: SpriteDefinition(
        frames=(
            SpriteFrame(0x0DB8D, bytes.fromhex('84 17'), 'Beach sword', layout='single'),
            SpriteFrame(0x0DB8B, bytes.fromhex('86 17'), 'Dropped shield', layout='single'),
        ), shared_graphics=True,
    ),
    0x32: SpriteDefinition(  # Iron Masks Mask
        frames=(
            SpriteFrame(0x0DB76, bytes.fromhex('74 00 76 00'), 'IronMasksMaskSpriteVariants / 0'),
            SpriteFrame(0x0DB7A, bytes.fromhex('76 20 74 20'), 'IronMasksMaskSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=0,
    ),
    0x33: None,  # Piece Of Power — Shared pickup graphics; deferred
    0x34: None,  # Guardian Acorn — Shared pickup graphics; deferred
    0x35: SpriteDefinition(
        frames=(
            SpriteFrame(0x0DA43, bytes.fromhex('AC 02 AC 22'), 'Heart Piece', layout='pair'),
        ), shared_graphics=True,
    ),
    0x36: None,  # Heart Container — Shared pickup graphics; deferred
    0x37: None,  # Droppable Arrows — Shared pickup graphics; deferred
    0x38: SpriteDefinition(
        frames=(
            SpriteFrame(0x0DFBE, bytes.fromhex('80 15'), 'Bomb pickup', layout='single'),
        ), shared_graphics=True,
    ),
    0x39: None,  # Instrument Of The Sirens — Instrument-specific layouts; deferred
    0x3A: SpriteDefinition(
        frames=(
            SpriteFrame(0x0DD39, bytes.fromhex('5E 02 5E 22'), 'Sleepy Toadstool', layout='pair'),
        ), shared_graphics=False, required_slot=1,
    ),
    0x3B: None,  # Droppable Magic Powder — Shared pickup graphics; deferred
    0x3C: SpriteDefinition(
        frames=(
            SpriteFrame(0x0DFF9, bytes.fromhex('CA 14'), 'Slime Key', layout='single'),
        ), shared_graphics=True,
    ),
    0x3D: SpriteDefinition(
        frames=(
            SpriteFrame(0x0DFCF, bytes.fromhex('9E 14'), 'Secret Seashell', layout='single'),
        ), shared_graphics=True,
    ),
    0x3E: SpriteDefinition(  # Marin
        frames=(
            SpriteFrame(0x14E2A, bytes.fromhex('68 01 6A 01'), 'MarinCreditsSpriteVariants / 0'),
            SpriteFrame(0x14E2E, bytes.fromhex('6A 21 68 21'), 'MarinCreditsSpriteVariants / 1'),
            SpriteFrame(0x14E32, bytes.fromhex('66 01 66 21'), 'MarinCreditsSpriteVariants / 2'),
            SpriteFrame(0x14E36, bytes.fromhex('66 01 66 21'), 'MarinCreditsSpriteVariants / 3'),
            SpriteFrame(0x14E3A, bytes.fromhex('6C 01 6E 01'), 'MarinCreditsSpriteVariants / 4'),
            SpriteFrame(0x14E3E, bytes.fromhex('6C 01 6E 01'), 'MarinCreditsSpriteVariants / 5'),
            SpriteFrame(0x14E42, bytes.fromhex('6E 21 6C 21'), 'MarinCreditsSpriteVariants / 6'),
            SpriteFrame(0x14E46, bytes.fromhex('6E 21 6C 21'), 'MarinCreditsSpriteVariants / 7'),
            SpriteFrame(0x14E4A, bytes.fromhex('60 01 62 01'), 'MarinCreditsSpriteVariants / 8'),
            SpriteFrame(0x14E4E, bytes.fromhex('64 01 64 21'), 'MarinCreditsSpriteVariants / 9'),
            SpriteFrame(0x14E52, bytes.fromhex('62 21 60 21'), 'MarinCreditsSpriteVariants / 10'),
            SpriteFrame(0x14E0A, bytes.fromhex('60 01 62 01'), 'MarinIndoorSpriteVariants / 0'),
            SpriteFrame(0x14E0E, bytes.fromhex('62 21 60 21'), 'MarinIndoorSpriteVariants / 1'),
            SpriteFrame(0x14E12, bytes.fromhex('64 01 66 01'), 'MarinIndoorSpriteVariants / 2'),
            SpriteFrame(0x14E16, bytes.fromhex('66 21 64 21'), 'MarinIndoorSpriteVariants / 3'),
            SpriteFrame(0x14E1A, bytes.fromhex('68 01 6A 01'), 'MarinIndoorSpriteVariants / 4'),
            SpriteFrame(0x14E1E, bytes.fromhex('6C 01 6E 01'), 'MarinIndoorSpriteVariants / 5'),
            SpriteFrame(0x14E22, bytes.fromhex('6A 21 68 21'), 'MarinIndoorSpriteVariants / 6'),
            SpriteFrame(0x14E26, bytes.fromhex('6E 21 6C 21'), 'MarinIndoorSpriteVariants / 7'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x3F: SpriteDefinition(  # Tarin
        frames=(
            SpriteFrame(0x14912, bytes.fromhex('78 02 7A 02'), 'Tarin1SpriteVariants / 0'),
            SpriteFrame(0x14916, bytes.fromhex('7A 22 78 22'), 'Tarin1SpriteVariants / 1'),
            SpriteFrame(0x1491A, bytes.fromhex('7C 02 7E 02'), 'Tarin1SpriteVariants / 2'),
            SpriteFrame(0x1491E, bytes.fromhex('78 02 7A 02'), 'Tarin1SpriteVariants / 3'),
            SpriteFrame(0x14922, bytes.fromhex('70 02 72 02'), 'Tarin1SpriteVariants / 4'),
            SpriteFrame(0x14926, bytes.fromhex('74 02 76 02'), 'Tarin1SpriteVariants / 5'),
            SpriteFrame(0x1492A, bytes.fromhex('76 22 74 22'), 'Tarin1SpriteVariants / 6'),
            SpriteFrame(0x1492E, bytes.fromhex('72 22 70 22'), 'Tarin1SpriteVariants / 7'),
            SpriteFrame(0x14932, bytes.fromhex('5A 22 58 22'), 'Tarin3SpriteVariants / 0'),
            SpriteFrame(0x14936, bytes.fromhex('58 02 5A 02'), 'Tarin3SpriteVariants / 1'),
            SpriteFrame(0x1493A, bytes.fromhex('50 02 52 02'), 'Tarin3SpriteVariants / 2'),
            SpriteFrame(0x1493E, bytes.fromhex('50 02 52 02'), 'Tarin3SpriteVariants / 3'),
            SpriteFrame(0x14942, bytes.fromhex('54 02 56 02'), 'Tarin4SpriteVariants / 0'),
            SpriteFrame(0x14946, bytes.fromhex('7A 07 7C 07'), 'Tarin2SpriteVariants / 0'),
            SpriteFrame(0x14DC7, bytes.fromhex('74 07 76 07'), 'Tarin6SpriteVariants / 0'),
            SpriteFrame(0x14DCB, bytes.fromhex('70 00 72 00'), 'Tarin5SpriteVariants / 0'),
        ),
        display_frame=0,
        fallback_palette=2,
    ),
    0x40: SpriteDefinition(  # Witch
        frames=(
            SpriteFrame(0x14780, bytes.fromhex('00 00 60 01 00 08 62 01 10 00 64 02 10 08 66 02'), 'Data_005_4780 / 0', layout='rect'),
            SpriteFrame(0x14790, bytes.fromhex('00 00 68 01 00 08 6A 01 10 00 6C 02 10 08 6E 02'), 'Data_005_4780 / 1', layout='rect'),
            SpriteFrame(0x147A0, bytes.fromhex('00 00 62 21 00 08 60 21 10 00 66 22 10 08 64 22'), 'Data_005_4780 / 2', layout='rect'),
            SpriteFrame(0x147B0, bytes.fromhex('00 00 68 01 00 08 6A 01 10 00 6C 02 10 08 6E 02'), 'Data_005_4780 / 3', layout='rect'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x41: SpriteDefinition(  # Owl Event
        frames=(
            SpriteFrame(0x1AA33, bytes.fromhex('78 01 78 21'), 'OwlEventSpriteVariants / 0'),
            SpriteFrame(0x1AA37, bytes.fromhex('7A 01 7A 21'), 'OwlEventSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x42: SpriteDefinition(  # Owl Statue
        frames=(
            SpriteFrame(0x61E05, bytes.fromhex('5E 01 5E 21'), 'OwlStatueSpriteVariants / 0'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x43: None,  # Invisible tree dialog trigger; see SPRITE_CONTROLLER_NOTES.
    0x44: None,  # Invisible Magic Powder dialog trigger; see SPRITE_CONTROLLER_NOTES.
    0x45: SpriteDefinition(  # Boulders
        frames=(
            SpriteFrame(0x543AE, bytes.fromhex('5C 00 5E 00'), 'Unknown043SpriteVariants / 0'),
            SpriteFrame(0x543B2, bytes.fromhex('5E 20 5C 20'), 'Unknown043SpriteVariants / 1'),
            SpriteFrame(0x543B6, bytes.fromhex('5E 60 5C 60'), 'Unknown043SpriteVariants / 2'),
            SpriteFrame(0x543BA, bytes.fromhex('5C 40 5E 40'), 'Unknown043SpriteVariants / 3'),
        ),
        display_frame=0,
        fallback_palette=0,
    ),
    0x46: None,  # Moving Block Left Top — Not added yet
    0x47: None,  # Moving Block Left Bottom — Not added yet
    0x48: None,  # Moving Block Bottom Left — Not added yet
    0x49: None,  # Moving Block Bottom Right — Not added yet
    0x4A: None,  # Color Dungeon Book — Not added yet
    0x4B: None,  # 4B — Not added yet
    0x4C: None,  # Unknown sprite — Not added yet
    0x4D: SpriteDefinition(  # Shop Owner
        frames=(
            SpriteFrame(0x136CB, bytes.fromhex('60 03 62 03'), 'ShopOwnerSpriteVariants / 0'),
            SpriteFrame(0x136CF, bytes.fromhex('62 23 60 23'), 'ShopOwnerSpriteVariants / 1'),
            SpriteFrame(0x136D3, bytes.fromhex('64 03 66 03'), 'ShopOwnerSpriteVariants / 2'),
            SpriteFrame(0x136D7, bytes.fromhex('66 23 64 23'), 'ShopOwnerSpriteVariants / 3'),
            SpriteFrame(0x136DB, bytes.fromhex('68 03 6A 03'), 'ShopOwnerSpriteVariants / 4'),
            SpriteFrame(0x136DF, bytes.fromhex('6C 03 6E 03'), 'ShopOwnerSpriteVariants / 5'),
            SpriteFrame(0x136E3, bytes.fromhex('6A 23 68 23'), 'ShopOwnerSpriteVariants / 6'),
            SpriteFrame(0x136E7, bytes.fromhex('6E 23 6C 23'), 'ShopOwnerSpriteVariants / 7'),
        ),
        display_frame=0,
        fallback_palette=3,
    ),
    0x4E: None,  # 4E — Not added yet
    0x4F: None,  # Trendy Game Owner — Not added yet
    0x50: SpriteDefinition(  # Boo Buddy
        frames=(
            SpriteFrame(0x1B985, bytes.fromhex('62 20 60 20'), 'BooBuddySpriteVariants / 0'),
            SpriteFrame(0x1B989, bytes.fromhex('66 20 64 20'), 'BooBuddySpriteVariants / 1'),
            SpriteFrame(0x1B98D, bytes.fromhex('60 00 62 00'), 'BooBuddySpriteVariants / 2'),
            SpriteFrame(0x1B991, bytes.fromhex('64 00 66 00'), 'BooBuddySpriteVariants / 3'),
            SpriteFrame(0x1B995, bytes.fromhex('68 00 68 20'), 'BooBuddySpriteVariants / 4'),
            SpriteFrame(0x1B999, bytes.fromhex('6A 00 6A 20'), 'BooBuddySpriteVariants / 5'),
            SpriteFrame(0x1B99D, bytes.fromhex('6E 20 6C 20'), 'BooBuddySpriteVariants / 6'),
            SpriteFrame(0x1B9A1, bytes.fromhex('6C 00 6E 00'), 'BooBuddySpriteVariants / 7'),
        ),
        display_frame=0,
        fallback_palette=0,
    ),
    0x51: None,  # Knight — Not added yet
    0x52: SpriteDefinition(  # Tractor Device
        frames=(
            SpriteFrame(0x12814, bytes.fromhex('4C 07 4C 27'), 'TractorDeviceSpriteVariants / 0'),
            SpriteFrame(0x12818, bytes.fromhex('4E 04 4E 24'), 'TractorDeviceSpriteVariants / 1'),
            SpriteFrame(0x1281C, bytes.fromhex('7C 07 7C 27'), 'TractorDeviceBottleGrottoSpriteVariants / 0'),
            SpriteFrame(0x12820, bytes.fromhex('7E 04 7E 24'), 'TractorDeviceBottleGrottoSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=7,
    ),
    0x53: SpriteDefinition(  # Tractor Device Reverse
        frames=(
            SpriteFrame(0x12814, bytes.fromhex('4C 07 4C 27'), 'TractorDeviceSpriteVariants / 0'),
            SpriteFrame(0x12818, bytes.fromhex('4E 04 4E 24'), 'TractorDeviceSpriteVariants / 1'),
            SpriteFrame(0x1281C, bytes.fromhex('7C 07 7C 27'), 'TractorDeviceBottleGrottoSpriteVariants / 0'),
            SpriteFrame(0x12820, bytes.fromhex('7E 04 7E 24'), 'TractorDeviceBottleGrottoSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=7,
    ),
    0x54: SpriteDefinition(  # Overworld pond fisherman; rod occupies two extra OBJs.
        frames=(
            SpriteFrame(0x11F28, bytes.fromhex('00 F0 78 01 00 F8 7A 01 00 00 70 01 00 08 72 01'), 'Fisherman / rod low', layout='rect'),
            SpriteFrame(0x11F38, bytes.fromhex('00 F0 7C 01 00 F8 7E 01 00 00 70 01 00 08 72 01'), 'Fisherman / rod high', layout='rect'),
            SpriteFrame(0x11F48, bytes.fromhex('00 F0 78 01 00 F8 7A 01 00 00 74 01 00 08 76 01'), 'Fisherman / facing Link', layout='rect'),
        ), required_slot=3, fallback_palette=1, draw_offset=(-16, 0),
    ),
    0x55: SpriteDefinition(  # Bouncing Bombite
        frames=(
            SpriteFrame(0x13E01, bytes.fromhex('7A 22 78 22'), 'BouncingBombite1SpriteVariants / 0'),
            SpriteFrame(0x13E05, bytes.fromhex('78 02 7A 02'), 'BouncingBombite1SpriteVariants / 1'),
            SpriteFrame(0x13E09, bytes.fromhex('6A 22 68 22'), 'BouncingBombite2SpriteVariants / 0'),
            SpriteFrame(0x13E0D, bytes.fromhex('68 02 6A 02'), 'BouncingBombite2SpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=2,
    ),
    0x56: SpriteDefinition(  # Timer Bombite
        frames=(
            SpriteFrame(0x13CFB, bytes.fromhex('7A 20 78 20'), 'Bombite1SpriteVariants / 0'),
            SpriteFrame(0x13CFF, bytes.fromhex('78 00 7A 00'), 'Bombite1SpriteVariants / 1'),
            SpriteFrame(0x13D03, bytes.fromhex('7E 00 7E 20'), 'Bombite1SpriteVariants / 2'),
            SpriteFrame(0x13D07, bytes.fromhex('70 00 72 00'), 'Bombite1SpriteVariants / 3'),
            SpriteFrame(0x13D0B, bytes.fromhex('74 00 76 00'), 'Bombite1SpriteVariants / 4'),
            SpriteFrame(0x13D0F, bytes.fromhex('7C 00 7C 20'), 'Bombite1SpriteVariants / 5'),
            SpriteFrame(0x13D13, bytes.fromhex('6A 20 68 20'), 'Bombite2SpriteVariants / 0'),
            SpriteFrame(0x13D17, bytes.fromhex('68 00 6A 00'), 'Bombite2SpriteVariants / 1'),
            SpriteFrame(0x13D1B, bytes.fromhex('6E 00 6E 20'), 'Bombite2SpriteVariants / 2'),
            SpriteFrame(0x13D1F, bytes.fromhex('60 00 62 00'), 'Bombite2SpriteVariants / 3'),
            SpriteFrame(0x13D23, bytes.fromhex('64 00 66 00'), 'Bombite2SpriteVariants / 4'),
            SpriteFrame(0x13D27, bytes.fromhex('6C 00 6C 20'), 'Bombite2SpriteVariants / 5'),
        ),
        display_frame=0,
        fallback_palette=0,
    ),
    0x57: SpriteDefinition(  # Pairodd
        frames=(
            SpriteFrame(0x11DD1, bytes.fromhex('70 01 72 01'), 'PairoddSpriteVariants / 0'),
            SpriteFrame(0x11DD5, bytes.fromhex('72 21 70 21'), 'PairoddSpriteVariants / 1'),
            SpriteFrame(0x11DD9, bytes.fromhex('74 01 74 21'), 'PairoddSpriteVariants / 2'),
            SpriteFrame(0x11DDD, bytes.fromhex('00 00 00 00'), 'PairoddSpriteVariants / 3'),
            SpriteFrame(0x11DE1, bytes.fromhex('7A 01 7A 21'), 'PairoddSpriteVariants / 4'),
            SpriteFrame(0x11DE5, bytes.fromhex('FF 00 FF 00'), 'PairoddSpriteVariants / 5'),
            SpriteFrame(0x11DE9, bytes.fromhex('76 01 78 01'), 'PairoddSpriteVariants / 6'),
            SpriteFrame(0x11DED, bytes.fromhex('78 21 76 21'), 'PairoddSpriteVariants / 7'),
        ),
        display_frame=0,
        fallback_palette=1,
    ),
    0x58: SpriteDefinition(  # Pairodd Projectile
        frames=(
            SpriteFrame(0x11EF4, bytes.fromhex('7C 00 7C 20'), 'PairoddProjectileSpriteVariants / 0'),
            SpriteFrame(0x11EF8, bytes.fromhex('7E 00 7E 20'), 'PairoddProjectileSpriteVariants / 1'),
        ),
        display_frame=0,
        fallback_palette=0,
    ),
    0x59: None,  # Moldorm — Boss; deferred
    0x5A: None,  # Facade — Boss; deferred
    0x5B: None,  # Slime Eye — Boss; deferred
    0x5C: None,  # Genie — Boss; deferred
    0x5D: None,  # Slime Eel — Boss; deferred
    0x5E: None,  # Ghoma — Boss; deferred
    0x5F: None,  # Master Stalfos — Boss; deferred
    0x60: None,  # Dodongo Snake — Boss/miniboss; deferred
    0x61: SpriteDefinition(  # Fixed phase of the overworld four-particle orbit.
        frames=(SpriteFrame(0x64404, bytes.fromhex('3E 00'), 'Overworld warp sparkle orbit', layout='single'),),
        shared_graphics=True, overworld_only=True, draw_offset=(-2, -2),
        # Derived from 19_warp.asm's orbit tables at phase zero. The main
        # particle is (0,-2); the other three are relative to that particle.
        parts=(
            SpritePart(SpriteFrame(0x64404, bytes.fromhex('3E 00'), 'Warp sparkle / right', layout='single'), 6, 6),
            SpritePart(SpriteFrame(0x64404, bytes.fromhex('3E 00'), 'Warp sparkle / bottom', layout='single'), 0, 12),
            SpritePart(SpriteFrame(0x64404, bytes.fromhex('3E 00'), 'Warp sparkle / left', layout='single'), -6, 6),
        ),
    ),
    0x62: None,  # Hot Head — Boss; deferred
    0x63: None,  # Evil Eagle — Boss; deferred
    0x64: None,  # South Face Shrine Door — Background doorway controller; deferred
    0x65: None,  # Angler Fish — Boss; deferred
    0x66: SpriteDefinition(  # Crystal Switch
        frames=(
            SpriteFrame(0x54320, bytes.fromhex('58 03 58 23'), 'CrystalSwitchSpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0x67: None,  # Sprite 67 — Unused/unknown handler; deferred
    0x68: None,  # Hookshot Bridge — Background bridge assembly; deferred
    0x69: None,  # Moving Block Mover — Multipart moving-block mechanism; deferred
    0x6A: SpriteDefinition(  # Raft / Raft Owner
        frames=(
            SpriteFrame(0x153D4, bytes.fromhex('5C 01 5C 21'), 'RaftOwnerOnOverworldSpriteVariants / 0'),
            SpriteFrame(0x153D8, bytes.fromhex('5E 01 5E 21'), 'RaftOwnerOnOverworldSpriteVariants / 1'),
            SpriteFrame(0x1533E, bytes.fromhex('60 00 62 00'), 'RaftOwnerIndoorSpriteVariants / 0'),
            SpriteFrame(0x15342, bytes.fromhex('62 20 60 20'), 'RaftOwnerIndoorSpriteVariants / 1'),
            SpriteFrame(0x15346, bytes.fromhex('64 00 66 00'), 'RaftOwnerIndoorSpriteVariants / 2'),
            SpriteFrame(0x1534A, bytes.fromhex('66 20 64 20'), 'RaftOwnerIndoorSpriteVariants / 3'),
            SpriteFrame(0x1534E, bytes.fromhex('68 00 6A 00'), 'RaftOwnerIndoorSpriteVariants / 4'),
            SpriteFrame(0x15352, bytes.fromhex('6C 00 6E 00'), 'RaftOwnerIndoorSpriteVariants / 5'),
            SpriteFrame(0x15356, bytes.fromhex('6A 20 68 20'), 'RaftOwnerIndoorSpriteVariants / 6'),
            SpriteFrame(0x1535A, bytes.fromhex('6E 20 6C 20'), 'RaftOwnerIndoorSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x6B: None,  # Text Debugger — Debug controller; no ordinary sprite
    0x6C: SpriteDefinition(  # Cucco
        frames=(
            SpriteFrame(0x14514, bytes.fromhex('50 01 52 01'), 'CuccoSpriteVariants / 0'),
            SpriteFrame(0x14518, bytes.fromhex('54 01 56 01'), 'CuccoSpriteVariants / 1'),
            SpriteFrame(0x1451C, bytes.fromhex('52 21 50 21'), 'CuccoSpriteVariants / 2'),
            SpriteFrame(0x14520, bytes.fromhex('56 21 54 21'), 'CuccoSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x6D: SpriteDefinition(  # Bow Wow
        frames=(
            SpriteFrame(0x14000, bytes.fromhex('70 03 70 23'), 'BowWowAtHomeSpriteVariants / 0'),
            SpriteFrame(0x14004, bytes.fromhex('72 03 72 23'), 'BowWowAtHomeSpriteVariants / 1'),
            SpriteFrame(0x14008, bytes.fromhex('74 03 76 03'), 'BowWowAtHomeSpriteVariants / 2'),
            SpriteFrame(0x1400C, bytes.fromhex('78 03 7A 03'), 'BowWowAtHomeSpriteVariants / 3'),
            SpriteFrame(0x14010, bytes.fromhex('76 23 74 23'), 'BowWowAtHomeSpriteVariants / 4'),
            SpriteFrame(0x14014, bytes.fromhex('7A 23 78 23'), 'BowWowAtHomeSpriteVariants / 5'),
            SpriteFrame(0x14018, bytes.fromhex('7C 03 7C 23'), 'BowWowAtHomeSpriteVariants / 6'),
            SpriteFrame(0x1401C, bytes.fromhex('40 03 40 23'), 'BowWowFollowingSpriteVariants / 0'),
            SpriteFrame(0x14020, bytes.fromhex('42 03 42 23'), 'BowWowFollowingSpriteVariants / 1'),
            SpriteFrame(0x14024, bytes.fromhex('44 03 46 03'), 'BowWowFollowingSpriteVariants / 2'),
            SpriteFrame(0x14028, bytes.fromhex('48 03 4A 03'), 'BowWowFollowingSpriteVariants / 3'),
            SpriteFrame(0x1402C, bytes.fromhex('46 23 44 23'), 'BowWowFollowingSpriteVariants / 4'),
            SpriteFrame(0x14030, bytes.fromhex('4A 23 48 23'), 'BowWowFollowingSpriteVariants / 5'),
            SpriteFrame(0x14034, bytes.fromhex('4C 03 4C 23'), 'BowWowFollowingSpriteVariants / 6'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0x6E: SpriteDefinition(  # Butterfly
        frames=(
            SpriteFrame(0x1ABB9, bytes.fromhex('5E 01'), 'ButterflyOAMAttributes / 0', layout='single'),
            SpriteFrame(0x1ABBB, bytes.fromhex('5E 41'), 'ButterflyOAMAttributes / 1', layout='single'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
        canvas_size=(16, 16),
    ),
    0x6F: SpriteDefinition(  # Dog
        frames=(
            SpriteFrame(0x648CA, bytes.fromhex('58 01 5A 01'), 'DogSpriteVariants / 0'),
            SpriteFrame(0x648CE, bytes.fromhex('58 01 5C 01'), 'DogSpriteVariants / 1'),
            SpriteFrame(0x648D2, bytes.fromhex('5A 21 58 21'), 'DogSpriteVariants / 2'),
            SpriteFrame(0x648D6, bytes.fromhex('5C 21 58 21'), 'DogSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x70: SpriteDefinition(  # Kid 70
        frames=(
            SpriteFrame(0x1A04F, bytes.fromhex('70 00 72 00'), 'Kid71SpriteVariants / 0'),
            SpriteFrame(0x1A053, bytes.fromhex('72 20 70 20'), 'Kid71SpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0x71: SpriteDefinition(  # Kid 71
        frames=(
            SpriteFrame(0x1A04F, bytes.fromhex('70 00 72 00'), 'Kid71SpriteVariants / 0'),
            SpriteFrame(0x1A053, bytes.fromhex('72 20 70 20'), 'Kid71SpriteVariants / 1'),
            SpriteFrame(0x1A057, bytes.fromhex('74 00 76 00'), 'Kid71SpriteVariants / 2'),
            SpriteFrame(0x1A05B, bytes.fromhex('76 20 74 20'), 'Kid71SpriteVariants / 3'),
            SpriteFrame(0x1A06F, bytes.fromhex('78 02 7A 02'), 'Unknown019SpriteVariants / 0'),
            SpriteFrame(0x1A073, bytes.fromhex('7C 02 7E 02'), 'Unknown019SpriteVariants / 1'),
            SpriteFrame(0x1A077, bytes.fromhex('7A 20 78 20'), 'Unknown019SpriteVariants / 2'),
            SpriteFrame(0x1A07B, bytes.fromhex('7E 20 7C 20'), 'Unknown019SpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0x72: SpriteDefinition(  # Kid 72
        frames=(
            SpriteFrame(0x1A05F, bytes.fromhex('70 02 72 02'), 'Kid72SpriteVariants / 0'),
            SpriteFrame(0x1A063, bytes.fromhex('72 22 70 22'), 'Kid72SpriteVariants / 1'),
            SpriteFrame(0x1A067, bytes.fromhex('74 02 76 02'), 'Kid72SpriteVariants / 2'),
            SpriteFrame(0x1A06B, bytes.fromhex('76 22 74 22'), 'Kid72SpriteVariants / 3'),
            SpriteFrame(0x1A06F, bytes.fromhex('78 02 7A 02'), 'Unknown019SpriteVariants / 0'),
            SpriteFrame(0x1A073, bytes.fromhex('7C 02 7E 02'), 'Unknown019SpriteVariants / 1'),
            SpriteFrame(0x1A077, bytes.fromhex('7A 20 78 20'), 'Unknown019SpriteVariants / 2'),
            SpriteFrame(0x1A07B, bytes.fromhex('7E 20 7C 20'), 'Unknown019SpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0x73: SpriteDefinition(  # Kid 73
        frames=(
            SpriteFrame(0x1A04F, bytes.fromhex('70 00 72 00'), 'Kid71SpriteVariants / 0'),
            SpriteFrame(0x1A053, bytes.fromhex('72 20 70 20'), 'Kid71SpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0x74: SpriteDefinition(  # Papahls Wife
        frames=(
            SpriteFrame(0x60E2F, bytes.fromhex('00 F8 60 01 00 00 62 01 00 08 64 01'), 'Data_018_4E2B / 0', layout='rect'),
            SpriteFrame(0x60E3B, bytes.fromhex('00 F8 66 01 00 00 68 01 00 08 6A 01'), 'Data_018_4E2B / 1', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
        canvas_size=(32, 16),
    ),
    0x75: SpriteDefinition(  # Grandma Ulrira
        frames=(
            SpriteFrame(0x60CFF, bytes.fromhex('62 21 60 21'), 'GrandmaUlrira1SpriteVariants / 0'),
            SpriteFrame(0x60D03, bytes.fromhex('66 21 64 21'), 'GrandmaUlrira1SpriteVariants / 1'),
            SpriteFrame(0x60D07, bytes.fromhex('6C 01 6E 01'), 'GrandmaUlrira1SpriteVariants / 2'),
            SpriteFrame(0x60D0B, bytes.fromhex('68 01 6A 01'), 'GrandmaUlrira2SpriteVariants / 0'),
            SpriteFrame(0x60D0F, bytes.fromhex('6A 21 68 21'), 'GrandmaUlrira2SpriteVariants / 1'),
            SpriteFrame(0x60D13, bytes.fromhex('6C 01 6E 01'), 'GrandmaUlrira2SpriteVariants / 2'),
            SpriteFrame(0x60D17, bytes.fromhex('9A 14 9C 14'), 'GrandmaUlrira3SpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x76: SpriteDefinition(  # Mr Write
        frames=(
            SpriteFrame(0x60B19, bytes.fromhex('00 00 70 01 00 08 72 01 10 00 74 01 10 08 74 21'), 'Data_018_4B15 / 0', layout='rect'),
            SpriteFrame(0x60B29, bytes.fromhex('00 00 72 21 00 08 70 21 10 00 74 01 10 08 74 21'), 'Data_018_4B15 / 1', layout='rect'),
            SpriteFrame(0x60B39, bytes.fromhex('00 00 78 21 00 08 76 21 10 00 74 01 10 08 74 21'), 'Data_018_4B15 / 2', layout='rect'),
            SpriteFrame(0x60B49, bytes.fromhex('00 00 76 01 00 08 78 01 10 00 74 01 10 08 74 21'), 'Data_018_4B15 / 3', layout='rect'),
            SpriteFrame(0x60B59, bytes.fromhex('00 00 70 00 00 08 72 00 10 00 74 00 10 08 74 20'), 'Data_018_4B55 / 0', layout='rect'),
            SpriteFrame(0x60B69, bytes.fromhex('00 00 72 20 00 08 70 20 10 00 74 00 10 08 74 20'), 'Data_018_4B55 / 1', layout='rect'),
            SpriteFrame(0x60B79, bytes.fromhex('00 00 78 20 00 08 76 20 10 00 74 00 10 08 74 20'), 'Data_018_4B55 / 2', layout='rect'),
            SpriteFrame(0x60B89, bytes.fromhex('00 00 76 00 00 08 78 00 10 00 74 00 10 08 74 20'), 'Data_018_4B55 / 3', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
        canvas_size=(16, 32),
        draw_offset=(0, -16),
    ),
    0x77: SpriteDefinition(  # Grandpa Ulrira
        frames=(
            SpriteFrame(0x19C51, bytes.fromhex('F7 00 70 02 F7 08 72 02 07 00 74 02 07 08 76 02'), 'Data_006_5C51 / 0', layout='rect'),
            SpriteFrame(0x19C61, bytes.fromhex('F7 00 78 02 F7 08 7A 02 07 00 7C 02 07 08 7E 02'), 'Data_006_5C51 / 1', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
        canvas_size=(16, 32),
        draw_offset=(0, -16),
    ),
    0x78: SpriteDefinition(  # Yip Yip
        frames=(
            SpriteFrame(0x199A8, bytes.fromhex('70 02 72 02'), 'YipYipSpriteVariants / 0'),
            SpriteFrame(0x199AC, bytes.fromhex('74 02 76 02'), 'YipYipSpriteVariants / 1'),
            SpriteFrame(0x199B0, bytes.fromhex('72 22 70 22'), 'YipYipSpriteVariants / 2'),
            SpriteFrame(0x199B4, bytes.fromhex('76 22 74 22'), 'YipYipSpriteVariants / 3'),
            SpriteFrame(0x199B8, bytes.fromhex('00 02 02 02'), 'YipYipSpriteVariants / 4'),
            SpriteFrame(0x199BC, bytes.fromhex('04 02 06 02'), 'YipYipSpriteVariants / 5'),
            SpriteFrame(0x199C0, bytes.fromhex('02 22 00 22'), 'YipYipSpriteVariants / 6'),
            SpriteFrame(0x199C4, bytes.fromhex('06 22 04 22'), 'YipYipSpriteVariants / 7'),
            SpriteFrame(0x199C8, bytes.fromhex('78 02 7A 02'), 'YipYipWithRibbonSpriteVariants / 0'),
            SpriteFrame(0x199CC, bytes.fromhex('7C 02 7E 02'), 'YipYipWithRibbonSpriteVariants / 1'),
            SpriteFrame(0x199D0, bytes.fromhex('7A 22 78 22'), 'YipYipWithRibbonSpriteVariants / 2'),
            SpriteFrame(0x199D4, bytes.fromhex('7E 22 7C 22'), 'YipYipWithRibbonSpriteVariants / 3'),
            SpriteFrame(0x199D8, bytes.fromhex('10 02 12 02'), 'YipYipWithRibbonSpriteVariants / 4'),
            SpriteFrame(0x199DC, bytes.fromhex('14 02 16 02'), 'YipYipWithRibbonSpriteVariants / 5'),
            SpriteFrame(0x199E0, bytes.fromhex('12 22 10 22'), 'YipYipWithRibbonSpriteVariants / 6'),
            SpriteFrame(0x199E4, bytes.fromhex('16 22 14 22'), 'YipYipWithRibbonSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0x79: SpriteDefinition(  # Madam Meowmeow
        frames=(
            SpriteFrame(0x19B56, bytes.fromhex('60 01 62 01'), 'MadamMeowMeowSpriteVariants / 0'),
            SpriteFrame(0x19B5A, bytes.fromhex('62 21 60 21'), 'MadamMeowMeowSpriteVariants / 1'),
            SpriteFrame(0x19B5E, bytes.fromhex('64 01 66 01'), 'MadamMeowMeowSpriteVariants / 2'),
            SpriteFrame(0x19B62, bytes.fromhex('66 21 64 21'), 'MadamMeowMeowSpriteVariants / 3'),
            SpriteFrame(0x19B66, bytes.fromhex('68 01 6A 01'), 'MadamMeowMeowSpriteVariants / 4'),
            SpriteFrame(0x19B6A, bytes.fromhex('6C 01 6E 01'), 'MadamMeowMeowSpriteVariants / 5'),
            SpriteFrame(0x19B6E, bytes.fromhex('6A 21 68 21'), 'MadamMeowMeowSpriteVariants / 6'),
            SpriteFrame(0x19B72, bytes.fromhex('6E 21 6C 21'), 'MadamMeowMeowSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x7A: SpriteDefinition(  # Crow
        frames=(
            SpriteFrame(0x19C89, bytes.fromhex('50 03 52 03'), 'CrowSpriteVariants / 0'),
            SpriteFrame(0x19C8D, bytes.fromhex('54 03 56 03'), 'CrowSpriteVariants / 1'),
            SpriteFrame(0x19C91, bytes.fromhex('52 23 50 23'), 'CrowSpriteVariants / 2'),
            SpriteFrame(0x19C95, bytes.fromhex('56 23 54 23'), 'CrowSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0x7B: SpriteDefinition(  # Crazy Tracy
        frames=(
            SpriteFrame(0x19E65, bytes.fromhex('00 00 64 02 00 08 66 02 10 00 68 02 10 08 6A 02'), 'CrazyTracySpriteAttributes / 0', layout='rect'),
            SpriteFrame(0x19E75, bytes.fromhex('00 00 60 02 00 08 62 02 10 00 68 02 10 08 6A 02'), 'CrazyTracySpriteAttributes / 1', layout='rect'),
            SpriteFrame(0x19E85, bytes.fromhex('00 00 66 22 00 08 64 22 10 00 6A 22 10 08 68 22'), 'CrazyTracySpriteAttributes / 2', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
        canvas_size=(16, 32),
        draw_offset=(0, -16),
    ),
    0x7C: SpriteDefinition(  # Giant Goponga Flower
        frames=(
            SpriteFrame(0x1A318, bytes.fromhex('F8 F8 70 02 F8 00 72 02 F8 08 72 22 F8 10 70 22 08 F8 74 02 08 00 76 02 08 08 76 22 08 10 74 22'), 'Data_006_6316 / 0', layout='rect'),
            SpriteFrame(0x1A338, bytes.fromhex('F9 F9 70 02 F9 01 72 02 F9 07 72 22 F9 0F 70 22 07 F9 74 02 07 01 76 02 07 07 76 22 07 0F 74 22'), 'Data_006_6316 / 1', layout='rect'),
            SpriteFrame(0x1A358, bytes.fromhex('F8 F8 78 02 F8 00 7A 02 F8 08 7A 22 F8 10 78 22 08 F8 7C 02 08 00 7E 02 08 08 7E 22 08 10 7C 22'), 'Data_006_6316 / 2', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
        canvas_size=(32, 32),
        draw_offset=(0, -16),
    ),
    0x7D: None,  # Goponga Flower Projectile — Projectile uses graphics outside the mapped room slots; deferred
    0x7E: SpriteDefinition(  # Goponga Flower
        frames=(
            SpriteFrame(0x1A3F6, bytes.fromhex('50 02 50 22'), 'GopongaFlowerSpriteVariants / 0'),
            SpriteFrame(0x1A3FA, bytes.fromhex('52 02 52 22'), 'GopongaFlowerSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0x7F: SpriteDefinition(  # Six 8x16 OAM pieces per head frame.
        frames=(
            SpriteFrame(0x6359D, bytes.fromhex('F0 F8 7A 16 F0 00 7C 16 F0 08 7C 36 F0 10 7A 36 00 00 7E 16 00 08 7E 36'), 'Turtle Rock head / dormant', layout='rect'),
            SpriteFrame(0x635B5, bytes.fromhex('F0 F8 70 07 F0 00 7C 16 F0 08 7C 36 F0 10 7A 36 00 00 7E 16 00 08 7E 36'), 'Turtle Rock head / variant 1', layout='rect'),
            SpriteFrame(0x635CD, bytes.fromhex('F0 F8 70 07 F0 00 7C 16 F0 08 7C 36 F0 10 7A 36 00 00 7E 16 00 08 74 27'), 'Turtle Rock head / variant 2', layout='rect'),
            SpriteFrame(0x635E5, bytes.fromhex('F0 F8 70 07 F0 00 7C 16 F0 08 7C 36 F0 10 70 27 00 00 7E 16 00 08 74 27'), 'Turtle Rock head / variant 3', layout='rect'),
            SpriteFrame(0x635FD, bytes.fromhex('F0 F8 70 07 F0 00 7C 16 F0 08 7C 36 F0 10 70 27 00 00 74 07 00 08 74 27'), 'Turtle Rock head / variant 4', layout='rect'),
            SpriteFrame(0x63615, bytes.fromhex('F0 F8 70 07 F0 00 78 07 F0 08 7C 36 F0 10 70 27 00 00 74 07 00 08 74 27'), 'Turtle Rock head / variant 5', layout='rect'),
            SpriteFrame(0x6362D, bytes.fromhex('F0 F8 70 07 F0 00 78 07 F0 08 78 27 F0 10 70 27 00 00 74 07 00 08 74 27'), 'Turtle Rock head / variant 6', layout='rect'),
            SpriteFrame(0x63645, bytes.fromhex('F0 F8 70 07 F0 00 78 07 F0 08 78 27 F0 10 70 27 00 00 74 07 00 08 74 27'), 'Turtle Rock head / variant 7', layout='rect'),
            SpriteFrame(0x6365D, bytes.fromhex('F0 F8 70 07 F0 00 72 07 F0 08 72 27 F0 10 70 27 00 00 74 07 00 08 74 27'), 'Turtle Rock head / variant 8', layout='rect'),
        ), required_slot=3, fallback_palette=7, overworld_only=True,
        draw_offset=(-8, -16),
        # Runtime neck extension and flying debris are separate event effects.
    ),
    0x80: SpriteDefinition(  # Telephone
        frames=(
            SpriteFrame(0x1AA74, bytes.fromhex('50 02 52 02'), 'TelephoneSpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
        draw_offset=(0, -5),
    ),
    0x81: None,  # Rolling Bones — Boss/miniboss; deferred
    0x82: None,  # Rolling Bones Bar — Boss mechanism; deferred
    0x83: None,  # Dream Shrine Bed — Dream transition controller; background bed is not sprite artwork
    0x84: SpriteDefinition(  # Big Fairy: 24×32 artwork in a 32×32 canvas
        frames=(
            SpriteFrame(0x1B06D, bytes.fromhex('F0 FC 50 01 F0 04 52 01 F0 0C 54 01 00 FC 56 01 00 04 58 01 00 0C 5A 01'), 'Big Fairy / 0', layout='rect'),
            SpriteFrame(0x1B085, bytes.fromhex('F0 FC 50 01 F0 04 52 01 F0 0C 54 01 00 FC 5C 01 00 04 58 01 00 0C 5E 01'), 'Big Fairy / 1', layout='rect'),
        ),
        display_frame=0,
        fallback_palette=1,
        canvas_size=(32, 32),
        draw_offset=(0, -16),  # Bottom-left 16×16 tile is the placement cell.
    ),
    0x85: SpriteDefinition(  # Mr Writes Bird
        frames=(
            SpriteFrame(0x1B208, bytes.fromhex('68 01 6A 01'), 'MrWriteSpriteVariants / 0'),
            SpriteFrame(0x1B20C, bytes.fromhex('64 01 66 01'), 'MrWriteSpriteVariants / 1'),
            SpriteFrame(0x1B210, bytes.fromhex('6C 01 6E 01'), 'MrWriteSpriteVariants / 2'),
            SpriteFrame(0x1B214, bytes.fromhex('6A 21 68 21'), 'MrWriteSpriteVariants / 3'),
            SpriteFrame(0x1B218, bytes.fromhex('66 21 64 21'), 'MrWriteSpriteVariants / 4'),
            SpriteFrame(0x1B21C, bytes.fromhex('6E 21 6C 21'), 'MrWriteSpriteVariants / 5'),
            SpriteFrame(0x1B220, bytes.fromhex('68 00 6A 00'), 'MrWriteBirdChristineHouseSpriteVariants / 0'),
            SpriteFrame(0x1B224, bytes.fromhex('64 00 66 00'), 'MrWriteBirdChristineHouseSpriteVariants / 1'),
            SpriteFrame(0x1B228, bytes.fromhex('6C 00 6E 00'), 'MrWriteBirdChristineHouseSpriteVariants / 2'),
            SpriteFrame(0x1B22C, bytes.fromhex('6A 20 68 20'), 'MrWriteBirdChristineHouseSpriteVariants / 3'),
            SpriteFrame(0x1B230, bytes.fromhex('66 20 64 20'), 'MrWriteBirdChristineHouseSpriteVariants / 4'),
            SpriteFrame(0x1B234, bytes.fromhex('6E 20 6C 20'), 'MrWriteBirdChristineHouseSpriteVariants / 5'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x86: SpriteDefinition(
        frames=(
            SpriteFrame(0x1BAD9, bytes.fromhex('A6 15'), 'Floating item / 10 Rupees', layout='single'),
            SpriteFrame(0x1BADB, bytes.fromhex('8E 16'), 'Floating item / Magic Powder', layout='single'),
            SpriteFrame(0x1BADD, bytes.fromhex('80 15'), 'Floating item / Bombs', layout='single'),
            SpriteFrame(0x1BADF, bytes.fromhex('A6 15'), 'Floating item / 10 Rupees', layout='single'),
        ), shared_graphics=True, overworld_only=True, draw_offset=(-4, -15),
        # First normal-room hover phase is Z=15. Contents and wings share it.
        parts=(SpritePart(SpriteFrame(0x1BAE7, bytes.fromhex('00 FC 22 00 00 0C 22 20'), 'Floating item wings / down', layout='rect')),),
    ),
    0x87: SpriteDefinition(  # Fixed downward emerged pose, head at placement.
        frames=(SpriteFrame(0x198A7, bytes.fromhex('70 03 70 23'), 'Desert Lanmola / static emerged pose', layout='pair'),),
        required_slot=3, fallback_palette=3, overworld_only=True,
        draw_offset=(0, -72),
        # The game uses six history delays (12,24,36,48,60,72 frames) and
        # alternates which segments it draws each video frame. Show the full
        # body in a straight editor pose: five middle sections and one tail.
        parts=(
            SpritePart(SpriteFrame(0x198AF, bytes.fromhex('76 03 76 23'), 'Desert Lanmola body', layout='pair'), 0, -12),
            SpritePart(SpriteFrame(0x198AF, bytes.fromhex('76 03 76 23'), 'Desert Lanmola body', layout='pair'), 0, -24),
            SpritePart(SpriteFrame(0x198AF, bytes.fromhex('76 03 76 23'), 'Desert Lanmola body', layout='pair'), 0, -36),
            SpritePart(SpriteFrame(0x198AF, bytes.fromhex('76 03 76 23'), 'Desert Lanmola body', layout='pair'), 0, -48),
            SpritePart(SpriteFrame(0x198AF, bytes.fromhex('76 03 76 23'), 'Desert Lanmola body', layout='pair'), 0, -60),
            SpritePart(SpriteFrame(0x198BB, bytes.fromhex('78 03 78 63'), 'Desert Lanmola tail', layout='pair'), 0, -72),
        ),
    ),
    0x88: None,  # Armos Knight — Boss/miniboss; deferred
    0x89: None,  # Hinox — Boss/miniboss; deferred
    0x8A: None,  # Tile Glint Shown — Glint effect uses unmapped global sprite tiles; deferred
    0x8B: None,  # Tile Glint Hidden — Glint effect uses unmapped global sprite tiles; deferred
    0x8C: None,  # Raisable Block Shifted Right — Unused mechanism uses unmapped runtime tiles; deferred
    0x8D: None,  # Raisable Block Shifted Down — Unused mechanism uses unmapped runtime tiles; deferred
    0x8E: None,  # Cue Ball — Boss/miniboss; deferred
    0x8F: SpriteDefinition(  # Masked Mimic / Goriya
        frames=(
            SpriteFrame(0x64796, bytes.fromhex('6A 22 68 22'), 'MaskedMimicGoriyaSpriteVariants / 0'),
            SpriteFrame(0x6479A, bytes.fromhex('6E 22 6C 22'), 'MaskedMimicGoriyaSpriteVariants / 1'),
            SpriteFrame(0x6479E, bytes.fromhex('68 02 6A 02'), 'MaskedMimicGoriyaSpriteVariants / 2'),
            SpriteFrame(0x647A2, bytes.fromhex('6C 02 6E 02'), 'MaskedMimicGoriyaSpriteVariants / 3'),
            SpriteFrame(0x647A6, bytes.fromhex('64 02 66 02'), 'MaskedMimicGoriyaSpriteVariants / 4'),
            SpriteFrame(0x647AA, bytes.fromhex('66 22 64 22'), 'MaskedMimicGoriyaSpriteVariants / 5'),
            SpriteFrame(0x647AE, bytes.fromhex('60 02 62 02'), 'MaskedMimicGoriyaSpriteVariants / 6'),
            SpriteFrame(0x647B2, bytes.fromhex('62 22 60 22'), 'MaskedMimicGoriyaSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0x90: SpriteDefinition(  # Three Of A Kind
        frames=(
            SpriteFrame(0x18911, bytes.fromhex('74 02 76 02'), 'ThreeOfAKindSpriteVariants / 0'),
            SpriteFrame(0x18915, bytes.fromhex('76 22 74 22'), 'ThreeOfAKindSpriteVariants / 1'),
            SpriteFrame(0x18919, bytes.fromhex('70 01 72 01'), 'ThreeOfAKindSpriteVariants / 2'),
            SpriteFrame(0x1891D, bytes.fromhex('72 21 70 21'), 'ThreeOfAKindSpriteVariants / 3'),
            SpriteFrame(0x18921, bytes.fromhex('78 00 7A 00'), 'ThreeOfAKindSpriteVariants / 4'),
            SpriteFrame(0x18925, bytes.fromhex('7A 20 78 20'), 'ThreeOfAKindSpriteVariants / 5'),
            SpriteFrame(0x18929, bytes.fromhex('7C 03 7E 03'), 'ThreeOfAKindSpriteVariants / 6'),
            SpriteFrame(0x1892D, bytes.fromhex('7E 23 7C 23'), 'ThreeOfAKindSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0x91: SpriteDefinition(  # Anti Kirby
        frames=(
            SpriteFrame(0x18436, bytes.fromhex('62 21 60 21'), 'AntiKirbySpriteVariants / 0'),
            SpriteFrame(0x1843A, bytes.fromhex('68 21 66 21'), 'AntiKirbySpriteVariants / 1'),
            SpriteFrame(0x1843E, bytes.fromhex('60 01 62 01'), 'AntiKirbySpriteVariants / 2'),
            SpriteFrame(0x18442, bytes.fromhex('66 01 68 01'), 'AntiKirbySpriteVariants / 3'),
            SpriteFrame(0x18446, bytes.fromhex('62 21 60 21'), 'AntiKirbySpriteVariants / 4'),
            SpriteFrame(0x1844A, bytes.fromhex('68 21 66 21'), 'AntiKirbySpriteVariants / 5'),
            SpriteFrame(0x1844E, bytes.fromhex('60 01 62 01'), 'AntiKirbySpriteVariants / 6'),
            SpriteFrame(0x18452, bytes.fromhex('66 01 68 01'), 'AntiKirbySpriteVariants / 7'),
            SpriteFrame(0x18456, bytes.fromhex('00 FC 62 21 00 04 6A 21 00 0C 64 21'), 'Data_006_4456 / 0', layout='rect'),
            SpriteFrame(0x18462, bytes.fromhex('00 FC 64 01 00 04 6A 01 00 0C 62 01'), 'Data_006_4456 / 1', layout='rect'),
            SpriteFrame(0x1846E, bytes.fromhex('00 FC 62 21 00 04 6A 21 00 0C 64 21'), 'Data_006_4456 / 2', layout='rect'),
            SpriteFrame(0x1847A, bytes.fromhex('00 FC 64 01 00 04 6A 01 00 0C 62 01'), 'Data_006_4456 / 3', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x92: None,  # Smasher — Boss/miniboss; deferred
    0x93: SpriteDefinition(  # Mad Bomber
        frames=(
            SpriteFrame(0x18126, bytes.fromhex('FF 00 FF 20'), 'MadBomberSpriteVariants / 0'),
            SpriteFrame(0x1812A, bytes.fromhex('70 02 70 22'), 'MadBomberSpriteVariants / 1'),
            SpriteFrame(0x1812E, bytes.fromhex('72 02 72 22'), 'MadBomberSpriteVariants / 2'),
            SpriteFrame(0x18132, bytes.fromhex('74 02 76 02'), 'MadBomberSpriteVariants / 3'),
            SpriteFrame(0x18136, bytes.fromhex('76 22 74 22'), 'MadBomberSpriteVariants / 4'),
        ),
        display_frame=3,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0x94: None,  # Kanalet Bombable Wall — Background wall controller; deferred
    0x95: SpriteDefinition(  # Richard
        frames=(
            SpriteFrame(0x18000, bytes.fromhex('50 03 52 03'), 'RichardSpriteVariants / 0'),
            SpriteFrame(0x18004, bytes.fromhex('54 03 56 03'), 'RichardSpriteVariants / 1'),
            SpriteFrame(0x18008, bytes.fromhex('50 03 52 03'), 'RichardSpriteVariants / 2'),
            SpriteFrame(0x1800C, bytes.fromhex('54 03 56 03'), 'RichardSpriteVariants / 3'),
            SpriteFrame(0x18010, bytes.fromhex('58 03 5A 03'), 'RichardSpriteVariants / 4'),
            SpriteFrame(0x18014, bytes.fromhex('5C 03 5E 03'), 'RichardSpriteVariants / 5'),
            SpriteFrame(0x18018, bytes.fromhex('5A 23 58 23'), 'RichardSpriteVariants / 6'),
            SpriteFrame(0x1801C, bytes.fromhex('5E 23 5C 23'), 'RichardSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0x96: SpriteDefinition(  # Richard Frog
        frames=(
            SpriteFrame(0x65BA0, bytes.fromhex('64 00 64 20'), 'RichardFrogSpriteVariants / 0'),
            SpriteFrame(0x65BA4, bytes.fromhex('66 00 66 20'), 'RichardFrogSpriteVariants / 1'),
            SpriteFrame(0x65BA8, bytes.fromhex('60 00 60 20'), 'RichardFrogSpriteVariants / 2'),
            SpriteFrame(0x65BAC, bytes.fromhex('62 00 62 20'), 'RichardFrogSpriteVariants / 3'),
            SpriteFrame(0x65BB0, bytes.fromhex('68 00 6A 00'), 'RichardFrogSpriteVariants / 4'),
            SpriteFrame(0x65BB4, bytes.fromhex('6C 00 6E 00'), 'RichardFrogSpriteVariants / 5'),
            SpriteFrame(0x65BB8, bytes.fromhex('6A 20 68 20'), 'RichardFrogSpriteVariants / 6'),
            SpriteFrame(0x65BBC, bytes.fromhex('6E 20 6C 20'), 'RichardFrogSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0x97: None,  # Invisible diving warp trigger; see SPRITE_CONTROLLER_NOTES.
    0x98: SpriteDefinition(  # Horse Piece
        frames=(
            SpriteFrame(0x1F61A, bytes.fromhex('60 03 62 03'), 'HorsePieceSpriteVariants / 0'),
            SpriteFrame(0x1F61E, bytes.fromhex('64 03 66 03'), 'HorsePieceSpriteVariants / 1'),
            SpriteFrame(0x1F622, bytes.fromhex('62 63 60 63'), 'HorsePieceSpriteVariants / 2'),
            SpriteFrame(0x1F626, bytes.fromhex('66 63 64 63'), 'HorsePieceSpriteVariants / 3'),
            SpriteFrame(0x1F62A, bytes.fromhex('66 23 64 23'), 'HorsePieceSpriteVariants / 4'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0x99: SpriteDefinition(  # Water Tektite
        frames=(
            SpriteFrame(0x1F569, bytes.fromhex('70 00 70 20'), 'WaterTektiteSpriteVariants / 0'),
            SpriteFrame(0x1F56D, bytes.fromhex('72 00 72 20'), 'WaterTektiteSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0x9A: None,  # Flying Tiles — Spawner uses background tiles; deferred
    0x9B: SpriteDefinition(  # Hiding Zol
        frames=(
            SpriteFrame(0x1F2D7, bytes.fromhex('FF FF FF FF'), 'HidingZol2SpriteVariants / 0'),
            SpriteFrame(0x1F2DB, bytes.fromhex('FF FF FF FF'), 'HidingZol2SpriteVariants / 1'),
            SpriteFrame(0x1F2DF, bytes.fromhex('54 00 54 20'), 'HidingZol2SpriteVariants / 2'),
            SpriteFrame(0x1F2E3, bytes.fromhex('52 00 52 20'), 'HidingZol2SpriteVariants / 3'),
            SpriteFrame(0x1F2E7, bytes.fromhex('56 00'), 'HidingZol1SpriteVariants / 0', layout='single'),
            SpriteFrame(0x1F2E9, bytes.fromhex('56 00'), 'HidingZol1SpriteVariants / 1', layout='single'),
        ),
        display_frame=3,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
        canvas_size=(16, 16),
    ),
    0x9C: SpriteDefinition(  # Star
        frames=(
            SpriteFrame(0x1F283, bytes.fromhex('74 01 74 21'), 'StarSpriteVariants / 0'),
            SpriteFrame(0x1F287, bytes.fromhex('76 01 78 01'), 'StarSpriteVariants / 1'),
            SpriteFrame(0x1F28B, bytes.fromhex('7A 01 7A 21'), 'StarSpriteVariants / 2'),
            SpriteFrame(0x1F28F, bytes.fromhex('78 21 76 21'), 'StarSpriteVariants / 3'),
            SpriteFrame(0x1F293, bytes.fromhex('7C 01 7C 01'), 'StarSpriteVariants / 4'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0x9D: SpriteDefinition(  # Liftable Statue
        frames=(
            SpriteFrame(0x64000, bytes.fromhex('F0 00 48 06 F0 08 48 26 00 00 4A 06 00 08 4A 26'), 'LiftableStatueSpriteRect / 0', layout='rect'),
            SpriteFrame(0x64010, bytes.fromhex('F0 00 78 06 F0 08 78 26 00 00 7A 06 00 08 7A 26'), 'LiftableStatueSpriteRect_BottleGrotto / 0', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=6,
        canvas_size=(16, 32),
        draw_offset=(0, -16),
    ),
    0x9E: None,  # Fireball Shooter — Invisible fireball spawning controller
    0x9F: SpriteDefinition(  # Goomba
        frames=(
            SpriteFrame(0x1E60A, bytes.fromhex('4A 02 4C 02'), 'GoombaSpriteVariants / 0'),
            SpriteFrame(0x1E60E, bytes.fromhex('4C 22 4A 22'), 'GoombaSpriteVariants / 1'),
            SpriteFrame(0x1E612, bytes.fromhex('4E 02 4E 22'), 'GoombaSpriteVariants / 2'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xA0: SpriteDefinition(  # Peahat
        frames=(
            SpriteFrame(0x1E73D, bytes.fromhex('40 02 40 22'), 'PeaHatSpriteVariants / 0'),
            SpriteFrame(0x1E741, bytes.fromhex('42 02 42 22'), 'PeaHatSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xA1: SpriteDefinition(  # Snake
        frames=(
            SpriteFrame(0x1E87A, bytes.fromhex('44 03 46 03'), 'SnakeSpriteVariants / 0'),
            SpriteFrame(0x1E87E, bytes.fromhex('44 03 48 03'), 'SnakeSpriteVariants / 1'),
            SpriteFrame(0x1E882, bytes.fromhex('46 23 44 23'), 'SnakeSpriteVariants / 2'),
            SpriteFrame(0x1E886, bytes.fromhex('48 23 44 23'), 'SnakeSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0xA2: SpriteDefinition(  # Piranha Plant
        frames=(
            SpriteFrame(0xDAFD9, bytes.fromhex('FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF'), 'Data_036_6FC2 / 0', layout='rect'),
            SpriteFrame(0xDAFE9, bytes.fromhex('F0 00 74 02 F0 08 74 22 FF FF FF FF FF FF FF FF'), 'Data_036_6FC2 / 1', layout='rect'),
            SpriteFrame(0xDAFF9, bytes.fromhex('00 00 70 02 00 08 70 22 FF FF FF FF FF FF FF FF'), 'Data_036_6FC2 / 2', layout='rect'),
            SpriteFrame(0xDB009, bytes.fromhex('00 00 70 02 00 08 70 22 08 00 76 00 08 08 76 20'), 'Data_036_6FC2 / 3', layout='rect'),
            SpriteFrame(0xDB019, bytes.fromhex('00 00 70 02 00 08 70 22 10 00 72 00 10 08 72 20'), 'Data_036_6FC2 / 4', layout='rect'),
            SpriteFrame(0xDB029, bytes.fromhex('00 00 78 02 00 08 78 22 10 00 72 00 10 08 72 20'), 'Data_036_6FC2 / 5', layout='rect'),
        ),
        display_frame=4,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
        canvas_size=(16, 32),
        draw_offset=(0, -16),
    ),
    0xA3: SpriteDefinition(  # Side View Platform Horizontal
        frames=(
            SpriteFrame(0x1E363, bytes.fromhex('00 00 50 07 00 08 52 07 00 10 52 27 00 18 50 27'), 'Data_007_6348 / 0', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=7,
    ),
    0xA4: SpriteDefinition(  # Side View Platform Vertical
        frames=(
            SpriteFrame(0x1E363, bytes.fromhex('00 00 50 07 00 08 52 07 00 10 52 27 00 18 50 27'), 'Data_007_6348 / 0', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=7,
    ),
    0xA5: SpriteDefinition(  # Side View Platform
        frames=(
            SpriteFrame(0x1E43D, bytes.fromhex('00 00 50 07 00 08 52 07 00 10 52 27 00 18 50 27'), 'Data_007_6422 / 0', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=7,
    ),
    0xA6: SpriteDefinition(  # Side View Weights
        frames=(
            SpriteFrame(0x1E1E9, bytes.fromhex('50 07 50 27'), 'SideViewWeightsSpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=7,
    ),
    0xA7: None,  # Smashable Pillar — Specialized collapsing pillar renderer; deferred
    0xA8: SpriteDefinition(  # Wrecking Ball
        frames=(
            SpriteFrame(0x1E003, bytes.fromhex('4E 00 4E 20'), 'WreckingBallSprite / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0xA9: SpriteDefinition(  # Blooper
        frames=(
            SpriteFrame(0x1DBF1, bytes.fromhex('6A 00 6A 20'), 'BlooperSpriteVariants / 0'),
            SpriteFrame(0x1DBF5, bytes.fromhex('68 00 68 20'), 'BlooperSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0xAA: SpriteDefinition(  # Cheep Cheep Horizontal
        frames=(
            SpriteFrame(0x66B4A, bytes.fromhex('60 01 62 01'), 'CheepCheepSpriteVariants / 0'),
            SpriteFrame(0x66B4E, bytes.fromhex('64 01 66 01'), 'CheepCheepSpriteVariants / 1'),
            SpriteFrame(0x66B52, bytes.fromhex('62 21 60 21'), 'CheepCheepSpriteVariants / 2'),
            SpriteFrame(0x66B56, bytes.fromhex('66 21 64 21'), 'CheepCheepSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xAB: SpriteDefinition(  # Cheep Cheep Vertical
        frames=(
            SpriteFrame(0x66B4A, bytes.fromhex('60 01 62 01'), 'CheepCheepSpriteVariants / 0'),
            SpriteFrame(0x66B4E, bytes.fromhex('64 01 66 01'), 'CheepCheepSpriteVariants / 1'),
            SpriteFrame(0x66B52, bytes.fromhex('62 21 60 21'), 'CheepCheepSpriteVariants / 2'),
            SpriteFrame(0x66B56, bytes.fromhex('66 21 64 21'), 'CheepCheepSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xAC: SpriteDefinition(  # Cheep Cheep Jumping
        frames=(
            SpriteFrame(0x66B4A, bytes.fromhex('60 01 62 01'), 'CheepCheepSpriteVariants / 0'),
            SpriteFrame(0x66B4E, bytes.fromhex('64 01 66 01'), 'CheepCheepSpriteVariants / 1'),
            SpriteFrame(0x66B52, bytes.fromhex('62 21 60 21'), 'CheepCheepSpriteVariants / 2'),
            SpriteFrame(0x66B56, bytes.fromhex('66 21 64 21'), 'CheepCheepSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xAD: SpriteDefinition(  # Kiki The Monkey
        frames=(
            SpriteFrame(0x1D81A, bytes.fromhex('78 02 72 02'), 'KikiTheMonkey2SpriteVariants / 0'),
            SpriteFrame(0x1D81E, bytes.fromhex('7A 02 72 02'), 'KikiTheMonkey2SpriteVariants / 1'),
            SpriteFrame(0x1D822, bytes.fromhex('70 02 72 02'), 'KikiTheMonkey2SpriteVariants / 2'),
            SpriteFrame(0x1D826, bytes.fromhex('7C 02 7E 02'), 'KikiTheMonkey2SpriteVariants / 3'),
            SpriteFrame(0x1D82A, bytes.fromhex('74 02 76 02'), 'KikiTheMonkey2SpriteVariants / 4'),
            SpriteFrame(0x1D82E, bytes.fromhex('72 22 78 22'), 'KikiTheMonkey1SpriteVariants / 0'),
            SpriteFrame(0x1D832, bytes.fromhex('72 22 7A 22'), 'KikiTheMonkey1SpriteVariants / 1'),
            SpriteFrame(0x1D836, bytes.fromhex('72 22 70 22'), 'KikiTheMonkey1SpriteVariants / 2'),
            SpriteFrame(0x1D83A, bytes.fromhex('7E 22 7C 22'), 'KikiTheMonkey1SpriteVariants / 3'),
            SpriteFrame(0x1D83E, bytes.fromhex('76 22 74 22'), 'KikiTheMonkey1SpriteVariants / 4'),
            SpriteFrame(0x1D94D, bytes.fromhex('9A 17 9C 17'), 'KikiTheMonkey3SpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xAE: SpriteDefinition(  # Body plus global wing tiles at their OAM positions.
        frames=(
            SpriteFrame(0x1D62D, bytes.fromhex('50 02 50 22'), 'Winged Octorok body / 0', layout='pair'),
            SpriteFrame(0x1D631, bytes.fromhex('52 02 52 22'), 'Winged Octorok body / 1', layout='pair'),
            SpriteFrame(0x1D635, bytes.fromhex('50 42 50 62'), 'Winged Octorok body / 2', layout='pair'),
            SpriteFrame(0x1D639, bytes.fromhex('52 42 52 62'), 'Winged Octorok body / 3', layout='pair'),
            SpriteFrame(0x1D63D, bytes.fromhex('54 02 56 02'), 'Winged Octorok body / 4', layout='pair'),
            SpriteFrame(0x1D641, bytes.fromhex('58 02 5A 02'), 'Winged Octorok body / 5', layout='pair'),
            SpriteFrame(0x1D645, bytes.fromhex('56 22 54 22'), 'Winged Octorok body / 6', layout='pair'),
            SpriteFrame(0x1D649, bytes.fromhex('5A 22 58 22'), 'Winged Octorok body / 7', layout='pair'),
        ), required_slot=1, shared_graphics=True, fallback_palette=2,
        draw_offset=(-4, 0),
        parts=(SpritePart(SpriteFrame(0x1D7F5, bytes.fromhex('00 FC 22 40 00 0C 22 60'), 'Winged Octorok wings / raised', layout='rect')),),
    ),
    0xAF: SpriteDefinition(  # Trading Item
        frames=(
            SpriteFrame(0x1D4D4, bytes.fromhex('74 00 76 00'), 'TradingItem2SpriteVariants / 0'),
            SpriteFrame(0x1D4D0, bytes.fromhex('9A 16 9C 16'), 'TradingItem1SpriteVariants / 0'),
            SpriteFrame(0x1D4D8, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 0'),
            SpriteFrame(0x1D4DC, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 1'),
            SpriteFrame(0x1D4E0, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 2'),
            SpriteFrame(0x1D4E4, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 3'),
            SpriteFrame(0x1D4E8, bytes.fromhex('9A 14 9C 14'), 'TradingItem3SpriteVariants / 4'),
            SpriteFrame(0x1D4EC, bytes.fromhex('9A 14 9C 14'), 'TradingItem3SpriteVariants / 5'),
            SpriteFrame(0x1D4F0, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 6'),
            SpriteFrame(0x1D4F4, bytes.fromhex('9A 14 9C 14'), 'TradingItem3SpriteVariants / 7'),
            SpriteFrame(0x1D4F8, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 8'),
            SpriteFrame(0x1D4FC, bytes.fromhex('9A 16 9C 16'), 'TradingItem3SpriteVariants / 9'),
            SpriteFrame(0x1D500, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 10'),
            SpriteFrame(0x1D504, bytes.fromhex('9A 16 9C 16'), 'TradingItem3SpriteVariants / 11'),
            SpriteFrame(0x1D508, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 12'),
            SpriteFrame(0x1D50C, bytes.fromhex('9A 17 9C 17'), 'TradingItem3SpriteVariants / 13'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0xB0: SpriteDefinition(  # Pincer
        frames=(
            SpriteFrame(0x1D42B, bytes.fromhex('FF 00 FF 20'), 'PincerSpriteVariants / 0'),
            SpriteFrame(0x1D42F, bytes.fromhex('6C 02 6C 22'), 'PincerSpriteVariants / 1'),
            SpriteFrame(0x1D433, bytes.fromhex('64 22 62 22'), 'PincerSpriteVariants / 2'),
            SpriteFrame(0x1D437, bytes.fromhex('68 22 66 22'), 'PincerSpriteVariants / 3'),
            SpriteFrame(0x1D43B, bytes.fromhex('60 02 60 22'), 'PincerSpriteVariants / 4'),
            SpriteFrame(0x1D43F, bytes.fromhex('66 02 68 02'), 'PincerSpriteVariants / 5'),
            SpriteFrame(0x1D443, bytes.fromhex('62 02 64 02'), 'PincerSpriteVariants / 6'),
            SpriteFrame(0x1D447, bytes.fromhex('66 42 68 42'), 'PincerSpriteVariants / 7'),
            SpriteFrame(0x1D44B, bytes.fromhex('60 42 60 62'), 'PincerSpriteVariants / 8'),
            SpriteFrame(0x1D44F, bytes.fromhex('68 62 66 62'), 'PincerSpriteVariants / 9'),
        ),
        display_frame=1,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xB1: SpriteDefinition(  # Hole Filler
        frames=(
            SpriteFrame(0x1D104, bytes.fromhex('40 02 40 22'), 'HoleFillerSpriteVariants / 0'),
            SpriteFrame(0x1D108, bytes.fromhex('42 02 42 22'), 'HoleFillerSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xB2: SpriteDefinition(  # Explicit selector frames show the spawned child.
        frames=(
            SpriteFrame(0x57579, bytes.fromhex('70 00 72 00'), 'Spawned beetle / 0'),
            SpriteFrame(0x5757D, bytes.fromhex('72 20 70 20'), 'Spawned beetle / 1'),
        ), required_slot=3,
    ),
    0xB3: SpriteDefinition(  # Honeycomb
        frames=(
            SpriteFrame(0x1CC93, bytes.fromhex('70 01 70 21'), 'HoneycombSpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xB4: SpriteDefinition(  # Tarin Beekeeper
        frames=(
            SpriteFrame(0x1CE8D, bytes.fromhex('5A 22 58 22'), 'TarinBeekeeperSpriteVariants / 0'),
            SpriteFrame(0x1CE91, bytes.fromhex('5E 22 5C 22'), 'TarinBeekeeperSpriteVariants / 1'),
            SpriteFrame(0x1CE95, bytes.fromhex('58 02 5A 02'), 'TarinBeekeeperSpriteVariants / 2'),
            SpriteFrame(0x1CE99, bytes.fromhex('5C 02 5E 02'), 'TarinBeekeeperSpriteVariants / 3'),
            SpriteFrame(0x1CE9D, bytes.fromhex('54 02 56 02'), 'TarinBeekeeperSpriteVariants / 4'),
            SpriteFrame(0x1CEA1, bytes.fromhex('56 22 54 22'), 'TarinBeekeeperSpriteVariants / 5'),
            SpriteFrame(0x1CEA5, bytes.fromhex('50 02 52 02'), 'TarinBeekeeperSpriteVariants / 6'),
            SpriteFrame(0x1CEA9, bytes.fromhex('52 22 50 22'), 'TarinBeekeeperSpriteVariants / 7'),
            SpriteFrame(0x1CEAD, bytes.fromhex('74 02 76 02'), 'TarinBeekeeperSpriteVariants / 8'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xB5: SpriteDefinition(  # Bear
        frames=(
            SpriteFrame(0x1CB6B, bytes.fromhex('FA 00 70 03 FA 08 72 03 FA 10 74 03 FA 18 70 23 0A 00 76 03 0A 08 78 03 0A 10 78 23 0A 18 76 23'), 'Data_007_4B6B / 0', layout='rect'),
            SpriteFrame(0x1CB8B, bytes.fromhex('FA 00 70 03 FA 08 74 23 FA 10 72 23 FA 18 70 23 0A 00 76 03 0A 08 78 03 0A 10 78 23 0A 18 76 23'), 'Data_007_4B8B / 0', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
        canvas_size=(32, 32),
        draw_offset=(0, -16),
    ),
    0xB6: SpriteDefinition(  # Papahl
        frames=(
            SpriteFrame(0x1C9F7, bytes.fromhex('70 00 72 01'), 'PapahlDirectionSpriteVariants / 0'),
            SpriteFrame(0x1C9FB, bytes.fromhex('74 00 76 01'), 'PapahlDirectionSpriteVariants / 1'),
            SpriteFrame(0x1C9FF, bytes.fromhex('78 00 7A 01'), 'PapahlDirectionSpriteVariants / 2'),
            SpriteFrame(0x1CA03, bytes.fromhex('7C 00 76 01'), 'PapahlDirectionSpriteVariants / 3'),
            SpriteFrame(0x1CA07, bytes.fromhex('72 20 70 21'), 'Papahl2SpriteVariants / 0'),
            SpriteFrame(0x1CA0B, bytes.fromhex('76 20 74 21'), 'Papahl2SpriteVariants / 1'),
            SpriteFrame(0x1CA0F, bytes.fromhex('7A 20 78 21'), 'Papahl2SpriteVariants / 2'),
            SpriteFrame(0x1CA13, bytes.fromhex('76 20 7C 21'), 'Papahl2SpriteVariants / 3'),
            SpriteFrame(0x1C9EF, bytes.fromhex('6E 20 6C 20'), 'Papahl1SpriteVariants / 0'),
            SpriteFrame(0x1C9F3, bytes.fromhex('6C 00 6E 00'), 'Papahl1SpriteVariants / 1'),
            SpriteFrame(0x1CA17, bytes.fromhex('7E 01 7E 21'), 'Papahl4SpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0xB7: SpriteDefinition(  # Mermaid
        frames=(
            SpriteFrame(0x1C683, bytes.fromhex('72 21 70 21'), 'Mermaid1SpriteVariants / 0'),
            SpriteFrame(0x1C687, bytes.fromhex('70 01 72 01'), 'Mermaid1SpriteVariants / 1'),
            SpriteFrame(0x1C68B, bytes.fromhex('76 01 78 01'), 'Mermaid1SpriteVariants / 2'),
            SpriteFrame(0x1C68F, bytes.fromhex('78 21 76 21'), 'Mermaid1SpriteVariants / 3'),
            SpriteFrame(0x1C69B, bytes.fromhex('00 FC 7A 01 00 04 7C 01 00 0C 7E 01'), 'Data_007_469B / 0', layout='rect'),
            SpriteFrame(0x1C6A7, bytes.fromhex('00 FC 7E 21 00 04 7C 21 00 0C 7A 21'), 'Data_007_469B / 1', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xB8: None,  # Fisherman Under Bridge — Multipart fishing scene with spawned props; deferred
    0xB9: SpriteDefinition(  # Buzz Blob
        frames=(
            SpriteFrame(0x63738, bytes.fromhex('62 00 64 00'), 'BuzzBlobSpriteVariants / 0'),
            SpriteFrame(0x6373C, bytes.fromhex('60 00 60 20'), 'BuzzBlobSpriteVariants / 1'),
            SpriteFrame(0x63740, bytes.fromhex('64 20 62 20'), 'BuzzBlobSpriteVariants / 2'),
            SpriteFrame(0x63744, bytes.fromhex('66 00 68 00'), 'BuzzBlobSpriteVariants / 3'),
            SpriteFrame(0x63748, bytes.fromhex('60 00 60 20'), 'BuzzBlobSpriteVariants / 4'),
            SpriteFrame(0x6374C, bytes.fromhex('68 20 66 20'), 'BuzzBlobSpriteVariants / 5'),
            SpriteFrame(0x63750, bytes.fromhex('6C 00 6E 00'), 'BuzzBlobSpriteVariants / 6'),
            SpriteFrame(0x63754, bytes.fromhex('6A 00 6A 20'), 'BuzzBlobSpriteVariants / 7'),
            SpriteFrame(0x63758, bytes.fromhex('6E 20 6C 20'), 'BuzzBlobSpriteVariants / 8'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0xBA: SpriteDefinition(  # Bomber
        frames=(
            SpriteFrame(0x637FC, bytes.fromhex('00 FC 70 02 00 04 72 02 00 0C 70 22'), 'Data_018_77ED / 0', layout='rect'),
            SpriteFrame(0x63808, bytes.fromhex('00 FC 74 02 00 04 72 02 00 0C 74 22'), 'Data_018_77ED / 1', layout='rect'),
            SpriteFrame(0x63814, bytes.fromhex('00 FC 76 02 00 04 72 02 00 0C 76 22'), 'Data_018_77ED / 2', layout='rect'),
            SpriteFrame(0x63820, bytes.fromhex('00 FC 74 02 00 04 72 02 00 0C 74 22'), 'Data_018_77ED / 3', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xBB: SpriteDefinition(  # Bush Crawler
        frames=(
            SpriteFrame(0x1C00A, bytes.fromhex('7C 02 7E 02'), 'Bushcrawler2SpriteVariants / 0'),
            SpriteFrame(0x1C00E, bytes.fromhex('7E 22 7C 22'), 'Bushcrawler2SpriteVariants / 1'),
            SpriteFrame(0x1C012, bytes.fromhex('F4 16 F6 16'), 'BushcrawlerOutdoorSpriteVariants / 0'),
            SpriteFrame(0x1C016, bytes.fromhex('F0 17 F2 17'), 'BushcrawlerOutdoorSpriteVariants / 1'),
            SpriteFrame(0x1C01A, bytes.fromhex('F4 16 F6 16'), 'BushcrawlerIndoorSpriteVariants / 0'),
            SpriteFrame(0x1C01E, bytes.fromhex('F0 16 F2 16'), 'BushcrawlerIndoorSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xBC: None,  # Grim Creeper — Boss/miniboss; deferred
    0xBD: SpriteDefinition(  # Vire
        frames=(
            SpriteFrame(0x62EE6, bytes.fromhex('00 FC 60 02 00 04 62 02 00 0C 60 22'), 'Data_018_6ED7 / 0', layout='rect'),
            SpriteFrame(0x62EF2, bytes.fromhex('00 FC 64 02 00 04 66 02 00 0C 64 22'), 'Data_018_6ED7 / 1', layout='rect'),
            SpriteFrame(0x62EFE, bytes.fromhex('00 FC 68 02 00 04 6A 02 00 0C 68 22'), 'Data_018_6ED7 / 2', layout='rect'),
            SpriteFrame(0x62F77, bytes.fromhex('6C 00 6C 20'), 'Vire2SpriteVariants / 0'),
            SpriteFrame(0x62F7B, bytes.fromhex('6E 00 6E 20'), 'Vire2SpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xBE: None,  # Blaino — Boss/miniboss; deferred
    0xBF: SpriteDefinition(  # Zombie
        frames=(
            SpriteFrame(0x62407, bytes.fromhex('FF FF FF FF'), 'ZombieSpriteVariants / 0'),
            SpriteFrame(0x6240B, bytes.fromhex('6C 02 6C 22'), 'ZombieSpriteVariants / 1'),
            SpriteFrame(0x6240F, bytes.fromhex('68 02 6A 02'), 'ZombieSpriteVariants / 2'),
            SpriteFrame(0x62413, bytes.fromhex('60 02 62 02'), 'ZombieSpriteVariants / 3'),
            SpriteFrame(0x62417, bytes.fromhex('64 02 66 02'), 'ZombieSpriteVariants / 4'),
        ),
        display_frame=3,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xC0: None,  # Invisible sign-reading sequence controller; see notes below.
    0xC1: SpriteDefinition(  # Marin At The Shore
        frames=(
            SpriteFrame(0x61EC3, bytes.fromhex('60 01 62 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 0'),
            SpriteFrame(0x61EC7, bytes.fromhex('62 21 60 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 1'),
            SpriteFrame(0x61ECB, bytes.fromhex('64 01 66 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 2'),
            SpriteFrame(0x61ECF, bytes.fromhex('66 21 64 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 3'),
            SpriteFrame(0x61ED3, bytes.fromhex('68 01 6A 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 4'),
            SpriteFrame(0x61ED7, bytes.fromhex('6C 01 6E 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 5'),
            SpriteFrame(0x61EDB, bytes.fromhex('6A 21 68 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 6'),
            SpriteFrame(0x61EDF, bytes.fromhex('6E 21 6C 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xC2: SpriteDefinition(  # Marin At Tal Tal Heights
        frames=(
            SpriteFrame(0x61EC3, bytes.fromhex('60 01 62 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 0'),
            SpriteFrame(0x61EC7, bytes.fromhex('62 21 60 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 1'),
            SpriteFrame(0x61ECB, bytes.fromhex('64 01 66 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 2'),
            SpriteFrame(0x61ECF, bytes.fromhex('66 21 64 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 3'),
            SpriteFrame(0x61ED3, bytes.fromhex('68 01 6A 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 4'),
            SpriteFrame(0x61ED7, bytes.fromhex('6C 01 6E 01'), 'MarinAtTalTalAndInStoreSpriteVariants / 5'),
            SpriteFrame(0x61EDB, bytes.fromhex('6A 21 68 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 6'),
            SpriteFrame(0x61EDF, bytes.fromhex('6E 21 6C 21'), 'MarinAtTalTalAndInStoreSpriteVariants / 7'),
            SpriteFrame(0x620E4, bytes.fromhex('50 02 52 02'), 'MarinAtTalTal2SpriteVariants / 0'),
            SpriteFrame(0x620E8, bytes.fromhex('52 22 50 22'), 'MarinAtTalTal2SpriteVariants / 1'),
            SpriteFrame(0x620EC, bytes.fromhex('54 02 56 02'), 'MarinAtTalTal2SpriteVariants / 2'),
            SpriteFrame(0x620F0, bytes.fromhex('56 22 54 22'), 'MarinAtTalTal2SpriteVariants / 3'),
            SpriteFrame(0x620F4, bytes.fromhex('58 02 5A 02'), 'MarinAtTalTal2SpriteVariants / 4'),
            SpriteFrame(0x620F8, bytes.fromhex('5C 02 5E 02'), 'MarinAtTalTal2SpriteVariants / 5'),
            SpriteFrame(0x620FC, bytes.fromhex('5A 22 58 22'), 'MarinAtTalTal2SpriteVariants / 6'),
            SpriteFrame(0x62100, bytes.fromhex('5E 22 5C 22'), 'MarinAtTalTal2SpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xC3: SpriteDefinition(  # Mamu And Frogs
        frames=(
            SpriteFrame(0x602B9, bytes.fromhex('00 00 60 00 00 08 62 00 00 10 64 00 00 18 66 00 10 00 68 00 10 08 6A 00 10 10 6C 00 10 18 6E 00'), 'Data_018_42BA / 0', layout='rect'),
            SpriteFrame(0x602D9, bytes.fromhex('00 00 70 00 00 08 72 00 00 10 74 00 00 18 76 00 10 00 68 00 10 08 6A 00 10 10 6C 00 10 18 6E 00'), 'Data_018_42BA / 1', layout='rect'),
            SpriteFrame(0x602F9, bytes.fromhex('00 00 78 00 00 08 7A 00 00 10 7C 00 00 18 7E 00 10 00 68 00 10 08 6A 00 10 10 6C 00 10 18 6E 00'), 'Data_018_42BA / 2', layout='rect'),
            SpriteFrame(0x60319, bytes.fromhex('00 00 7E 20 00 08 7C 20 00 10 7A 20 00 18 78 20 10 00 6E 20 10 08 6C 20 10 10 6A 20 10 18 68 20'), 'Data_018_42BA / 3', layout='rect'),
            SpriteFrame(0x60339, bytes.fromhex('00 00 76 20 00 08 74 20 00 10 72 20 00 18 70 20 10 00 6E 20 10 08 6C 20 10 10 6A 20 10 18 68 20'), 'Data_018_42BA / 4', layout='rect'),
            SpriteFrame(0x603B2, bytes.fromhex('58 00 58 20'), 'MamuAndFrogsSpriteVariants / 0'),
            SpriteFrame(0x603B6, bytes.fromhex('5A 00 5A 20'), 'MamuAndFrogsSpriteVariants / 1'),
            SpriteFrame(0x603BA, bytes.fromhex('5C 00 5E 00'), 'MamuAndFrogsSpriteVariants / 2'),
            SpriteFrame(0x603BE, bytes.fromhex('5E 20 5C 20'), 'MamuAndFrogsSpriteVariants / 3'),
            SpriteFrame(0x603C2, bytes.fromhex('F0 00 50 00 F0 08 52 00 00 00 54 00 00 08 56 00'), 'MamuAndFrogsSpriteList / 0', layout='rect'),
            SpriteFrame(0x603D2, bytes.fromhex('F0 00 52 20 F0 08 50 20 00 00 56 20 00 08 54 20'), 'MamuAndFrogsSpriteList / 1', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
        canvas_size=(32, 32),
        draw_offset=(0, -16),
    ),
    0xC4: SpriteDefinition(  # Walrus
        frames=(
            SpriteFrame(0x617A9, bytes.fromhex('00 00 60 01 00 08 62 01 00 10 64 01 00 18 66 01 10 00 68 01 10 08 6A 01 10 10 6C 01 10 18 6E 01'), 'Data_018_579B / 0', layout='rect'),
            SpriteFrame(0x617C9, bytes.fromhex('00 00 60 01 00 08 70 01 00 10 64 01 00 18 66 01 10 00 68 01 10 08 6A 01 10 10 6C 01 10 18 6E 01'), 'Data_018_579B / 1', layout='rect'),
            SpriteFrame(0x617E9, bytes.fromhex('00 00 72 01 00 08 74 01 00 10 64 01 00 18 66 01 10 00 76 01 10 08 6A 01 10 10 6C 01 10 18 6E 01'), 'Data_018_579B / 2', layout='rect'),
            SpriteFrame(0x61809, bytes.fromhex('00 00 78 01 00 08 7A 01 00 10 7C 01 00 18 7E 01 10 00 78 41 10 08 7A 41 10 10 7C 41 10 18 7E 41'), 'Data_018_579B / 3', layout='rect'),
            SpriteFrame(0x61829, bytes.fromhex('00 00 68 41 00 08 6A 41 00 10 6C 41 00 18 6E 41 10 00 60 41 10 08 62 41 10 10 64 41 10 18 66 41'), 'Data_018_579B / 4', layout='rect'),
            SpriteFrame(0x61849, bytes.fromhex('0E 00 68 41 0E 08 6A 41 0E 10 6C 41 0E 18 6E 41 10 00 FF 41 10 08 FF 41 10 10 FF 41 10 18 FF 41'), 'Data_018_579B / 5', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
        canvas_size=(32, 32),
        draw_offset=(0, -16),
    ),
    0xC5: SpriteDefinition(  # Urchin
        frames=(
            SpriteFrame(0x57385, bytes.fromhex('5C 03 5E 03'), 'Urchin2SpriteVariants / 0'),
            SpriteFrame(0x57389, bytes.fromhex('5E 23 5C 23'), 'Urchin2SpriteVariants / 1'),
            SpriteFrame(0x5738D, bytes.fromhex('5E 63 5C 63'), 'Urchin2SpriteVariants / 2'),
            SpriteFrame(0x57391, bytes.fromhex('5C 43 5E 43'), 'Urchin2SpriteVariants / 3'),
            SpriteFrame(0x57395, bytes.fromhex('2C 03 2E 03'), 'Urchin1SpriteVariants / 0'),
            SpriteFrame(0x57399, bytes.fromhex('2E 23 2C 23'), 'Urchin1SpriteVariants / 1'),
            SpriteFrame(0x5739D, bytes.fromhex('2E 63 2C 63'), 'Urchin1SpriteVariants / 2'),
            SpriteFrame(0x573A1, bytes.fromhex('2C 43 2E 43'), 'Urchin1SpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0xC6: SpriteDefinition(  # Sand Crab
        frames=(
            SpriteFrame(0x57322, bytes.fromhex('58 02 58 22'), 'SandCrabSpriteVariants / 0'),
            SpriteFrame(0x57326, bytes.fromhex('5A 02 5A 22'), 'SandCrabSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xC7: None,  # Manbo And Fishes — Multipart Manbo scene and spawned fishes; deferred
    0xC8: SpriteDefinition(  # Bunny Calling Marin
        frames=(
            SpriteFrame(0x6129A, bytes.fromhex('5A 21 58 21'), 'BunnyCallingMarinSpriteVariants / 0'),
            SpriteFrame(0x6129E, bytes.fromhex('5E 21 5C 21'), 'BunnyCallingMarinSpriteVariants / 1'),
            SpriteFrame(0x612A2, bytes.fromhex('58 01 5A 01'), 'BunnyCallingMarinSpriteVariants / 2'),
            SpriteFrame(0x612A6, bytes.fromhex('5C 01 5E 01'), 'BunnyCallingMarinSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xC9: None,  # Musical Note — Musical note uses unmapped global sprite tiles
    0xCA: SpriteDefinition(  # Mad Batter
        frames=(
            SpriteFrame(0x61094, bytes.fromhex('00 FC 70 03 00 04 72 03 00 0C 70 23'), 'Data_018_5090 / 0', layout='rect'),
            SpriteFrame(0x610A0, bytes.fromhex('00 FC 74 03 00 04 76 03 00 0C 74 23'), 'Data_018_509C / 0', layout='rect'),
            SpriteFrame(0x610BF, bytes.fromhex('7E 03 7E 23'), 'MadBatterSpriteVariants / 0'),
            SpriteFrame(0x610C3, bytes.fromhex('7E 43 7E 63'), 'MadBatterSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0xCB: SpriteDefinition(  # Zora
        frames=(
            SpriteFrame(0x609C4, bytes.fromhex('FF FF FF FF'), 'ZoraSpriteVariants / 0'),
            SpriteFrame(0x609C8, bytes.fromhex('54 02 54 62'), 'ZoraSpriteVariants / 1'),
            SpriteFrame(0x609CC, bytes.fromhex('54 42 54 22'), 'ZoraSpriteVariants / 2'),
            SpriteFrame(0x609D0, bytes.fromhex('56 02 56 22'), 'ZoraSpriteVariants / 3'),
            SpriteFrame(0x609D4, bytes.fromhex('52 02 52 22'), 'ZoraSpriteVariants / 4'),
        ),
        display_frame=4,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xCC: SpriteDefinition(  # Fish
        frames=(
            SpriteFrame(0x5449F, bytes.fromhex('FF 00 FF 00'), 'FishSpriteVariants / 0'),
            SpriteFrame(0x544A3, bytes.fromhex('54 00 56 00'), 'FishSpriteVariants / 1'),
            SpriteFrame(0x544A7, bytes.fromhex('58 00 5A 00'), 'FishSpriteVariants / 2'),
            SpriteFrame(0x544AB, bytes.fromhex('56 20 54 20'), 'FishSpriteVariants / 3'),
            SpriteFrame(0x544AF, bytes.fromhex('5A 20 58 20'), 'FishSpriteVariants / 4'),
        ),
        display_frame=1,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
    ),
    0xCD: SpriteDefinition(  # Bananas Schule Sale
        frames=(
            SpriteFrame(0x66F0B, bytes.fromhex('08 04 70 01 08 0C 72 01 08 14 70 21'), 'Overworld banana bunch', layout='rect'),
            SpriteFrame(0x66E2B, bytes.fromhex('00 00 50 03 00 08 52 03 00 10 54 03 10 00 56 03 10 08 58 03 10 10 5A 03 FF FF FF FF FF FF FF FF'), 'Data_019_6E25 / 0', layout='rect'),
            SpriteFrame(0x66E4B, bytes.fromhex('00 00 50 03 00 08 52 03 00 10 5C 03 10 00 56 03 10 08 58 03 10 10 5E 03 10 18 60 03 FF FF FF FF'), 'Data_019_6E25 / 1', layout='rect'),
            SpriteFrame(0x66E6B, bytes.fromhex('00 00 62 03 00 08 64 03 00 10 66 03 10 00 68 03 10 08 58 03 10 10 5E 03 10 18 60 03 FF FF FF FF'), 'Data_019_6E25 / 2', layout='rect'),
            SpriteFrame(0x66E8B, bytes.fromhex('00 00 6A 03 00 08 6C 03 00 10 6E 03 10 00 68 03 10 08 58 03 10 10 5E 03 10 18 60 03 FF FF FF FF'), 'Data_019_6E25 / 3', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
        draw_offset=(4, 8),
    ),
    0xCE: SpriteDefinition(  # Mermaid Statue
        frames=(
            SpriteFrame(0x6092C, bytes.fromhex('F0 00 70 01 F0 08 72 01 00 00 74 01 00 08 76 01'), 'Data_018_4928 / 0', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
        canvas_size=(16, 32),
        draw_offset=(0, -16),
    ),
    0xCF: None,  # Seashell Mansion — Background and event-sequence controller; deferred
    0xD0: SpriteDefinition(  # Animal D0
        frames=(
            SpriteFrame(0x17F3D, bytes.fromhex('50 01 52 01'), 'AnimalD0SpriteVariants / 0'),
            SpriteFrame(0x17F41, bytes.fromhex('52 21 50 21'), 'AnimalD0SpriteVariants / 1'),
            SpriteFrame(0x17F45, bytes.fromhex('54 01 56 01'), 'AnimalD0SpriteVariants / 2'),
            SpriteFrame(0x17F49, bytes.fromhex('56 21 54 21'), 'AnimalD0SpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xD1: SpriteDefinition(  # Animal D1
        frames=(
            SpriteFrame(0x57F88, bytes.fromhex('74 03 76 03'), 'AnimalD1SpriteVariants / 0'),
            SpriteFrame(0x57F8C, bytes.fromhex('70 03 72 03'), 'AnimalD1SpriteVariants / 1'),
            SpriteFrame(0x57F90, bytes.fromhex('76 23 74 23'), 'AnimalD1SpriteVariants / 2'),
            SpriteFrame(0x57F94, bytes.fromhex('72 23 70 23'), 'AnimalD1SpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0xD2: SpriteDefinition(  # Animal D2
        frames=(
            SpriteFrame(0x6125F, bytes.fromhex('78 01 7A 01'), 'AnimalD2SpriteVariants / 0'),
            SpriteFrame(0x61263, bytes.fromhex('7C 01 7E 01'), 'AnimalD2SpriteVariants / 1'),
            SpriteFrame(0x61267, bytes.fromhex('7A 21 78 21'), 'AnimalD2SpriteVariants / 2'),
            SpriteFrame(0x6126B, bytes.fromhex('7E 21 7C 21'), 'AnimalD2SpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xD3: SpriteDefinition(  # Bunny D3
        frames=(
            SpriteFrame(0x611BC, bytes.fromhex('50 01 52 01'), 'BunnyD3SpriteVariants / 0'),
            SpriteFrame(0x611C0, bytes.fromhex('52 21 50 21'), 'BunnyD3SpriteVariants / 1'),
            SpriteFrame(0x611C4, bytes.fromhex('54 01 56 01'), 'BunnyD3SpriteVariants / 2'),
            SpriteFrame(0x611C8, bytes.fromhex('56 21 54 21'), 'BunnyD3SpriteVariants / 3'),
            SpriteFrame(0x611CC, bytes.fromhex('58 01 5A 01'), 'BunnyD3SpriteVariants / 4'),
            SpriteFrame(0x611D0, bytes.fromhex('58 01 5A 01'), 'BunnyD3SpriteVariants / 5'),
            SpriteFrame(0x611D4, bytes.fromhex('5A 21 58 21'), 'BunnyD3SpriteVariants / 6'),
            SpriteFrame(0x611D8, bytes.fromhex('5A 21 58 21'), 'BunnyD3SpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=1,
    ),
    0xD4: SpriteDefinition(  # Ghost
        frames=(
            SpriteFrame(0x65DF8, bytes.fromhex('42 23 40 23'), 'GhostSpriteVariants / 0'),
            SpriteFrame(0x65DFC, bytes.fromhex('46 23 44 23'), 'GhostSpriteVariants / 1'),
            SpriteFrame(0x65E00, bytes.fromhex('40 03 42 03'), 'GhostSpriteVariants / 2'),
            SpriteFrame(0x65E04, bytes.fromhex('44 03 46 03'), 'GhostSpriteVariants / 3'),
            SpriteFrame(0x65E08, bytes.fromhex('48 03 4A 03'), 'GhostSpriteVariants / 4'),
            SpriteFrame(0x65E0C, bytes.fromhex('4C 03 4E 03'), 'GhostSpriteVariants / 5'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
        graphics_overrides=((0, 0xD8),),  # Engine follower override, bank0.asm 00:2EB9–2EC7.
    ),
    0xD5: SpriteDefinition(  # Rooster
        frames=(
            SpriteFrame(0x659BC, bytes.fromhex('42 23 40 23'), 'RoosterSpriteVariants / 0'),
            SpriteFrame(0x659C0, bytes.fromhex('46 23 44 23'), 'RoosterSpriteVariants / 1'),
            SpriteFrame(0x659C4, bytes.fromhex('40 03 42 03'), 'RoosterSpriteVariants / 2'),
            SpriteFrame(0x659C8, bytes.fromhex('44 03 46 03'), 'RoosterSpriteVariants / 3'),
            SpriteFrame(0x659CC, bytes.fromhex('4C 03 4C 23'), 'RoosterSpriteVariants / 4'),
            SpriteFrame(0x659D0, bytes.fromhex('4E 03 4E 23'), 'RoosterSpriteVariants / 5'),
            SpriteFrame(0x659D4, bytes.fromhex('48 03 48 23'), 'RoosterSpriteVariants / 6'),
            SpriteFrame(0x659D8, bytes.fromhex('4A 03 4A 23'), 'RoosterSpriteVariants / 7'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
        graphics_overrides=((0, 0xDD),),  # Engine follower override, bank0.asm 00:2EB9–2EC7.
    ),
    0xD6: SpriteDefinition(  # Side View Pot
        frames=(
            SpriteFrame(0x658D9, bytes.fromhex('5E 06 5E 26'), 'SideViewPotSpriteVariants / 0'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=6,
    ),
    0xD7: SpriteDefinition(  # Thwimp
        frames=(
            SpriteFrame(0x656BD, bytes.fromhex('5A 03 5A 23'), 'ThwimpSpriteVariants / 0'),
            SpriteFrame(0x656C1, bytes.fromhex('58 02 58 22'), 'ThwimpSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0xD8: None,  # Thwomp — Separate body and moving eyes; multipart rendering deferred
    0xD9: SpriteDefinition(  # Thwomp Rammable
        frames=(
            SpriteFrame(0x6554B, bytes.fromhex('00 00 50 02 00 08 52 02 00 10 52 22 00 18 50 22 10 00 54 02 10 08 56 02 10 10 56 22 10 18 54 22'), 'Data_019_554B / 0', layout='rect'),
            SpriteFrame(0x6556B, bytes.fromhex('00 00 50 03 00 08 52 03 00 10 52 23 00 18 50 23 10 00 54 03 10 08 56 03 10 10 56 23 10 18 54 23'), 'Data_019_556B / 0', layout='rect'),
            SpriteFrame(0x6554B, bytes.fromhex('00 00 50 02 00 08 52 02 00 10 52 22 00 18 50 22 10 00 54 02 10 08 56 02 10 10 56 22 10 18 54 22'), 'Data_019_554B / 0, tile shift 8, preview 1', layout='rect', tile_offset=8),
            SpriteFrame(0x6556B, bytes.fromhex('00 00 50 03 00 08 52 03 00 10 52 23 00 18 50 23 10 00 54 03 10 08 56 03 10 10 56 23 10 18 54 23'), 'Data_019_556B / 0, tile shift 8, preview 1', layout='rect', tile_offset=8),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
        canvas_size=(32, 32),
        draw_offset=(0, -16),
    ),
    0xDA: SpriteDefinition(  # Podoboo
        frames=(
            SpriteFrame(0x653E0, bytes.fromhex('7A 42 7A 62'), 'PodobooSpriteVariants / 0'),
            SpriteFrame(0x653E4, bytes.fromhex('7A 54 7A 74'), 'PodobooSpriteVariants / 1'),
            SpriteFrame(0x653E8, bytes.fromhex('7A 02 7A 22'), 'PodobooSpriteVariants / 2'),
            SpriteFrame(0x653EC, bytes.fromhex('7A 14 7A 34'), 'PodobooSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xDB: SpriteDefinition(  # Giant Bubble
        frames=(
            SpriteFrame(0x6536C, bytes.fromhex('F8 F8 60 00 F8 00 62 00 F8 08 62 20 F8 10 60 20 08 F8 60 40 08 00 62 40 08 08 62 60 08 10 60 60'), 'GiantBubbleSpriteRect / 0', layout='rect'),
            SpriteFrame(0x6536C, bytes.fromhex('F8 F8 60 00 F8 00 62 00 F8 08 62 20 F8 10 60 20 08 F8 60 40 08 00 62 40 08 08 62 60 08 10 60 60'), 'GiantBubbleSpriteRect / 0, tile shift 4, preview 1', layout='rect', tile_offset=4),
            SpriteFrame(0x6536C, bytes.fromhex('F8 F8 60 00 F8 00 62 00 F8 08 62 20 F8 10 60 20 08 F8 60 40 08 00 62 40 08 08 62 60 08 10 60 60'), 'GiantBubbleSpriteRect / 0, tile shift 8, preview 2', layout='rect', tile_offset=8),
            SpriteFrame(0x6536C, bytes.fromhex('F8 F8 60 00 F8 00 62 00 F8 08 62 20 F8 10 60 20 08 F8 60 40 08 00 62 40 08 08 62 60 08 10 60 60'), 'GiantBubbleSpriteRect / 0, tile shift 4, preview 3', layout='rect', tile_offset=4),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
        canvas_size=(32, 32),
        draw_offset=(0, -16),
    ),
    0xDC: SpriteDefinition(  # Outdoor event state 1 draws the moving statue.
        frames=(
            SpriteFrame(0x651AD, bytes.fromhex('F0 00 78 07 F0 08 7A 07 00 00 7C 07 00 08 7E 07'),
                        'Moving rooster statue', layout='rect'),
        ), required_slot=3, fallback_palette=7, overworld_only=True,
        # Map placement is an invisible controller, so keep the marker anchor.
        # The selector composes the event rect's complete 16x32 bounding box.
    ),
    0xDD: None,  # Book — Pointer-driven book and runtime graphics forms; deferred
    0xDE: SpriteDefinition(  # Explicit frames show the song's instrument children.
        frames=(
            SpriteFrame(0x64BAC, bytes.fromhex('50 06 52 06'), 'Full Moon Cello'),
            SpriteFrame(0x64BB0, bytes.fromhex('54 06 56 06'), 'Conch Horn'),
            SpriteFrame(0x64BB4, bytes.fromhex('58 06 5A 06'), "Sea Lily's Bell"),
            SpriteFrame(0x64BB8, bytes.fromhex('5C 06 5E 06'), 'Surf Harp'),
            SpriteFrame(0x64BBC, bytes.fromhex('60 06 62 06'), 'Wind Marimba'),
            SpriteFrame(0x64BC0, bytes.fromhex('64 06 66 06'), 'Coral Triangle'),
            SpriteFrame(0x64BC4, bytes.fromhex('68 06 6A 06'), 'Organ of Evening Calm'),
            SpriteFrame(0x64BC8, bytes.fromhex('6C 06 6E 06'), 'Thunder Drum'),
        ), fallback_palette=6, overworld_only=True,
    ),
    0xDF: None,  # Sword Beam — Sword beam uses global runtime graphics; deferred
    0xE0: SpriteDefinition(  # Monkey
        frames=(
            SpriteFrame(0x5764D, bytes.fromhex('00 00 74 02 00 08 74 22 00 00 FF 02'), 'Data_015_764B / 0', layout='rect'),
            SpriteFrame(0x57659, bytes.fromhex('F0 08 7A 02 00 00 76 02 00 08 78 02'), 'Data_015_764B / 1', layout='rect'),
            SpriteFrame(0x57665, bytes.fromhex('F0 00 7A 22 00 00 78 22 00 08 76 22'), 'Data_015_764B / 2', layout='rect'),
            SpriteFrame(0x57671, bytes.fromhex('00 00 74 42 00 08 74 62 00 00 FF 02'), 'Data_015_764B / 3', layout='rect'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xE1: SpriteDefinition(  # Witch Rat
        frames=(
            SpriteFrame(0x5788F, bytes.fromhex('50 03 52 03'), 'WitchRatSpriteVariants / 0'),
            SpriteFrame(0x57893, bytes.fromhex('54 03 56 03'), 'WitchRatSpriteVariants / 1'),
            SpriteFrame(0x57897, bytes.fromhex('52 23 50 23'), 'WitchRatSpriteVariants / 2'),
            SpriteFrame(0x5789B, bytes.fromhex('56 23 54 23'), 'WitchRatSpriteVariants / 3'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=3,
    ),
    0xE2: SpriteDefinition(  # Flame Shooter
        frames=(
            SpriteFrame(0x54D3B, bytes.fromhex('70 02 70 22'), 'FlameShooterSpriteVariants / 0'),
            SpriteFrame(0x54D3F, bytes.fromhex('72 03 72 23'), 'FlameShooterSpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=2,
    ),
    0xE3: SpriteDefinition(  # Pokey
        frames=(
            SpriteFrame(0x54B17, bytes.fromhex('E8 FE 74 00 E8 06 74 20 F4 01 76 00 F4 09 76 20 00 00 76 00 00 08 76 20'), 'Data_015_4B17 / 0', layout='rect'),
            SpriteFrame(0x54B2F, bytes.fromhex('E8 00 74 00 E8 08 74 20 F4 00 76 00 F4 08 76 20 00 00 76 00 00 08 76 20'), 'Data_015_4B17 / 1', layout='rect'),
            SpriteFrame(0x54B47, bytes.fromhex('E8 02 74 00 E8 0A 74 20 F4 FF 76 00 F4 07 76 20 00 00 76 00 00 08 76 20'), 'Data_015_4B17 / 2', layout='rect'),
            SpriteFrame(0x54B5F, bytes.fromhex('E8 00 74 00 E8 08 74 20 F4 00 76 00 F4 08 76 20 00 00 76 00 00 08 76 20'), 'Data_015_4B17 / 3', layout='rect'),
            SpriteFrame(0x54B77, bytes.fromhex('F4 FF 74 00 F4 07 74 20 00 00 76 00 00 08 76 20'), 'Data_015_4B77 / 0', layout='rect'),
            SpriteFrame(0x54B87, bytes.fromhex('F4 00 74 00 F4 08 74 20 00 00 76 00 00 08 76 20'), 'Data_015_4B77 / 1', layout='rect'),
            SpriteFrame(0x54B97, bytes.fromhex('F4 01 74 00 F4 09 74 20 00 00 76 00 00 08 76 20'), 'Data_015_4B77 / 2', layout='rect'),
            SpriteFrame(0x54BA7, bytes.fromhex('F4 00 74 00 F4 08 74 20 00 00 76 00 00 08 76 20'), 'Data_015_4B77 / 3', layout='rect'),
            SpriteFrame(0x54BB7, bytes.fromhex('00 FF 74 00 00 07 74 20'), 'Data_015_4BB7 / 0', layout='rect'),
            SpriteFrame(0x54BBF, bytes.fromhex('00 00 74 00 00 08 74 20'), 'Data_015_4BB7 / 1', layout='rect'),
            SpriteFrame(0x54BC7, bytes.fromhex('00 01 74 00 00 09 74 20'), 'Data_015_4BB7 / 2', layout='rect'),
            SpriteFrame(0x54BCF, bytes.fromhex('00 00 74 00 00 08 74 20'), 'Data_015_4BB7 / 3', layout='rect'),
        ),
        display_frame=1,  # Static map frame; preview arrows are independent.
        fallback_palette=0,
        draw_offset=(0, -24),
    ),
    0xE4: None,  # Moblin King — Boss/miniboss; deferred
    0xE5: SpriteDefinition(
        frames=(
            SpriteFrame(0x1BAE1, bytes.fromhex('A9 14'), 'Floating item / Hearts', layout='single'),
            SpriteFrame(0x1BAE3, bytes.fromhex('2A 41 2A 61'), 'Floating item / Arrows', layout='pair'),
        ), shared_graphics=True, overworld_only=True, draw_offset=(-4, -15),
        # First normal-room hover phase is Z=15. Contents and wings share it.
        parts=(SpritePart(SpriteFrame(0x1BAE7, bytes.fromhex('00 FC 22 00 00 0C 22 20'), 'Floating item wings / down', layout='rect')),),
    ),
    0xE6: None,  # Final Nightmare — Boss/miniboss; deferred
    0xE7: None,  # Kanalet Castle Gate Switch — Background gate switch/controller; deferred
    0xE8: None,  # Ending Owl Stair Climbing — Ending scene controller; deferred
    0xE9: None,  # Color Shell Red — Color Dungeon graphics loader and layouts; deferred
    0xEA: None,  # Color Shell Green — Color Dungeon graphics loader and layouts; deferred
    0xEB: None,  # Color Shell Blue — Color Dungeon graphics loader and layouts; deferred
    0xEC: None,  # Color Ghoul Red — Color Dungeon graphics loader and layouts; deferred
    0xED: None,  # Color Ghoul Green — Color Dungeon graphics loader and layouts; deferred
    0xEE: None,  # Color Ghoul Blue — Color Dungeon graphics loader and layouts; deferred
    0xEF: None,  # Rotoswitch Red — Color Dungeon graphics loader and layouts; deferred
    0xF0: None,  # Rotoswitch Yellow — Color Dungeon graphics loader and layouts; deferred
    0xF1: None,  # Rotoswitch Blue — Color Dungeon graphics loader and layouts; deferred
    0xF2: None,  # Flying Hopper Bombs — Color Dungeon graphics loader and layouts; deferred
    0xF3: None,  # Hopper — Color Dungeon graphics loader and layouts; deferred
    0xF4: None,  # Avalaunch — Boss/miniboss; deferred
    0xF5: None,  # Bouncing Boulder — Color Dungeon graphics loader and layouts; deferred
    0xF6: None,  # Color Guardian Blue — Color Dungeon NPC with specialized graphics; deferred
    0xF7: None,  # Color Guardian Red — Color Dungeon NPC with specialized graphics; deferred
    0xF8: None,  # Giant Buzz Blob — Boss/miniboss; deferred
    0xF9: None,  # Hardhit Beetle — Boss/miniboss; deferred
    0xFA: SpriteDefinition(  # Photographer
        frames=(
            SpriteFrame(0xD88CE, bytes.fromhex('44 07 46 07'), 'PhotographerOverworldSpriteVariants / 0'),
            SpriteFrame(0xD88D2, bytes.fromhex('48 07 4A 07'), 'PhotographerOverworldSpriteVariants / 1'),
            SpriteFrame(0xD88D6, bytes.fromhex('46 27 44 27'), 'PhotographerOverworldSpriteVariants / 2'),
            SpriteFrame(0xD88DA, bytes.fromhex('4A 27 48 27'), 'PhotographerOverworldSpriteVariants / 3'),
            SpriteFrame(0xD88DE, bytes.fromhex('40 07 42 07'), 'PhotographerOverworldSpriteVariants / 4'),
            SpriteFrame(0xD88E2, bytes.fromhex('70 06 72 06'), 'Photographer2SpriteVariants / 0'),
            SpriteFrame(0xD88E6, bytes.fromhex('74 06 76 06'), 'Photographer2SpriteVariants / 1'),
            SpriteFrame(0xD88EA, bytes.fromhex('6A 26 68 26'), 'Photographer2SpriteVariants / 2'),
            SpriteFrame(0xD88EE, bytes.fromhex('6E 26 6C 26'), 'Photographer2SpriteVariants / 3'),
            SpriteFrame(0xD88F2, bytes.fromhex('70 06 72 06'), 'Unknown074SpriteVariants / 0'),
            SpriteFrame(0xD88F6, bytes.fromhex('74 06 76 06'), 'Unknown074SpriteVariants / 1'),
            SpriteFrame(0xD88FA, bytes.fromhex('48 06 4A 06'), 'Unknown075SpriteVariants / 0'),
            SpriteFrame(0xD88FE, bytes.fromhex('4C 06 4E 06'), 'Unknown075SpriteVariants / 1'),
            SpriteFrame(0xD8902, bytes.fromhex('70 06 72 06'), 'Unknown075SpriteVariants / 2'),
            SpriteFrame(0xD8906, bytes.fromhex('74 06 76 06'), 'Unknown075SpriteVariants / 3'),
            SpriteFrame(0xD890A, bytes.fromhex('4E 26 4C 26'), 'Unknown076SpriteVariants / 0'),
            SpriteFrame(0xD890E, bytes.fromhex('4A 26 48 26'), 'Unknown076SpriteVariants / 1'),
        ),
        display_frame=0,  # Static map frame; preview arrows are independent.
        fallback_palette=7,
        graphics_sources=((0, 0xE0000),),  # PhotographerTiles bank 38, photos_animations.asm uploads to 8400.
    ),
}


# Placed controllers have no OAM artwork of their own. Keep a selectable
# ROM-backed map marker. Some IDs are reused for visible runtime children;
# explicit selector frame requests may preview those children separately.
SPRITE_CONTROLLER_NOTES = {
    0x43: ('Invisible Seashell Mansion tree dialog trigger. Face it nearby and '
           'press A to talk; the trees are room background graphics.'),
    0x44: ('Invisible Magic Powder dialog trigger. This entity draws no sprite; '
           'the bones are part of the room background.'),
    0x97: ('Invisible diving-warp trigger. Dive nearby while swimming; the '
           "destination depends on the room and, near Catfish's Maw, Link's X position."),
    0xB2: ('Invisible beetle spawner. Frame previews show its spawned beetles; '
           'the map marker identifies the spawn point.'),
    0xC0: ('Invisible signpost-maze controller. Checks the 14-sign reading sequence '
           "and reveals Mamu's cave; the signs are background tiles."),
    0xDC: ('Invisible outdoor rooster-statue controller. Push upward with the '
           'level-2 bracelet to open the staircase. Frame preview shows the moving '
           'statue; indoor rooster events are not previewed.'),
    0xDE: ('Invisible Egg song controller. Handles the Ballad sequence and summoned '
           'instruments; frame previews show all eight instruments.'),
}


def sprite_placement_frame(sprite_id, x, y):
    """Choose floating contents from original entity initialization code.

    LoadEntityFromDefinition stores X=x*16+8 and Y=y*16+16. Running
    EntityInitFloatingItem on those coordinates gives (x&1)|((y&1)<<1).
    The second initializer gives variant 4+(x&1), represented here as frames
    zero and one. Follow the instructions; older disassembly prose reverses
    some of the item/parity descriptions. Other entities retain their default.
    """
    if sprite_id == 0x86:
        return (x & 1) | ((y & 1) << 1)
    if sprite_id == 0xE5:
        return x & 1
    return None
