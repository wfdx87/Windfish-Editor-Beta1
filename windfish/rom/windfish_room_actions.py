"""Atomic whole-room operations. Preserve warps, events, rewards and other rooms."""

def repeated_cells(width,height,values):
    if not 1<=width<=16 or not 1<=height<=16 or len(values)!=width*height:
        raise ValueError('Select a valid tile or rectangular tile stamp.')
    if any(not isinstance(t,int) or not 0<=t<=511 for t in values):raise ValueError('Tile IDs must be 000–1FF.')
    return [(x,y,values[(y%height)*width+x%width]) for y in range(8) for x in range(10)]


def changes(data,room,action,*,map_id=None,alternate=False,stamp=(1,1,(0,)),add_collisions=False):
    if action not in ('bg','sprites','collisions','all','fill'):raise ValueError('Unknown room action.')
    trial=bytearray(data)
    if map_id is None:
        from windfish.overworld.windfish_collision_objects import clear_room_objects,read_room_objects
        from windfish.rendering.windfish_overworld_render import direct_map
        if action in ('collisions','all'):clear_room_objects(trial,room,alternate)
        if action in ('bg','all','fill'):
            cells=repeated_cells(*stamp) if action=='fill' else [(x,y,read_room_objects(trial,room,alternate).header[1]) for y in range(8) for x in range(10)]
            if action=='fill' and add_collisions:
                from windfish.overworld.windfish_direct_collisions import direct_collision_changes
                for at,old,new,_,_ in direct_collision_changes(trial,[(room,x,y,t,alternate) for x,y,t in cells],{}):trial[at]=new
            else:
                from windfish.rom import windfish_shared_map16 as shared
                if shared.enabled(trial):
                    for at,old,new in shared.paint_changes(trial,room,alternate,cells):trial[at]=new
                else:
                    start,_=direct_map(trial,room,special=alternate)
                    for x,y,t in cells:trial[start+y*10+x]=t
        sprite_key=room
    else:
        from windfish.dungeon import windfish_dungeon_room_data as ops,windfish_dungeon_visuals as visuals
        from windfish.rendering import windfish_dungeon_render as renderer
        if action in ('collisions','all'):
            for at,old,new in ops.clear_changes(trial,map_id,room):trial[at]=new
        if action in ('bg','all','fill'):
            floor=renderer.read_room(trial,map_id,room).floor
            cells=repeated_cells(*stamp) if action=='fill' else [(x,y,floor) for y in range(8) for x in range(10)]
            if action=='fill' and add_collisions:
                from windfish.dungeon.windfish_dungeon_collisions import placement_changes
                edits=placement_changes(trial,map_id,room,cells,combined=True)
            else:edits=visuals.paint_cells_changes(trial,map_id,room,cells)
            for at,old,new in edits:trial[at]=new
        sprite_key=ops.sprite_index(map_id,room)
    if action in ('sprites','all'):
        from windfish.rom import windfish_sprite_storage as sprites
        if not sprites.enabled(trial):raise ValueError('Reopen the ROM and accept expanded sprite storage.')
        lists=sprites.read_lists(trial,True);lists[sprite_key]=[]
        trial[sprites.EXTENDED:sprites.END]=sprites._pack(lists).ljust(sprites.END-sprites.EXTENDED,b'\0')
        sprites.validate_mode(trial)
    return [(at,old,new) for at,(old,new) in enumerate(zip(data,trial)) if old!=new]
