"""Read-only Link's Awakening DX Rev 2 overworld renderer, based on LALE TileLoader.cs.
Requires Pillow: python -m pip install pillow
"""
import argparse
from pathlib import Path
from PIL import Image
# Direct overworld maps are stored as 80-byte grids.
SPECIAL_MAP = {0x06:0x5040, 0x0E:0x5090, 0x1B:0x50E0,
               0x2B:0x5130, 0x79:0x5180, 0x8C:0x51D0}

def direct_map(data, room, special=False):
    if not 0 <= room <= 0xFF:
        raise ValueError("room must be between 0x00 and 0xFF")
    if special and room in SPECIAL_MAP:
        offset = 0x98000 + SPECIAL_MAP[room]
    elif room < 0xCC:
        offset = 0x98000 + room * 0x50
    else:
        offset = 0x9C000 + (room - 0xCC) * 0x50
    if offset + 80 > len(data):
        raise ValueError("ROM is too small for this room map")
    return offset, list(data[offset:offset + 80])

def u16(d,p): return d[p] | (d[p+1]<<8)
def bankptr(d,p): return (p//0x4000)*0x4000 + u16(d,p)-0x4000

def palette(d,room):
    idx=d[0x842EF+room]
    from windfish.rom.windfish_palette_patch import is_installed
    if 0x1F <= idx <= 0x3F and is_installed(d):
        at = 0x1D2C00 + (idx - 0x1F) * 0x50
    else:
        at=bankptr(d,0x842B1+idx*2)
    colors=[]
    for i in range(32):
        v=u16(d,at+i*2)
        colors.append(((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3))
    return idx,at,colors

def animation_id(d,room,special=False):
    from windfish.rom.windfish_collision_storage import enabled,resolve_stream
    if enabled(d):
        start,_=resolve_stream(d,room,special)
        return d[start]
    special_ptr={6:0x31F4,14:0x31C4,27:0x3204,43:0x3214,121:0x31E4,140:0x31D4}
    if special and room in special_ptr:
        p=bankptr(d,special_ptr[room]); p+=0x68000 if room>127 else 0x24000
    else:
        p=bankptr(d,0x24000+room*2)
        if room>127:p+=0x44000
    return d[p]

def animation_data(d,aid):
    from windfish.rendering.windfish_animation_editor import frame_address, SPECIAL
    if aid not in SPECIAL and 0 <= aid < 18:
        at = frame_address(d, aid)
        return d[at:at+64]
    if aid==7:return d[0xB2D00:0xB2D40]
    p=u16(d,0x1BD0+aid*2)
    # Mirrors LALE Animate(): scan for byte 0x26 then read next byte as graphics page
    for _ in range(0x4000):
        if d[p]==0x26:
            page=d[p+1]
            at=0xB0000+(page-0x40)*0x100
            return d[at:at+0x40]
        p+=1
    raise ValueError(f'Animation command 0x26 not found for {aid:02X}')

def sog_id(d,room):
    from windfish.rom.windfish_bg_graphics import selector_offset
    return d[selector_offset(d,room)]


def graphics(d,room,special=False):
    sog=sog_id(d,room)
    from windfish.rom.windfish_bg_graphics import block_data
    from windfish.rom.windfish_room_graphics import custom,landscape_data
    chunk=landscape_data(d,room) if custom(d,room) else (bytes(0x200) if sog==0x0F else block_data(d,room))+bytes(d[0xB1200:0xB1800])
    buf=bytearray(d[0xB0F00:0xB1000]+chunk)
    aid=animation_id(d,room,special)
    buf[0x7C0:0x800]=animation_data(d,aid)
    if len(buf)!=0x900:raise ValueError(f'Unexpected tile graphics size {len(buf):X}')
    return sog,aid,buf

def attributes(d,room):
    bank=d[0x6A476+room]
    p=0x69E76+room*2
    at=bank*0x4000 + d[p]+(d[p+1]-0x40)*0x100
    return at,d[at:at+0x400]

def render(d,room,special=False,scale=3,animation_frame=None):
    palid,palat,pals=palette(d,room)
    sog,anim,gfx=graphics(d,room,special)
    if animation_frame is not None:
        if len(animation_frame) != 64: raise ValueError("Animation frame must contain four tiles.")
        gfx[0x7C0:0x800] = animation_frame
    attrat,attrs=attributes(d,room)
    from windfish.rom.windfish_room_tiles import definition_offset,is_custom
    custom=is_custom(d,room)
    formation_at=definition_offset(d,room)
    formation=d[formation_at:formation_at+0x400]
    from windfish.rom import windfish_shared_map16 as shared
    extra=shared.enabled(d)
    if extra:
        from windfish.rom.windfish_room_map16 import offsets
        page_at,page_attr=offsets(d,room)
        formation=bytes(formation)+bytes(d[page_at:page_at+1024])
        attrs=bytes(attrs)+bytes(d[page_attr:page_attr+1024])
    custom_gfx=bytearray(d[0xB0800:0xB1000])+gfx[0x100:]
    count=512 if extra else 256
    if len(formation)!=count*4 or len(attrs)!=count*4:raise ValueError('Missing tile definitions')
    from windfish.rom.windfish_vram_bank1 import background_data
    bank1_gfx=background_data(d,room)
    tiles=Image.new('RGB',(256,16*(count//16)))
    # A 512-metatile sheet repeats many 8x8 pieces. Decode each source tile
    # and palette once, then let Pillow paste/flip the reusable 8x8 image.
    # This cache belongs to this one sheet build, so edits cannot leave stale
    # colors, VRAM-bank data or animation frames behind.
    pieces={}
    for t in range(count):
        raw_mapping=custom or t>=256
        for corner in range(4):
            raw_tid=formation[t*4+corner]
            tid=raw_tid
            if not raw_mapping and (0xB0<=tid<0xB4 or tid==0xC0):tid=0
            tid=(tid^0x80) if raw_mapping else (tid+0x10)&0xFF
            a=attrs[t*4+corner]
            pal=a&7
            source_id=2 if a&8 else 1 if raw_mapping else 0
            source=(gfx,custom_gfx,bank1_gfx)[source_id]
            if a&8:tid=raw_tid^0x80
            key=(source_id,tid,pal)
            piece=pieces.get(key)
            if piece is None:
                pixels=[]
                for y in range(8):
                    lo=source[tid*16+y*2];hi=source[tid*16+y*2+1]
                    pixels.extend(pals[pal*4+((lo>>bit)&1)+(((hi>>bit)&1)<<1)] for bit in range(7,-1,-1))
                piece=Image.new('RGB',(8,8));piece.putdata(pixels)
                pieces[key]=piece
            if a&0x60:
                flip_key=key+(a&0x60,)
                flipped=pieces.get(flip_key)
                if flipped is None:
                    flipped=piece
                    if a&0x20:flipped=flipped.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    if a&0x40:flipped=flipped.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    pieces[flip_key]=flipped
                piece=flipped
            tiles.paste(piece,((t%16)*16+(corner%2)*8,(t//16)*16+(corner//2)*8))
    mapat,grid=direct_map(d,room,special)
    if extra:grid=shared.cells(d,room,special)
    result=Image.new('RGB',(160,128))
    for i,t in enumerate(grid):
        result.paste(tiles.crop(((t%16)*16,(t//16)*16,(t%16+1)*16,(t//16+1)*16)),((i%10)*16,(i//10)*16))
    if scale!=1:
        result=result.resize((160*scale,128*scale),Image.Resampling.NEAREST)
    return result,tiles,{'palette_id':palid,'palette_offset':palat,'sog':sog,'animation':anim,'attributes_offset':attrat,'map_offset':mapat}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',type=Path)
    p.add_argument('--room',type=lambda s:int(s,0),default=0)
    p.add_argument('--special',action='store_true')
    p.add_argument('--scale',type=int,default=3)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    if not 0<=args.room<=255 or not 1<=args.scale<=10:p.error('room 0..255, scale 1..10')
    data=args.rom.read_bytes()
    if len(data) not in (0x100000,0x200000) or data[0x14C]!=2:p.error('Expected 1 or 2 MiB Link\'s Awakening DX Rev 2 ROM')
    img,tiles,info=render(data,args.room,args.special,args.scale)
    path=args.output or Path(f'room_{args.room:02X}{"_alternate" if args.special else ""}.png')
    img.save(path)
    tiles.save(path.with_name(path.stem+'_tileset.png'))
    print('Saved',path,'and tileset; ROM info:',info)
if __name__=='__main__':main()
