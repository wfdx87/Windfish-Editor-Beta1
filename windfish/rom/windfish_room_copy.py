"""Atomic room component copies; retain destination warps and metadata."""


def _objects(data,record):
    """Extract object bytes, excluding warps, from an indoor stream."""
    out=bytearray();at=record.start+2
    while at<record.end-1:
        tag=data[at];size=5 if tag&0xFC==0xE0 else 3 if tag&0x90==0x80 else 2
        if size!=5:out.extend(data[at:at+size])
        at+=size
    return bytes(out)


def changes(data,source,destination,*,bg=True,sprites=True,collisions=True,
            source_map=None,destination_map=None,source_alternate=False,destination_alternate=False,gfx=False,map16=False):
    if not any((bg,sprites,collisions,gfx,map16)):raise ValueError('Choose at least one component to copy.')
    if any(type(room) is not int or not 0<=room<256 for room in (source,destination)):raise ValueError('Room IDs must be 00–FF.')
    if (source_map is None)!=(destination_map is None):raise ValueError('Copy within the overworld or within indoor banks.')
    if map16 and source_map is not None:raise ValueError('Room-specific Map16 assignments are only available on the overworld.')
    trial=bytearray(data)
    if source_map is None:
        from windfish.rendering.windfish_overworld_render import direct_map
        from windfish.overworld.windfish_collision_objects import read_room_objects
        from windfish.rom import windfish_collision_storage as storage
        src=read_room_objects(data,source,source_alternate);dst=read_room_objects(data,destination,destination_alternate)
        if source==destination and storage.room_key(source,source_alternate)==storage.room_key(destination,destination_alternate):return []
        source_bg=direct_map(data,source,source_alternate)[1]
        from windfish.rom import windfish_shared_map16 as shared
        source_logical=shared.cells(data,source,source_alternate)
        if collisions:
            payload=bytes((dst.header[0],src.header[1]))+b''.join(e.raw for e in src.entries if e.kind=='object')+b''.join(e.raw for e in dst.entries if e.kind=='warp')+b'\xfe'
            for at,old,new in storage.replacement_changes(trial,destination,destination_alternate,payload):trial[at]=new
        if bg:
            at,_=direct_map(trial,destination,destination_alternate);trial[at:at+80]=bytes(source_bg)
            if shared.enabled(trial):
                for at,old,new in shared.paint_changes(trial,destination,destination_alternate,[(i%10,i//10,t) for i,t in enumerate(source_logical)]):trial[at]=new
        src_key,dst_key=source,destination
    else:
        from windfish.rendering import windfish_dungeon_render as render
        from windfish.dungeon import windfish_dungeon_visuals as visuals,windfish_dungeon_room_data as rooms
        src=render.read_room(data,source_map,source);dst=render.read_room(data,destination_map,destination)
        if source==destination and render.room_bank(source_map)==render.room_bank(destination_map):return []
        src_bg=visuals.apply_to_cells(data,source_map,source,render.layout(data,src))
        dst_bg=visuals.apply_to_cells(data,destination_map,destination,render.layout(data,dst))
        if collisions:
            payload=bytes((dst.animation,(src.template<<4)|src.floor))+_objects(data,src)+b''.join(dst.warps)+b'\xfe'
            for at,old,new in rooms.replace_stream(trial,destination_map,destination,payload):trial[at]=new
        if bg or collisions:
            # Rebase the visual overrides onto the new collision objects. A
            # collision-only copy must preserve the destination's visible BG.
            desired=src_bg if bg else dst_bg
            for at,old,new in visuals.paint_cells_changes(trial,destination_map,destination,[(i%10,i//10,t) for i,t in enumerate(desired)]):trial[at]=new
        src_key=rooms.sprite_index(source_map,source);dst_key=rooms.sprite_index(destination_map,destination)
    if gfx:
        _copy_graphics(data,trial,source,destination,source_map,destination_map,source_alternate,destination_alternate)
    if map16:
        _copy_map16(data,trial,source,destination)
    if sprites:
        from windfish.rom import windfish_sprite_storage as storage
        if not storage.enabled(trial):raise ValueError('Reopen the ROM and accept expanded sprite storage.')
        records=storage.read_lists(trial,True);original=storage.read_lists(data,True)
        records[dst_key]=list(original[src_key])
        trial[storage.EXTENDED:storage.END]=storage._pack(records).ljust(storage.END-storage.EXTENDED,b'\0')
        storage.validate_mode(trial)
    return [(at,old,new) for at,(old,new) in enumerate(zip(data,trial)) if old!=new]


def _copy_graphics(data,out,source,destination,source_map,destination_map,source_alternate,destination_alternate):
    """Copy assignments, not shared assets; keep the whole operation atomic.

    Existing library IDs stay shared. Native per-map indoor floor/wall/item
    loaders remain tied to the destination map context rather than modifying
    other rooms through their global tables.
    """
    from windfish.compatibility import api as profile
    def copy(src,dst,size=1):out[dst:dst+size]=data[src:src+size]
    def apply(edits):
        for at,old,new in edits:out[at]=new
    if source_map is None:
        from windfish.rom import windfish_bg_graphics as bg,windfish_room_graphics as graphics,windfish_vram_bank1 as bank1,windfish_room_tiles as tiles
        from windfish.rendering.windfish_room_animation import animation_changes
        from windfish.overworld.windfish_collision_objects import read_room_objects
        copy(bg.selector_offset(data,source),bg.selector_offset(out,destination))
        table=profile.bank20_table(data,0x830DB);copy(table+source,table+destination)
        # Copy disabled assignments too, so re-enabling reproduces the source.
        if graphics.enabled(data):
            for table,stride in ((graphics.FLAGS,1),(graphics.SLOTS,4),(graphics.SLOT_MASKS,1)):
                copy(table+source*stride,table+destination*stride,stride)
        if bank1.installed(data):
            for table,stride in ((bank1.FLAGS,1),(bank1.SLOTS,8),(bank1.MASKS,1)):
                copy(table+source*stride,table+destination*stride,stride)
        apply(animation_changes(out,destination,destination_alternate,read_room_objects(data,source,source_alternate).header[0]))
    else:
        from windfish.dungeon import windfish_dungeon_graphics as graphics,windfish_dungeon_room_data as rooms
        from windfish.rendering import windfish_dungeon_render as render
        if (source_map==255)!=(destination_map==255):
            raise ValueError('GFX settings cannot be copied between Color Dungeon and normal indoor banks.')
        if source_map==255:
            for table in graphics.COLOR_SLOTS:copy(table+source*2,table+destination*2,2)
        else:
            copy(graphics.configuration_offset(source_map,source,data),graphics.configuration_offset(destination_map,destination,out))
            table=profile.indoor_bg_table(data,render.BG_SELECTORS)
            copy(table+(256 if render.room_bank(source_map)=='B' else 0)+source,table+(256 if render.room_bank(destination_map)=='B' else 0)+destination)
        src=render.read_room(data,source_map,source);dst=render.read_room(out,destination_map,destination)
        payload=bytes((src.animation,))+bytes(out[dst.start+1:dst.end])
        apply(rooms.replace_stream(out,destination_map,destination,payload))


def _copy_map16(data,out,source,destination):
    """Reuse the source page assignments without changing shared artwork."""
    from windfish.compatibility import api as profile
    from windfish.rom import windfish_room_tiles as tiles,windfish_room_map16 as page1
    backups=profile.backups(data,tiles.BACKUPS)
    out[backups+destination*3:backups+destination*3+3]=data[backups+source*3:backups+source*3+3]
    for at,old,new in tiles.assign_set(out,destination,tiles.room_set(data,source)):out[at]=new
    if page1.enabled(data):
        for at,old,new in page1.assign_set(out,destination,page1.room_set(data,source)):out[at]=new
