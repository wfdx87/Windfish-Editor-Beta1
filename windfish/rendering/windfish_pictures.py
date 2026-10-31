"""Static album pictures use palettes selected by TILESET request, not tilemap.

Mural: tileset $14, map $15. Painting: tileset $20, map $23. The palette
loader indexes Data_021_74F0 with tileset request minus one (interrupts.asm).
"""
from PIL import Image
from windfish.rom.windfish_world_map import decode_frame

MURAL={'graphics':0xC3000,'tilemap':0x23283,'attributes':0x92547,'palettes':0x876D6}

PAINTING={'graphics':0xC3800,'tilemap':0x23781,'attributes':0x925B0,'palettes':0x8772E}
CHRISTINE={'graphics':0xC1800,'tilemap':0x23422,'attributes':0x92459,'palettes':0x87696}

# Camera Shop uses 13 far pointers (address low/high, bank), including the
# alternate first photo. Each raw map is 360 tiles followed by 360 attributes.
# The album loads 256 tiles in signed-ID order and replaces BG palette zero
# with the eight sepia bytes at $28:4424 before displaying a photo.
_ALBUM_NAMES=('Link','Marin at the Cliff','Marin in the Well','Mabe Village',
              'Ulrira','BowWow','Shop Theft','Fisherman','Zora','Kanalet Castle',
              'Ghost','Bridge','Link — Alternate')
PHOTOS=(('Face Shrine Mural','face-shrine-mural',MURAL),
        ('Schule’s Painting','schule-painting',PAINTING),
        ('Christine’s Portrait','christine-portrait',CHRISTINE))+tuple(
        (name,'album-'+str(i+1),{'album':i,'size':4096})
        for i,name in enumerate(_ALBUM_NAMES))

def _far_pointer(data,offset):
    if offset+3>len(data):raise ValueError('Incomplete photo pointer table.')
    address=int.from_bytes(data[offset:offset+2],'little');bank=data[offset+2]
    if not 0x4000<=address<0x8000:raise ValueError('Invalid photo pointer.')
    return bank*0x4000+address-0x4000

def _spec(data,picture):
    spec=PHOTOS[picture][2]
    if 'album' in spec:
        i=spec['album'];layout=_far_pointer(data,0xA0507+i*3)
        return dict(spec,graphics=_far_pointer(data,0xA04E0+i*3),
                    tilemap=layout,attributes=layout+360,palettes=0xA0424)
    return spec


def render_picture(data,picture=0):
    spec=_spec(data,picture);size=spec.get('size',2048)
    if len(data)<spec['graphics']+size:raise ValueError('ROM is too small for the selected picture.')
    if 'album' in spec:
        tiles=data[spec['tilemap']:spec['tilemap']+360]
        attrs=data[spec['attributes']:spec['attributes']+360]
        if len(tiles)!=360 or len(attrs)!=360:raise ValueError('Incomplete photo layout.')
    else:
        tiles=decode_frame(data,spec['tilemap'],0)
        attrs=decode_frame(data,spec['attributes'],0)
    raw=data[spec['graphics']:spec['graphics']+size]
    colors=[]
    for offset in range(spec['palettes'],spec['palettes']+(8 if 'album' in spec else 64),2):
        word=int.from_bytes(data[offset:offset+2],'little')
        colors.append(tuple(((word>>shift)&31)*8 for shift in (0,5,10)))
    image=Image.new('RGB',(160,144));cache={}
    for cy in range(18):
        for cx in range(20):
            pos=cy*(20 if 'album' in spec else 32)+cx;tile,attr=tiles[pos],attrs[pos]
            if tile>=size//16 or attr&8 or ('album' in spec and attr&7):raise ValueError('Picture uses graphics outside the researched tile bank.')
            key=(tile,attr)
            if key not in cache:
                piece=Image.new('RGB',(8,8));start=tile*16
                for y in range(8):
                    lo,hi=raw[start+y*2:start+y*2+2]
                    for x in range(8):
                        bit=x if attr&32 else 7-x;value=((lo>>bit)&1)|(((hi>>bit)&1)<<1)
                        piece.putpixel((x,7-y if attr&64 else y),colors[(attr&7)*4+value])
                cache[key]=piece
            image.paste(cache[key],(cx*8,cy*8))
    return image


def extract_mural_gfx(data):return extract_picture_gfx(data,0)


def mural_gfx_changes(data,raw):return picture_gfx_changes(data,raw,0)


def render_mural(data):return render_picture(data,0)


def extract_picture_gfx(data,picture=0):
    spec=_spec(data,picture);start=spec['graphics'];size=spec.get('size',2048)
    raw=bytes(data[start:start+size])
    if len(raw)!=size:raise ValueError('Incomplete picture graphics.')
    return raw


def picture_gfx_changes(data,raw,picture=0):
    spec=_spec(data,picture);size=spec.get('size',2048)
    if len(raw)!=size:raise ValueError(f'Picture GFX must be exactly {size} bytes ({size//16} Game Boy 2bpp tiles).')
    original=extract_picture_gfx(data,picture);start=spec['graphics']
    return [(start+i,old,new) for i,(old,new) in enumerate(zip(original,raw)) if old!=new]


def extract_picture_tilemap(data,picture=0):
    """Raw VRAM tile IDs: 20 columns by 18 rows, no header or attributes."""
    spec=_spec(data,picture);start=spec['tilemap']
    if 'album' in spec:
        raw=bytes(data[start:start+360])
        if len(raw)!=360:raise ValueError('Incomplete photo tilemap.')
        return raw
    grid=decode_frame(data,start,0)
    return bytes(grid[y*32+x] for y in range(18) for x in range(20))


def picture_tilemap_changes(data,raw,picture=0):
    """Import IDs without touching graphics, attributes, palettes or pointers.

    Static pictures use engine draw commands; encode 18 literal rows within
    their original allocation. Never borrow space from an adjacent picture.
    Camera Shop layouts already store the same 360 raw bytes we export.
    """
    if len(raw)!=360:raise ValueError('Tilemap must be exactly 360 bytes (20 × 18 tile IDs).')
    spec=_spec(data,picture);start=spec['tilemap']
    if any(tile>=spec.get('size',2048)//16 for tile in raw):
        raise ValueError('This picture only loads tile IDs 00–7F.')
    if raw==extract_picture_tilemap(data,picture):return []
    if 'album' in spec:encoded=bytes(raw)
    else:
        capacity={0:415,1:415,2:449}[picture]
        # Validate the current stream is contained in the researched block
        # and only writes the visible picture before replacing it.
        at=start;end=start+capacity
        while True:
            if at>=end:raise ValueError('Picture tilemap exceeds its reserved block.')
            high=data[at]
            if not high:break
            if at+3>end:raise ValueError('Incomplete picture command.')
            address=(high<<8)|data[at+1];flags=data[at+2]
            count=(flags&63)+1;step=32 if flags&128 else 1
            for i in range(count):
                pos=address-0x9800+i*step
                if not 0<=pos<18*32 or pos%32>=20:
                    raise ValueError('Picture has custom off-screen commands; import is not supported.')
            at+=3+(1 if flags&64 else count)
            if at>end:raise ValueError('Incomplete picture command.')
        encoded=bytearray()
        for y in range(18):
            address=0x9800+y*32
            encoded.extend((address>>8,address&255,19));encoded.extend(raw[y*20:y*20+20])
        encoded.append(0)
        if len(encoded)>capacity:raise ValueError('Tilemap does not fit the picture block.')
    if start+len(encoded)>len(data):raise ValueError('Incomplete photo tilemap.')
    return [(start+i,data[start+i],new) for i,new in enumerate(encoded) if data[start+i]!=new]
