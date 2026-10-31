"""Atomic direct tile drawing plus matching ordinary collision objects."""
from itertools import groupby
from windfish.rendering.windfish_overworld_render import direct_map
from windfish.overworld.windfish_collision_objects import collision_changes, expanded_cells
from windfish.overworld.windfish_collision_definitions import SINGLE_ONLY


def direct_collision_changes(data,cells,capacities):
    from windfish.rom import windfish_shared_map16 as shared
    if not shared.enabled(data):return _native_direct_collision_changes(data,cells,capacities)
    trial=bytearray(data);touched={}
    native=[(room,x,y,shared.proxy(data[shared.BEHAVIORS+(tile&255)]) if tile>=256 else tile,alt)
            for room,x,y,tile,alt in cells]
    for at,old,new,room,alt in _native_direct_collision_changes(trial,native,capacities):
        trial[at]=new;touched[at]=(room,alt)
    for at,old,new,room,alt in shared.drawing_changes(trial,cells):
        trial[at]=new;touched[at]=(room,alt)
    return [(at,data[at],trial[at],room,alt) for at,(room,alt) in touched.items() if data[at]!=trial[at]]


def _native_direct_collision_changes(data, cells, capacities):
    # Resolve overlapping source/destination cells of a moved stamp last-write-wins.
    final = {(room,bool(alt),x,y):tile for room,x,y,tile,alt in cells}
    for (room,alt,x,y),tile in final.items():
        if not (0 <= room <= 255 and 0 <= x < 10 and 0 <= y < 8 and 0 <= tile <= 0xF4):
            raise ValueError('Add Collisions supports tiles 00–F4. Use Add Collisions for macros, or uncheck it for graphics-only drawing.')
    trial = bytearray(data)
    touched = {}
    rows = sorted((room,alt,y,x,tile) for (room,alt,x,y),tile in final.items())
    for (room,alt,y),entries in groupby(rows,key=lambda v:v[:3]):
        row = list(entries)
        index = 0
        while index < len(row):
            _,_,_,x,tile = row[index]
            end = index+1
            if tile not in SINGLE_ONLY:
                while end < len(row) and row[end][3] == x+end-index and row[end][4] == tile:
                    end += 1
            length = end-index
            current,_ = expanded_cells(trial,room,alt)
            if any(current[y*10+cx] != tile for cx in range(x,x+length)):
                changes = collision_changes(trial,room,alt,x,y,capacities,tile,
                                            'Horizontal' if length > 1 else 'Single',length)
                for at,old,new in changes:
                    trial[at] = new; touched[at] = (room,alt)
            index = end
        map_offset,_ = direct_map(trial,room,special=alt)
        for _,_,_,x,tile in row:
            at = map_offset+y*10+x
            trial[at] = tile; touched[at] = (room,alt)
    return [(at,data[at],trial[at],room,alt) for at,(room,alt) in sorted(touched.items())
            if data[at] != trial[at]]
