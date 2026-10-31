"""Validated Rev2 ROM documents, format conversion and atomic saves."""
from pathlib import Path
from hashlib import sha256
import os
import tempfile
from windfish.rendering.windfish_overworld_render import direct_map

SIZE = 0x100000
EXPANDED_SIZE = 0x200000
SUPPORTED_SIZES = (SIZE,EXPANDED_SIZE)


def validate(data):
    from windfish.rom.windfish_engine_revisions import reject_unsupported
    reject_unsupported(data)
    from windfish.rom.windfish_layout import reject_old
    reject_old(data)
    from windfish.compatibility import api as profile
    vwf=profile.is_vwf(data)
    if vwf:
        profile.validate_identity(data)
        if not profile.ready(data):return
    if not vwf and (len(data) not in SUPPORTED_SIZES or data[0x14C] != 2 or data[0x143] not in (0x80, 0xC0) or data[0x13F:0x143] != b'AZLE'):
        raise ValueError('Expected a 1 or 2 MiB English Link’s Awakening DX Rev 2 ROM (AZLE, revision 02).')
    if data[0x148] != (5 if len(data)==SIZE else 6):
        raise ValueError('ROM size does not match its cartridge header.')
    from windfish.rom import windfish_dialogue_expansion
    windfish_dialogue_expansion.records(data)
    from windfish.rom.windfish_identifiers import reject_patches
    reject_patches(data)
    from windfish.rom import windfish_layout as layout
    from windfish.rom import windfish_sprite_storage as sprites
    if len(data)==SIZE or layout.installed(data):sprites.validate_mode(data)
    from windfish.rom.windfish_collision_storage import validate_mode
    validate_mode(data)
    from windfish.rom.windfish_bg_graphics import validate as validate_bg
    validate_bg(data)
    from windfish.rom.windfish_room_tiles import validate as validate_tiles
    validate_tiles(data)
    from windfish.rom.windfish_room_graphics import validate as validate_graphics
    validate_graphics(data)
    from windfish.dungeon.windfish_dungeon_storage import validate as validate_dungeons
    validate_dungeons(data)
    from windfish.dungeon.windfish_dungeon_visuals import validate as validate_dungeon_visuals
    validate_dungeon_visuals(data)
    from windfish.rom.windfish_shared_map16 import validate as validate_shared
    validate_shared(data)
    if layout.installed(data):
        from windfish.rom.windfish_editing_patch import validate_palettes
        validate_palettes(data)


def expand_to_2mib(data):
    """Return a new buffer; preserve every original byte except size/checksums."""
    validate(data)
    if data[0x147]!=0x1B:raise ValueError('Expansion requires the original MBC5+RAM+battery cartridge type (1B).')
    if len(data)==EXPANDED_SIZE:return bytearray(data)
    out=bytearray(data)
    out.extend(bytes([0xFF])*(EXPANDED_SIZE-len(out)))
    out[0x148]=6
    from windfish.rom.windfish_palette_patch import fix_checksums
    fix_checksums(out)
    validate(out)
    return out


class RomDocument:
    def __init__(self, path):
        self.path = Path(path)
        original = self.path.read_bytes()
        from windfish.rom.windfish_format_conversion import convert
        prepared=convert(original)
        self.format_converted=prepared!=original
        validate(prepared)
        from windfish.rom import windfish_layout as layout
        if len(prepared)==EXPANDED_SIZE and not layout.installed(prepared) and any(v!=255 for v in prepared[SIZE:]):
            raise ValueError('Unrecognized Windfish expanded format. Start from an original native English Rev2 ROM or a supported Windfish ROM.')
        self.original = original
        self.data = bytearray(prepared)
        self.saved_snapshot = bytes(original)

    @property
    def dirty(self):
        return self.data != self.saved_snapshot

    def set_direct_tile(self, room, x, y, tile, alternate=False):
        """Modify one visual tile map byte in memory; no object-stream update."""
        if not (0 <= x < 10 and 0 <= y < 8 and 0 <= tile <= 255):
            raise ValueError('x must be 0..9, y 0..7, tile 0..255')
        if alternate and room not in (0x06, 0x0E, 0x1B, 0x2B, 0x79, 0x8C):
            raise ValueError('No alternate map for this room')
        start, _ = direct_map(self.data, room, special=alternate)
        offset = start + y * 10 + x
        before = self.data[offset]
        self.data[offset] = tile
        return offset, before, tile

    def changed_offsets(self):
        return [i for i, (a, b) in enumerate(zip(self.saved_snapshot, self.data)) if a != b]

    def _verified_atomic_write(self, target, *, overwrite):
        """Write in same directory, verify, then replace destination atomically."""
        target = Path(target)
        from windfish.rom.windfish_palette_patch import fix_checksums
        from windfish.rom.windfish_palette_effects import refresh
        refresh(self.data)
        fix_checksums(self.data)
        content = bytes(self.data)
        validate(content)
        if not overwrite and target.exists():
            raise FileExistsError(f'Output already exists: {target}')
        fd, tmp = tempfile.mkstemp(prefix='.windfish-', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if Path(tmp).read_bytes() != content:
                raise IOError('Temporary ROM verification failed')
            # Save As must not silently overwrite an existing ROM.
            if not overwrite:
                try:
                    os.link(tmp, target)
                except FileExistsError:
                    raise FileExistsError(f'Output already exists: {target}')
                except OSError:
                    # Windows may not permit hard-link creation; use exclusive
                    # creation there instead. An interrupted write could leave
                    # a partial NEW file, never an overwritten existing ROM.
                    with target.open('xb') as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
            else:
                os.replace(tmp, target)
            if target.read_bytes() != content:
                raise IOError('Saved ROM verification failed')
            self.saved_snapshot = content
            return target
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def save(self):
        """Save to the currently active ROM file."""
        return self._verified_atomic_write(self.path, overwrite=True)

    def save_as(self, path):
        """Save to a NEW ROM file, which becomes the active document."""
        target = Path(path)
        if target.resolve() == self.path.resolve():
            return self.save()
        result = self._verified_atomic_write(target, overwrite=False)
        self.path = result
        return result

    def report(self):
        return {'source_sha256': sha256(self.original).hexdigest(),
                'current_sha256': sha256(self.data).hexdigest(),
                'modified_offsets': self.changed_offsets()}
