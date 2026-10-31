"""Reusable ExGFX 00-FF library, four independently selected blocks per room.

Banks 40-47 hold 256 reusable 512-byte blocks. Bank 6E holds
helpers and flags. CGB scrolling uses four bounded 512-byte GDMA steps;
DMG keeps its original eight 64-byte CPU transfers. Cached bank is untouched.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.compatibility import api as profile

from windfish.rom.windfish_room_tiles import _assemble
import windfish.rom.windfish_bg_graphics as bg
DATA_START=allocation['exgfx'].start
DATA_END=allocation['exgfx'].end
START=allocation['graphics_engine'].start
END=START+0x4000
BANK=0x6E
MARKER=ID_SLOTS['graphics']
MAGIC=b'WFRG0003'
FLAGS=START+0x1000
SLOTS=START+0x1100
ASSET_FLAGS=START+0x1500
SLOT_MASKS=START+0x1600
BIT_TABLE=START+0x1700
# Fixed-bank space reuses only the existing 72-byte overworld VBlank loader.
VBLANK=bg.VBLANK
FULL=bg.FULL
DMA=VBLANK+24
CPU=VBLANK+48
RESTORE=VBLANK+60

def call(at):return bytes((0xCD,at&255,at>>8))
def jump(at):return bytes((0xC3,at&255,at>>8))
VBLANK_CODE=(bytes.fromhex('3e 6e ea 00 21')+call(0x4000)+jump(RESTORE)).ljust(12,b'\0')
VBLANK_CODE+=(bytes.fromhex('3e 6e ea 00 21')+call(0x4100)+jump(RESTORE)).ljust(12,b'\0')
# A=source bank, HL=source, DE=destination, B=(length/16)-1.
VBLANK_CODE+=(bytes.fromhex('ea 00 21 7c e0 51 7d e0 52 7a e0 53 7b e0 54 78 e0 55 3e 6e ea 00 21 c9'))
VBLANK_CODE+=bytes.fromhex('ea 00 21 cd 0b 29 3e 6e ea 00 21 c9')
VBLANK_CODE+=bytes.fromhex('fa af db ea 00 21 c9')
VBLANK_CODE=VBLANK_CODE.ljust(len(bg.VBLANK_ORIGINAL),b'\0')
FULL_CODE=(jump(VBLANK+12)).ljust(len(bg.FULL_ORIGINAL),b'\0')
# Keep legacy per-room selection, but schedule all CGB room changes. This
# restores shared graphics when leaving a custom room, even for equal BG IDs.
_select=bytearray(bg._code)
for branch in (23,28):_select[branch+1]=len(_select)-(branch+2)
SELECT_CODE=(bytes(_select)+bytes.fromhex('f0 fe a7 28 04 3e 01 e0 90')).ljust(len(bg.PATCH),b'\0')

# Stage helper: A=0..3. Select the room's complete replacement or the original
# 32-tile block followed by the shared 96 tiles. Call fixed-bank DMA and return
# while still executing bank 6E. No CPU executes from a bank being unmapped.
PHASE=0x4200
_phase=_assemble([
 'f5 f0 f6 6f 26 50 7e a7',(0x28,'original'),
 # Check the room slot mask; a clear bit means original graphics for this slot.
 'f0 f6 6f 26 56 7e 47 f1 f5 6f 26 57 7e a0',(0x28,'original'),
 # HL = room_slots + room*4 + phase; read ExGFX ID.
 'f0 f6 6f 26 00 29 29 11 00 51 19 f1 f5 5f 16 00 19 7e 4f',
 # 32 blocks per bank, each block aligned to 200 hex bytes.
 'e6 1f 87 c6 40 67 2e 00 79 cb 3f cb 3f cb 3f cb 3f cb 3f c6 40 4f',
 (0x18,'dest'),
 ('label','original'),'f1 f5 a7',(0x28,'block'),
 '3d 87 c6 52 67 2e 00 0e 2c',(0x18,'dest'),
 ('label','block'),'f0 94 c6 40 e6 7f 67 2e 00 f0 94 e6 80 0e 2f',(0x28,'dest'),'0e 75',
 ('label','dest'),'f1 87 c6 90 57 1e 00 06 1f 79',call(DMA).hex(),'c9'])
# During scrolling the engine suspends animation updates. Preserve the live
# four-tile animation frame rather than replacing it with static BG data.
BASE_PHASE=_phase
_phase=_assemble([
 bytes(BASE_PHASE[:-4]).hex(),
 'fa 24 c1 a7',(0x28,'whole'),
 # Normal groups animate 96C0; group 07 also animates 90C0.
 '7a fe 90',(0x20,'upper'),
 'f0 a4 fe 07',(0x28,'split'),(0x18,'whole'),
 ('label','upper'),'fe 96',(0x20,'whole'),
 # Photography (11) uses its own destination table.
 'f0 a4 a7',(0x28,'whole'),
 'fe 11',(0x28,'whole'),
 ('label','split'),'06 0b 79',call(DMA).hex(),
 # Copy xx00-xxBF and (xx+1)00-(xx+1)FF; preserve xxC0-xxFF.
 '7c 3c 67 7a 3c 57 06 0f 79',call(DMA).hex(),'c9',
 ('label','whole'),'79',call(DMA).hex(),'c9'])
VBLANK_HELPER=_assemble([
 'f0 fe a7',(0x28,'dmg'),
 'f0 4f f5 af e0 4f f0 92',call(PHASE).hex(),
 'f1 e0 4f f0 92 3c e0 92 fe 04',(0x20,'return'),'af e0 90 e0 92',('label','return'),'c9',
 ('label','dmg'),
 # Offset BC=stage*64, destination9000+offset, source selected block+offset.
 'f0 92 4f 06 00',*['cb 21 cb 10']*6,
 '21 00 90 09 5d 54 f0 94 c6 40 e6 7f 67 2e 00 09 01 40 00',
 'f0 94 e6 80 3e 0f',(0x28,'copy'),'3e 75',('label','copy'),call(CPU).hex(),
 'f0 92 3c e0 92 fe 08',(0x20,'done'),'af e0 90 e0 92',('label','done'),'c9'])
FULL_HELPER=_assemble([
 'f0 fe a7',(0x28,'dmg'),
 'f0 4f f5 af e0 4f',*sum(([f'3e {i:02x}',call(PHASE).hex()] for i in range(4)),[]),'f1 e0 4f c9',
 ('label','dmg'),'f0 94 fe 0f',(0x28,'done'),
 'c6 40 e6 7f 67 2e 00 01 00 02 f0 94 e6 80 3e 0f',(0x28,'copy'),'3e 75',
 ('label','copy'),call(CPU).hex(),('label','done'),'c9'])
HELPERS={START:VBLANK_HELPER,START+0x100:FULL_HELPER,START+0x200:_phase}
HOOKS={VBLANK:VBLANK_CODE,FULL:FULL_CODE,bg.HOOK:SELECT_CODE}


def version(data):
    if len(data)<END:return 0
    marker=bytes(data[MARKER:MARKER+8])
    return 3 if marker==MAGIC else 0


def enabled(data):return bool(version(data))


def validate(data):
    ver=version(data)
    if not ver:
        if len(data)>=END and bytes(data[MARKER:MARKER+4])==b'WFRG':raise ValueError('Unsupported room graphics patch version.')
        if bytes(data[VBLANK:VBLANK+len(VBLANK_CODE)])==VBLANK_CODE:raise ValueError('Room graphics patch marker is missing.')
        return False
    if bytes(data[bg.MARKER:bg.MARKER+8])!=bg.MAGIC:raise ValueError('Room graphics requires the current BG selection patch.')
    helpers=dict(HELPERS)
    expected_code=profile.code(data,'graphics') if profile.is_vwf(data) else {**HOOKS,**helpers}
    from windfish.rom import windfish_vram_bank1 as bank1
    expected_code=bank1.expected(data,expected_code)
    from windfish.rom.windfish_shared_map16 import adapt_code
    expected_code=adapt_code(data,expected_code)
    bank1.validate(data)
    for at,raw in expected_code.items():
        if bytes(data[at:at+len(raw)])!=raw:raise ValueError('Room graphics loader is damaged.')
    if any(v not in (0,1) for v in data[FLAGS:FLAGS+256]):raise ValueError('Invalid room graphics flags.')
    if ver>=2:
        if bytes(data[BIT_TABLE:BIT_TABLE+4])!=bytes((1,2,4,8)):raise ValueError('Room graphics slot mask helper is damaged.')
        if any(v not in (0,1) for v in data[ASSET_FLAGS:ASSET_FLAGS+256]):raise ValueError('Invalid ExGFX library flags.')
        for room in range(256):
            mask=data[SLOT_MASKS+room]
            if mask>15:raise ValueError('Invalid room graphics slot mask.')
            for slot in range(4):
                if mask&(1<<slot) and not data[ASSET_FLAGS+data[SLOTS+room*4+slot]]:
                    raise ValueError('Room graphics references an empty ExGFX ID.')
    return True


def install(data):
    if profile.is_vwf(data):
        validate(data)
        if not profile.ready(data):raise ValueError('Reopen the ROM to install the VWF editing engine.')
        return bytearray(data)
    from windfish.rom.windfish_rom import validate as validate_rom
    validate_rom(data)
    if version(data)==3:return bytearray(data)
    if len(data)!=0x200000:raise ValueError('A 2 MiB Windfish ROM is required.')
    for start,end in ((DATA_START,DATA_END),(START,END)):
        if any(v!=255 for v in data[start:end]):raise ValueError('Reserved ExGFX storage is occupied.')
    out=bg.install(data)
    out[START:END]=bytes(0x4000)
    out[MARKER:MARKER+8]=MAGIC
    out[BIT_TABLE:BIT_TABLE+4]=bytes((1,2,4,8))
    for at,raw in {**HOOKS,**HELPERS}.items():out[at:at+len(raw)]=raw
    validate_rom(out)
    return out


def asset_offset(asset):
    if not isinstance(asset,int) or not 0<=asset<=255:raise ValueError('ExGFX ID must be 00-FF.')
    return DATA_START+asset*512


def available_assets(data):return [i for i in range(256) if version(data)>=2 and data[ASSET_FLAGS+i]]


def asset_data(data,asset):
    at=asset_offset(asset)
    if asset not in available_assets(data):raise ValueError(f'ExGFX {asset:02X} has not been inserted.')
    return bytes(data[at:at+512])


def custom(data,room):
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Overworld room must be 00-FF.')
    return enabled(data) and data[FLAGS+room]==1


def room_slots(data,room):
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Overworld room must be 00-FF.')
    if version(data)<2:return (None,)*4
    mask=data[SLOT_MASKS+room]
    return tuple(data[SLOTS+room*4+i] if mask&(1<<i) else None for i in range(4))


def original_block(data,room,slot):
    if slot==0:return bg.block_data(data,room)
    at=0xB1200+(slot-1)*512
    return bytes(data[at:at+512])


def export_block(data,room,slot):
    if not isinstance(slot,int) or not 0<=slot<4:raise ValueError('Graphics block must be 0-3.')
    if custom(data,room):
        asset=room_slots(data,room)[slot]
        if asset is not None:return asset_data(data,asset)
    return original_block(data,room,slot)


def export_blocks(data,room):return tuple(export_block(data,room,i) for i in range(4))
def landscape_data(data,room):
    # KEEP depends on the previous runtime room. Match the existing preview's
    # blank fallback for that one unknown slot while rendering other slots.
    parts=[]
    for slot in range(4):
        inherited=(slot==0 and data[bg.selector_offset(data,room)]==15 and
            not (custom(data,room) and room_slots(data,room)[0] is not None))
        parts.append(bytes(512) if inherited else export_block(data,room,slot))
    return b''.join(parts)


def _changes(data,out):return [(i,b,a) for i,(b,a) in enumerate(zip(data,out)) if b!=a]


def insert_assets(data,entries):
    """Prepare a batch of filename-ID/payload pairs without assigning a room."""
    entries=list(entries);seen=set()
    for asset,raw in entries:
        asset_offset(asset)
        if asset in seen:raise ValueError(f'Duplicate ExGFX ID {asset:02X} in this insertion.')
        if len(raw)!=512:raise ValueError(f'ExGFX {asset:02X} must contain exactly 512 bytes (32 Game Boy 2bpp tiles).')
        seen.add(asset)
    if not seen:raise ValueError('Choose at least one exgfx_XX.bin file.')
    out=install(data)
    for asset,raw in entries:
        at=asset_offset(asset);out[at:at+512]=raw;out[ASSET_FLAGS+asset]=1
    validate(out)
    return _changes(data,out)


def filename_id(path):
    import re
    from pathlib import Path
    match=re.fullmatch(r'exgfx_([0-9a-f]{2})\.bin',Path(path).name,re.IGNORECASE)
    if not match:raise ValueError('Use filenames exgfx_00.bin through exgfx_FF.bin (two hexadecimal digits).')
    return int(match.group(1),16)


def assign_slots(data,room,slots,enabled=True):
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Overworld room must be 00-FF.')
    if len(slots)!=4:raise ValueError('A room has four graphics slots.')
    out=install(data)
    mask=0
    for i,asset in enumerate(slots):
        if asset is not None:
            asset_data(out,asset);mask|=1<<i;out[SLOTS+room*4+i]=asset
        else:out[SLOTS+room*4+i]=0
    out[SLOT_MASKS+room]=mask;out[FLAGS+room]=int(bool(enabled));validate(out)
    return _changes(data,out)


def use_original(data,room):
    return [(FLAGS+room,1,0)] if custom(data,room) else []


def import_blocks(data,room,blocks):
    """Compatibility helper: deduplicate four blocks and assign library IDs."""
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Overworld room must be 00-FF.')
    if len(blocks)!=4 or any(len(block)!=512 for block in blocks):
        raise ValueError('Choose four files, each exactly 512 bytes (32 Game Boy 2bpp tiles).')
    out=install(data);slots=[]
    for raw in blocks:
        asset=next((i for i in available_assets(out) if asset_data(out,i)==raw),None)
        if asset is None:
            asset=next((i for i in range(256) if not out[ASSET_FLAGS+i]),None)
            if asset is None:raise ValueError('All 256 ExGFX IDs are occupied.')
            at=asset_offset(asset);out[at:at+512]=raw;out[ASSET_FLAGS+asset]=1
        slots.append(asset)
    for at,b,a in assign_slots(out,room,slots):out[at]=a
    return _changes(data,out)
