"""Native inventory dungeon map tables, separate from room-ID layouts.

English Rev2 loader at A72A selects A49A + map*64, A69A collapsed,
or A6DA Color. Visited-room shapes are generated from saved door flags.
"""
from PIL import Image

BASE=0xA49A
SUPPORTED=tuple(range(8))+(12,255)
BRUSHES=(0x7D,0xEF,0xED,0xEE)+tuple(range(0xD0,0xE0))
LABELS={0x7D:'Blank',0xEF:'Room',0xED:'Chest marker',0xEE:'Nightmare boss marker'}


def record(data,layout_id):
    if layout_id not in SUPPORTED:raise ValueError('This layout has no separate native inventory map table. Choose dungeon 00–07, collapsed Eagle’s Tower, or Color Dungeon.')
    # Verify actual Rev2 loader operands before editing the table.
    if bytes(data[0xA72A:0xA72D])!=bytes.fromhex('21 9a 64') or bytes(data[0xA733:0xA736])!=bytes.fromhex('21 da 66'):
        raise ValueError('Inventory map loader differs from the supported ROM.')
    index=9 if layout_id==255 else 8 if layout_id==12 else layout_id
    at=BASE+index*64;raw=bytes(data[at:at+64])
    if len(raw)!=64:raise ValueError('Incomplete inventory map table.')
    return at,raw


def changes(data,layout_id,values,expected=None):
    at,raw=record(data,layout_id)
    if expected is not None and expected!=(at,raw):raise ValueError('Inventory map changed. Select the dungeon again to reload it.')
    values=tuple(values)
    if len(values)!=64 or any(v not in BRUSHES for v in values):raise ValueError('Use the supported room, marker, blank or doorway-shape tiles on all 64 cells.')
    return [(at+i,old,new) for i,(old,new) in enumerate(zip(raw,values)) if old!=new]


def tile_image(data,tile):
    if tile not in BRUSHES:raise ValueError('Unsupported map tile.')
    # Signed BG tile IDs: D0–EF at VRAM 8D00–8EFF, loaded from bank 32.
    at=0xCBE00+(tile-0xD0)*16 if tile!=0x7D else 0xBD7D0
    raw=data[at:at+16]
    if len(raw)!=16:raise ValueError('Map graphics are outside the ROM.')
    colors=((248,248,216),(176,176,168),(112,112,128),(40,40,64))
    image=Image.new('RGB',(8,8))
    for y in range(8):
        lo,hi=raw[y*2:y*2+2]
        for x in range(8):image.putpixel((x,y),colors[((lo>>(7-x))&1)|(((hi>>(7-x))&1)<<1)])
    return image
