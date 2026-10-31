"""Format-3 allocation contract with identifiers in original-ROM bank 3F.

Expanded data/code allocations retain their addresses. The old bank-78 header
is retired and kept reserved. File-open conversion handles known native
format-1/2 engine revisions without moving room data, graphics or scripts.
"""
from dataclasses import dataclass

from windfish.rom import windfish_identifiers as identifiers
FORMAT_VERSION=identifiers.FORMAT_VERSION
HEADER=identifiers.START
MAGIC=b'WINDFISH'
HEADER_BYTES=identifiers.HEADER

@dataclass(frozen=True)
class Region:
    name:str
    start:int
    end:int
    fill:int=255

REGIONS=(
    Region('exgfx',0x100000,0x120000),
    Region('metatiles',0x120000,0x180000),
    Region('dungeon_rooms',0x180000,0x194000),
    Region('dungeon_visuals',0x194000,0x1B8000),
    Region('graphics_engine',0x1B8000,0x1BC000),
    Region('tile_gateway',0x1BC000,0x1C0000),
    Region('profile_metadata',0x1C0000,0x1C4000),
    Region('sprite_storage',0x1C4000,0x1C8000,0),
    Region('collision_storage',0x1C8000,0x1D0000,0),
    Region('palettes_and_bg',0x1D0000,0x1D4000,0),
    Region('bg_import_blocks',0x1D4000,0x1D8000,0),
    Region('shared_map16_engine',0x1D8000,0x1DC000),
    Region('custom_collisions',0x1DC000,0x1E0000),
    Region('reserved_bank_78',0x1E0000,0x1E4000),
    Region('shared_map16_rooms',0x1E4000,0x1F4000),
    Region('platform_engine',0x1F4000,0x1F8000),
    Region('persistence_engine',0x1F8000,0x1FC000),
    Region('additional_dialogs',0x1FC000,0x200000),
)
BY_NAME={r.name:r for r in REGIONS}

def check_map():
    ordered=sorted(REGIONS,key=lambda r:r.start)
    if len(BY_NAME)!=len(REGIONS):raise ValueError('Duplicate allocation name.')
    for r in ordered:
        if not 0x100000<=r.start<r.end<=0x200000:raise ValueError('Allocation outside expanded ROM.')
    for a,b in zip(ordered,ordered[1:]):
        if a.end>b.start:raise ValueError(f'Allocation overlap: {a.name} and {b.name}.')
    return True

def installed(data):return identifiers.installed(data)

def reject_old(data):
    identifiers.reject_patches(data)
    identifiers.validate(data)
    if installed(data):return
    if len(data)>0x1E0008 and bytes(data[0x1E0000:0x1E0008])==MAGIC:
        raise ValueError('Previous Windfish ROM: open it through File → Open ROM to convert its identifiers.')

def initialize(data):
    """Prepare a private fresh expansion; never replace an existing layout."""
    check_map();reject_old(data)
    out=bytearray(data)
    if installed(out):return out
    if len(out)!=0x200000:raise ValueError('Windfish requires a 2 MiB expansion.')
    if any(v!=255 for v in out[0x100000:]):
        raise ValueError('Expanded ROM space is occupied by an unknown format.')
    for r in REGIONS:
        if r.fill!=255:out[r.start:r.end]=bytes((r.fill,))*(r.end-r.start)
    seal(out)
    return out

def seal(data):identifiers.initialize(data)

check_map()
