"""Dungeon Room Properties operations; native tables and guarded stream edits."""
from windfish.compatibility import api as profile

from PIL import Image
import windfish.rendering.windfish_dungeon_render as d
import windfish.dungeon.windfish_dungeon_storage as storage
import windfish.dungeon.windfish_dungeon_visuals as visuals
from windfish.dungeon.windfish_dungeon_properties import room_details,guard_shared
from windfish.overworld.windfish_chests import CHEST_ITEMS


def chest_offset(data,map_id,room):
    d.check_map(map_id)
    if not isinstance(room,int) or not 0<=room<(22 if map_id==255 else 256):raise ValueError('Invalid room.')
    return (0x50860 if map_id==255 else 0x50760 if d.room_bank(map_id)=='B' else 0x50660)+room


def chest_changes(data,map_id,room,item):
    if item not in CHEST_ITEMS:raise ValueError('Unsupported chest reward.')
    at=chest_offset(data,map_id,room)
    return [] if data[at]==item else [(at,data[at],item)]


def replace_stream(data,map_id,room,payload):
    if storage.enabled(data):return storage.replacement_changes(data,map_id,room,payload)
    record=d.read_room(data,map_id,room)
    if len(payload)>record.end-record.start:raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    raw=payload+bytes([255])*(record.end-record.start-len(payload))
    changes=[(record.start+i,data[record.start+i],v) for i,v in enumerate(raw) if data[record.start+i]!=v]
    guard_shared(data,map_id,room,changes);return changes


def warp_changes(data,map_id,room,index=None,values=None,remove=False,expected=None):
    record,objects,warps=room_details(data,map_id,room);original=bytes(data[record.start:record.end]);payload=bytearray(original)
    if expected is not None and expected!=(record.start,original):raise ValueError('Room data changed. Select the warp again.')
    if index is None:
        if len(warps)>=4:raise ValueError('A room supports at most four warp records.')
        payload[-1:]=bytes((0xE0,0,0,0x50,0x70,254))
    else:
        if not isinstance(index,int) or not 0<=index<len(warps):raise ValueError('Select a warp.')
        row=warps[index];raw=bytes.fromhex(row[-1]);offset=int(row[1],16)-record.start
        if remove:payload[offset:offset+5]=b''
        else:
            if values is None or len(values)!=5 or any(not isinstance(v,int) or not 0<=v<=255 for v in values) or values[0]>3:raise ValueError('Type must be 00–03; other fields must be hex bytes 00–FF.')
            if values[0]==3 and raw[0]!=0xE3:raise ValueError('Reserved warp type 03 can only be preserved.')
            new=bytes((0xE0|values[0],*values[1:]));payload[offset:offset+5]=new
    return replace_stream(data,map_id,room,bytes(payload))


def clear_changes(data,map_id,room):
    """Pass-through floor 00, no template; retain CGB artwork and all warps."""
    record=d.read_room(data,map_id,room)
    visible=visuals.apply_to_cells(data,map_id,room,d.layout(data,record))
    trial=bytearray(data)
    if not storage.enabled(trial):trial=storage.install(trial)
    if not visuals.enabled(trial):trial=visuals.install(trial)
    record=d.read_room(trial,map_id,room)
    payload=bytes((record.animation,0xF0))+b''.join(record.warps)+b'\xfe'
    for at,old,new in storage.replacement_changes(trial,map_id,room,payload):trial[at]=new
    for at,old,new in visuals.paint_cells_changes(trial,map_id,room,[(i%10,i//10,t) for i,t in enumerate(visible)]):trial[at]=new
    return [(i,old,new) for i,(old,new) in enumerate(zip(data,trial)) if old!=new]


def sprite_index(map_id,room):
    d.check_map(map_id)
    if not isinstance(room,int) or not 0<=room<(22 if map_id==255 else 256):raise ValueError('Invalid room.')
    return (768 if map_id==255 else 512 if d.room_bank(map_id)=='B' else 256)+room


def clear_room_changes(data,map_id,room):
    """Blank template 00/floor 00; remove contents, warps, sprites and event."""
    import windfish.rom.windfish_sprite_storage as s
    from windfish.dungeon.windfish_dungeon_events import event_offset
    if not storage.enabled(data) or not visuals.enabled(data) or not s.enabled(data):
        raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    trial=bytearray(data)
    for at,old,new in storage.replacement_changes(trial,map_id,room,b'\x00\x00\xfe'):trial[at]=new
    for at,old,new in visuals.paint_cells_changes(trial,map_id,room,[(x,y,0) for y in range(8) for x in range(10)],erase=True):trial[at]=new
    lists=s.read_lists(trial,True);lists[sprite_index(map_id,room)]=[]
    trial[s.EXTENDED:s.END]=s._pack(lists).ljust(s.END-s.EXTENDED,b'\0')
    trial[event_offset(trial,map_id,room)]=0
    trial[chest_offset(trial,map_id,room)]=0
    return [(at,old,new) for at,(old,new) in enumerate(zip(data,trial)) if old!=new]


def sprites(data,map_id,room):
    import windfish.rom.windfish_sprite_storage as s
    s.validate_mode(data)
    return tuple(s.read_lists(data,s.enabled(data))[sprite_index(map_id,room)])


def sprite_changes(data,map_id,room,index=None,values=None,remove=False,expected=None):
    import windfish.rom.windfish_sprite_storage as s
    if not s.enabled(data):raise ValueError('Enable expanded sprite storage before editing sprites.')
    s.validate_mode(data);lists=s.read_lists(data,True);key=sprite_index(map_id,room);entries=lists[key]
    if expected is not None and tuple(entries)!=expected:raise ValueError('Sprites changed. Select the sprite again.')
    if remove:
        if index is None or not 0<=index<len(entries):raise ValueError('Select a sprite.')
        del entries[index]
    else:
        if values is None or len(values)!=3:raise ValueError('Enter X, Y and sprite ID.')
        x,y,tile=values
        if not 0<=x<10 or not 0<=y<8 or not 0<=tile<255:raise ValueError('X must be 0–9, Y 0–7 and ID 00–FE.')
        if index is None:
            from windfish.rom.windfish_sprite_limits import check_room_sprite_count
            check_room_sprite_count(len(entries), len(entries) + 1)
            entries.append((y*16+x,tile))
        elif not 0<=index<len(entries):raise ValueError('Select a sprite.')
        else:entries[index]=(y*16+x,tile)
    packed=s._pack(lists).ljust(s.END-s.EXTENDED,b'\0')
    return [(s.EXTENDED+i,data[s.EXTENDED+i],v) for i,v in enumerate(packed) if data[s.EXTENDED+i]!=v]


def loaded_sprite_graphics(data,map_id,room):
    from windfish.rendering.windfish_sprite_graphics import graphics_source_offset,COLORS
    sprite_index(map_id,room)
    if map_id==255:
        sources=[];selectors=[]
        for base in (0x806AA,0x806D6,0x80702,0x8072E):
            page,bank=data[base+room*2:base+room*2+2]
            selectors.append((page,bank));sources.append(bank*0x4000+page*256-0x4000 if bank else None)
        group=None
    else:
        group=data[profile.bank20_table(data,0x830DB)+(512 if d.room_bank(map_id)=='B' else 256)+room]
        if map_id==0x10 and room==0xB5:group=0x3D
        selectors=tuple(data[profile.bank20_table(data,0x83643)+group*4:profile.bank20_table(data,0x83643)+group*4+4])
        sources=[graphics_source_offset(data,value) for value in selectors]
    raw=b''.join(bytes(256) if at is None else bytes(data[at:at+256]) for at in sources)
    if len(raw)!=1024:raise ValueError('Missing sprite graphics block.')
    from windfish.rendering.windfish_sprite_graphics import RoomSpriteGraphics
    return RoomSpriteGraphics(group,tuple(selectors),tuple(sources),raw)


def sprite_graphics(data,map_id,room):
    from windfish.rendering.windfish_sprite_graphics import COLORS
    loaded=loaded_sprite_graphics(data,map_id,room)
    raw=loaded.graphics
    image=Image.new('RGB',(128,32));pixels=image.load()
    for tile in range(64):
        for y in range(8):
            lo,hi=raw[tile*16+y*2:tile*16+y*2+2]
            for x in range(8):pixels[tile%16*8+x,tile//16*8+y]=COLORS[((lo>>(7-x))&1)|(((hi>>(7-x))&1)<<1)]
    return image,loaded.bank_id,loaded.selectors,loaded.offsets
