"""English Rev2 dungeon collision expansion, using five reserved 2 MiB banks.

Original room streams/pointers remain intact. Each half-bank group has its own
native 16-bit pointer table. The alternate Goriya stream retains its quest gate.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.compatibility import api as profile

import zlib
from windfish.rom.windfish_room_tiles import _assemble

START=allocation['dungeon_rooms'].start
END=allocation['dungeon_rooms'].end
MARKER=ID_SLOTS['dungeon_rooms']
MAGIC=b'WFDC0001'
HOOK=0x3173
ORIGINAL=bytes.fromhex('3e 0a ea 00 21 e0 e8 f0 f7 fe ff 20 06 21 77 7b c3 1b 32 fe 1f 20 13 f0 f6 fe f5 20 0d fa 0e db fe 0e 20 06 01 55 78 c3 31 32 21 00 40 f0 f7 fe 1a 30 75 fe 06 38 71 3e 0b ea 00 21 e0 e8 21 00 40 18 65')
# Enter with BC=room*2; leave BC and DE intact except the original alternate
# Goriya path, which sets BC directly to that stream. Neither path alters DBAF.
_CODE=_assemble([
 'd5 f0 f7 fe ff',(0x20,'normal'),'3e 64',(0x18,'bank'),
 ('label','normal'),'d6 06 fe 14',(0x30,'a'),'16 62',(0x18,'group'),
 ('label','a'),'16 60',('label','group'),'f0 f6 07 e6 01 82',
 ('label','bank'),'ea 00 21 e0 e8 d1 21 00 40',
 'f0 f7 fe 1f',(0x20,'fetch'),'f0 f6 fe f5',(0x20,'fetch'),
 'fa 0e db fe 0e',(0x20,'fetch'),'01 00 7e c3 31 32',
 ('label','fetch'),'c3 1b 32'])
assert len(_CODE)<=len(ORIGINAL)
PATCH=_CODE.ljust(len(ORIGINAL),b'\0')
KEYS=tuple((g,r) for g,n in (('A',256),('B',256),('Color',22)) for r in range(n))+(('Alt',0xF5),)


def enabled(data):return bytes(data[MARKER:MARKER+8])==MAGIC


def group(map_id):return 'Color' if map_id==255 else 'B' if 6<=map_id<26 else 'A'


def bank_for(key):
    g,r=key
    return 0x64 if g=='Color' else 0x61 if g=='Alt' else (0x62 if g=='B' else 0x60)+(r>>7)


def stream_end(data,start,limit):
    if start<0 or start+2>=limit or limit>len(data):raise ValueError('Invalid dungeon stream bounds.')
    at=start+2
    while at<limit:
        tag=data[at]
        if tag==254:return at+1
        at+=5 if tag&252==224 else 3 if tag&144==128 else 2
    raise ValueError('Dungeon stream has no bounded terminator.')


def resolve(data,map_id,room):
    key=(group(map_id),room);bank=bank_for(key);base=bank*0x4000
    ptr=int.from_bytes(data[base+room*2:base+room*2+2],'little')
    if not 0x4200<=ptr<0x7E00:raise ValueError('Unused or invalid expanded dungeon room pointer.')
    return base+ptr-0x4000,base+0x3E00


def _span(data,key,expanded):
    g,r=key
    if expanded:
        bank=bank_for(key);base=bank*0x4000
        if g=='Alt':return base+0x3E00,base+0x3F00
        m=255 if g=='Color' else 6 if g=='B' else 0
        return resolve(data,m,r)
    if g=='Alt':return 0x2B855,0x2C000
    table=0x2BB77 if g=='Color' else 0x2C000 if g=='B' else 0x28000
    ptr=int.from_bytes(data[table+r*2:table+r*2+2],'little')
    if not 0x4000<=ptr<0x8000:raise ValueError('Invalid original dungeon pointer.')
    bank=table//0x4000
    return bank*0x4000+ptr-0x4000,(bank+1)*0x4000


def read_records(data,expanded=None):
    if expanded is None:expanded=enabled(data)
    records={}
    for key in KEYS:
        try:
            at,limit=_span(data,key,expanded);end=stream_end(data,at,limit)
            records[key]=bytes(data[at:end])
        except ValueError:
            if key!=('B',255):raise
            records[key]=None
    return records


def _crc(data):return zlib.crc32(data[START:END-0x100])


def _pack(data,records):
    out=bytearray(data);out[START:END]=bytes([255])*(END-START)
    cursors={bank:0x4200 for bank in range(0x60,0x65)}
    for key in KEYS:
        raw=records[key]
        if raw is None:continue
        if stream_end(raw,0,len(raw))!=len(raw):raise ValueError('Trailing dungeon record bytes.')
        bank=bank_for(key);base=bank*0x4000;g,r=key
        ptr=0x7E00 if g=='Alt' else cursors[bank]
        limit=0x7F00 if g=='Alt' else 0x7E00
        if ptr+len(raw)>limit:raise ValueError(f'Expanded dungeon bank {bank:02X} is full. No changes made.')
        start=base+ptr-0x4000;out[start:start+len(raw)]=raw
        if g!='Alt':out[base+r*2:base+r*2+2]=ptr.to_bytes(2,'little');cursors[bank]+=len(raw)
    out[MARKER:MARKER+8]=MAGIC
    out[MARKER+8:MARKER+10]=len(KEYS).to_bytes(2,'little')
    out[MARKER+10:MARKER+14]=_crc(out).to_bytes(4,'little')
    return out


def validate(data):
    if not enabled(data):
        if bytes(data[MARKER:MARKER+4])==b'WFDC' or bytes(data[HOOK:HOOK+len(PATCH)])==PATCH:
            raise ValueError('Dungeon storage patch marker is missing or unsupported.')
        return False
    if len(data)!=0x200000 or data[0x148]!=6:raise ValueError('Expanded dungeon storage requires a 2 MiB ROM.')
    if profile.is_vwf(data):profile.check_code(data,'dungeons')
    elif bytes(data[HOOK:HOOK+len(PATCH)])!=PATCH:raise ValueError('Dungeon room loader patch is damaged.')
    if int.from_bytes(data[MARKER+8:MARKER+10],'little')!=len(KEYS):raise ValueError('Dungeon storage directory size mismatch.')
    if int.from_bytes(data[MARKER+10:MARKER+14],'little')!=_crc(data):raise ValueError('Dungeon storage checksum mismatch.')
    records=read_records(data,True);spans=[]
    for key,raw in records.items():
        if raw is not None:
            at,limit=_span(data,key,True);spans.append((at,at+len(raw)))
    if profile.is_vwf(data):spans=list(set(spans))  # Test 02 deduplicates identical immutable streams.
    spans.sort()
    if any(end>start for (at,end),(start,last) in zip(spans,spans[1:])):raise ValueError('Expanded dungeon streams overlap.')
    return True


def install(data):
    if profile.is_vwf(data):
        validate(data)
        if not profile.ready(data):raise ValueError('Reopen the ROM to install the VWF editing engine.')
        return bytearray(data)
    from windfish.rom.windfish_rom import validate as validate_rom
    validate_rom(data)
    if validate(data):return bytearray(data)
    if len(data)!=0x200000:raise ValueError('A 2 MiB ROM is required. Reopen it and accept the expanded editing capabilities upgrade.')
    if bytes(data[HOOK:HOOK+len(ORIGINAL)])!=ORIGINAL:raise ValueError('Dungeon loader differs from English Rev2; refusing installation.')
    out=bytearray(data)
    if any(v!=255 for v in out[START:END]):raise ValueError('Dungeon storage banks 60–64 are occupied. No changes made.')
    records=read_records(out,False);out=_pack(out,records)
    out[HOOK:HOOK+len(PATCH)]=PATCH
    validate_rom(out)
    return out


def replacement_changes(data,map_id,room,payload):
    validate(data);key=(group(map_id),room)
    if key not in KEYS:raise ValueError('Invalid dungeon room.')
    records=read_records(data,True);records[key]=bytes(payload)
    out=_pack(data,records);validate(out)
    return [(at,old,new) for at,(old,new) in enumerate(zip(data,out)) if old!=new]


def used_space(data,map_id,room):
    bank=bank_for((group(map_id),room));records=read_records(data)
    used=sum(len(raw) for key,raw in records.items() if raw is not None and key[0]!='Alt' and bank_for(key)==bank)
    return used,0x3C00
