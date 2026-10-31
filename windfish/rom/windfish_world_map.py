"""Select-screen map tables, native/VWF labels, and read-only screen rendering.

The inner map is 16x16 8-pixel cells. Names are existing shared dialogues;
no independent per-cell strings, relocated text, or new runtime code is added.
"""
from PIL import Image
from windfish.compatibility.api import world_map_offsets
from windfish.rom import windfish_dialogue as dialogue

GRAPHICS=0xB3800
PALETTES=0x8786E
FRAME_TILES=0x222E9
FRAME_ATTRS=0x926E1
TILE_IDS=tuple(range(0xF0,256))+tuple(range(0x70))


def region_index(room):
    if not 0<=room<256:raise ValueError('Room must be 00–FF.')
    return (room&15)//2+(room//32)*8


def location(data,room,owl_seen=True):
    """Resolve normal map selection, including the game's hardcoded exceptions.

    owl_seen is a preview assumption only; no saved-game data is read/written.
    Caller can inspect both fallback and conditional special dialogue.
    """
    offsets=world_map_offsets(data);region=region_index(room)
    code=data[offsets['special']+room]
    if code>=80:raise ValueError(f'Room {room:02X} has invalid special-location code {code:02X}.')
    fallback=0x76 if room in (0x24,0x34) else data[offsets['regions']+region]
    special=data[offsets['lookup']+code] if code else None
    use_special=bool(code and (code>=0x10 or owl_seen))
    low=special if use_special else fallback
    index=low+(0x100 if low==0xA7 or room==0x37 else 0)
    category=('None','Owl reminder','Dungeon','Shop','Point of interest','Point of interest')
    kind=category[0 if not code else (code>>4)+1]
    return {'room':room,'region':region,'code':code,'category':kind,
            'conditional':bool(0<code<0x10),'special_active':use_special,
            'fallback':fallback,'dialogue':index}


def cell_changes(data,room,tile,palette):
    region_index(room)
    if tile not in TILE_IDS:raise ValueError('Use a map-sheet tile: F0–FF or 00–6F.')
    if not 0<=palette<8:raise ValueError('Palette must be 0–7.')
    offsets=world_map_offsets(data);at=offsets['attributes']+room
    # Keep bank, flip and priority flags. Only change the selected palette.
    pairs=((offsets['tiles']+room,tile),(at,(data[at]&0xF8)|palette))
    return [(at,data[at],value) for at,value in pairs if data[at]!=value]


def palettes(data):
    raw=data[PALETTES:PALETTES+64]
    if len(raw)!=64:raise ValueError('Missing world map palettes.')
    return tuple(tuple(((int.from_bytes(raw[i:i+2],'little')>>shift)&31)*8 for shift in (0,5,10)) for i in range(0,64,2))


def tile_image(data,tile,attribute):
    if tile not in TILE_IDS:raise ValueError(f'Tile {tile:02X} is outside the map graphics sheet.')
    if attribute&8:raise ValueError('Map preview does not support VRAM bank 1 graphics.')
    at=GRAPHICS+((tile-0xF0)&255)*16;raw=data[at:at+16]
    colors=palettes(data);base=(attribute&7)*4;image=Image.new('RGB',(8,8))
    for y in range(8):
        lo,hi=raw[y*2:y*2+2]
        for x in range(8):
            bit=x if attribute&32 else 7-x
            value=((lo>>bit)&1)|(((hi>>bit)&1)<<1)
            image.putpixel((x,7-y if attribute&64 else y),colors[base+value])
    return image


def sheet(data,palette=0):
    image=Image.new('RGB',(128,64))
    for pos,tile in enumerate(TILE_IDS):image.paste(tile_image(data,tile,palette),((pos%16)*8,(pos//16)*8))
    return image


def decode_frame(data,at,default):
    """Decode the engine's literal/repeat, horizontal/vertical draw commands."""
    grid=[default]*1024
    for _ in range(128):
        high=data[at];at+=1
        if not high:return grid
        address=(high<<8)|data[at];flags=data[at+1];at+=2
        count=(flags&63)+1;step=32 if flags&128 else 1
        for i in range(count):
            value=data[at] if flags&64 else data[at+i]
            dest=address-0x9800+i*step
            if not 0<=dest<1024:raise ValueError('Invalid map frame command.')
            grid[dest]=value
        at+=1 if flags&64 else count
    raise ValueError('Unterminated map frame.')


def render(data):
    """Fully revealed 160x144 map background, including its native frame.

    Selection outline belongs to the editor. Runtime cursor/Link and the
    condition-dependent location illustration are sprites, not baked into BG.
    """
    cells=screen_grid(data)
    image=Image.new('RGB',(160,144));cache={}
    for y in range(18):
        for x in range(20):
            key=cells[y*20+x]
            if key not in cache:cache[key]=tile_image(data,*key)
            image.paste(cache[key],(x*8,y*8))
    return image


def selection_rect(start,end):
    return min(start[0],end[0]),min(start[1],end[1]),max(start[0],end[0]),max(start[1],end[1])


def capture_stamp(data,rect):
    """Snapshot a map rectangle so overlapping pastes never smear the source."""
    x0,y0,x1,y1=rect
    if not 0<=x0<=x1<16 or not 0<=y0<=y1<16:raise ValueError('Invalid map selection.')
    offsets=world_map_offsets(data)
    cells=tuple((data[offsets['tiles']+y*16+x],data[offsets['attributes']+y*16+x])
                for y in range(y0,y1+1) for x in range(x0,x1+1))
    return x1-x0+1,y1-y0+1,cells,True


def stamp_changes(data,x,y,stamp):
    """Stamp within the inner map; edge clipping never touches border/name tables.

    Map selections carry complete attributes. Sheet selections carry palettes,
    retaining the destination's non-palette bits as single-cell edits did.
    """
    width,height,cells,full_attributes=stamp
    if not 1<=width<=16 or not 1<=height<=16 or len(cells)!=width*height:
        raise ValueError('Invalid tile stamp.')
    if not 0<=x<16 or not 0<=y<16:raise ValueError('Paint inside the inner map.')
    if any(tile not in TILE_IDS or not 0<=attr<=255 for tile,attr in cells):
        raise ValueError('Stamp contains an invalid map tile or attribute.')
    offsets=world_map_offsets(data);changes=[]
    for sy in range(min(height,16-y)):
        for sx in range(min(width,16-x)):
            tile,attr=cells[sy*width+sx];room=(y+sy)*16+x+sx
            at=offsets['attributes']+room
            value=attr if full_attributes else (data[at]&0xf8)|(attr&7)
            for pos,new in ((offsets['tiles']+room,tile),(at,value)):
                if data[pos]!=new:changes.append((pos,data[pos],new))
    return changes

# Dedicated 256-byte records in verified bank-tail padding. Each retains the
# loader's original bank; only the map's own background pointers are changed.
# First use refuses occupied storage. Undo restores both records and pointers.
BORDER_RECORDS=((0x8053B,FRAME_TILES,0x23C00),(0x91C5B,FRAME_ATTRS,0x93D00))
BORDER_MAGIC=b'WFMAPB01'


def frame_address(data,kind):
    pointer,original,reserved=BORDER_RECORDS[kind]
    word=int.from_bytes(data[pointer:pointer+2],'little')
    bank=original//0x4000;at=bank*0x4000+word-0x4000
    if at==original:return at
    if at!=reserved or bytes(data[reserved+240:reserved+248])!=BORDER_MAGIC:
        raise ValueError('Unrecognized overworld map border storage.')
    return at


def screen_grid(data):
    tiles=decode_frame(data,frame_address(data,0),0xFF)
    attrs=decode_frame(data,frame_address(data,1),0)
    offsets=world_map_offsets(data)
    for room in range(256):
        pos=(room//16+1)*32+room%16+2
        tiles[pos]=data[offsets['tiles']+room];attrs[pos]=data[offsets['attributes']+room]
    return tuple((tiles[y*32+x],attrs[y*32+x]) for y in range(18) for x in range(20))


def capture_screen_stamp(data,rect):
    x0,y0,x1,y1=rect
    if not 0<=x0<=x1<20 or not 0<=y0<=y1<18:raise ValueError('Invalid screen selection.')
    cells=screen_grid(data)
    return x1-x0+1,y1-y0+1,tuple(cells[y*20+x] for y in range(y0,y1+1) for x in range(x0,x1+1)),True


def encode_border(cells,component):
    """Literal row/column commands give every border cell independent storage.

    Maximum payload 123 bytes; the 256-byte record has room for the marker.
    Interior cells are omitted because the separate inner map loader owns them.
    """
    raw=bytearray()
    for x,y,count,vertical in ((0,0,20,False),(0,17,20,False),
                               (0,1,16,True),(1,1,16,True),(18,1,16,True),(19,1,16,True)):
        address=0x9800+y*32+x
        raw.extend((address>>8,address&255,(count-1)|(128 if vertical else 0)))
        raw.extend(cells[(y+i if vertical else y)*20+(x if vertical else x+i)][component] for i in range(count))
    raw.append(0)
    return bytes(raw).ljust(240,b'\0')+BORDER_MAGIC+bytes(8)


def screen_stamp_changes(data,x,y,stamp,border_enabled=False):
    if not border_enabled:
        width,height,cells,full=stamp
        if not 1<=width<=20 or not 1<=height<=18 or len(cells)!=width*height:raise ValueError('Invalid screen stamp.')
        w,h=min(width,16),min(height,16)
        clipped=(w,h,tuple(cells[sy*width+sx] for sy in range(h) for sx in range(w)),full)
        return stamp_changes(data,x-2,y-1,clipped)
    width,height,cells,full=stamp
    if not 1<=width<=20 or not 1<=height<=18 or len(cells)!=width*height:
        raise ValueError('Invalid screen stamp.')
    if not 0<=x<20 or not 0<=y<18:raise ValueError('Paint inside the map screen.')
    if any(tile not in TILE_IDS or not 0<=attr<=255 or attr&8 for tile,attr in cells):
        raise ValueError('Stamp uses unsupported map graphics or attributes.')
    before=screen_grid(data);after=list(before);border_changed=False
    for sy in range(min(height,18-y)):
        for sx in range(min(width,20-x)):
            pos=(y+sy)*20+x+sx;tile,attr=cells[sy*width+sx]
            value=attr if full else (before[pos][1]&0xf8)|(attr&7)
            after[pos]=(tile,value)
            if after[pos]!=before[pos] and not (2<=x+sx<18 and 1<=y+sy<17):border_changed=True
    trial=bytearray(data);offsets=world_map_offsets(data)
    for room in range(256):
        tile,attr=after[(room//16+1)*20+room%16+2]
        trial[offsets['tiles']+room]=tile;trial[offsets['attributes']+room]=attr
    if border_changed:
        for kind,(pointer,original,reserved) in enumerate(BORDER_RECORDS):
            current=frame_address(data,kind)
            if current==original and any(data[reserved:reserved+256]):
                raise ValueError(f'Border storage at {reserved:06X} is occupied; no changes made.')
            trial[reserved:reserved+256]=encode_border(after,kind)
            trial[pointer:pointer+2]=(0x4000+reserved%0x4000).to_bytes(2,'little')
    spans=[(offsets['tiles'],256),(offsets['attributes'],256)]
    if border_changed:spans.extend((p,2) for p,_,_ in BORDER_RECORDS);spans.extend((r,256) for _,_,r in BORDER_RECORDS)
    return [(at,data[at],trial[at]) for start,size in spans for at in range(start,start+size) if data[at]!=trial[at]]


def extract_graphics(data):
    """128 native-order GB 2bpp tiles, F0–FF then 00–6F, exactly 2048 bytes."""
    raw=bytes(data[GRAPHICS:GRAPHICS+2048])
    if len(raw)!=2048:raise ValueError('Incomplete map graphics.')
    return raw


def graphics_changes(data,raw):
    if len(raw)!=2048:raise ValueError('Map GFX must be exactly 2048 bytes (128 Game Boy 2bpp tiles).')
    original=extract_graphics(data)
    return [(GRAPHICS+i,old,new) for i,(old,new) in enumerate(zip(original,raw)) if old!=new]
