"""Static sprite rendering with ROM-verified definitions and safe fallbacks."""
from functools import lru_cache
from dataclasses import dataclass
from windfish.rendering.windfish_sprite_definitions import SPRITE_DEFINITIONS, SPRITE_CONTROLLER_NOTES
from PIL import Image
from windfish.rendering.windfish_sprite_oam import decode_2bpp
from windfish.rendering.windfish_sprite_palettes import object_palettes
from windfish.rendering.windfish_sprite_oam import OAMSprite, compose_oam
from windfish.rendering.windfish_sprite_vram import room_vram_provider, shared_item_tile
from windfish.compatibility import api as profile

# Identical X tiles survive at this address in native Rev2 and original VWF.
PLACEHOLDER_TILE_OFFSET = 0xBDA00


def render_placeholder(rom, palette_index=0, room=0, palettes=None):
    """Draw four consecutive 8x8 2bpp tiles as one 16x16 image (2x2)."""
    if not isinstance(palette_index, int) or not 0 <= palette_index < 8:
        raise ValueError('OBJ palette index must be between 0 and 7')
    raw = rom[PLACEHOLDER_TILE_OFFSET:PLACEHOLDER_TILE_OFFSET + 64]
    if len(raw) != 64:
        return None
    return _placeholder_image(bytes(raw), (object_palettes(rom, room) if palettes is None else palettes)[palette_index]).copy()


@lru_cache(maxsize=32)
def _placeholder_image(raw, colors):
    icon = Image.new('RGBA', (16, 16))
    for i in range(4):
        tile = decode_2bpp(raw[i * 16:(i + 1) * 16])
        ox, oy = (i % 2) * 8, (i // 2) * 8
        for y in range(8):
            for x in range(8):
                icon.putpixel((ox + x, oy + y), (*colors[tile.getpixel((x, y))], 255))
    return icon


@lru_cache(maxsize=1024)
def _compose_sprite(pieces, tile_bytes, palettes, canvas_size):
    lookup = dict(tile_bytes)
    image, _ = compose_oam(pieces, lambda tile, bank: lookup[(tile, bank)],
                           height=16, palettes=palettes)
    if canvas_size is not None:
        width, height = canvas_size
        if image.width > width or image.height > height:
            raise ValueError('Sprite frame exceeds its declared canvas')
        canvas = Image.new('RGBA', canvas_size)
        canvas.alpha_composite(image, ((width-image.width)//2, (height-image.height)//2))
        image = canvas
    return image


def _frame_pieces(raw, source, tile_offset):
    if source.layout == 'single':
        # RenderActiveEntitySprite adds four pixels to X; important when a
        # single item is composed alongside its wing/particle rect records.
        return (OAMSprite(4, 0, (raw[0]+tile_offset)&255, raw[1]),)
    if source.layout == 'pair':
        return tuple(OAMSprite(i*8, 0, (raw[i*2]+tile_offset)&255, raw[i*2+1])
                     for i in range(2))
    signed = lambda value: value-256 if value >= 128 else value
    # RenderActiveEntitySpritesRect records are signed Y, signed X, tile, flags.
    return tuple(OAMSprite(signed(raw[i+1]), signed(raw[i]),
                           (raw[i+2]+tile_offset)&255, raw[i+3])
                 for i in range(0, len(raw), 4) if raw[i+2] != 0xFF)


def _render_frame(rom, room, definition, source, raw, palette_room=None, provider=None, palettes=None):
    fetch, slots = (provider(definition) if provider is not None else room_vram_provider(rom, room, graphics_overrides=definition.graphics_overrides,
                                     graphics_sources=definition.graphics_sources))
    if definition.required_slot is not None:
        selector = slots[definition.required_slot].selector
        if not selector or (definition.required_selector is not None
                            and selector != definition.required_selector):
            return None
    pieces = list(_frame_pieces(raw, source, definition.tile_offset + source.tile_offset))
    for part in definition.parts:
        at, expected = profile.sprite_frame(rom, part.frame.offset, part.frame.expected)
        part_raw = bytes(rom[at:at+len(expected)])
        if part_raw != expected:
            raise ValueError('Multipart frame data differs from the supported ROM')
        pieces.extend(OAMSprite(piece.x + part.x, piece.y + part.y, piece.tile, piece.attributes)
                      for piece in _frame_pieces(part_raw, part.frame,
                                                definition.tile_offset + part.frame.tile_offset))
    pieces = tuple(pieces)
    if not pieces:
        return None
    tiles = {}
    for piece in pieces:
        base, bank = piece.tile & 0xFE, (piece.attributes >> 3) & 1
        for tile in (base, base+1):
            if definition.shared_graphics and (0x20 <= tile < 0x30 or 0x3E <= tile < 0x40 or 0x80 <= tile <= 0xFF):
                tiles[(tile, bank)] = shared_item_tile(rom, tile, bank, overworld=provider is None)
            else:
                tiles[(tile, bank)] = bytes(fetch(tile, bank))
    return _compose_sprite(pieces, tuple(sorted(tiles.items())), (object_palettes(rom, room if palette_room is None else palette_room) if palettes is None else palettes),
                           definition.canvas_size).copy()


@dataclass(frozen=True)
class SpriteRenderResult:
    image: Image.Image | None
    is_placeholder: bool
    message: str = ''


def render_sprite_result(rom, room, sprite_id, frame=None, palette_room=None, *, provider=None, palettes=None):
    """Return a static image plus an inline-friendly explanation of fallbacks."""
    colors_room = room if palette_room is None else palette_room
    definition = SPRITE_DEFINITIONS.get(sprite_id)
    palette = definition.fallback_palette if definition else 0
    if definition is None:
        return SpriteRenderResult(render_placeholder(rom, palette, colors_room, palettes), True,
                                  SPRITE_CONTROLLER_NOTES.get(sprite_id, 'No rendering definition yet.'))
    if sprite_id in SPRITE_CONTROLLER_NOTES and frame is None:
        # Map artwork represents the placed controller, not an entity it may
        # spawn later. Only explicit selector requests show a child frame.
        return SpriteRenderResult(render_placeholder(rom, 0, colors_room, palettes), True,
                                  SPRITE_CONTROLLER_NOTES[sprite_id])
    if definition.overworld_only and provider is not None:
        return SpriteRenderResult(render_placeholder(rom, palette, colors_room, palettes), True,
                                  'Overworld preview only; indoor behavior is not previewed.')
    if sprite_id == 0x61 and room in (0xCE, 0xCF, 0xDE):
        return SpriteRenderResult(render_placeholder(rom, palette, colors_room, palettes), True,
                                  'Invisible desert fall trigger; this room does not draw warp sparkles.')
    selected = definition.display_frame if frame is None else frame
    if not isinstance(selected, int) or not 0 <= selected < len(definition.frames):
        raise ValueError(f'Sprite {sprite_id:02X} frame must be 0–{len(definition.frames)-1}')
    source = definition.frames[selected]
    offset, expected = profile.sprite_frame(rom, source.offset, source.expected)
    raw = bytes(rom[offset:offset + len(expected)])
    message = 'Frame data differs from the supported ROM.'
    parts_match = True
    for part in definition.parts:
        part_at, part_expected = profile.sprite_frame(rom, part.frame.offset, part.frame.expected)
        if bytes(rom[part_at:part_at+len(part_expected)]) != part_expected:
            parts_match = False
            break
    if raw == expected and parts_match:
        message = 'Frame graphics unavailable in this room.'
        rooms = [room]
        if provider is None and definition.room_fallback and room == definition.room_fallback[0]:
            rooms.append(definition.room_fallback[1])
        for graphics_room in rooms:
            try:
                image = _render_frame(rom, graphics_room, definition, source, raw, palette_room=colors_room, provider=provider, palettes=palettes)
                if image is not None:
                    controller_note = SPRITE_CONTROLLER_NOTES.get(sprite_id)
                    message = (f'{source.label}. {controller_note}' if controller_note else
                               source.label if sprite_id in (0x7F, 0x86, 0x87, 0xE5) else '')
                    return SpriteRenderResult(image, False, message)
            except (ValueError, IndexError, KeyError):
                pass
    return SpriteRenderResult(render_placeholder(rom, palette, colors_room, palettes), True, message)


def render_sprite(rom, room, sprite_id, frame=None):
    """Draw ONE configured static frame; optional frame override is preview-only."""
    return render_sprite_result(rom, room, sprite_id, frame).image


def sprite_draw_offset(sprite_id, *, room=None, indoor=False):
    """Offset from the placement cell to the artwork's top-left pixel."""
    definition = SPRITE_DEFINITIONS.get(sprite_id)
    if definition and definition.overworld_only and indoor:
        return (0, 0)
    if sprite_id == 0x61 and room in (0xCE, 0xCF, 0xDE):
        return (0, 0)
    return definition.draw_offset if definition else (0, 0)
