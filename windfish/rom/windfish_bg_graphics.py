"""Experimental per-room overworld BG block selectors for English Rev2."""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.compatibility import api as profile

TABLE=allocation['palettes_and_bg'].start+0x3800
MARKER=ID_SLOTS['bg']
MAGIC=b'WFBG0003'
HOOK=0xD55
ORIGINAL=bytes.fromhex('f0 f6 fe 07 20 01 3c 57 cb 3f cb 3f e6 f8 5f 7a cb 3f e6 07 b3 5f 16 00 21 7b 6e 19 f0 94 5f 7e bb 28 15 fe 0f 28 11 fe 1a 20 07 f0 f6 fe 37 20 07 7e e0 94 3e 01 e0 90')
NAME='room-bg-graphics-patch'
# SelectRoomTilesets deliberately changes the hardware bank without changing
# wCurrentBank: that variable belongs to its CALLER and is used on return.
_code=bytearray.fromhex('f0 f6 5f 16 00 3e 74 ea 00 21 21 00 78 19 5e 3e 20 ea 00 21 f0 94 bb 28 00 7b fe 0f 28 00 e0 94 3e 01 e0 90')
for branch in (23,28):_code[branch+1]=len(ORIGINAL)-(branch+2)
# Normal selection skips the helper; the two BG copy paths CALL it directly.
HELPER=HOOK+38
BANK_HELPER=bytes.fromhex('f0 94 e6 80 3e 2f 28 02 3e 74 ea 00 21 c9')
PATCH=bytes(_code)+bytes((0x18,len(ORIGINAL)-38))+BANK_HELPER+bytes(len(ORIGINAL)-38-len(BANK_HELPER))
FLAGS=TABLE+0x110
CUSTOM_IDS=(0xBA,0xBC,0xBE)
CUSTOM_START=allocation['bg_import_blocks'].start+0x3A00
VBLANK=0x652
VBLANK_ORIGINAL=bytes.fromhex('3e 0f cd 07 0b ea 00 21 f0 92 4f 06 00 cb 21 cb 10 cb 21 cb 10 cb 21 cb 10 cb 21 cb 10 cb 21 cb 10 cb 21 cb 10 21 00 90 09 5d 54 f0 94 c6 40 67 2e 00 09 01 40 00 cd 0b 29 f0 92 3c e0 92 fe 08 20 05 af e0 90 e0 92 c9')
FULL=0x2FA4
FULL_ORIGINAL=bytes.fromhex('3e 0f cd 07 0b ea 00 21 f0 94 fe 0f 28 0b c6 40 67 2e 00 01 00 02 cd 0b 29 c9')
def copy_hook(raw):
    result=bytes((0xCD,HELPER&255,HELPER>>8))+raw[8:]
    result=result.replace(bytes.fromhex('c6 40 67'),bytes.fromhex('c6 40 e6 7f 67'))
    if raw==FULL_ORIGINAL:result=result.replace(bytes.fromhex('28 0b'),bytes.fromhex('28 0d'))
    return result+bytes(len(raw)-len(result))
COPY_HOOKS={VBLANK:(VBLANK_ORIGINAL,copy_hook(VBLANK_ORIGINAL)),FULL:(FULL_ORIGINAL,copy_hook(FULL_ORIGINAL))}


def enabled(data):
    return bytes(data[MARKER:MARKER+8]) ==MAGIC


def legacy_offset(room):
    r=8 if room==7 else room
    return 0x82E7B+(((r>>1)&7)|((r>>2)&0xF8))


def selector_offset(data,room):
    return TABLE+room if enabled(data) else profile.original_bg_selector(data,room)


def validate(data):
    if profile.is_vwf(data):
        profile.check_code(data,'graphics')
        if bytes(data[MARKER:MARKER+8])!=MAGIC:raise ValueError('VWF BG marker is damaged.')
        if any(v not in (0,1) for v in data[FLAGS:FLAGS+3]):raise ValueError('Invalid custom BG slot flags.')
        for value in data[TABLE:TABLE+256]:
            if value<=0x3E:continue
            if value not in CUSTOM_IDS or not data[FLAGS+CUSTOM_IDS.index(value)]:raise ValueError('Invalid VWF BG selector.')
        return True
    from windfish.rom.windfish_room_graphics import enabled as graphics_enabled, validate as validate_graphics, HOOKS
    from windfish.rom.windfish_shared_map16 import adapt_code
    HOOKS=adapt_code(data,HOOKS)
    extended=graphics_enabled(data)
    if extended:validate_graphics(data)
    marker=bytes(data[MARKER:MARKER+8])
    if marker ==MAGIC:
        expected=HOOKS[HOOK] if extended else PATCH
        if bytes(data[HOOK:HOOK+len(PATCH)])!=expected:raise ValueError('Room BG graphics marker and loader disagree.')
        if marker==MAGIC:
            for at,(old,new) in COPY_HOOKS.items():
                if bytes(data[at:at+len(new)])!=(HOOKS[at] if extended else new):raise ValueError('Custom BG copy hook is damaged.')
            if any(v not in (0,1) for v in data[FLAGS:FLAGS+3]):raise ValueError('Invalid custom BG slot flags.')
        for value in data[TABLE:TABLE+256]:
            if value<=0x3E:continue
            if marker!=MAGIC or value not in CUSTOM_IDS or data[FLAGS+CUSTOM_IDS.index(value)]!=1:
                raise ValueError('Invalid or uninitialized room BG graphics selector.')
        return True
    # Original ROMs leave this reserved area empty. A recognizable unsupported
    # version must not be mistaken for an unpatched ROM.
    if marker.startswith(b'WFBG'):raise ValueError('Unsupported room BG graphics patch version.')
    if bytes(data[HOOK:HOOK+len(PATCH)]) ==PATCH:raise ValueError('Room BG graphics patch marker is missing.')
    return False


def install(data):
    if profile.is_vwf(data):
        validate(data)
        if not profile.ready(data):raise ValueError('Reopen the ROM to install the VWF editing engine.')
        return bytearray(data)
    if len(data) not in (0x100000,0x200000) or data[0x13F:0x143]!=b'AZLE' or data[0x14C]!=2:
        raise ValueError('This patch requires English LADX Rev2, 1 or 2 MiB.')
    already=validate(data)
    if already:return bytearray(data)
    if not already and bytes(data[HOOK:HOOK+len(ORIGINAL)])!=ORIGINAL:raise ValueError('Room BG loader has conflicting modifications.')
    if not already and any(data[TABLE:TABLE+0x108]):raise ValueError('Room BG reserved storage is occupied.')
    if any(data[FLAGS:FLAGS+3]) or any(data[CUSTOM_START:CUSTOM_START+0x600]):
        raise ValueError('Custom BG reserved storage is occupied.')
    for at,(old,new) in COPY_HOOKS.items():
        if bytes(data[at:at+len(old)])!=old:raise ValueError('Custom BG copy loader has conflicting modifications.')
    out=bytearray(data)
    for room in (() if already else range(256)):
        value=data[legacy_offset(room)]
        # Preserve the original camera-shop special case on installation.
        out[TABLE+room]=0x0F if value==0x1A and room!=0x37 else value
    out[MARKER:MARKER+8]=MAGIC;out[HOOK:HOOK+len(PATCH)]=PATCH
    for at,(old,new) in COPY_HOOKS.items():out[at:at+len(new)]=new
    validate(out)
    return out


def available_ids(data):
    result=list(range(0x3F))
    if bytes(data[MARKER:MARKER+8])==MAGIC:
        result.extend(value for i,value in enumerate(CUSTOM_IDS) if data[FLAGS+i])
    return result


def block_data(data,room):
    value=data[selector_offset(data,room)]
    if value==15:raise ValueError('0F inherits graphics from a previous room; choose an explicit BG block first.')
    at=profile.bg_custom(data,CUSTOM_START)+CUSTOM_IDS.index(value)*0x200 if value in CUSTOM_IDS else 0xBC000+value*0x100
    return bytes(data[at:at+0x200])


def import_block(data,room,payload):
    if len(payload)!=512:raise ValueError('Expected exactly 512 bytes: 32 tiles in Game Boy 2bpp format.')
    if not enabled(data):raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    validate(data)
    selectors=bytes(data[TABLE:TABLE+256])
    current=selectors[room]
    reusable=[i for i,value in enumerate(CUSTOM_IDS) if value not in selectors or value==current and selectors.count(value)==1]
    if not reusable:raise ValueError('All three custom BG slots are assigned. Unassign a slot from its rooms before importing another block.')
    slot=reusable[0];out=bytearray(data)
    start=profile.bg_custom(data,CUSTOM_START)
    out[start+slot*512:start+(slot+1)*512]=payload
    out[FLAGS+slot]=1;out[TABLE+room]=CUSTOM_IDS[slot]
    validate(out)
    return [(i,b,a) for i,(b,a) in enumerate(zip(data,out)) if b!=a],CUSTOM_IDS[slot]
