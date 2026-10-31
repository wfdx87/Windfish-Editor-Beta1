"""Reusable custom 16x16 sets 40-FF, packed eight sets per ROM bank.

Bank 6F holds helpers and per-room assignments. Banks 48-5F hold 192
2-KiB sets: 1024 tile-number bytes followed by 1024 attribute bytes.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.compatibility import api as profile

BANK=0x6F
START=allocation['tile_gateway'].start
END=START+0x4000
HELPER=START+0x3800
POINTER_HELPER=START+0x3900
NEW_MARKER=ID_SLOTS['map16']
MAGIC=b'WFMT0002'
ASSIGNMENTS=START+0x3A00
FLAGS=START+0x3B00
BACKUPS=START+0x3C00
DATA_START=allocation['metatiles'].start
DATA_END=allocation['metatiles'].end
HOOK=0x38FC
ORIGINAL=bytes.fromhex('fa a5 db a7 20 04 3e 1a 18 02 3e 08 ea 00 21 c9')
PATCH=bytes.fromhex('3e 6f ea 00 21 cd 00 78 ea 00 21 c9')+bytes(4)
TRAMPOLINE=HOOK
POINTER_SITES=(0x2285,0x3043)
POINTER_ORIGINAL=bytes.fromhex('21 1d 6b')
POINTER_PATCH=bytes((0xCD,TRAMPOLINE&255,TRAMPOLINE>>8))
NAME='room-tile-definitions-patch'


def _assemble(parts):
    code=bytearray();labels={};fixups=[]
    for part in parts:
        if isinstance(part,str):code.extend(bytes.fromhex(part))
        elif part[0]=='label':labels[part[1]]=len(code)
        else:
            code.append(part[0]);fixups.append((len(code),part[1]));code.append(0)
    for at,label in fixups:
        delta=labels[label]-at-1
        if not -128<=delta<=127:raise ValueError('Helper branch out of range')
        code[at]=delta&255
    return bytes(code)


_BANK_CORE=_assemble([
 'e5 fa a5 db a7',(0x20,'indoor'),'f0 fe a7',(0x28,'original'),
 'f0 f6 6f 26 7a 7e fe 40',(0x38,'original'),
 'd6 40 cb 3f cb 3f cb 3f c6 48 6f af a7 7d e1 c9',
 ('label','original'),'af a7 3e 1a e1 c9',
 ('label','indoor'),'3e 08 e1 c9'])
# The existing 16-byte fixed-bank gateway is shared by bank selection and
# pointer lookup. The helper recognizes the two pointer CALL return addresses.
# Stack on entry: helper return, outer return; preserve HL before peeking.
_GATEWAY=_assemble([
 'e5 f8 04 2a fe 88',(0x20,'other'),'7e fe 22',(0x28,'pointer'),(0x18,'normal'),
 ('label','other'),'fe 46',(0x20,'normal'),'7e fe 30',(0x28,'pointer'),
 ('label','normal'),'e1 c3 80 78',
 ('label','pointer'),'e1 c3 00 79'])
BANK_HELPER=_GATEWAY+bytes(0x80-len(_GATEWAY))+_BANK_CORE
POINTER_CODE=_assemble([
 'c5 d5 f0 f6 4f 06 00 21 00 7a 09 7e fe 40',(0x38,'original'),
 'd6 40 4f e6 07 07 07 07 c6 40 67 2e 00 79 cb 3f cb 3f cb 3f c6 48 d1 c1 c9',
 ('label','original'),'21 1d 6b 3e 1a d1 c1 c9'])


def version(data):
    if len(data)<END:return 0
    if bytes(data[NEW_MARKER:NEW_MARKER+8])==MAGIC:return 2
    return 0


def enabled(data):return bool(version(data))


def room_set(data,room):
    ver=version(data)
    return data[ASSIGNMENTS+room] if ver==2 else 0


def is_custom(data,room):return room_set(data,room)>=0x40


def owner(data):
    rooms=[r for r in range(256) if is_custom(data,r)]
    return rooms[0] if len(rooms)==1 else None


def set_offset(set_id):
    if not 0x40<=set_id<=0xFF:raise ValueError('Custom set ID must be 40-FF.')
    return DATA_START+(set_id-0x40)*0x800


def definition_offset(data,room):
    value=room_set(data,room)
    return set_offset(value) if value else 0x6AB1D


def attribute_offset(data,room):
    bank=data[0x6A476+room];at=0x69E76+room*2
    return bank*0x4000+int.from_bytes(data[at:at+2],'little')-0x4000


def available_sets(data):
    return [i+0x40 for i in range(192) if version(data)==2 and data[FLAGS+i]]


def validate(data):
    ver=version(data)
    if ver:
        from windfish.rom.windfish_shared_map16 import adapt_code
        if profile.is_vwf(data):profile.check_code(data,'tiles')
        if not profile.is_vwf(data) and bytes(data[HOOK:HOOK+len(PATCH)])!=adapt_code(data,{HOOK:PATCH})[HOOK]:raise ValueError('Custom 16x16 loader is damaged.')
        if not profile.is_vwf(data) and (bytes(data[HELPER:HELPER+len(BANK_HELPER)])!=BANK_HELPER or bytes(data[POINTER_HELPER:POINTER_HELPER+len(POINTER_CODE)])!=POINTER_CODE):
            raise ValueError('Custom set helper is damaged.')
        if not profile.is_vwf(data) and any(bytes(data[p:p+3])!=POINTER_PATCH for p in POINTER_SITES):
            raise ValueError('Custom set pointer loader is damaged.')
        if any(v not in (0,1) for v in data[FLAGS:FLAGS+192]):raise ValueError('Invalid custom set flags.')
        for room in range(256):
            value=data[ASSIGNMENTS+room]
            if value:
                if value<0x40 or data[FLAGS+value-0x40]!=1:raise ValueError('Room references an uninitialized custom set.')
                expected=set_offset(value)+1024
            else:
                bank,lo,hi=data[profile.backups(data,BACKUPS)+room*3:profile.backups(data,BACKUPS)+room*3+3]
                if not 1<=bank<=0x3F or not 0x4000<=lo+hi*256<0x8000:raise ValueError('Invalid original attribute backup.')
                expected=bank*0x4000+lo+hi*256-0x4000
            if attribute_offset(data,room)!=expected:raise ValueError('Room attribute pointer and custom assignment disagree.')
        return True
    if len(data)>=END and bytes(data[NEW_MARKER:NEW_MARKER+4])==b'WFMT':
        raise ValueError('Unsupported custom 16x16 patch version.')
    if bytes(data[HOOK:HOOK+len(PATCH)])==PATCH:raise ValueError('Custom 16x16 marker is missing.')
    return False


def changes_between(data,out):return [(i,b,a) for i,(b,a) in enumerate(zip(data,out)) if b!=a]


def _write_attribute_pointer(out,room,raw):
    from windfish.rom import windfish_shared_map16 as shared
    for base in (0,START-0x68000)+((shared.BASE-0x68000,) if shared.enabled(out) else ()):
        out[base+0x6A476+room]=raw[0]
        at=base+0x69E76+room*2;out[at:at+2]=raw[1:]


def _assign(out,room,set_id):
    if set_id==0:raw=out[profile.backups(out,BACKUPS)+room*3:profile.backups(out,BACKUPS)+room*3+3]
    else:
        at=set_offset(set_id)+1024;bank=at//0x4000;ptr=0x4000+at%0x4000
        raw=bytes((bank,ptr&255,ptr>>8))
    out[ASSIGNMENTS+room]=set_id;_write_attribute_pointer(out,room,raw)
    from windfish.rom import windfish_shared_map16 as shared
    if shared.enabled(out):out[shared.BASE+0x3A00+room]=set_id


def install(data):
    if profile.is_vwf(data):
        validate(data)
        if not profile.ready(data):raise ValueError('Reopen the ROM to install the VWF editing engine.')
        return bytearray(data)
    from windfish.rom.windfish_rom import validate as validate_rom
    validate_rom(data)
    if len(data)!=0x200000:raise ValueError('A 2 MiB ROM is required. Reopen it and accept the expanded editing capabilities upgrade.')
    ver=version(data)
    if ver==2:return bytearray(data)
    if ver==0 and bytes(data[HOOK:HOOK+len(ORIGINAL)])!=ORIGINAL:raise ValueError('Tilemap-bank loader has conflicting modifications.')
    if ver==0 and any(v!=255 for v in data[START:END]):raise ValueError('Tile gateway bank 6F is occupied.')
    if any(v!=255 for v in data[DATA_START:DATA_END]):raise ValueError('Custom tile set storage is occupied.')
    if any(bytes(data[p:p+3])!=POINTER_ORIGINAL for p in POINTER_SITES):
        raise ValueError('Custom tile pointer hook space is occupied.')
    out=bytearray(data)
    if ver==0:out[START:END]=data[0x68000:0x6C000]
    for room in range(256):
        raw=bytes((data[0x6A476+room],))+bytes(data[0x69E76+room*2:0x69E78+room*2])
        out[profile.backups(out,BACKUPS)+room*3:profile.backups(out,BACKUPS)+room*3+3]=raw
    out[ASSIGNMENTS:ASSIGNMENTS+256]=bytes(256);out[FLAGS:FLAGS+192]=bytes(192)
    out[HELPER:HELPER+len(BANK_HELPER)]=BANK_HELPER
    out[POINTER_HELPER:POINTER_HELPER+len(POINTER_CODE)]=POINTER_CODE
    out[NEW_MARKER:NEW_MARKER+8]=MAGIC
    out[HOOK:HOOK+len(PATCH)]=PATCH
    for p in POINTER_SITES:out[p:p+3]=POINTER_PATCH
    validate(out)
    return out


def create_set(data,room,set_id=None):
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Room must be 00-FF.')
    out=install(data)
    if set_id is None:
        set_id=next((i for i in range(0x40,256) if out[FLAGS+i-0x40]==0),None)
        if set_id is None:raise ValueError('All 192 custom sets are initialized.')
    at=set_offset(set_id)
    if out[FLAGS+set_id-0x40]:raise ValueError('That set already exists. Select it to share, or choose an unused ID.')
    if any(v!=255 for v in out[at:at+2048]):raise ValueError('Unused custom set storage is occupied; refusing to overwrite it.')
    source=definition_offset(out,room);attr=attribute_offset(out,room)
    out[at:at+1024]=out[source:source+1024]
    out[at+1024:at+2048]=out[attr:attr+1024]
    out[FLAGS+set_id-0x40]=1;_assign(out,room,set_id)
    validate(out)
    return changes_between(data,out)


def assign_set(data,room,set_id):
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Room must be 00-FF.')
    if set_id==0 and version(data)==0:return []
    if set_id!=0:set_offset(set_id)
    out=install(data)
    if set_id and not out[FLAGS+set_id-0x40]:
        # Every ID is selectable. First use clones the current room so choosing
        # an unused set does not unexpectedly replace its existing artwork.
        at=set_offset(set_id)
        if any(v!=255 for v in out[at:at+2048]):raise ValueError('Unused custom set storage is occupied.')
        source=definition_offset(out,room);attr=attribute_offset(out,room)
        out[at:at+1024]=out[source:source+1024];out[at+1024:at+2048]=out[attr:attr+1024]
        out[FLAGS+set_id-0x40]=1
    _assign(out,room,set_id);validate(out)
    return changes_between(data,out)


def clear_set(data,set_id):
    at=set_offset(set_id)
    out=install(data)
    if not out[FLAGS+set_id-0x40] and any(v!=255 for v in out[at:at+2048]):
        raise ValueError('Unused custom set storage is occupied.')
    out[at:at+2048]=bytes(2048);out[FLAGS+set_id-0x40]=1
    validate(out)
    return changes_between(data,out)


def tile_changes(data,room,tile,pieces,attributes):
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Room must be 00-FF.')
    validate(data)
    if not is_custom(data,room):raise ValueError('Select a custom set for this room first.')
    if not 0<=tile<=255 or len(pieces)!=4 or len(attributes)!=4:raise ValueError('A tile needs four pieces and four attributes.')
    if any(not isinstance(v,int) or not 0<=v<=255 for v in list(pieces)+list(attributes)):raise ValueError('Tile numbers and attributes must be bytes.')
    result=[]
    for start,values in ((definition_offset(data,room),pieces),(attribute_offset(data,room),attributes)):
        for i,value in enumerate(values):
            at=start+tile*4+i
            if data[at]!=value:result.append((at,data[at],value))
    return result
