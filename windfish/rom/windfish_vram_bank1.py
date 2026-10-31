"""Optional overworld bank-1 ExGFX engine, layered on the four-phase loader.

Eight library blocks occupy VRAM 1:8800-97FF (background IDs 00-FF).
Bank 1's tile attributes at 9800-9FFF are never overwritten. The first four
stages retain the original bank-0 phase plus one bank-1 block. Four additional stages load only bank 1, preserving the previous
maximum of 1024 transferred bytes per VBlank. Full redraws load all eight
stages with the LCD off. DMG never calls these phases. Disabled/unassigned slots are cleared
so revisiting rooms cannot accidentally display another room's graphics.
All persistent data and code occupy the shared expanded graphics bank $6E.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom import windfish_room_graphics as gfx
from windfish.rom.windfish_room_tiles import _assemble

START=gfx.START
WRAPPER=START+0x400
LOADER=START+0x500
FLAGS=START+0x1800
SLOTS=START+0x2400
MASKS=START+0x2C00
BITS=START+0x2D00
ZERO=START+0x2000
MARKER=ID_SLOTS['vram1']
MAGIC=b'WFVB0002'
REGIONS=((WRAPPER,START+0x600),(FLAGS,FLAGS+256),(SLOTS,BITS+8),(ZERO,ZERO+512),(MARKER,MARKER+8))

def version(data):
    if len(data)<gfx.END:return 0
    marker=bytes(data[MARKER:MARKER+8])
    return 2 if marker==MAGIC else 0

def installed(data):return bool(version(data))

def engine(dma=None):
    if dma is None:dma=gfx.DMA
    wrapper=_assemble([
        'f5 fe 04',(0x30,'bank1'),gfx.call(gfx.PHASE).hex(),
        ('label','bank1'),'f1 f5 c5 d5 e5',gfx.call(0x4500).hex(),
        'e1 d1 c1 f1 c9'])
    loader=_assemble([
        'f5 f0 f6 6f 26 58 7e a7',(0x28,'blank'),
        'f0 f6 6f 26 6c 7e 47 f1 f5 6f 26 6d 7e a0',(0x28,'blank'),
        # 6400 + room*8 + slot; IDs reuse the existing shared ExGFX pool.
        'f0 f6 6f 26 00 29 29 29 11 00 64 19 f1 f5 5f 16 00 19 7e 4f',
        'e6 1f 87 c6 40 67 2e 00 79 cb 3f cb 3f cb 3f cb 3f cb 3f c6 40 4f',
        (0x18,'copy'),('label','blank'),'21 00 60 0e 6e',
        ('label','copy'),
        # Slots 0-3: IDs 00-7F at 9000. Slots 4-7: IDs 80-FF at 8800.
        'f1 fe 04',(0x38,'low'),'d6 04 87 c6 88',(0x18,'dest'),
        ('label','low'),'87 c6 90',('label','dest'),
        '57 1e 00 f0 4f f5 3e 01 e0 4f 06 1f 79',
        gfx.call(dma).hex(),'f1 e0 4f c9'])
    return {WRAPPER:wrapper,LOADER:loader}

def expanded_helpers(base):
    """Reschedule CGB only; retain the exact original DMG instruction path."""
    result=dict(base)
    old=gfx.call(gfx.PHASE);new=gfx.call(0x4400)
    for at in (START,START+0x100):result[at]=result[at].replace(old,new)
    seq=bytes.fromhex('f0 92 3c e0 92 fe 04')
    if result[START].count(seq)!=1:raise ValueError('Unknown graphics stage scheduler.')
    result[START]=result[START].replace(seq,seq[:-1]+b'\x08')
    end=bytes.fromhex('f1 e0 4f c9')
    if result[START+0x100].count(end)!=1:raise ValueError('Unknown full graphics loader.')
    extra=b''.join(bytes((0x3e,i))+new for i in range(4,8))
    full=bytearray(result[START+0x100].replace(end,extra+end))
    # The leading JR Z skips the enlarged CGB path to the untouched DMG path.
    if full[:4]!=bytes.fromhex('f0 fe a7 28'):raise ValueError('Unknown graphics mode gate.')
    full[4]+=len(extra)
    result[START+0x100]=bytes(full)
    return result

def expected(data,base):
    """Extend exact engine signatures; never accept arbitrary modified helpers."""
    result=dict(base)
    if not installed(data):return result
    ver=version(data)
    if ver==2 and bytes.fromhex('f0 92 3c e0 92 fe 04') in result[START]:result=expanded_helpers(result)
    from windfish.compatibility import api as profile
    result.update(engine(profile.graphics_dma_entry(data,gfx.DMA)))
    return result

def validate(data):
    if not installed(data):
        if len(data)>=gfx.END and bytes(data[MARKER:MARKER+4])==b'WFVB':
            raise ValueError('Unknown bank 1 graphics engine version.')
        return False
    if any(data[ZERO:ZERO+512]):raise ValueError('Bank 1 blank graphics block is damaged.')
    if version(data)==2 and bytes(data[BITS:BITS+8])!=bytes(1<<i for i in range(8)):
        raise ValueError('Bank 1 slot bit table is damaged.')
    assets=set(gfx.available_assets(data))
    for room in range(256):
        if data[FLAGS+room] not in (0,1):
            raise ValueError('Invalid bank 1 room graphics settings.')
        slots=room_slots(data,room)
        for asset in slots:
            if asset is not None and asset not in assets:
                raise ValueError('Bank 1 references an ExGFX ID that is not inserted.')
    return True

def install(data):
    out=gfx.install(data);gfx.validate(out)
    ver=version(out)
    if ver==2:return out
    if not ver:
        for a,b in REGIONS:
            if any(out[a:b]):raise ValueError('Reserved bank 1 engine storage is occupied.')
    from windfish.compatibility import api as profile
    if profile.is_vwf(out):
        base=profile.code(out,'graphics')
    else:base=gfx.HELPERS
    for at,raw in expanded_helpers(base).items():
        if at in (START,START+0x100):out[at:at+len(raw)]=raw
    for at,raw in engine(profile.graphics_dma_entry(out,gfx.DMA)).items():out[at:at+len(raw)]=raw
    out[BITS:BITS+8]=bytes(1<<i for i in range(8))
    out[MARKER:MARKER+8]=MAGIC
    gfx.validate(out)
    return out


def room_slots(data,room):
    if not 0<=room<256:raise ValueError('Overworld room must be 00-FF.')
    ver=version(data)
    if not ver:return (None,)*8
    return tuple(data[SLOTS+room*8+i] if data[MASKS+room]&(1<<i) else None for i in range(8))

def enabled(data,room):return installed(data) and bool(data[FLAGS+room])

def assign_slots(data,room,slots,active=True):
    if not 0<=room<256 or len(slots)!=8:raise ValueError('Choose eight graphics slots for an overworld room.')
    out=install(data);mask=0
    for i,asset in enumerate(slots):
        if asset is not None:gfx.asset_data(out,asset);mask|=1<<i
        out[SLOTS+room*8+i]=asset if asset is not None else 0
    out[FLAGS+room]=int(bool(active));out[MASKS+room]=mask
    gfx.validate(out)
    return gfx._changes(data,out)

def background_data(data,room):
    """Physical VRAM order: IDs 80-FF ($8800), then IDs 00-7F ($9000)."""
    slots=room_slots(data,room)
    blocks=[gfx.asset_data(data,a) if enabled(data,room) and a is not None else bytes(512) for a in slots]
    return b''.join(blocks[4:]+blocks[:4])
