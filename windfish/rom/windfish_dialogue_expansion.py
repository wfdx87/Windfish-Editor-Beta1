"""Bank 7F dialog extension: stable IDs 2B0–3AF and compacted text.

The native ROM0 reader selects the pointer-table bank before reading it, then
selects the text bank. This preserves native pointers and bank flag semantics.
Only added text is repacked; IDs remain stable when earlier entries grow.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
CODE=b'\xfas\xc1_\xfa\x12\xc1W\xfe\x028) \x05{\xfe\xb08"{\xd6\xb0_z\xde\x02W\xa7 \x0e\xcb#\xcb\x12!\x00B\x19\x11\x10A>\x7f\xc9!\x12A\x11\x10A>\x7f\xc9!AG\x19\xe5\xcb#\xcb\x12!\x01@\x19\xd1>\x1c\xc9\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xcd\x00@bk\xc9\xff\xff'
ORIGINALS={9543: b'\xfa\x12\xc1W\xfas\xc1_\xcb#\xcb\x12!\x01@\x19*_V\xd5\xfas\xc1_\xfa\x12\xc1W!AG\x19~\xe6?\xea\x00!\xe1', 9914: b">\x1c\xea\x00!\xfa\x95\xdb\xfe\x07\xca\x82'\xfas\xc1_\xfa\x12\xc1W!AG\x19~\xa7\xca\x82'"}

BASE=0x1FC000
HEADER=BASE+0x100
IDENTIFIER=ID_SLOTS['dialogs']
POINTERS=BASE+0x200
POOL=BASE+0x400
END=0x200000
MAGIC=b'WFTEXT01'
FIRST=0x2B0
LIMIT=0x3B0
# These two immediate operands bound CC_ShowDialog's full 16-bit ID.
API_START=0x1F8600
API_OLD=bytes.fromhex('c5 d5 e5 7a fe 03 30')
HOOKS={
    0x2547:bytes.fromhex('3e7fea0021cd0040ea00212af57e67f16f1afe7f2802e63fea0021').ljust(39,b'\0'),
    0x26BA:bytes.fromhex('fa95dbfe07ca82273e7fea0021cd6040ea00217ea7ca8227').ljust(30,b'\0'),
}

def enabled(data):return bytes(data[IDENTIFIER:IDENTIFIER+8])==MAGIC

def api_image(data,bank,expected):
    """Validate the exact optional text-extension adaptation of the API."""
    if bank==0x7E and enabled(data):
        expected=bytearray(expected)
        expected[0x605]=4
        expected[0x609]=3
    return expected

def records(data):
    if not enabled(data):
        if any(bytes(data[a:a+len(p)])==p for a,p in HOOKS.items()):
            raise ValueError('Expanded dialog header is missing.')
        return ()
    if len(data)!=END:raise ValueError('Expanded dialogs require a 2 MiB ROM.')
    for at,raw in HOOKS.items():
        if bytes(data[at:at+len(raw)])!=raw:raise ValueError('Expanded dialog reader is damaged.')
    if bytes(data[BASE:BASE+len(CODE)])!=CODE:raise ValueError('Expanded dialog lookup code is damaged.')
    count=int.from_bytes(data[HEADER+10:HEADER+12],'little')
    used=int.from_bytes(data[HEADER+12:HEADER+14],'little')
    if count>LIMIT-FIRST or used>END-POOL:raise ValueError('Expanded dialog metadata is invalid.')
    expected_header=bytearray(32);expected_header[8]=1
    expected_header[10:12]=count.to_bytes(2,'little');expected_header[12:14]=used.to_bytes(2,'little')
    expected_header[16:20]=bytes.fromhex('7fff1141')
    if data[HEADER:HEADER+32]!=expected_header:raise ValueError('Expanded dialog header is damaged.')
    result=[];cursor=POOL
    for i in range(LIMIT-FIRST):
        pointer=int.from_bytes(data[POINTERS+i*2:POINTERS+i*2+2],'little')
        if i>=count:
            if pointer!=0x4111:raise ValueError('Unused dialog pointer is damaged.')
            continue
        if pointer!=0x4000+cursor-BASE:raise ValueError('Expanded dialog pointers are not packed in ID order.')
        end=next((a+1 for a in range(cursor,POOL+used) if data[a] in (0xFE,0xFF)),None)
        if end is None:raise ValueError('Expanded dialog is missing its ending.')
        result.append((cursor,bytes(data[cursor:end]),0x7F));cursor=end
    if cursor!=POOL+used:raise ValueError('Expanded dialog text length is inconsistent.')
    for a,b in ((BASE+len(CODE),HEADER),(HEADER+32,POINTERS),(cursor,END)):
        if any(x!=255 for x in data[a:b]):raise ValueError('Reserved dialog storage contains unknown data.')
    return tuple(result)

def _write(out,raws):
    count=len(raws);size=sum(map(len,raws))
    if count>LIMIT-FIRST:raise ValueError('All 256 additional dialog IDs are allocated.')
    if size>END-POOL:raise ValueError(f'Added text needs {size} bytes; bank 7F has {END-POOL} bytes.')
    out[POINTERS:POOL]=bytes.fromhex('1141')*(LIMIT-FIRST)
    out[POOL:END]=b'\xff'*(END-POOL)
    cursor=POOL
    for i,raw in enumerate(raws):
        pointer=0x4000+cursor-BASE
        out[POINTERS+i*2:POINTERS+i*2+2]=pointer.to_bytes(2,'little')
        out[cursor:cursor+len(raw)]=raw;cursor+=len(raw)
    out[HEADER+10:HEADER+12]=count.to_bytes(2,'little')
    out[HEADER+12:HEADER+14]=size.to_bytes(2,'little')

def install(data):
    if enabled(data):records(data);return bytearray(data)
    from windfish.compatibility import api as profile
    if profile.is_vwf(data) or profile.top_hud.validate(data):raise ValueError('Dialog expansion currently supports the native Rev2 test profile.')
    if len(data)!=END or any(v!=255 for v in data[BASE:END]):raise ValueError('Bank 7F is occupied; dialog expansion was not installed.')
    for at,raw in ORIGINALS.items():
        if data[at:at+len(raw)]!=raw:raise ValueError('Native dialog lookup was modified by another patch.')
    # Require the known native API implementation before adapting its bounds.
    if bytes(data[API_START:API_START+7])!=API_OLD or data[API_START+8:API_START+10]!=bytes.fromhex('fe02'):
        raise ValueError('The current Windfish API runtime is required for dialog expansion.')
    out=bytearray(data)
    for at,raw in HOOKS.items():out[at:at+len(raw)]=raw
    out[BASE:BASE+len(CODE)]=CODE
    header=bytearray(32);header[8]=1;header[16:20]=bytes.fromhex('7fff1141')
    out[IDENTIFIER:IDENTIFIER+16]=MAGIC+bytes((1,))+bytes(7)
    out[HEADER:HEADER+32]=header
    out[API_START+5]=4;out[API_START+9]=3
    _write(out,[]);records(out);return out

def changes(data,index=None,raw=b'\xff',expected=None):
    existing=records(data)
    if index is not None:
        i=index-FIRST
        if not 0<=i<len(existing):raise ValueError('Select an existing additional dialog.')
        if expected is not None and existing[i]!=expected:raise ValueError('Dialog changed. Reload it before applying.')
    if not raw or raw[-1] not in (0xFE,0xFF) or any(b in (0xFE,0xFF) for b in raw[:-1]):raise ValueError('Invalid dialog ending.')
    out=install(data);raws=[r[1] for r in existing]
    if index is None:raws.append(raw)
    else:raws[index-FIRST]=raw
    _write(out,raws);records(out)
    return [(a,b,c) for a,(b,c) in enumerate(zip(data,out)) if b!=c]


def delete_changes(data,index,expected=None):
    """Remove one added entry and repack; later added IDs shift down by one.

    Native dialogs are never removed. References in arbitrary user assembly
    cannot be rewritten safely, so the editor confirms renumbering explicitly.
    """
    existing=records(data)
    if type(index) is not int or not FIRST<=index<FIRST+len(existing):
        raise ValueError('Only added dialog IDs can be deleted.')
    i=index-FIRST
    if expected is not None and existing[i]!=expected:
        raise ValueError('Dialog changed. Reload it before deleting.')
    out=bytearray(data)
    raws=[record[1] for record in existing]
    del raws[i]
    _write(out,raws)
    records(out)
    return [(a,b,c) for a,(b,c) in enumerate(zip(data,out)) if b!=c]
