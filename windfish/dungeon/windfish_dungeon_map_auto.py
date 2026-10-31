"""Generate native map/compass artwork from assigned dungeon rooms.

Visited-room doorway shapes remain the game's responsibility: those depend on
save progress, rather than this ROM map table. No save file is needed here.
"""
import windfish.rendering.windfish_dungeon_render as dungeon
import windfish.rom.windfish_sprite_storage as sprites
from windfish.dungeon.windfish_dungeon_room_data import sprite_index
from windfish.dungeon.windfish_dungeon_events import event_offset

BOSSES=frozenset((0x59,0x5A,0x5B,0x5C,0x5D,0x62,0x63,0x65,0xF9))


def generate(data,layout_id,rooms):
    rooms=tuple(rooms)
    if len(rooms) != 64:
        raise ValueError('A map must contain 64 room cells.')
    context=6 if layout_id==12 else layout_id
    sprites.validate_mode(data)
    lists=sprites.read_lists(data,sprites.enabled(data))
    # Keep native proxy markers (side-view bosses and scripted chests) tied to
    # their room IDs when moving rooms. Side-view spaces are not map squares.
    from windfish.dungeon.windfish_dungeon_metadata import layout_record
    from windfish.dungeon.windfish_dungeon_minimap import record as map_record
    original=layout_record(data,layout_id)[1]
    artwork=map_record(data,layout_id)[1]
    markers={room:tile for i,(room,tile) in enumerate(zip(original,artwork))
             if (room or layout_id==255 and i==25) and tile in (0xED,0xEE)}
    sideview=dungeon.sideview_rooms(data,context)
    result = []
    cache = {}
    for i,room in enumerate(rooms):
        if room==0 and not (layout_id==255 and i==25):
            result.append(0x7D)
            continue
        if room not in cache:
            record=dungeon.read_room(data,context,room)
            boss=any(entity in BOSSES for xy,entity in lists[sprite_index(context,room)])
            chest=any(obj==0xA0 for xy,obj,length,vertical in record.objects)
            chest=chest or data[event_offset(data,context,room)]&0xE0==0x60
            cache[room]=0x7D if room in sideview else markers.get(room,0xEE if boss else 0xED if chest else 0xEF)
        result.append(cache[room])
    return tuple(result)


# Low-nibble room flags -> native visited-room tile offsets (minimap.asm).
DOOR_SHAPES=(0,2,3,7,5,10,11,15,4,8,9,14,6,12,13,1)
DOOR_FLAGS={**{obj:(4,8,2,1)[(obj-0xEC)%4] for obj in range(0xEC,0xF8)},
            0xF8:4,0xFC:8,0xFD:1}


def completed(data,layout_id,rooms,tiles=None):
    """Simulate completed native door flags; never write progress or ROM tables.

Includes explicit door macros, entrance quirks, template/placed bomb walls,
plus reciprocal flags written by completed locked-door/bomb-wall events.
Arbitrary entity scripts that rewrite room objects are not executed.
"""
    rooms=tuple(rooms)
    base=generate(data,layout_id,rooms) if tiles is None else tuple(tiles)
    if len(base) != 64:
        raise ValueError('A map must contain 64 artwork cells.')
    context=6 if layout_id==12 else layout_id
    templates = dungeon.templates(data)
    doors = dungeon.doors(data)
    physics=0x20CD4 if context==255 else 0x20BD4
    masks = [0] * 64
    propagate = [0] * 64
    for i,(room,tile) in enumerate(zip(rooms,base)):
        if tile == 0x7D:
            continue
        record=dungeon.read_room(data,context,room)
        for xy,obj,length,vertical in record.objects:
            flag = DOOR_FLAGS.get(obj, 0)
            masks[i] |= flag
            if 0xEC <= obj <= 0xEF or obj == 0xF8:
                propagate[i] |= flag
        # Bomb code adds the indoor offset (100); Color uses its next table.
        for obj in dungeon.layout(data,record,templates,doors):
            value=data[physics+obj]
            if 0x99<=value<=0x9C:
                flag=(4,8,2,1)[value-0x99]
                masks[i] |= flag
                propagate[i] |= flag
    for i,flags in enumerate(propagate):
        for flag,delta,opposite in ((4,-8,8),(8,8,4),(2,-1,1),(1,1,2)):
            if not flags & flag:
                continue
            j=i+delta
            # Match engine's linear map-position arithmetic, including row wrap.
            if 0 <= j < 64 and base[j] != 0x7D:
                masks[j] |= opposite
    return tuple(0x7D if tile==0x7D else 0xD0+DOOR_SHAPES[mask] for tile,mask in zip(base,masks))


def with_markers(layout_id, rooms, tiles, markers):
    """Apply explicit room-linked native artwork without marking filler cells.

    Overrides live in the editor draft and persist as ordinary map-table bytes;
    no custom ROM metadata is installed. Room keys keep markers with rooms when
    a draft assignment moves to another cell.
    """
    rooms = tuple(rooms)
    result = list(tiles)
    if len(rooms) != 64 or len(result) != 64:
        raise ValueError('A map must contain 64 cells.')
    for index, room in enumerate(rooms):
        if room == 0 and not (layout_id == 255 and index == 25):
            result[index] = 0x7D
        elif room in markers:
            tile = markers[room]
            if tile not in (0x7D, 0xEF, 0xED, 0xEE):
                raise ValueError('Unsupported room marker.')
            result[index] = tile
    return tuple(result)
