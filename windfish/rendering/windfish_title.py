"""Read-only CGB title background: signed BG IDs plus separate DX sprites."""
from PIL import Image
from windfish.rom.windfish_world_map import decode_frame

TILEMAP=0x2310A
ATTRMAP=0x93BF0
PALETTES=0x87DEE


def colors(data):
    return [tuple(((int.from_bytes(data[i:i+2],'little')>>s)&31)*8 for s in (0,5,10))
            for i in range(PALETTES,PALETTES+64,2)]


def graphics(data):
    if len(data)<0xE1C00:raise ValueError('ROM is too small for title graphics.')
    # Intro1 supplies signed BG IDs 00–7F at $9000; the title logo
    # replaces $8800–8EFF (IDs 80–EF). Read in ID order, not file order.
    return bytes(data[0xC0800:0xC1000]+data[0xBC900:0xBD000]+bytes(256))


def grids(data):
    return decode_frame(data,TILEMAP,0x7F),decode_frame(data,ATTRMAP,0)


def tile(data,identifier,attribute=0):
    if attribute&8:raise ValueError('Unresearched title VRAM bank 1 tile.')
    raw=graphics(data);pal=colors(data);im=Image.new('RGB',(8,8));at=identifier*16
    for y in range(8):
        lo,hi=raw[at+y*2:at+y*2+2]
        for x in range(8):
            bit=x if attribute&32 else 7-x
            value=((lo>>bit)&1)|(((hi>>bit)&1)<<1)
            im.putpixel((x,7-y if attribute&64 else y),pal[(attribute&7)*4+value])
    return im


def render(data):
    ids,attrs=grids(data);im=Image.new('RGB',(160,144));cache={}
    for y in range(18):
        for x in range(20):
            key=(ids[y*32+x],attrs[y*32+x])
            if key not in cache:cache[key]=tile(data,*key)
            im.paste(cache[key],(x*8,y*8))
    return im


def sheet(data,palette=0):
    im=Image.new('RGB',(128,128))
    for i in range(256):im.paste(tile(data,i,palette),((i%16)*8,(i//16)*8))
    return im


def render_complete(data,dx=True):
    im=render(data)
    if not dx:return im
    # Locate the US final DX OAM definition/palette in bank 1. Native and
    # VWF builds have different bank-1 offsets; never assume one address.
    definition=data.find(bytes.fromhex('002852160020501610184e1600184c16'),0x4000,0x8000)
    palette=data.find(bytes.fromhex('f57a0000b1215f3f'),0x4000,0x8000)
    if definition<0 or palette<0:raise ValueError('Unsupported title DX sprite layout/palette.')
    pal=[tuple(((int.from_bytes(data[i:i+2],'little')>>s)&31)*8 for s in (0,5,10)) for i in range(palette,palette+8,2)]
    for at in range(definition,definition+40,4):
        dy,dxpos,identifier,flags=data[at:at+4]
        for y in range(16):
            raw=0xE1800+(identifier-0x40)*16+y*2
            lo,hi=data[raw:raw+2]
            for x in range(8):
                bit=x if flags&32 else 7-x;value=((lo>>bit)&1)|(((hi>>bit)&1)<<1)
                if not value:continue
                px=112+dxpos+x;py=73+dy+(15-y if flags&64 else y)
                if 0<=px<160 and 0<=py<144:im.putpixel((px,py),pal[value])
    return im
