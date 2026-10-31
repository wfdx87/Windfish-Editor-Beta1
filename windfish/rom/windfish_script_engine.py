"""Install and validate the current API runtime; script insertion is external."""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_script_payload import BLOBS,FRAME_BLOBS,FIXED_BLOBS
from windfish.rom import windfish_shared_map16 as shared
from windfish.rom.windfish_room_tiles import _assemble as asm
BASE=0x1DC000
DESCRIPTOR=ID_SLOTS['api']
MARKER=DESCRIPTOR
MAGIC=b'CCAPI001'
RECORD=MAGIC+bytes((4,))+bytes(7)
TABLE=BASE+0x2000
POINTERS=TABLE
LENGTHS=BASE+0x2200
BINDINGS=0x1F0000
BEHAVIORS=0x1D9C00
OWNERS=BINDINGS+0x200
TILES=BINDINGS+0x220

def enabled(data):return bytes(data[DESCRIPTOR:DESCRIPTOR+8])==MAGIC
current=shared_replacements=live_pages_enabled=room_load_enabled=collision_state_enabled=room_events_enabled=routes_enabled=enabled

def hx(a):return f'{a&255:02x} {a>>8:02x}'
def call(a):return 'cd '+hx(a)
def jp(a):return 'c3 '+hx(a)
def points(data):return {'query':0x1FAB,'continue':0x1FFE}

def require_profile(data):
    from windfish.rom.windfish_identifiers import reject_patches
    reject_patches(data)

def validate(data):
    if not enabled(data):
        if bytes(data[MARKER:MARKER+4])==b'WFCB':raise ValueError('Old API runtime is unsupported; use a fresh input.')
        return False
    require_profile(data)
    if bytes(data[DESCRIPTOR:DESCRIPTOR+16])!=RECORD:raise ValueError('Unsupported API descriptor.')
    for at,blob in FIXED_BLOBS.items():
        if bytes(data[at:at+len(blob)])!=blob:raise ValueError(f'API native integration differs at {at:06X}.')
    for bank,sections in ((0x77,BLOBS),(0x7E,FRAME_BLOBS),(0x7D,{0x4000+(at&0x3FFF):blob for at,blob in FIXED_BLOBS.items() if at//0x4000==0x7D})):
        expected=bytearray(b'\xff'*0x4000)
        for a,blob in sections.items():expected[a-0x4000:a-0x4000+len(blob)]=blob
        actual=bytearray(data[bank*0x4000:(bank+1)*0x4000])
        if bank==0x77:
            for a,b in ((0x6000,0x6600),(0x6800,0x7800)):actual[a-0x4000:b-0x4000]=expected[a-0x4000:b-0x4000]
        from windfish.rom import windfish_dialogue_expansion as text_extension
        expected=text_extension.api_image(data,bank,expected)
        if actual!=expected:raise ValueError('API runtime changed or contains unsupported code.')
    spans=[]
    for i in range(256):
        ptr=int.from_bytes(data[TABLE+2*i:TABLE+2*i+2],'little');n=int.from_bytes(data[LENGTHS+2*i:LENGTHS+2*i+2],'little')
        if bool(ptr)!=bool(n) or ptr and not 0x6800<=ptr<ptr+n<=0x7800:raise ValueError('Invalid script allocation.')
        if ptr:
            if not data[OWNERS+i//8]&(1<<(i%8)):raise ValueError('Unowned API handler.')
            spans.append((ptr,ptr+n))
        if data[BEHAVIORS+i]==3 and (not ptr or not data[TILES+i]):raise ValueError('Custom behavior has no handler.')
    spans.sort()
    if any(a[1]>b[0] for a,b in zip(spans,spans[1:])):raise ValueError('Script allocations overlap.')
    _validate_registry(data)
    from windfish.rom.windfish_palette_effects import blocks,validate_native
    blocks(data)
    validate_native(data)
    return True

def install(raw):
    require_profile(raw)
    if enabled(raw):validate(raw);return bytearray(raw)
    validate(raw)
    for a,b in ((BASE,BASE+0x4000),(BINDINGS,BINDINGS+0x40C),(0x1F4000,0x1FC000)):
        if any(v!=255 for v in raw[a:b]):raise ValueError('API reservation occupied; use a fresh input.')
    if bytes(raw[0x3159:0x3164])!=bytes.fromhex('f0f9a77e2003f68077e0f8'):
        raise ValueError('Native room-status hook is modified; installation refused.')
    for at,expected in ((0x3108,bytes.fromhex('3e20ea0021cdb76d')),(0x3100,bytes.fromhex('3e21ea0021cdb340')),(0x1022,bytes.fromhex('3e24cd0708c30574')),(0x23A6,b'\xc9')):
        if bytes(raw[at:at+len(expected)])!=expected:raise ValueError('Native palette gateway conflict; installation refused.')
    for at,expected in ((0x3108,bytes.fromhex('3e20ea0021cdb76d')),(0x3100,bytes.fromhex('3e21ea0021cdb340')),(0x1022,bytes.fromhex('3e24cd0708c30574')),(0x23A6,b'\xc9')):
        if bytes(raw[at:at+len(expected)])!=expected:raise ValueError('Native palette gateway conflict; installation refused.')
    out=bytearray(raw)
    for a,blob in BLOBS.items():out[BASE+a-0x4000:BASE+a-0x4000+len(blob)]=blob
    for a,blob in FRAME_BLOBS.items():out[0x1F8000+a-0x4000:0x1F8000+a-0x4000+len(blob)]=blob
    for at,blob in FIXED_BLOBS.items():out[at:at+len(blob)]=blob
    out[TABLE:TABLE+0x600]=bytes(0x600);out[BINDINGS:BINDINGS+0x40C]=bytes(0x40C)
    out[DESCRIPTOR:DESCRIPTOR+16]=RECORD
    for at,blob in shared.code(out).items():out[at:at+len(blob)]=blob
    for bank in shared.RECORD_BANKS:
        for a,n in ((0x4A80,66),(0x4FF0,8)):
            out[bank*0x4000+a-0x4000:bank*0x4000+a-0x4000+n]=out[BASE+a-0x4000:BASE+a-0x4000+n]
    from windfish.rom import windfish_collision_storage as storage
    blob=reset_helper(out)+storage.HELPER_BYTES;out[storage.HELPER:storage.HELPER+len(blob)]=blob
    validate(out);return out


def reset_helper(data=None):
    # No CALL/PUSH/POP while SVBK 6 maps the stack window. The 128 bytes cover
    # padded cells; the room loader invokes this before loading fresh objects.
    body=bytes.fromhex('c5 d5 e5 f0 ff 47 af e0 ff f0 70 4f 3e 06 e0 70 '
        '21 00 d1 16 80 af 22 15 20 fc 79 e0 70 78 e0 ff e1 d1 c1')
    if data is None or shared_replacements(data):
        body=body.replace(bytes.fromhex('16 80'),bytes.fromhex('16 00')).replace(bytes.fromhex('79 e0 70'),bytes.fromhex('21 02 d0 22 22 77 79 e0 70'))
    if data is not None and room_load_enabled(data):
        body=body.replace(bytes.fromhex('79 e0 70'),bytes.fromhex('3e 01 ea 05 d0 79 e0 70'))
    if data is not None and routes_enabled(data):
        body=body.replace(bytes.fromhex('79 e0 70'),bytes.fromhex('af ea 06 d0 79 e0 70'))
    if data is not None and collision_state_enabled(data):
        # State is separate from consumed/replacement bookkeeping. Clear it
        # only when selecting a real room object stream, before room-load ASM.
        body=body.replace(bytes.fromhex('79 e0 70'),bytes.fromhex('21 00 d2 16 80 af 22 15 20 fc 79 e0 70'))
    if data is not None and room_events_enabled(data):
        body=body.replace(bytes.fromhex('79 e0 70'),bytes.fromhex('af ea 80 d2 ea 84 d2 3e ff ea 82 d2 79 e0 70'))
    return bytes.fromhex('f0 fe a7 28')+bytes((len(body),))+body

def room_load_renderer_helpers(data):
    """Bank-76 bridge; IE and the temporary cached bank are always restored.

    Existing ROM0 gateway restores the cached bank. Save the actual native
    cache and temporarily use 76 while entering the batch, without growing
    the fixed gateway or publishing another original-ROM hook.
    """
    gate=points(data)['query']+4
    result={
        0x4F40:asm(['f5 f0 fe a7',(0x28,'skip'),'fa a5 db a7',(0x20,'skip'),
            'c5 d5 e5 f0 ff f5 e6 02 e0 ff f0 70 4f '
            '3e 06 e0 70 fa 05 d0 57 79 e0 70 7a a7',
            (0x20,'pending'),jp(0x4FD0),('label','pending'),
            'fa af db f5 3e 76 ea af db 3e 0d',call(gate),('label','skip'),'f1 c9']),
        # The gateway is entered by CALL here, so discard that return frame
        # before restoring cache/IE. Recompute the first caller's native index:
        # it may have multiplied the placeholder's old physical ID before init.
        0x4F90:asm(['33 33 f1 ea af db f1 e0 ff e1 d1 c1 f1 f5 e5 7c fe d7',
            (0x28,'cell'),'f0 d9 c6 11 6f 26 d7',('label','cell'),
            '4e e1 06 00 cb 21 cb 10 cb 21 cb 10 f1 c9']),
        0x4FC0:bytes.fromhex(jp(0x4F90)),
        0x4FD0:bytes.fromhex('f1 e0 ff e1 d1 c1 f1 c9')}
    result[0x4F90]=bytes.fromhex('33 33 f1 ea af db f1 e0 ff e1 d1 c1 f1 '+jp(0x4D00))
    result[0x4D00]=asm(['f5 d5 e5 7c fe d7',(0x28,'cell'),
        'f0 d9 c6 11 6f 26 d7',('label','cell'),
        'f0 70 57 3e 02 e0 70 4e 7a e0 70 '
        'e1 d1 06 00 cb 21 cb 10 cb 21 cb 10 f1 c9'])
    return result

MASK_LOW=BASE+0x2400
MASK_HIGH=BASE+0x2500
BINDING_SIZE=0x40C
OLD_BEHAVIORS=BINDINGS+0x320
ALTERNATES={0x06,0x0E,0x1B,0x2B,0x79,0x8C}
def allocations(data):
    result=[]
    for script in range(256):
        ptr=int.from_bytes(data[POINTERS+script*2:POINTERS+script*2+2],'little')
        size=int.from_bytes(data[LENGTHS+script*2:LENGTHS+script*2+2],'little')
        if bool(ptr)!=bool(size) or ptr and not 0x6800<=ptr<ptr+size<=0x7800:
            raise ValueError('Invalid existing script allocation.')
        if ptr:result.append((script,ptr,size))
    for i,(script,start,size) in enumerate(result):
        if not (data[MASK_LOW+script] | data[MASK_HIGH+script]<<8):
            raise ValueError('Existing handler has an invalid zero event mask.')
        for other,other_start,other_size in result[i+1:]:
            if max(start,other_start)<min(start+size,other_start+other_size) and (start,size)!=(other_start,other_size):
                raise ValueError('Existing handler allocations overlap without exact aliasing.')
    for script in range(256):
        if data[0x1D9C00+script]==3 and not any(s==script for s,_,_ in result):
            raise ValueError('Existing Custom collision has no registered handler.')
    return result
def owned(data, script):
    return bool(data[OWNERS + script // 8] & (1 << (script % 8)))
def _validate_registry(data):
    if data[DESCRIPTOR:DESCRIPTOR+16] != RECORD:
        raise ValueError('Unknown API format descriptor.')
    if any(data[OLD_BEHAVIORS+64:BINDINGS+BINDING_SIZE]):
        raise ValueError('Room-script reserved metadata is occupied.')
    used = {s: (a, n) for s, a, n in allocations(data)}
    if any(not owned(data,i) for i in used):raise ValueError("Unowned/legacy handlers are unsupported.")
    referenced = set()
    for room in range(256):
        enabled, script = data[BINDINGS+room*2:BINDINGS+room*2+2]
        if enabled == 0 and script == 0:
            continue
        if enabled != 1 or room in ALTERNATES or script not in used or not owned(data, script):
            raise ValueError('Invalid or unowned room binding.')
        referenced.add(script)
    collision_ids = set()
    for tile in range(256):
        flag = data[TILES+tile]
        if flag not in (0,1):
            raise ValueError('Invalid collision binding flag.')
        if flag:
            if tile in referenced or tile not in used or not owned(data,tile) or data[BEHAVIORS+tile]!=3:
                raise ValueError('Invalid collision binding or conflicting room binding.')
            collision_ids.add(tile)
        elif (data[OLD_BEHAVIORS+tile//4] >> ((tile%4)*2)) & 3:
            raise ValueError('Unbound collision retains behavior metadata.')
    referenced |= collision_ids
    for script in range(256):
        if not owned(data, script):
            continue
        if script not in referenced or (data[BEHAVIORS+script]==3 and script not in collision_ids):
            raise ValueError('Owned script is orphaned or also used as a collision handler.')
        if data[MASK_LOW+script] != 0 or data[MASK_HIGH+script] != 0x20:
            raise ValueError('Owned script has a changed event mask.')
    return used
