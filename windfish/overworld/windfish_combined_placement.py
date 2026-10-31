"""Prepare one atomic object-stream and visual-map placement transaction."""
from windfish.rendering.windfish_overworld_render import direct_map
from windfish.overworld.windfish_collision_objects import (collision_changes, read_room_objects,
                                       expanded_cells)


def combined_placement_changes(data, room, alternate, x, y, capacities,
                               object_id=0, direction='Single', length=1):
    """Return byte changes for placement plus its final expanded graphics.

All validation/expansion happens in a private buffer, before the caller writes.
Only cells produced by the new placement, or changed by its effect on later
macro expansion, are synchronized. Unrelated Direct Draw artwork is preserved.
    """
    stream = read_room_objects(data, room, alternate)
    insertion_index = next((i for i,e in enumerate(stream.entries) if e.kind=='warp'), len(stream.entries))
    before_cells,_ = expanded_cells(data,room,alternate)
    changes = collision_changes(data,room,alternate,x,y,capacities,object_id,direction,length)
    trial = bytearray(data)
    for offset,before,after in changes:
        trial[offset] = after
    cells,sources = expanded_cells(trial,room,alternate)
    added=len(read_room_objects(trial,room,alternate).entries)-len(stream.entries)
    map_offset,_ = direct_map(trial,room,special=alternate)
    graphics=[]
    for i,obj in enumerate(cells):
        if sources[i] is not None and insertion_index <= sources[i] < insertion_index+added or before_cells[i] != obj:
            graphics.append((i%10,i//10,obj))
            offset = map_offset+i
            if data[offset] != obj:
                changes.append((offset,data[offset],obj))
    from windfish.rom.windfish_shared_map16 import combine_native_graphics
    return combine_native_graphics(data,room,alternate,changes,graphics)


def combined_edit_changes(data,room,alternate,index,capacities,**options):
    """Move/resize/delete both layers, filling vacated visible cells with floor."""
    from windfish.overworld.windfish_collision_objects import edit_collision_changes
    if options.get('delete',False):
        return edit_collision_changes(data,room,alternate,index,capacities,**options)
    stream=read_room_objects(data,room,alternate)
    before,old_sources=expanded_cells(data,room,alternate)
    changes=edit_collision_changes(data,room,alternate,index,capacities,**options)
    trial=bytearray(data)
    for at,old,new in changes:trial[at]=new
    after,new_sources=expanded_cells(trial,room,alternate)
    map_offset,_=direct_map(data,room,special=alternate)
    delete=options.get('delete',False)
    count=len(read_room_objects(trial,room,alternate).entries)-len(stream.entries)+1
    graphics=[]
    for i,value in enumerate(after):
        graphic=None
        if old_sources[i]==index:graphic=stream.header[1]
        if not delete and new_sources[i] is not None and index<=new_sources[i]<index+count:graphic=value
        elif before[i]!=value and old_sources[i]!=index:graphic=value
        if graphic is not None:
            graphics.append((i%10,i//10,graphic))
            if data[map_offset+i]!=graphic:changes.append((map_offset+i,data[map_offset+i],graphic))
    from windfish.rom.windfish_shared_map16 import combine_native_graphics
    return combine_native_graphics(data,room,alternate,changes,graphics)
