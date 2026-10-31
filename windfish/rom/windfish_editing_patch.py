"""Atomic aggregate installation of Windfish's required editing capabilities."""
from windfish.rom.windfish_rom import RomDocument,validate,expand_to_2mib
import windfish.rom.windfish_palette_patch as palettes
import windfish.rom.windfish_sprite_storage as sprites
import windfish.rom.windfish_collision_storage as collisions
import windfish.rom.windfish_bg_graphics as bg
import windfish.rom.windfish_room_tiles as tiles
import windfish.rom.windfish_room_graphics as graphics
import windfish.dungeon.windfish_dungeon_storage as dungeons
import windfish.dungeon.windfish_dungeon_visuals as visuals
import windfish.rom.windfish_shared_map16 as shared

import windfish.rom.windfish_script_engine as custom

NAME='expanded-editing-capabilities-patch'


def validate_palettes(data):
    from windfish.compatibility import api as profile
    custom.require_profile(data)
    if profile.is_vwf(data):
        profile.check_code(data,'palettes')
        if data[palettes.MARKER]!=1:raise ValueError('VWF palette expansion marker is damaged.')
        return True
    flag=data[palettes.MARKER] if len(data)>palettes.MARKER else 0
    if flag not in (0,1):raise ValueError('Unknown palette expansion marker.')
    if not flag:return False
    for at,raw in shared.adapt_code(data,palettes.code(False)).items():
        if bytes(data[at:at+len(raw)])!=raw:raise ValueError(f'Palette engine is damaged at {at:06X}.')
    return True


def missing_components(data):
    validate(data)
    from windfish.compatibility import api as profile
    from windfish.rom.windfish_layout import installed
    if not installed(data):return ('Windfish expanded ROM format',)
    if profile.is_vwf(data) and not profile.ready(data):return ('VWF expanded editing engine',)
    states=(('2 MiB ROM',len(data)==0x200000),
            ('Expanded palettes',validate_palettes(data)),
            ('Expanded sprite placements',sprites.validate_mode(data)),
            ('Expanded overworld collisions',collisions.validate_mode(data)),
            ('Room BG selection',bg.enabled(data)),
            ('Custom 16×16 sets',tiles.version(data)==2),
            ('Reusable ExGFX',graphics.version(data)==3),
            ('Expanded dungeon storage',dungeons.validate(data)),
            ('Dungeon Direct Draw',visuals.validate(data)),
            ('Shared Map16 collision control',shared.validate(data) and shared.version(data)==7),
            ('Custom Collision API runtime',custom.validate(data)))
    return tuple(label for label,ready in states if not ready)


def install(data):
    """Return a fully validated private buffer; never alter the supplied ROM."""
    from windfish.compatibility import api as profile
    custom.require_profile(data)
    if profile.is_vwf(data):
        out=profile.install(data)
        from windfish.rom import windfish_layout as layout
        out=shared.install(out)
        layout.seal(out);palettes.fix_checksums(out)
        if missing_components(out):raise ValueError('VWF installation is incomplete.')
        return out
    missing=missing_components(data)
    if not missing:return bytearray(data)
    from windfish.rom import windfish_layout as layout
    out=layout.initialize(expand_to_2mib(data))
    if not palettes.is_installed(out):out=palettes.install_patch(out)
    if not sprites.enabled(out):out=sprites.install_or_enable(out)
    if not collisions.enabled(out):out=collisions.install(out)
    out=bg.install(out)
    out=tiles.install(out)
    out=graphics.install(out)
    out=dungeons.install(out)
    out=visuals.install(out)
    out=shared.install(out)
    out=custom.install(out)
    layout.seal(out)
    palettes.fix_checksums(out)
    if missing_components(out):raise ValueError('Editing capability installation is incomplete; no changes were applied.')
    return out


def open_document(path,confirm):
    """A rejected/failed upgrade leaves both disk and the active document alone."""
    document=RomDocument(path)
    if document.format_converted and not confirm(('Update previous Windfish format/runtime',),len(document.data)):return None
    missing=missing_components(document.data)
    if missing:
        if not confirm(missing,len(document.data)):return None
        document.data=install(document.data)
    return document
