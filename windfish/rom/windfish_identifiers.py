"""Central 512-byte engine directory in unused original-ROM bank 3F.

The first 16 bytes identify the editor format; 31 fixed 16-byte slots follow.
Component signatures encode their own revisions. Remaining record bytes are
component-owned metadata, such as counts, flags and checksums. ExGFX never moves.
"""
START=0xFFE00
END=0x100000
FORMAT_VERSION=3
HEADER=b'WINDFISH'+FORMAT_VERSION.to_bytes(2,'little')+(512).to_bytes(2,'little')+bytes((16,0,0,0))
NAMES=('palettes','sprites','bg','graphics','vram1','map16','collisions','dungeon_rooms','dungeon_visuals','shared_map16','api','dialogs')
SLOTS={name:START+16+i*16 for i,name in enumerate(NAMES)}
SIGNATURES=dict(zip(NAMES,(b'WFPAL001',b'WFSPR001',b'WFBG0003',b'WFRG0003',b'WFVB0002',b'WFMT0002',b'WFCEXP01',b'WFDC0001',b'WFDV0001',b'WFM16007',b'CCAPI001',b'WFTEXT01')))

def installed(data):return bytes(data[START:START+16])==HEADER

def reject_patches(data):
    # Identification only: no third-party engine or HUD integration is installed.
    if bytes(data[0xFFF57:0xFFF5F])==b'WFHUDTOP':
        raise ValueError('HUD on Top ROMs are not supported by this Windfish format. The standalone patch must be updated before support returns.')
    if len(data)>0x1C0405 and bytes(data[0x1C0400:0x1C0405])==b'WFVWF' or len(data)>0x150 and data[0x13F:0x143]==bytes(4) and data[0x14C]==0:
        raise ValueError('VWF ROMs are not supported by this Windfish format.')

def initialize(data):
    reject_patches(data)
    if installed(data):validate(data);return
    if any(data[START:END]):raise ValueError('Reserved identifier space FFE00–FFFFF is occupied. No data was overwritten.')
    data[START:END]=bytes(512)
    data[START:START+16]=HEADER

def validate(data):
    if not installed(data):
        if bytes(data[START:START+8])==b'WINDFISH':raise ValueError('Unsupported or damaged Windfish identifier directory.')
        return False
    for name,at in SLOTS.items():
        record=bytes(data[at:at+16])
        if record!=bytes(16) and record[:8]!=SIGNATURES[name]:raise ValueError(f'Invalid {name} identifier record.')
    # Unassigned directory slots must remain empty until a future format knows them.
    if any(data[START+16+len(NAMES)*16:END]):raise ValueError('Unknown records occupy reserved identifier slots.')
    return True
