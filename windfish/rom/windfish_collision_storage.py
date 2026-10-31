"""English DX Rev2 collision expansion, version 1, in expanded banks 72/73.

All edits are prepared in private buffers. Streams never cross bank boundaries.
Original room streams, palette allocations and bank 3F remain untouched.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.compatibility import api as profile

import zlib

NAME='extended-collision-placements-patch'
STORAGE_HEADER=allocation['collision_storage'].start+0x4000
MARKER=ID_SLOTS['collisions']
MAGIC=b'WFCEXP01'
TABLE=STORAGE_HEADER+0x20
HELPER=STORAGE_HEADER+0x340
CRC_AT=MARKER+10
REGIONS=((allocation['collision_storage'].start+0x2600,STORAGE_HEADER),(STORAGE_HEADER+0x400,allocation['collision_storage'].end))
ALTERNATE_POINTERS={0x06:0x31F4,0x0E:0x31C4,0x1B:0x3204,0x2B:0x3214,0x79:0x31E4,0x8C:0x31D4}
KEYS=tuple((r,False) for r in range(256))+tuple((r,True) for r in sorted(ALTERNATE_POINTERS))
INDEX={key:i for i,key in enumerate(KEYS)}
ORIGINAL_HOOKS={
 0x3226:bytes.fromhex('f0 f6 fe 80 38 05 3e 1a ea 00 21'),
 0x3532:bytes.fromhex('f0 f6 fe 80 30 04 3e 09 18 02 3e 1a ea 00 21 c9'),
 0x3514:bytes.fromhex('f0 f6 fe 80 30 04 3e 09 18 02 3e 1a')}
PATCHED_HOOKS={
 0x3226:bytes.fromhex('3e 73 ea 00 21 cd 40 43 ea 00 21'),
 0x3532:bytes.fromhex('f0 e8 ea 00 21 c9')+bytes(10),
 # 351E is also entered directly by room 97 rocky-ground handling.
 0x3514:bytes.fromhex('f0 e8')+bytes(8)+bytes.fromhex('f0 e8')}
HELPER_BYTES=bytes.fromhex('d5 60 69 2a 57 4e 23 46 7a e0 e8 d1 c9')


def alternate_pointers(data):
 return {room:at+9 for room,at in ALTERNATE_POINTERS.items()} if profile.is_vwf(data) else ALTERNATE_POINTERS


def enabled(data):return bytes(data[MARKER:MARKER+8])==MAGIC


def room_key(room,alternate=False):
 if not 0<=room<256:raise ValueError('Invalid overworld room')
 return room,bool(alternate and room in ALTERNATE_POINTERS)


def cpu_address(offset):return 0x4000+offset%0x4000


def _crc(data):
 value=zlib.crc32(data[TABLE:TABLE+len(KEYS)*3])
 for start,end in REGIONS:value=zlib.crc32(data[start:end],value)
 return value


def resolve_stream(data,room,alternate=False):
 i=INDEX[room_key(room,alternate)];at=TABLE+i*3
 bank=data[at];ptr=int.from_bytes(data[at+1:at+3],'little')
 if not 0x4000<=ptr<0x8000:raise ValueError('Invalid expanded collision pointer')
 start=bank*0x4000+ptr-0x4000
 for a,b in REGIONS:
  if a<=start<b:return start,b
 raise ValueError('Expanded collision pointer outside reserved pool')


def _record_end(data,start,limit):
 if start+2>=limit or data[start]==0xFE:raise ValueError('Invalid collision header')
 p=start+2
 while p<limit:
  tag=data[p]
  if tag==0xFE:return p+1
  p+=5 if tag&0xFC==0xE0 else (3 if tag&0x90==0x80 else 2)
 raise ValueError('Collision stream has no in-bank terminator')


def _check_record(raw):
 if _record_end(raw,0,len(raw))!=len(raw):raise ValueError('Trailing collision record data')


def read_lists(data):
 records=[]
 for room,alt in KEYS:
  start,limit=resolve_stream(data,room,alt)
  records.append(bytes(data[start:_record_end(data,start,limit)]))
 return records


def validate_mode(data):
 if len(data) not in (0x100000,0x200000):raise ValueError('Collision storage requires a 1 or 2 MiB ROM')
 expanded=enabled(data)
 sig=bytes(data[MARKER:MARKER+8])
 if sig.startswith(b'WFCEXP') and not expanded:raise ValueError('Unsupported collision expansion version')
 hooks=PATCHED_HOOKS if expanded else ORIGINAL_HOOKS
 if profile.is_vwf(data):hooks={at+9:raw for at,raw in hooks.items()}
 for at,expected in hooks.items():
  if data[at:at+len(expected)]!=expected:raise ValueError(f'Collision loader differs at {at:05X}; refusing unsafe storage access')
 if not expanded:return False
 if int.from_bytes(data[MARKER+8:MARKER+10],'little')!=len(KEYS):raise ValueError('Collision directory count mismatch')
 from windfish.rom import windfish_script_engine as custom
 expected=(custom.reset_helper(data) if custom.enabled(data) else b'')+HELPER_BYTES
 if data[HELPER:HELPER+len(expected)]!=expected:raise ValueError('Collision selector code mismatch')
 for i,(room,alt) in enumerate(KEYS):
  pointer_at=alternate_pointers(data)[room] if alt else 0x24000+room*2
  if int.from_bytes(data[pointer_at:pointer_at+2],'little')!=cpu_address(TABLE+i*3):raise ValueError('Collision directory token mismatch')
  if alt and data[pointer_at-1]!=1:raise ValueError('Alternate collision selector instruction mismatch')
 if int.from_bytes(data[CRC_AT:CRC_AT+4],'little')!=_crc(data):raise ValueError('Expanded collision database integrity check failed')
 spans=[]
 for room,alt in KEYS:
  start,limit=resolve_stream(data,room,alt);end=_record_end(data,start,limit)
  spans.append((start,end))
 spans.sort()
 if any(b>c for (a,b),(c,d) in zip(spans,spans[1:])):raise ValueError('Expanded collision streams overlap')
 return True


def pack_streams(records):
 if len(records)!=len(KEYS):raise ValueError('Expected all 262 collision layouts')
 for raw in records:_check_record(raw)
 pointers=[None]*len(records);writes=[]
 cursors=[a for a,b in REGIONS]
 # Deterministic best-fit decreasing: a large room does not strand the
 # smaller bank, and no stream can spill across a bank boundary.
 for i in sorted(range(len(records)),key=lambda i:(-len(records[i]),i)):
  raw=records[i]
  candidates=[j for j,(a,b) in enumerate(REGIONS) if cursors[j]+len(raw)<=b]
  if not candidates:raise ValueError('Expanded collision pool is full or a stream cannot fit within one bank; no changes made')
  region=min(candidates,key=lambda j:REGIONS[j][1]-cursors[j]-len(raw))
  cursor=cursors[region]
  pointers[i]=(cursor//0x4000,cpu_address(cursor))
  writes.append((cursor,raw));cursors[region]+=len(raw)
 return pointers,writes


def _write_database(out,records):
 pointers,writes=pack_streams(records)
 for start,end in REGIONS:out[start:end]=bytes(end-start)
 for i,(bank,ptr) in enumerate(pointers):
  at=TABLE+i*3;out[at:at+3]=bytes([bank])+ptr.to_bytes(2,'little')
 for at,raw in writes:out[at:at+len(raw)]=raw
 out[CRC_AT:CRC_AT+4]=_crc(out).to_bytes(4,'little')


def install(data):
 if data[0x13F:0x143]!=b'AZLE' or data[0x14C]!=2:raise ValueError('Expected English LADX Rev2')
 if validate_mode(data):raise ValueError('Collision expansion is already installed')
 # Verified against main.asm bank 3E (unused) and the photo-data end in 3D.
 # Occupancy and exact hook checks reject conflicts with other modifications.
 for start,end in ((0x1CA600,0x1CC000),(0x1CC000,0x1D0000)):
  if any(data[start:end]):raise ValueError(f'Collision storage {start:05X}–{end-1:05X} is occupied; nothing was overwritten')
 from windfish.overworld.windfish_collision_objects import read_room_objects
 records=[]
 for room,alt in KEYS:
  stream=read_room_objects(data,room,alt);records.append(bytes(data[stream.start:stream.end]))
 out=bytearray(data)
 out[MARKER:MARKER+8]=MAGIC;out[MARKER+8:MARKER+10]=len(KEYS).to_bytes(2,'little')
 out[HELPER:HELPER+len(HELPER_BYTES)]=HELPER_BYTES
 for i,(room,alt) in enumerate(KEYS):
  at=ALTERNATE_POINTERS[room] if alt else 0x24000+room*2
  if alt and data[at-1]!=1:raise ValueError('Alternate room hook differs from Rev2')
  out[at:at+2]=cpu_address(TABLE+i*3).to_bytes(2,'little')
 for at,payload in PATCHED_HOOKS.items():out[at:at+len(payload)]=payload
 _write_database(out,records)
 from windfish.rom.windfish_palette_patch import fix_checksums
 fix_checksums(out);validate_mode(out)
 if read_lists(out)!=records:raise ValueError('Relocation verification failed')
 return out


def replacement_changes(data,room,alternate,raw):
 if not validate_mode(data):raise ValueError('Expanded collisions are not installed')
 records=read_lists(data);records[INDEX[room_key(room,alternate)]]=bytes(raw)
 out=bytearray(data);_write_database(out,records);validate_mode(out)
 # Rebase shared-page references in the same atomic edit as directory/pools.
 ranges=((CRC_AT,CRC_AT+4),(TABLE,TABLE+len(KEYS)*3))+REGIONS
 changes=[(at,data[at],out[at]) for a,b in ranges for at in range(a,b) if data[at]!=out[at]]
 from windfish.rom.windfish_shared_map16 import rebase_changes
 return changes+rebase_changes(out,room,alternate)


def free_bytes(data):
 if not enabled(data):return None
 used=sum(len(raw) for raw in read_lists(data))
 return sum(b-a for a,b in REGIONS)-used
