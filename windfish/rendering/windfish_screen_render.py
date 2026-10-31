"""Read-only graphics decoding for title and file-menu screens."""
from PIL import Image
from windfish.rom import windfish_screen_maps as maps


def segments(kind):
    # (VRAM ID start, ROM graphics start, byte count). File-menu font and
    # graphics are shared assets; imports deliberately edit those same assets.
    if kind=='title':return ((0,0xC0800,2048),(0x80,0xBC900,1792))
    if kind in ('file','copy','erase'):return ((0,0xBD000,2048),(0x80,0xBC000,1024),(0xC0,0xB0C00,512),(0xE0,0xB07A0,32),(0xE2,0xB0E20,480))
    return ((0x7F,0x3D7F0,16),(0x80,0x3C400,1280))


def raw_gfx(data,kind):return b''.join(bytes(data[at:at+size]) for _,at,size in segments(kind))


def tile_image(data,kind,identifier,attribute):
    pal=maps.SPECS[kind][2];start=None
    for first,at,size in segments(kind):
        if first<=identifier<first+size//16:start=at+(identifier-first)*16;break
    if start is None:return Image.new('RGB',(8,8),'#555555')
    if attribute&8:raise ValueError('VRAM bank 1 graphics are not supported by this screen.')
    im=Image.new('RGB',(8,8));base=pal+(attribute&7)*8
    colors=[tuple(((int.from_bytes(data[a:a+2],'little')>>s)&31)*8 for s in (0,5,10)) for a in range(base,base+8,2)]
    for y in range(8):
        lo,hi=data[start+y*2:start+y*2+2]
        for x in range(8):
            bit=x if attribute&32 else 7-x;value=((lo>>bit)&1)|(((hi>>bit)&1)<<1)
            im.putpixel((x,7-y if attribute&64 else y),colors[value])
    return im


