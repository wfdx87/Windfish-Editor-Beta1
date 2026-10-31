"""Shared raw GFX/tilemap transfer adapters for Screen Editor tabs."""
from windfish.rom import windfish_screen_maps as screens,windfish_world_map as world
from windfish.rendering import windfish_pictures as photos


def export_payload(data,kind,frame,tilemap=False):
    if kind=='photo':
        return (photos.extract_picture_tilemap if tilemap else photos.extract_picture_gfx)(data,frame.selected_photo())
    if kind=='world':
        return bytes(tile for tile,attr in world.screen_grid(data)) if tilemap else world.extract_graphics(data)
    if tilemap:return bytes(tile for tile,attr in screens.cells(data,kind))
    from windfish.rendering.windfish_screen_render import raw_gfx
    return raw_gfx(data,kind)


def import_changes(data,kind,frame,raw,tilemap=False):
    if kind=='photo':raise ValueError('Photo Album is read-only.')
    if not tilemap:
        if kind=='world':return world.graphics_changes(data,raw)
        from windfish.rendering.windfish_screen_render import segments,raw_gfx
        if len(raw)!=len(raw_gfx(data,kind)):raise ValueError(f'Expected {len(raw_gfx(data,kind))} GFX bytes.')
        edits=[];offset=0
        for first,at,count in segments(kind):
            edits.extend((at+i,data[at+i],raw[offset+i]) for i in range(count) if data[at+i]!=raw[offset+i]);offset+=count
        return edits
    if len(raw)!=360:raise ValueError('Tilemaps must contain exactly 360 raw IDs (20 columns × 18 rows).')
    if kind=='world':
        before=world.screen_grid(data)
        if any(tile not in world.TILE_IDS for tile in raw):raise ValueError('Map tile IDs must be F0–FF or 00–6F.')
        cells=tuple((tile,before[i][1]) for i,tile in enumerate(raw))
        if frame.border_enabled.get():return world.screen_stamp_changes(data,0,0,(20,18,cells,True),True)
        inner=tuple(cells[(y+1)*20+x+2] for y in range(16) for x in range(16))
        return world.stamp_changes(data,0,0,(16,16,inner,True))
    from windfish.rendering.windfish_screen_render import segments
    valid={tile for first,at,size in segments(kind) for tile in range(first,first+size//16)}
    if any(tile not in valid for tile in raw):raise ValueError('Tilemap references graphics not loaded by this screen.')
    before=screens.cells(data,kind);cells=tuple((tile,before[i][1]) for i,tile in enumerate(raw))
    return screens.stamp_changes(data,kind,0,0,(20,18,cells,True))
