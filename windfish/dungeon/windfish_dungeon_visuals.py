"""CGB dungeon visual-only metatile overrides; physics/object streams stay intact.

Each room has 80 reference objects, 80 visual tiles and 80 override flags.
Runtime changed objects bypass their override, preserving saved/event states.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.compatibility import api as profile

import zlib
from windfish.rom.windfish_room_tiles import _assemble
from windfish.dungeon.windfish_dungeon_storage import group

START=allocation['dungeon_visuals'].start
END=allocation['dungeon_visuals'].end
MARKER=ID_SLOTS['dungeon_visuals']
MAGIC=b'WFDV0001'
KEYS=tuple((g,r) for g,n in (('A',256),('B',256),('Color',22)) for r in range(n))
GATE=0x0AFB
FULL=0x30B3
SCROLL=0x2259
ORIGINALS={GATE:bytes.fromhex('f5 3e 36 ea 00 21 cd d5 72 c3 6e 09'),
           FULL:bytes.fromhex('cd 0f 30'),SCROLL:bytes.fromhex('cb 21 cb 10 cb 21 cb 10')}
HOOKS={GATE:bytes.fromhex('3e 65 ea 00 21 cd 00 7c c3 12 30 00'),
       FULL:bytes((0xCD,GATE&255,GATE>>8)),SCROLL:bytes.fromhex('3e 65 ea 00 21 cd 00 7d')}
# This code is mirrored at the same CPU address in every visual data bank.
# It switches banks in-place only after the destination bank has identical code.
LOOKUP=_assemble([
 'e5 d5 fa a5 db a7',(0x28,'done'),'4e f0 fe a7',(0x28,'done'),
 '7c fe d7',(0x20,'done'),'7d d6 11 fe 80',(0x30,'done'),
 'c6 80 6f 26 7e 7e fe 50',(0x30,'done'),'5f',
 'f0 f7 fe ff',(0x28,'color'),'d6 06 fe 14 16 65',(0x30,'normal'),'16 69',
 ('label','normal'),'f0 f6 07 07 e6 03 82',(0x18,'bank'),
 ('label','color'),'3e 6d',('label','bank'),'ea 00 21',
 'f0 f6 e6 3f 87 6f 26 7e 2a 66 6f 16 00 19 7e b9',(0x20,'done'),
 '11 a0 00 19 7e fe 01',(0x20,'done'),'11 b0 ff 19 4e',
 ('label','done'),'d1 e1 06 00 c9'])
assert len(LOOKUP)<=0x100
SCROLL_CODE=bytes.fromhex('cd 00 7c cb 21 cb 10 cb 21 cb 10 c3 fc 38')
POINTERS=b''.join((0x4000+i*240).to_bytes(2,'little') for i in range(64))
POSITIONS=bytes((y*10+x if x<10 else 255) for y in range(8) for x in range(16))


def enabled(data):return bytes(data[MARKER:MARKER+8])==MAGIC


def room_offset(map_id,room):
    g=group(map_id)
    if not isinstance(room,int) or not 0<=room<(22 if g=='Color' else 256):raise ValueError('Invalid visual room ID.')
    bank=0x6D if g=='Color' else (0x69 if g=='B' else 0x65)+(room>>6)
    return bank*0x4000+(room&63)*240


def _crc(data):return zlib.crc32(data[START:END-0x100])


def _finish(data):data[MARKER+10:MARKER+14]=_crc(data).to_bytes(4,'little')


def validate(data):
    if not enabled(data):
        if bytes(data[MARKER:MARKER+4])==b'WFDV' or bytes(data[GATE:GATE+len(HOOKS[GATE])])==HOOKS[GATE]:
            raise ValueError('Dungeon visual patch marker is missing or unsupported.')
        return False
    from windfish.dungeon.windfish_dungeon_storage import validate as validate_storage
    if len(data)!=0x200000 or not validate_storage(data):raise ValueError('Dungeon visuals require expanded dungeon storage in a 2 MiB ROM.')
    if int.from_bytes(data[MARKER+8:MARKER+10],'little')!=len(KEYS):raise ValueError('Dungeon visual room count mismatch.')
    if int.from_bytes(data[MARKER+10:MARKER+14],'little')!=_crc(data):raise ValueError('Dungeon visual checksum mismatch.')
    hook_code=profile.code(data,'visuals') if profile.is_vwf(data) else HOOKS
    for at,raw in hook_code.items():
        if bytes(data[at:at+len(raw)])!=raw:raise ValueError('Dungeon visual loader is damaged.')
    for bank in (() if profile.is_vwf(data) else range(0x65,0x6E)):
        base=bank*0x4000
        for off,raw in ((0x3C00,LOOKUP),(0x3D00,SCROLL_CODE),(0x3E00,POINTERS),(0x3E80,POSITIONS)):
            if bytes(data[base+off:base+off+len(raw)])!=raw:raise ValueError('Dungeon visual lookup helper is damaged.')
    for g,r in KEYS:
        m=255 if g=='Color' else 6 if g=='B' else 0
        at=room_offset(m,r)
        if any(v not in (0,1,255) for v in data[at+160:at+240]):raise ValueError('Invalid dungeon visual override flag.')
    return True


def install(data):
    if profile.is_vwf(data):
        validate(data)
        if not profile.ready(data):raise ValueError('Reopen the ROM to install the VWF editing engine.')
        return bytearray(data)
    from windfish.rom.windfish_rom import validate as validate_rom
    validate_rom(data)
    if validate(data):return bytearray(data)
    from windfish.dungeon.windfish_dungeon_storage import enabled as storage_enabled
    if not storage_enabled(data):raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    if any(v!=255 for v in data[START:END]):raise ValueError('Dungeon visual banks 65–6D are occupied. No changes made.')
    for at,raw in ORIGINALS.items():
        if bytes(data[at:at+len(raw)])!=raw:raise ValueError(f'Dungeon draw hook differs at {at:04X}; refusing installation.')
    out=bytearray(data)
    hook_code=profile.code(data,'visuals') if profile.is_vwf(data) else HOOKS
    for at,raw in hook_code.items():out[at:at+len(raw)]=raw
    for bank in (() if profile.is_vwf(data) else range(0x65,0x6E)):
        base=bank*0x4000
        for off,raw in ((0x3C00,LOOKUP),(0x3D00,SCROLL_CODE),(0x3E00,POINTERS),(0x3E80,POSITIONS)):
            out[base+off:base+off+len(raw)]=raw
    out[MARKER:MARKER+8]=MAGIC;out[MARKER+8:MARKER+10]=len(KEYS).to_bytes(2,'little');_finish(out)
    validate_rom(out)
    return out


def apply_to_cells(data,map_id,room,cells):
    if not enabled(data):return cells
    at=room_offset(map_id,room)
    return tuple(data[at+80+i] if data[at+160+i]==1 and data[at+i]==value else value for i,value in enumerate(cells))


def paint_cells_changes(data,map_id,room,cells,*,erase=False):
    final={(x,y):tile for x,y,tile in cells}
    for (x,y),tile in final.items():
        if not (isinstance(x,int) and isinstance(y,int) and 0<=x<10 and 0<=y<8 and isinstance(tile,int) and 0<=tile<=255):
            raise ValueError('Choose a room tile: X=0–9, Y=0–7, tile=00–FF.')
    if not validate(data):raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    from windfish.rendering.windfish_dungeon_render import read_room,layout
    record=read_room(data,map_id,room);physical=layout(data,record)
    at=room_offset(map_id,room);out=bytearray(data);touched=set()
    for (x,y),tile in final.items():
        i=y*10+x;out[at+160+i]=0 if erase else 1;touched.add(at+160+i)
        if not erase:
            out[at+i]=physical[i];out[at+80+i]=tile;touched.update((at+i,at+80+i))
    _finish(out);touched.update(range(MARKER+10,MARKER+14))
    return [(offset,data[offset],out[offset]) for offset in sorted(touched) if data[offset]!=out[offset]]


def paint_changes(data,map_id,room,x,y,tile,*,erase=False):
    return paint_cells_changes(data,map_id,room,[(x,y,tile)],erase=erase)
