"""Expanded palette engine with small, checked bank-local gateways.

Palette work runs in expanded bank 74. The native palette branch remains
original code; mirrored gates safely switch ROM banks without executing from
an unmapped bank. The custom branch saves/masks IE until it is back in the
original palette bank, preserving IME and the caller-owned cached ROM bank. No ROM0 helper allocation and no external IPS payload.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.rom.windfish_room_tiles import _assemble
PATCH_NAME='expanded-palettes'
IDENTIFIER=ID_SLOTS['palettes']
MAGIC=b'WFPAL001'
MARKER=IDENTIFIER+8
DATA_START=allocation['palettes_and_bg'].start+0x2C00
DATA_END=DATA_START+33*80
HOOK=0x840EA
CORE=allocation['palettes_and_bg'].start+0x3C00
COPY_SET=CORE+0x100
ENTRY=0x7E6E
ORIGINAL=bytes.fromhex('7ecb274f21b142092a46606fcdb441')

def fix_checksums(rom):
    rom[0x14D]=(-sum(rom[0x134:0x14D])-25)&255
    rom[0x14E:0x150]=((sum(rom)-rom[0x14E]-rom[0x14F])&65535).to_bytes(2,'big')

def is_installed(data):return len(data)>MARKER and data[MARKER]==1

def code(vwf=False):
    copy=bytes.fromhex('cd 14 29' if vwf else 'cd 0b 29')
    entry=_assemble(['7e fe 1f',(0x30,'custom'),ORIGINAL[1:].hex(),'c9',
        ('label','custom'),'47 f0 ff f5 af e0 ff 78 f5 3e 74 ea 00 21 c3 00 7c'])
    core=_assemble([
        'f1 d6 1f 21 00 6c 01 50 00 a7',(0x28,'ready'),
        ('label','offset'),'09 3d',(0x20,'offset'),
        ('label','ready'),'fa d5 dd a7',(0x20,'bank2'),
        'e5 cd 00 7d e1',('label','bank2'),'3e 02 e0 70 cd 00 7d af e0 70 c3 40 7f'])
    copyset=bytes.fromhex('11 10 dc 01 40 00')+copy+bytes.fromhex('e5 21 18 55 01 30 00 cd 20 7f e1 01 10 00')+copy+b'\xc9'
    shared=bytes.fromhex('f5 3e 21 ea 00 21')+copy+bytes.fromhex('3e 74 ea 00 21 f1 c9')
    finish=bytes.fromhex('3e 21 ea 00 21 f1 e0 ff c3 f7 41')
    result={HOOK:bytes.fromhex('cd 6e 7e')+bytes(12),CORE:core,COPY_SET:copyset}
    for base in (0x84000,0x1D0000):
        result[base+ENTRY-0x4000]=entry
        result[base+0x3F20]=shared
        result[base+0x3F40]=finish
    return result

def install_into(out,vwf=False):
    if out[HOOK:HOOK+len(ORIGINAL)]!=ORIGINAL:raise ValueError('Palette selection hook is modified.')
    for at,raw in code(vwf).items():
        if at==HOOK:continue
        fill=0 if at<0x100000 or at>=0x1D0000 else 255
        if any(v!=fill for v in out[at:at+len(raw)]):raise ValueError(f'Palette gateway storage occupied at {at:06X}.')
    for at,raw in code(vwf).items():out[at:at+len(raw)]=raw
    out[IDENTIFIER:IDENTIFIER+8]=MAGIC
    out[MARKER]=1
    return out

def install_patch(data):
    if is_installed(data):return bytearray(data)
    if len(data)!=0x200000:raise ValueError('Palette expansion requires a 2 MiB Windfish ROM.')
    return install_into(bytearray(data))
