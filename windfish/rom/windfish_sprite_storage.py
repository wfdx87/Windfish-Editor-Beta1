"""Optional English Rev2 sprite database in expanded bank $71; original bank $16 retained."""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom.windfish_layout import BY_NAME as allocation
from windfish.compatibility import api as profile

from windfish.rom.windfish_palette_patch import fix_checksums

NAME = 'extended-sprite-placements-patch'
IDENTIFIER=ID_SLOTS['sprites']
MAGIC=b'WFSPR001'
MARKER=IDENTIFIER+8
ORIGINAL = 0x58000
EXTENDED = allocation['sprite_storage'].start
TABLE_SIZE = 0x640
ORIGINAL_END = 0x59701
END = allocation['sprite_storage'].end  # Independent of the standalone HUD allocation.
CPU_BASE = 0x4000  # The directory occupies the beginning of bank $71.
# Rev2 bank switch and pointer-base operands; verified by relocation experiment.
HOOKS = {0x37FE:(0x16,0x71), 0x38DC:(0x16,0x71),
         0x3810:(0x40,0x40), 0x3849:(0x42,0x42), 0x3852:(0x46,0x46)}


def enabled(data):
    return len(data)>MARKER and data[MARKER] == 1


def validate_mode(data):
    flag = data[MARKER] if len(data)>MARKER else 0
    if flag not in (0,1):
        raise ValueError(f'Unknown extended-sprite marker {flag:02X} at 0x{MARKER:X}')
    for off,(old,new) in profile.sprite_hooks(data,HOOKS).items():
        expected = new if flag else old
        if data[off] != expected:
            raise ValueError(f'Sprite patch marker and loader disagree at 0x{off:X} (expected {expected:02X}, found {data[off]:02X})')
    if flag:
        read_lists(data, True)  # reject corrupt/incomplete relocated databases
    return bool(flag)


def read_lists(data, expanded):
    base = EXTENDED if expanded else ORIGINAL
    limit = storage_end(data) if expanded else 0x5C000
    out=[]
    for i in range(TABLE_SIZE//2):
        ptr = int.from_bytes(data[base+2*i:base+2*i+2], 'little')
        if not (CPU_BASE if expanded else 0x4000) <= ptr < 0x8000:
            raise ValueError(f'Invalid sprite pointer {ptr:04X} at index {i}')
        pos = base + ptr - (CPU_BASE if expanded else 0x4000)
        if pos < base+TABLE_SIZE or pos >= limit:
            raise ValueError(f'Sprite pointer outside list region at index {i}')
        entries=[]
        while True:
            if pos >= limit:
                raise ValueError(f'Unterminated sprite list at index {i}')
            xy=data[pos]
            if xy==0xFF:break
            if pos+1>=limit:raise ValueError('Truncated sprite entry')
            entries.append((xy,data[pos+1]))
            pos+=2
            if len(entries)>256:
                raise ValueError('Unreasonable sprite list length')
        out.append(entries)
    return out


def _pack(lists):
    """Preserve original pointer-group ordering; deduplicate identical streams."""
    result=bytearray(TABLE_SIZE)
    cursor=EXTENDED+TABLE_SIZE
    seen={}
    for i,entries in enumerate(lists):
        raw=bytes(b for xy,eid in entries for b in (xy,eid))+b'\xFF'
        if raw not in seen:
            if cursor+len(raw)>END:
                raise ValueError('Expanded sprite database is full; no changes were written')
            seen[raw]=cursor
            cursor+=len(raw)
        addr=CPU_BASE+(seen[raw]-EXTENDED)
        result[2*i:2*i+2]=addr.to_bytes(2,'little')
    output=bytearray(cursor-EXTENDED)
    output[:TABLE_SIZE]=result
    for raw,start in seen.items():
        offset=start-EXTENDED
        output[offset:offset+len(raw)]=raw
    return output


def install_or_enable(data):
    validate_mode(data)
    out=bytearray(data)
    if enabled(data):return out
    # Initialize once only. Disabled-but-previously-installed ROMs retain the entire database.
    if all(v==0 for v in data[EXTENDED:END]):
        lists=read_lists(data,False)
        out[EXTENDED:END]=_pack(lists).ljust(END-EXTENDED,b'\0')
    else:
        # Existing disabled database: verify before reactivation; never overwrite it.
        read_lists(data,True)
    for off,(_,new) in profile.sprite_hooks(data,HOOKS).items():out[off]=new
    out[IDENTIFIER:IDENTIFIER+8]=MAGIC
    out[MARKER]=1
    fix_checksums(out)
    validate_mode(out)
    return out


def disable(data):
    validate_mode(data)
    out=bytearray(data)
    for off,(old,_) in profile.sprite_hooks(data,HOOKS).items():out[off]=old
    out[MARKER]=0
    fix_checksums(out)
    validate_mode(out)
    return out


def replace_overworld_room(data,room,records):
    if not enabled(data):raise ValueError('Extended sprites are disabled')
    validate_mode(data)
    if not 0<=room<256:raise ValueError('Invalid overworld room')
    entries=[]
    for x,y,eid in records:
        if not(0<=x<10 and 0<=y<8 and 0<=eid<255):
            raise ValueError('Invalid sprite position or ID (FF is reserved)')
        entries.append(((y<<4)|x,eid))
    lists=read_lists(data,True)
    from windfish.rom.windfish_sprite_limits import check_room_sprite_count
    check_room_sprite_count(len(lists[room]), len(entries))
    lists[room]=entries
    packed=_pack(lists)
    out=bytearray(data)
    out[EXTENDED:END]=packed.ljust(END-EXTENDED,b'\0')
    fix_checksums(out)
    changes=[(i,data[i],out[i]) for i in range(len(data)) if data[i]!=out[i]]
    data[:]=out
    return changes


def storage_end(data):
    """The expanded sprite pool has one fixed, HUD-independent boundary."""
    return END
