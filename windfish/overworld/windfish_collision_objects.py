"""Lossless room-object stream reader and bounded clearing for overworld rooms.

Entries retain ROM order. Baseline macro expansion and bounded editing are supported.
Runtime saved-game state is not simulated.
"""
from dataclasses import dataclass
from windfish.overworld.windfish_collision_definitions import OBJECT_NAMES, MACRO_BOUNDS, SINGLE_ONLY, ENTRANCE_OBJECTS, entrance_count

from windfish.rom.windfish_collision_storage import (ALTERNATE_POINTERS, enabled as expanded_storage,
    resolve_stream, replacement_changes)


@dataclass(frozen=True)
class Entry:
    offset: int
    raw: bytes
    kind: str

    def describe(self):
        if self.kind == 'warp':
            return f'Warp {self.raw.hex(" ").upper()} (preserved)'
        pos, obj = self.raw[-2:]
        run = ''
        if len(self.raw) == 3:
            run = f'  {"horizontal" if self.raw[0] & 0x40 == 0 else "vertical"} ×{self.raw[0] & 15}'
        macro = '  macro' if obj >= 0xF5 else ''
        return f'ID {obj:02X}  X={pos & 15:X} Y={pos >> 4:X}{run}{macro}'

@dataclass(frozen=True)
class RoomObjects:
    start: int
    end: int
    header: bytes
    entries: tuple


def read_room_objects(data, room, alternate=False):
    if not 0 <= room <= 255:
        raise ValueError('Invalid overworld room')
    if expanded_storage(data):
        start,limit=resolve_stream(data,room,alternate)
    else:
        pointer = ALTERNATE_POINTERS[room] if alternate and room in ALTERNATE_POINTERS else 0x24000 + room * 2
        bank = 0x68000 if room >= 0x80 else 0x24000
        addr = int.from_bytes(data[pointer:pointer + 2], 'little')
        if not 0x4000 <= addr < 0x8000:
            raise ValueError('Invalid room pointer')
        start = bank + addr - 0x4000
        limit = min(bank + 0x4000, len(data))
    if start + 2 >= limit or data[start] == 0xFE:
        raise ValueError('Missing room header')
    entries = []
    p = start + 2
    while p < limit:
        tag = data[p]
        if tag == 0xFE:
            return RoomObjects(start, p + 1, bytes(data[start:start + 2]), tuple(entries))
        warp = tag & 0xFC == 0xE0
        size = 5 if warp else (3 if tag & 0x90 == 0x80 else 2)
        if p + size >= limit:
            raise ValueError('Truncated room object stream')
        entries.append(Entry(p, bytes(data[p:p + size]), 'warp' if warp else 'object'))
        p += size
    raise ValueError('Missing room terminator')


def clear_room_objects(data, room, alternate=False):
    """Remove placements, use pass-through floor 01, preserve animation and warps.

Never relocate or grow a stream. Reject shared/overlapping room streams before
    writing so another room cannot be changed implicitly.
    """
    target = read_room_objects(data, room, alternate)
    if expanded_storage(data):
        payload=bytes([target.header[0],1])+b''.join(e.raw for e in target.entries if e.kind=='warp')+b'\xFE'
        changes=replacement_changes(data,room,alternate,payload)
        for at,old,new in changes:data[at]=new
        return target
    key = (room, bool(alternate and room in ALTERNATE_POINTERS))
    for other in range(256):
        for alt in ((False, True) if other in ALTERNATE_POINTERS else (False,)):
            if (other, alt) == key:
                continue
            candidate = read_room_objects(data, other, alt)
            if target.start < candidate.end and candidate.start < target.end:
                raise ValueError(f'Room data is shared with or overlaps room {other:02X}' + (' alternate' if alt else '') + '. Clearing requires separate storage first.')
    payload = bytes([target.header[0], 0x01]) + b''.join(e.raw for e in target.entries if e.kind == 'warp') + b'\xFE'
    if len(payload) > target.end - target.start:
        raise ValueError('Cleared stream would exceed original storage')
    data[target.start:target.start + len(payload)] = payload
    return target

# Offset-list addresses in bank 24; tile IDs immediately follow each FF sentinel.
MACRO_TABLES = {0xF6: 0x762E, 0xF7: 0x765A, 0xF8: 0x760B,
                0xF9: 0x767A, 0xFA: 0x7694, 0xFB: 0x76B7,
                0xFC: 0x76CD, 0xFD: 0x76F7}

def snapshot_capacities(data):
    streams = {}
    for room in range(256):
        for alt in ((False, True) if room in ALTERNATE_POINTERS else (False,)):
            stream = read_room_objects(data, room, alt)
            streams[room, alt] = stream
    return streams


COLLISION_TYPES = {f'{OBJECT_NAMES.get(obj,"Tile")} — {obj:02X}':obj for obj in range(0xFE)}


def placement_bytes(x,y,object_id,direction='Single',length=1):
    if not (0<=x<10 and 0<=y<8):raise ValueError('Position must be within the 10×8 room')
    if not 0<=object_id<=0xFD:raise ValueError('FE and FF are reserved, not drawable object IDs')
    if direction not in ('Single','Horizontal','Vertical'):raise ValueError('Invalid placement direction')
    if not 1<=length<=15:raise ValueError('Length must be between 1 and 15')
    if object_id in SINGLE_ONLY and (direction!='Single' or length!=1):
        raise ValueError('This entrance or macro uses Single placement; only Tree macros support strips')
    count=1 if direction=='Single' else length
    if object_id==0xF5:
        width,height=(2,2*count) if direction=='Vertical' else (2*count,2)
        bounds=(0,0,width-1,height-1)
    else:
        bounds=MACRO_BOUNDS.get(object_id,(0,0,(count-1 if direction=='Horizontal' else 0),(count-1 if direction=='Vertical' else 0)))
    left,top,right,bottom=bounds
    if x+left<0 or y+top<0 or x+right>=10 or y+bottom>=8:
        raise ValueError('The entire object or macro footprint must fit inside this room')
    if direction=='Single':return bytes([y*16+x,object_id])
    return bytes([(0x80 if direction=='Horizontal' else 0xC0)|length,y*16+x,object_id])



def clipped_placement_records(data, room, alternate, x, y, object_id, direction='Single', length=1):
    """Encode an in-room footprint; flatten only presets cut by a room edge."""
    try:
        return [placement_bytes(x,y,object_id,direction,length)]
    except ValueError:
        # Validate non-geometric settings independently of the footprint.
        if not (0<=x<10 and 0<=y<8):raise
        if not 0<=object_id<=0xFD:raise
        if direction not in ('Single','Horizontal','Vertical') or not 1<=length<=15:raise
        if object_id in SINGLE_ONLY and (direction!='Single' or length!=1):raise
    count=1 if direction=='Single' else length
    if object_id<0xF5:
        count=min(count,(8-y) if direction=='Vertical' else (10-x))
        return [placement_bytes(x,y,object_id,direction,count)]
    cells,_=expanded_cells(data,room,alternate)
    output={}
    def put(xx,yy,tile):
        if 0<=xx<10 and 0<=yy<8:
            cells[yy*10+xx]=tile;output[xx,yy]=tile
    if object_id==0xF5:
        for n in range(count):
            xx=x+(2*n if direction=='Horizontal' else 0)
            yy=y+(2*n if direction=='Vertical' else 0)
            for dx,dy,base,overlap,bush in ((0,0,0x25,0x29,None),(1,0,0x26,0x2A,None),
                                           (0,1,0x27,0x2A,0x82),(1,1,0x28,0x29,0x83)):
                if not (0<=xx+dx<10 and 0<=yy+dy<8):continue
                old=cells[(yy+dy)*10+xx+dx]
                put(xx+dx,yy+dy,bush if bush is not None and old>=0x8A else overlap if old>=0x10 else base)
    else:
        at=0x90000+MACRO_TABLES[object_id]-0x4000
        offsets=[]
        while data[at]!=255:offsets.append(data[at]);at+=1
        for i,delta in enumerate(offsets):
            # Negative-left macros encode a signed linear displacement.
            if delta>=128:delta-=256
            dy,dx=divmod(delta,16)
            if dx>7:dx-=16;dy+=1
            put(x+dx,y+dy,data[at+1+i])
    from windfish.overworld.windfish_collision_recalculate import minimum_records
    return minimum_records({p:t for p,t in output.items() if t not in ENTRANCE_OBJECTS}) + [
        placement_bytes(xx,yy,t) for (xx,yy),t in output.items() if t in ENTRANCE_OBJECTS]


def solid_changes(data, room, alternate, x, y, capacities):
    return collision_changes(data, room, alternate, x, y, capacities)


def validate_entrance_change(stream,new_obj=None,index=None,delete=False):
    warps=[e for e in stream.entries if e.kind=='warp']
    existing=[(i,entrance_count(e.raw[-1])) for i,e in enumerate(stream.entries) if e.kind=='object']
    total=sum(count for i,count in existing if i!=index)+(0 if delete or new_obj is None else entrance_count(new_obj))
    if not 1<=len(warps)<=4 or total>len(warps) or any(e.raw[0] not in (0xE0,0xE1,0xE2) for e in warps):
        raise ValueError(f'This layout needs {total} entrance warp records (maximum four); only {len(warps)} preserved. Warp destinations are not created or edited yet.')
    if delete and any(i>index and count for i,count in existing):
        raise ValueError('Delete later entrances first; removing this one would shift their preserved warp destinations.')
    if index is None:
        insert=next((i for i,e in enumerate(stream.entries) if e.kind=='warp'),len(stream.entries))
        if any(i>=insert and count for i,count in existing):
            raise ValueError('This room interleaves entrances and warps; appending would change existing warp associations.')


def validate_house_door(stream,excluding=None):
    validate_entrance_change(stream,0xE2,index=excluding)


def collision_changes(data, room, alternate, x, y, capacities, object_id=0, direction='Single', length=1):
    """Return a bounded insertion; caller applies bytes through Undo history."""
    records = clipped_placement_records(data,room,alternate,x,y,object_id,direction,length)
    record = b''.join(records)
    key = (room, bool(alternate and room in ALTERNATE_POINTERS))
    stream = read_room_objects(data, *key)
    for raw in records:
        if entrance_count(raw[-1]):
            validate_entrance_change(stream,raw[-1])
    if sum(entrance_count(e.raw[-1]) for e in stream.entries if e.kind=='object')+sum(entrance_count(r[-1]) for r in records)>len([e for e in stream.entries if e.kind=='warp']):
        raise ValueError('Not enough preserved warp records for these entrances')
    if expanded_storage(data):
        insert=next((e.offset for e in stream.entries if e.kind=='warp'),stream.end-1)
        raw=bytes(data[stream.start:insert])+record+bytes(data[insert:stream.end])
        return replacement_changes(data,room,alternate,raw)
    original = capacities.get(key)
    if original is None or original.start != stream.start:
        raise ValueError('Room storage changed; reopen the ROM before editing')
    limit = original.end
    for other_key, other in capacities.items():
        if other_key != key and stream.start < other.end and other.start < limit:
            raise ValueError('Room storage is shared or overlapping; separate storage is required')
    if stream.end + len(record) > limit:
        raise ValueError('No verified space for another object. Clear this room during this session first. Reopening a cleared ROM does not recover its old capacity.')
    # Place after existing objects but before warp records to preserve warp order.
    insert = next((e.offset for e in stream.entries if e.kind == 'warp'), stream.end - 1)
    payload = record + bytes(data[insert:stream.end])
    return [(insert+i, data[insert+i], b) for i, b in enumerate(payload) if data[insert+i] != b]


def expanded_cells(data, room, alternate=False):
    """Baseline object map and source entry indexes; excludes saved-game changes.

Use the engine's padded 16-byte row addressing, including off-room macros.
    """
    stream = read_room_objects(data, room, alternate)
    grid = [stream.header[1]] * 256
    owners = [None] * 256
    def put(at, value, owner):
        at &= 255
        grid[at] = value
        owners[at] = owner
    for index, entry in enumerate(stream.entries):
        if entry.kind == 'warp':
            continue
        pos, obj = entry.raw[-2:]
        count = (entry.raw[0] & 15) or 256 if len(entry.raw) == 3 else 1
        step = 16 if len(entry.raw) == 3 and entry.raw[0] & 64 else 1
        if obj == 0xF5:
            # CopyTree ends at bottom-right (+17). Its loop adds +15
            # vertically or -15 horizontally: net strides +32 or +2.
            start = (0x11 + pos) & 255
            if start & 15 == 0:
                start = (start - 16) & 255
            for n in range(count):
                at = (start + n * (32 if step == 16 else 2)) & 255
                for delta, base, overlap, bush in ((0,0x25,0x29,None),(1,0x26,0x2A,None),
                                                   (16,0x27,0x2A,0x82),(17,0x28,0x29,0x83)):
                    old = grid[(at+delta-0x11)&255]
                    value = bush if bush is not None and old >= 0x8A else (overlap if old >= 0x10 else base)
                    put(at+delta-0x11, value, index)
        elif obj in MACRO_TABLES:
            at = 0x90000 + MACRO_TABLES[obj] - 0x4000
            offsets = []
            while data[at] != 255:
                offsets.append(data[at]); at += 1
            for i, offset in enumerate(offsets):
                put(pos + offset, data[at+1+i], index)
        elif obj >= 0xF5:
            raise ValueError(f'Unsupported macro {obj:02X}')
        else:
            for n in range(count):
                put(pos+n*step, obj, index)
    cells = [grid[y*16+x] for y in range(8) for x in range(10)]
    sources = [owners[y*16+x] for y in range(8) for x in range(10)]
    return cells, sources


def _edit_collision_changes(data, room, alternate, index, capacities, *, x=0, y=0,
                           direction='Single', length=1, delete=False):
    """Replace/delete one tested simple placement without reordering other records."""
    key = (room, bool(alternate and room in ALTERNATE_POINTERS))
    stream = read_room_objects(data, *key)
    if not 0 <= index < len(stream.entries):
        raise ValueError('Select a collision placement first')
    entry = stream.entries[index]
    if entry.kind != 'object' or entry.raw[-1] not in COLLISION_TYPES.values():
        raise ValueError('Warp records are read-only; select an object or macro.')
    if entrance_count(entry.raw[-1]):
        validate_entrance_change(stream,entry.raw[-1],index=index,delete=delete)
    if not delete and entrance_count(entry.raw[-1]):
        parts=clipped_placement_records(data,room,alternate,x,y,entry.raw[-1],direction,length)
        retained=sum(entrance_count(r[-1]) for r in parts)
        if retained<entrance_count(entry.raw[-1]) and any(
                e.kind=='object' and entrance_count(e.raw[-1]) for e in stream.entries[index+1:]):
            raise ValueError('Clipping would shift a later entrance to a different warp.')
        if entry.raw[-1] in MACRO_TABLES and retained<entrance_count(entry.raw[-1]):
            at=0x90000+MACRO_TABLES[entry.raw[-1]]-0x4000;offsets=[]
            while data[at]!=255:offsets.append(data[at]);at+=1
            kept=[]
            for i,delta in enumerate(offsets):
                if data[at+1+i] not in (0xE1,0xE2,0xE3):continue
                dy,dx=divmod(delta,16)
                kept.append(0<=x+dx<10 and 0<=y+dy<8)
            if any(kept[j] and not all(kept[:j]) for j in range(len(kept))):
                raise ValueError('Clipping would change this entrance warp association.')
    if expanded_storage(data):
        replacement=b'' if delete else b''.join(clipped_placement_records(data,room,alternate,x,y,entry.raw[-1],direction,length))
        raw=bytes(data[stream.start:entry.offset])+replacement+bytes(data[entry.offset+len(entry.raw):stream.end])
        return replacement_changes(data,room,alternate,raw)
    original = capacities.get(key)
    if original is None or original.start != stream.start:
        raise ValueError('Room storage changed; reopen the ROM')
    for other_key, other in capacities.items():
        if other_key != key and stream.start < other.end and other.start < original.end:
            raise ValueError('Room storage is shared or overlapping')
    replacement = b'' if delete else b''.join(clipped_placement_records(data,room,alternate,x,y,entry.raw[-1],direction,length))
    payload = replacement + bytes(data[entry.offset+len(entry.raw):stream.end])
    if entry.offset+len(payload) > original.end:
        raise ValueError('Not enough verified room storage for this change')
    return [(entry.offset+i,data[entry.offset+i],b) for i,b in enumerate(payload) if data[entry.offset+i]!=b]


def edit_collision_changes(data, room, alternate, index, capacities, **options):
    """Delete physics only; preserve artwork and Page-1 reference metadata."""
    changes = _edit_collision_changes(data, room, alternate, index, capacities, **options)
    if not options.get('delete', False):
        return changes
    from windfish.rom import windfish_shared_map16 as shared
    if not shared.enabled(data):
        return changes
    artwork = shared.cells(data, room, alternate)
    return shared.combine_native_graphics(data, room, alternate, changes,
        [(i % 10, i // 10, tile) for i, tile in enumerate(artwork)])
