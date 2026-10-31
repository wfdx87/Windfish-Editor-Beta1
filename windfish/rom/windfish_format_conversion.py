"""Convert recent native Windfish metadata without relocating any game assets.

Only the known current engine revisions are convertible. Full current-format
validation runs after conversion, before a document becomes editable. The disk
file remains untouched until the user saves; old API/probe ABIs are not guessed.
"""
from windfish.rom import windfish_identifiers as ids

# name, prior record offset, meaningful bytes, prior-region erase value
RECORDS=(
 ('bg',0x1D3900,8,0),('graphics',0x1BBF00,8,0),
 ('vram1',0x1BBE00,8,0),('map16',0x1BFF00,8,255),
 ('collisions',0x1CC000,14,0),('dungeon_rooms',0x193F00,14,255),
 ('dungeon_visuals',0x1B7F00,14,255),('shared_map16',0x1DBF80,8,255),
)

def convert(data):
    ids.reject_patches(data)
    if ids.installed(data):
        ids.validate(data)
        from windfish.rom.windfish_api_upgrade import upgrade
        return upgrade(data)
    old=bytes(data[0x1E0000:0x1E0020])
    known=tuple(b'WINDFISH'+v.to_bytes(2,'little')+bytes(22) for v in (1,2))
    if old not in known:
        if old[:8]==b'WINDFISH':raise ValueError('Unsupported previous Windfish ROM format.')
        return bytearray(data)
    if len(data)!=0x200000:raise ValueError('Previous Windfish conversion requires a 2 MiB ROM.')
    if any(data[ids.START:ids.END]):raise ValueError('Identifier directory conflicts with occupied original-ROM tail data.')
    out=bytearray(data);ids.initialize(out)
    for name,at,size,fill in RECORDS:
        raw=bytes(data[at:at+size])
        if raw[:8]!=ids.SIGNATURES[name]:
            if name=='vram1' and raw==bytes(size):continue
            raise ValueError(f'Cannot convert this {name} revision safely. Expected {ids.SIGNATURES[name]!r}.')
        out[ids.SLOTS[name]:ids.SLOTS[name]+size]=raw
        out[at:at+size]=bytes((fill,))*size
    for name,at in (('palettes',0x1D2BE0),('sprites',0x1D2BF1)):
        if data[at]!=1:raise ValueError(f'Previous {name} installation is missing or damaged.')
        target=ids.SLOTS[name];out[target:target+8]=ids.SIGNATURES[name];out[target+8]=1;out[at]=0
    # The previous integration record is retired, not assigned its own new slot.
    if data[0x1DFF80:0x1DFF88]!=b'WFCB0030' or data[0x1DFF88:0x1DFFA0]!=b'CCAPI001'+bytes((1,))+bytes(15):
        raise ValueError('This ROM has an older custom-collision API. Its scripts require porting; automatic ABI conversion is unsafe.')
    target=ids.SLOTS['api'];out[target:target+16]=b'CCAPI001'+bytes((1,))+bytes(7)
    out[0x1DFF80:0x1DFFA0]=b'\xff'*32
    if data[0x1FC100:0x1FC108]==b'WFTEXT01':
        target=ids.SLOTS['dialogs'];out[target:target+16]=b'WFTEXT01'+bytes((1,))+bytes(7)
        # Runtime counts, blank character, and pointer at 4112 remain in bank 7F.
        out[0x1FC100:0x1FC108]=bytes(8)
    out[0x1E0000:0x1E0020]=b'\xff'*32
    ids.validate(out)
    from windfish.rom.windfish_api_upgrade import upgrade
    out=upgrade(out)
    from windfish.rom.windfish_palette_patch import fix_checksums
    fix_checksums(out)
    return out
