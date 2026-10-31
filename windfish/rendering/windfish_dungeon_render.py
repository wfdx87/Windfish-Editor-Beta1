"""Read-only English Rev2 dungeon room renderer.

Fresh decoder follows LoadRoom, LoadRoomTemplate, indoor door macros,
LoadIndoorTiles and the CGB object/attribute/palette tables. No ROM writes.
Room flags, moving sprites and event-driven changes are not simulated.
"""
from dataclasses import dataclass
from PIL import Image
from windfish.rendering.windfish_overworld_render import animation_data

DUNGEONS=((0,'Tail Cave'),(1,'Bottle Grotto'),(2,'Key Cavern'),
          (3,"Angler’s Tunnel"),(4,"Catfish’s Maw"),(5,'Face Shrine'),
          (6,"Eagle’s Tower"),(7,'Turtle Rock'),(8,"Wind Fish’s Egg"),(255,'Color Dungeon'))
MAP_LAYOUT=0x50220
ROOM_TABLE_A=0x28000
ROOM_TABLE_B=0x2C000
ROOM_TABLE_COLOR=0x2BB77
FORMATION=0x203B0
COLOR_FORMATION=0x20760
ATTR_POINTERS=0x6A076
BG_SELECTORS=0x82EBB
DOOR_HANDLERS=0x32D7
TEMPLATE_HANDLERS=0x50881


def chunk(data,at,size):
    if at<0 or at+size>len(data):raise ValueError(f'Dungeon ROM read outside bounds: {at:X}+{size:X}')
    return bytes(data[at:at+size])


def word(data,at):return int.from_bytes(chunk(data,at,2),'little')

def bank_address(bank,ptr):
    if not 0x4000<=ptr<0x8000:raise ValueError(f'Invalid dungeon ROM pointer {ptr:04X}')
    return bank*0x4000+ptr-0x4000


def check_map(map_id):
    if map_id not in tuple(range(32))+(255,):raise ValueError('Choose a supported indoor map.')


def map_layout(data,map_id,collapsed=False):
    if map_id not in dict(DUNGEONS):raise ValueError('Choose a supported dungeon layout.')
    layout=11 if map_id==255 else 12 if map_id==6 and collapsed else map_id
    raw=chunk(data,MAP_LAYOUT+layout*64,64)
    return tuple(room if room or map_id==255 and i==25 else None for i,room in enumerate(raw))


@dataclass(frozen=True)
class DungeonRoom:
    map_id:int
    room:int
    start:int
    end:int
    animation:int
    template:int
    floor:int
    objects:tuple
    warps:tuple


def read_room(data,map_id,room):
    check_map(map_id)
    if not isinstance(room,int) or not 0<=room<=255 or map_id==255 and room>21:raise ValueError('Invalid dungeon room ID.')
    table=ROOM_TABLE_COLOR if map_id==255 else ROOM_TABLE_B if 6<=map_id<0x1A else ROOM_TABLE_A
    bank=table//0x4000
    from windfish.dungeon.windfish_dungeon_storage import enabled,resolve
    if enabled(data):at,limit=resolve(data,map_id,room)
    else:at=bank_address(bank,word(data,table+room*2));limit=(bank+1)*0x4000
    if at+2>=limit:raise ValueError('Missing dungeon room header.')
    animation,header=chunk(data,at,2);p=at+2;objects=[];warps=[]
    while p<limit:
        tag=data[p]
        if tag==254:return DungeonRoom(map_id,room,at,p+1,animation,header>>4,header&15,tuple(objects),tuple(warps))
        size=5 if tag&0xFC==0xE0 else 3 if tag&0x90==0x80 else 2
        if p+size>=limit:raise ValueError('Truncated dungeon object record.')
        raw=chunk(data,p,size)
        if size==5:warps.append(raw)
        else:
            xy,obj=raw[-2:];length=(tag&15) if size==3 else 1
            objects.append((xy,obj,length,bool(size==3 and tag&0x40)))
        p+=size
    raise ValueError('Dungeon room has no in-bank terminator.')


def _macro(data,handler,bank,search=80):
    """Read BC-offset and DE-value pointers from the engine's macro handler."""
    raw=chunk(data,handler,search)
    for i in range(len(raw)-8):
        if raw[i]==1 and raw[i+3]==0x11 and raw[i+6]==0xC3:
            offsets=int.from_bytes(raw[i+1:i+3],'little');values=int.from_bytes(raw[i+4:i+6],'little')
            a=bank_address(bank,offsets) if bank else offsets
            b=bank_address(bank,values) if bank else values
            result=[]
            for n in range(128):
                xy=chunk(data,a+n,1)[0]
                if xy==255:return tuple(result)
                result.append((xy,chunk(data,b+n,1)[0]))
            raise ValueError('Dungeon macro has no terminator.')
    raise ValueError(f'Unrecognized dungeon macro handler at {handler:05X}')


def templates(data):
    out=[]
    for i in range(16):
        handler=bank_address(0x14,word(data,TEMPLATE_HANDLERS+i*2))
        out.append(() if data[handler]==0xC9 else _macro(data,handler,0x14,16))
    return tuple(out)


def doors(data):
    from windfish.compatibility.api import door_table
    table=door_table(data,DOOR_HANDLERS)
    result={}
    for obj in range(0xEC,0xFE):
        # Shutters initially load as open doors; gameplay closes them later.
        target=obj+4 if 0xF0<=obj<=0xF3 else obj
        result[obj]=_macro(data,word(data,table+(target-0xEC)*2),0)
    return result


def layout(data,record,template_data=None,door_data=None):
    cells=[record.floor]*256
    def put(position,obj):
        # Engine room memory has a 16-byte stride. Crop its visible 10x8 area.
        if 0<=position<256:cells[position]=obj
    for xy,obj in (template_data or templates(data))[record.template]:put(xy,obj)
    macros=door_data or doors(data)
    for xy,obj,length,vertical in record.objects:
        if obj>=0xEC:
            for offset,tile in macros[obj]:put(xy+offset,tile)
        else:
            for i in range(length):put(xy+i*(16 if vertical else 1),obj)
    return tuple(cells[y*16+x] for y in range(8) for x in range(10))


def sideview_rooms(data,map_id):
    found=set()
    for room in range(22 if map_id==255 else 256):
        try:record=read_room(data,map_id,room)
        except ValueError:continue # Unused pointer-table entries need not be valid rooms.
        for warp in record.warps:
            if warp[0]&3==2 and warp[1]==map_id:found.add(warp[2])
    return frozenset(found)


def palette_offset(data,map_id,sideview=False,room=0):
    if map_id==255:at=0x867D0
    elif map_id==7 and sideview and room in (0x64,0x65,0x66,0x67,0x6A,0x6B):at=0x86750
    elif map_id>=10:
        indices=bank_address(0x21,word(data,0x84413+(map_id-10)*2))
        index=chunk(data,indices+room,1)[0]
        at=bank_address(0x21,word(data,0x8443F+index*2))
    else:at=bank_address(0x21,word(data,(0x84401 if sideview else 0x843EF)+map_id*2))
    return at


def palette(data,map_id,sideview=False,room=0):
    raw=chunk(data,palette_offset(data,map_id,sideview,room),64)
    return tuple(tuple(((int.from_bytes(raw[i:i+2],'little')>>shift)&31)<<3 for shift in (0,5,10)) for i in range(0,64,2))


def graphics(data,record,sideview=False,inherited=0):
    """4096 bytes in signed BG tile order: VRAM8800-97FF."""
    m=record.map_id;room=record.room
    buf=bytearray(chunk(data,0xB0800,0x800))+bytearray(0x800)
    warnings=[]
    # General dungeon objects, then dungeon-specific floor and wall pages.
    buf[0xA00:0x1000]=chunk(data,0xB4000,0x600)
    if m==255:
        buf[0x800:0x900]=chunk(data,0xD6200,0x100)
        buf[0x900:0xA00]=chunk(data,0xD6000,0x100)
        wall=data[0x805C9];item_bank,item_page=0x35,0x61
        page,bank=chunk(data,0x805EA+room*2,2)
        if bank:buf[0x800:0x900]=chunk(data,bank_address(bank,page*256),256)
    else:
        floor=data[0x80589+m];wall=data[0x805A9+m];item_bank,item_page=0x32,data[0x805CA+m]
        buf[0x900:0xA00]=chunk(data,bank_address(0x2D,floor*256),256)
    buf[0xA00:0xC00]=chunk(data,bank_address(0x2D,wall*256),512)
    buf[0x700:0x800]=chunk(data,bank_address(item_bank,item_page*256),256)
    if sideview:
        buf[0x800:]=chunk(data,0xB7000 if m==6 else 0xB7800,0x800)
        selector=None
    elif m!=255:
        from windfish.compatibility.api import indoor_bg_table
        selector=data[indoor_bg_table(data,BG_SELECTORS)+(256 if 6<=m<0x1A else 0)+room]
        effective=inherited if selector==255 else selector
        if not isinstance(effective,int) or not 0<=effective<=0x2F:raise ValueError('Invalid indoor BG graphics selector.')
        buf[0x800:0x900]=chunk(data,0xB5000+effective*256,256)
        if selector==255:warnings.append(f'Inherited BG FF: preview uses block {effective:02X}.')
    else:selector=None
    if record.animation and not sideview:
        try:buf[0xEC0:0xF00]=animation_data(data,record.animation)
        except (ValueError,IndexError):warnings.append('Animation sample is unavailable.')
    return bytes(buf),selector,tuple(warnings)


def tile_sheet(data,map_id,room,sideview=False,inherited=0,animation_frame=None):
    record=read_room(data,map_id,room)
    raw,selector,warnings=graphics(data,record,sideview,inherited)
    if animation_frame is not None:
        if len(animation_frame)!=64:raise ValueError('Animation frame must contain four tiles.')
        raw=bytearray(raw);raw[0xEC0:0xF00]=animation_frame
    mapping=chunk(data,COLOR_FORMATION if map_id==255 else FORMATION,0x400)
    attrs=attributes(data,map_id,room)
    colors=palette(data,map_id,sideview,room)
    sheet=Image.new('RGB',(256,256));pixels=sheet.load()
    for obj in range(256):
        for corner in range(4):
            tid=mapping[obj*4+corner];attr=attrs[obj*4+corner]
            if attr&8:raise ValueError('Dungeon VRAM bank 1 tiles are not supported yet.')
            at=(tid^128)*16;palette_id=(attr&7)*4
            for y in range(8):
                lo,hi=raw[at+y*2:at+y*2+2]
                for x in range(8):
                    value=((lo>>(7-x))&1)|(((hi>>(7-x))&1)<<1)
                    px=7-x if attr&32 else x;py=7-y if attr&64 else y
                    pixels[obj%16*16+corner%2*8+px,obj//16*16+corner//2*8+py]=colors[palette_id+value]
    return sheet,warnings


def render(data,map_id,room,sideview=False,inherited=0,scale=1,template_data=None,door_data=None):
    if not isinstance(scale,int) or not 1<=scale<=4:raise ValueError('Dungeon zoom must be 1-4.')
    record=read_room(data,map_id,room);cells=layout(data,record,template_data,door_data)
    from windfish.dungeon.windfish_dungeon_visuals import apply_to_cells
    cells=apply_to_cells(data,map_id,room,cells)
    sheet,warnings=tile_sheet(data,map_id,room,sideview,inherited)
    image=Image.new('RGB',(160,128))
    for i,obj in enumerate(cells):image.paste(sheet.crop((obj%16*16,obj//16*16,obj%16*16+16,obj//16*16+16)),(i%10*16,i//10*16))
    if scale!=1:image=image.resize((160*scale,128*scale),Image.Resampling.NEAREST)
    return image,record,warnings


def room_bank(map_id):
    return 'Color' if map_id==255 else 'B' if 6<=map_id<26 else 'A'


def room_contexts(data):
    """ROM layout and incoming-warp evidence; no invented owners for unused rooms.

    A shared room can have multiple valid map contexts. Layout membership wins
    for dungeon rooms; otherwise keep every incoming warp context in ROM order.
    """
    from windfish.overworld.windfish_collision_objects import read_room_objects,ALTERNATE_POINTERS
    contexts={};sides=set()
    def add(m,r,side=False):
        if m not in tuple(range(32))+(255,) or m==255 and r>21:return
        key=(room_bank(m),r)
        if m not in contexts.setdefault(key,[]):contexts[key].append(m)
        if side:sides.add((m,r))
    for m,_ in DUNGEONS:
        for collapsed in ((False,True) if m==6 else (False,)):
            for r in map_layout(data,m,collapsed):
                if r is not None:add(m,r)
    def warps(records):
        for raw in records:
            if raw[0]&3 in (1,2):add(raw[1],raw[2],raw[0]&3==2)
    for r in range(256):
        for alt in ((False,True) if r in ALTERNATE_POINTERS else (False,)):
            try:warps(e.raw for e in read_room_objects(data,r,alt).entries if e.kind=='warp')
            except (ValueError,IndexError):pass
    for m in (0,6,255):
        for r in range(22 if m==255 else 256):
            try:warps(read_room(data,m,r).warps)
            except (ValueError,IndexError):pass
    return {k:tuple(v) for k,v in contexts.items()},frozenset(sides)


def attributes(data,map_id,room):
    if map_id==255:return chunk(data,0x8E000,0x400)
    bank=0x23;table=ATTR_POINTERS;index=map_id
    if map_id>=9:
        bank=0x24;table+=0x200
        index={(10,0xFD):15,(17,0xC0):15,(17,0xC1):15,
               (15,0xA0):0,(31,0xEB):20,(31,0xEC):20,
               (16,0xE9):19,(16,0xB5):255}.get((map_id,room),map_id)
        if map_id==22 and room in (0x6F,0x7F,0x8F):bank=0x23
    return chunk(data,bank_address(bank,word(data,table+index*2)),0x400)


def dungeon_names(data):
    """English Rev2 level-title dialog block, FF terminated; Color has no title here."""
    names=dict(DUNGEONS);at=0x53393;limit=0x534AA
    for map_id in range(9):
        end=bytes(data).find(b'\xff',at,limit)
        if end<0:break
        raw=bytes(data[at:end]);at=end+1
        text=' '.join(raw.decode('ascii',errors='replace').replace('^',"'").split())
        if map_id<8 and text.startswith('Level ') and '--' in text:text=text.split('--',1)[1].strip()
        names[map_id]=text
    return names
