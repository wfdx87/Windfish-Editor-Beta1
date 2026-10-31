"""Additional Map16 page with global behaviors and optional room artwork tables.

Bank 76 contains shared definitions and masked renderer gateways. Banks 79–7C
hold compact room records and a mirrored leaf reader. Physical objects stay
byte-sized and independent of shared artwork. Checked painting/recalculation
generates explicit native collision objects; rendering never changes them.
"""
from windfish.rom.windfish_identifiers import SLOTS as ID_SLOTS
from windfish.rom import windfish_room_tiles as tiles
from windfish.compatibility import api as profile
from windfish.overworld.windfish_collision_objects import expanded_cells
from windfish.rom.windfish_layout import BY_NAME as allocation

BASE = allocation['shared_map16_engine'].start
BANK = BASE//0x4000
MARKER = ID_SLOTS['shared_map16']
from windfish.rom.windfish_engine_revisions import SHARED_MAP16 as MAGIC, reject_unsupported
ALTERNATES = (0x06,0x0E,0x1B,0x2B,0x79,0x8C)
KEYS = tuple((room,False) for room in range(256)) + tuple((room,True) for room in ALTERNATES)
RECORD_SIZE = 170
RECORD_BANKS = range(allocation['shared_map16_rooms'].start//0x4000,allocation['shared_map16_rooms'].end//0x4000)
DEFINITIONS = BASE + 0x1000
ATTRIBUTES = BASE + 0x1400
BEHAVIORS = BASE + 0x1C00
ROOM_FLAGS = BASE + 0x1D00
asm = tiles._assemble


def call(at):
    return bytes((0xCD, at & 255, at >> 8)).hex()


def jump(at):
    return bytes((0xC3, at & 255, at >> 8)).hex()


def _layout(data):
    return profile.map16_layout(data,{
        'gate':0x38FC,'full':0x2FA4,'attributes':(0x2288,0x301A),
        'render_returns':(0x2293,0x22C6,0x22F3,0x3025,0x3065,0x3091)})


def helpers(data):
    # A=page flag. Saves context on the caller's original stack, masks IE,
    # accesses bank 6 without CALL/PUSH/POP, restores SVBK then IE. IME is
    # untouched. This cache byte is written before every per-cell use.
    write_flag = bytes.fromhex(
        'f5 c5 d5 57 f0 ff 47 af e0 ff f0 70 4f 3e 06 e0 70 '
        '7a ea 00 d0 f0 f6 ea 01 d0 79 e0 70 78 e0 ff d1 c1 f1 c9')
    read_flag = bytes.fromhex(
        'c5 d5 f0 ff 47 af e0 ff f0 70 4f 3e 06 e0 70 '
        'fa 00 d0 57 79 e0 70 78 e0 ff 7a d1 c1 c9')
    # The reader returns a global ID and the original physical reference.
    # References prevent persistent/event replacements being covered back up.
    lookup = asm([
        'f0 fe a7 c8 c5 d5 e5 fa a5 db a7', (0x20, 'miss'),
        '7c fe d7', (0x20, 'miss'), '7d d6 11 fe 80', (0x30, 'miss'),
        'e5 c6 20 6f 26 5b 7e fe 50', (0x30, 'padding'), '5f',
        call(0x4B00), 'a7', (0x28,'empty_record'), call(0x4A00),
        ('label','empty_record'), 'e1 a7', (0x28, 'miss'),
        '7e b8', (0x28, 'hit'), call(0x4900), 'be', (0x20, 'miss'),
        ('label', 'hit'),
        '3e 01', call(0x4600), '79 e1 d1 c1 4f 06 00 '
        'cb 21 cb 10 cb 21 cb 10 37 c9',
        ('label','padding'), 'e1',
        ('label', 'miss'), 'af', call(0x4600), 'e1 d1 c1 a7 c9'])
    # Only renderer callers may consume the per-cell page flag. In particular,
    # LoadRoomTilemap's initial bank selection must ignore a previous tile.
    addresses = _layout(data)['render_returns']
    # SP+8: saved DE/HL, helper return and saved IE precede the outer return.
    parts = ['d5 e5 f8 08 2a 5f 56']
    for i, at in enumerate(addresses):
        parts += [f'7a fe {at >> 8:02x}', (0x20, f'next{i}'),
                  f'7b fe {at & 255:02x}', (0x28, 'check'), ('label', f'next{i}')]
    parts += ['e1 d1', jump(0x4800), ('label', 'check'), 'e1 d1',
              call(0x4680), 'a7', (0x28, 'ordinary'), 'e5 '+call(0x4240)+' e1 c9',
              ('label', 'ordinary'), jump(0x4800)]
    selector = asm([
        'f0 fe a7', (0x28, 'ordinary'),
        'fa a5 db a7', (0x20, 'ordinary'),
        *parts])
    # Same instructions at 4A00 in the engine and all record banks. No code
    # executes from a bank that changes underneath it. All callers mask IE.
    reader = asm([
        '7a ea 00 21 e5 7b e6 07 4f 06 00 21 f0 4f 09 46 50 e1 e5 '
        '7b cb 3f cb 3f cb 3f 4f 06 00 09 7e a2', (0x28,'empty'),
        'e1 01 0a 00 09 7b 4f 06 00 09 4e 11 50 00 19 46 '
        '3e 76 ea 00 21 3e 01 c9',
        ('label','empty'), 'e1 3e 76 ea 00 21 af c9'])
    parts = ['d5 f0 f6 4f 06 00']
    for i, room in enumerate(ALTERNATES):
        status = 0x2B if room==0x1B else room
        parts += [f'79 fe {room:02x}',(0x20,f'next{i}'),
                  f'fa {status:02x} d8 e6 10',(0x28,'key'),
                  f'01 {i:02x} 01',(0x18,'key'),('label',f'next{i}')]
    parts += [('label','key'),'21 00 5d 09 7e a7',(0x28,'inactive'),
              '60 69 29 09 01 00 58 09 2a 47 2a 66 6f d1 50 3e 01 c9',
              ('label','inactive'),'d1 af c9']
    from windfish.rom import windfish_script_engine as custom
    if custom.enabled(data):
        # Consumed overlays must stay native through every renderer path.
        check=bytes.fromhex('c5 d5 e5 f0 70 4f 3e 06 e0 70 '
            '7d d6 11 6f 26 d1 7e 57 79 e0 70 7a e1 d1 c1 a7 c9')
        # Preserve the existing lookup's relative branches by wrapping it.
        core=lookup
        lookup=asm(['c5 d5 e5 f0 fe a7',(0x28,'ordinary'),'7c fe d7',(0x20,'ordinary'),'7d d6 11 fe 80',(0x30,'ordinary'),
            call(0x4E00),'a7',(0x20,'consumed'),('label','ordinary'),'e1 d1 c1 '+jump(0x4E80),
            ('label','consumed'),'e1 d1 c1 af '+call(0x4600)+' a7 c9'])
        custom_parts={0x4E00:check,0x4E80:core}
        if custom.shared_replacements(data):
            custom_parts[0x4F00]=bytes.fromhex('c5 d5 e5 f0 70 4f 3e 06 e0 70 '
                '7d d6 11 c6 80 6f 26 d1 7e 57 79 e0 70 7a e1 d1 c1 c9')
            lookup=asm(['c5 d5 e5 f0 fe a7',(0x28,'ordinary'),
                'fa a5 db a7',(0x20,'ordinary'),'7c fe d7',(0x20,'ordinary'),
                '7d d6 11 fe 80',(0x30,'ordinary'),call(0x4E00),
                *(['fe 03',(0x28,'live')] if custom.live_pages_enabled(data) else []),'fe 02',
                (0x28,'override'),'a7',(0x20,'consumed'),
                ('label','ordinary'),'e1 d1 c1 '+jump(0x4E80),
                ('label','override'),call(0x4F00),'4f',call(0x4900),'be',
                (0x20,'consumed'),
                *([('label','live'),call(0x4F00),'4f'] if custom.live_pages_enabled(data) else []),
                '3e 01',call(0x4600),'79 e1 d1 c1 4f 06 00 '
                'cb 21 cb 10 cb 21 cb 10 37 c9',
                ('label','consumed'),'e1 d1 c1 af '+call(0x4600)+' a7 c9'])

    else:custom_parts={}
    result={0x4000: lookup, 0x4400: selector,
            0x4600: write_flag, 0x4680: read_flag,
            0x4700: tiles.POINTER_CODE, 0x4800: tiles._BANK_CORE,
            # Resolve behavior from the shared ID, never a room-local choice.
            0x4900: bytes.fromhex('e5 69 26 5c 7e e1 c9'),
            0x4A00: reader, 0x4B00: asm(parts),
            0x4FF0: bytes(1<<i for i in range(8)),
            0x7880: bytes.fromhex(jump(0x4400)),
            0x6576: bytes.fromhex(jump(0x4200)) + b'\x00\x00'}
    from windfish.rom import windfish_room_map16 as room_tables
    result.update(room_tables.helpers(asm,call))
    result[0x7900]=asm(['e5 7c fe d7',(0x28,'lookup'),
        'f0 d9 c6 11 6f 26 d7',('label','lookup'),call(0x4000),
        'e1',(0x30,'original'),call(0x4240),'c9',
        ('label','original'),jump(0x4700)])
    result[0x4200]=bytes.fromhex(jump(0x4300))
    result[0x4300]=asm([
        '7d a7',(0x20,'lookup'),'7c e6 07',(0x20,'lookup'),
        '7c fe 40',(0x38,'lookup'),'fe 80',(0x30,'lookup'),
        call(0x4680),'a7',(0x20,'custom'),('label','lookup'),
        call(0x4000),(0x30,'original'),('label','custom'),
        'e5 d5',call(0x4240),'f5 11 00 04 19 09 7c e0 e0 7d e0 e1 '
        'f1 e0 df d1 e1 c9',('label','original'),'e5 c5 fa a5 db '+jump(0x657B)])
    if len(result[0x4300])>0x100:raise ValueError('Page-01 scrolling attributes exceed their slot.')
    result.update(custom_parts)
    if custom.enabled(data) and custom.room_load_enabled(data):
        result[0x4000]=bytes.fromhex(call(0x4F40))+result[0x4000]
        result.update(custom.room_load_renderer_helpers(data))
    if custom.enabled(data):result[0x4900]=bytes.fromhex('e5 69 26 5c 7e fe 03 20 01 af e1 c9')
    return result


def enabled(data):
    return bool(version(data))


def version(data):
    return 7 if bytes(data[MARKER:MARKER+8]) == MAGIC else 0


def record_offset(room, alternate=False):
    if not isinstance(room,int) or not 0<=room<256:
        raise ValueError('Room must be 00–FF.')
    key = 256+ALTERNATES.index(room) if alternate and room in ALTERNATES else room
    return (RECORD_BANKS.start+key//66)*0x4000+0x1000+(key%66)*RECORD_SIZE


def flag_offset(room,alternate=False):
    return ROOM_FLAGS+(256+ALTERNATES.index(room) if alternate and room in ALTERNATES else room)


def install(raw):
    validate(raw)  # Reject obsolete revisions before fresh-install checks.
    if enabled(raw):
        return bytearray(raw)
    from windfish.rom.windfish_transition_tiles import check_original
    check_original(raw)
    data = bytearray(raw)
    if any(value != 255 for value in data[BASE:BASE + 0x4000]):
        raise ValueError('Shared Map16 engine bank 76 is occupied.')
    if any(v!=255 for v in data[allocation['shared_map16_rooms'].start:allocation['shared_map16_rooms'].end]):
        raise ValueError('Shared Map16 placement banks 79–7C are occupied.')
    original = bytes(data)
    data[BASE:BASE + 0x4000] = data[tiles.START:tiles.END]
    data[MARKER:MARKER+8]=MAGIC
    from windfish.rom.windfish_room_map16 import ASSIGNMENTS
    data[ASSIGNMENTS:ASSIGNMENTS+256]=bytes(256)
    for at, blob in helpers(data).items():
        offset = BASE + at - 0x4000
        data[offset:offset + len(blob)] = blob
    # Retain all 256 page-00 entries; page 01 is an independent 256-entry set.
    graphics = tiles.definition_offset(original, 0xA2)
    attributes = tiles.attribute_offset(original, 0xA2)
    data[BASE + 0x1000:BASE + 0x1400] = original[graphics:graphics + 1024]
    data[BASE + 0x1400:BASE + 0x1800] = original[attributes:attributes + 1024]
    # No rooms are changed on installation. The shared page starts with room
    # A2's artwork and walkable behavior; the user can edit all 256 entries.
    data[BASE + 0x1800:BASE + 0x1C00] = bytes(1024)
    data[BASE + 0x1C00:BASE + 0x1D00] = bytes([2]) * 256
    data[ROOM_FLAGS:ROOM_FLAGS+len(KEYS)]=bytes(len(KEYS))
    for key,(room,alt) in enumerate(KEYS):
        at=record_offset(room,alt);ptr=0x4000+at%0x4000
        data[BASE+0x1800+key*3:BASE+0x1803+key*3]=bytes((at//0x4000,ptr&255,ptr>>8))
        data[at:at+RECORD_SIZE]=bytes(RECORD_SIZE)
    data[BASE+0x1B20:BASE+0x1BA0]=bytes(y*10+x if x<10 else 255 for y in range(8) for x in range(16))
    built=helpers(data)
    for bank in RECORD_BANKS:
        for cpu in (0x4A00,0x4FF0):
            at=bank*0x4000+cpu-0x4000
            data[at:at+len(built[cpu])]=built[cpu]
    for at,raw in code(data).items():data[at:at+len(raw)]=raw
    data[MARKER:MARKER + 8] = MAGIC
    validate(data)
    return data

def code(data):
    points=_layout(data)
    result={BASE+at-0x4000:raw for at,raw in helpers(data).items()}
    from windfish.rom.windfish_transition_tiles import code as transition_code
    result.update(transition_code(data))
    # Mask IE in fixed ROM for the entire banked helper, not just leaf RAM
    # accesses. The game's cached ROM bank must not be changed: callers own it.
    gate = points['gate']
    # Reuse padding in the existing full-graphics trampoline for the prologue.
    # No new original-ROM allocation and no standalone HUD allocation needed.
    full = points['full']
    stub = full + 3
    prologue = bytes.fromhex('f0 ff f5 af e0 ff 3e 76 ea 00 21 cd 00 78 ea 00 21') + bytes.fromhex(jump(gate + 3))
    result[stub] = prologue
    # Preserve helper AF and HL while retrieving the caller's IE from the
    # stack. Restore the selected ROM bank before re-enabling interrupt sources.
    epilogue = bytes.fromhex('f5 e5 f8 05 7e e0 ff e1 f1 33 33 c9')
    fixed = bytes.fromhex(jump(stub)) + epilogue
    result[gate] = fixed.ljust(16, b'\x00')
    attr_returns = []
    # Only full-room and scrolling attribute calls are routed to the mirror.
    for at in points['attributes']:
        result[at] = bytes.fromhex(call(gate)) + bytes(5)
        attr_returns.append(at + 3)
    # The IE save adds two bytes to the gateway's caller stack. Dispatch the
    # two new attribute calls before the existing pointer/indoor dispatch.
    old = bytes(data[tiles.HELPER:tiles.HELPER + 128])
    tail = old.rstrip(b'\x00').replace(bytes.fromhex('f8 04'), bytes.fromhex('f8 06'))
    prelude = ['d5 e5 f8 08 2a 5f 56']
    for i, ret in enumerate(attr_returns):
        prelude += [f'7a fe {ret >> 8:02x}', (0x20, f'next{i}'),
                    f'7b fe {ret & 255:02x}', (0x28, 'attribute'), ('label', f'next{i}')]
    prelude += ['e1 d1', tail.hex(), ('label', 'attribute'),
                'e1 d1', call(0x4200), '3e 76 c9']
    dispatch = asm(prelude)
    if len(dispatch) > 128:
        raise ValueError('Prototype gateway dispatch exceeds its allocation.')
    result[BASE + 0x3800] = dispatch.ljust(128, b'\x00')
    if points.get('indoor_prefix'):
        # VWF's indoor dispatcher inserts a renderer continuation underneath
        # the gateway return. Move the added IE frame along with that return,
        # so the fixed epilogue consumes IE before entering the continuation.
        prefix = points['indoor_prefix']
        if len(prefix) > 0x30:
            raise ValueError('VWF indoor continuation exceeds its gateway slot.')
        result[BASE + 0x3BC0] = prefix
    return result


def adapt_code(data, expected):
    """Layer exact feature hooks over the base engine's existing signatures."""
    if not enabled(data):return expected
    hooks=code(data);result={}
    for at,raw in expected.items():
        value=bytearray(raw)
        for start,replacement in hooks.items():
            lo=max(at,start);hi=min(at+len(raw),start+len(replacement))
            if lo<hi:value[lo-at:hi-at]=replacement[lo-start:hi-start]
        result[at]=bytes(value)
    return result


def validate(data):
    reject_unsupported(data)
    if not enabled(data):
        if bytes(data[MARKER:MARKER+5])==b'WFM16':raise ValueError('Unsupported shared Map16 engine revision. Use a clean supported Rev2 ROM or a ROM with a supported engine revision.')
        return False
    for at,raw in code(data).items():
        if bytes(data[at:at+len(raw)])!=raw:raise ValueError(f'Shared Map16 code differs at {at:06X}.')
    built=helpers(data)
    for bank in RECORD_BANKS:
        for cpu in (0x4A00,0x4FF0):
            raw=built[cpu];at=bank*0x4000+cpu-0x4000
            if bytes(data[at:at+len(raw)])!=raw:raise ValueError('Shared Map16 record reader differs.')
    if any(v not in (0,2,3) for v in data[BEHAVIORS:BEHAVIORS+256]):
        raise ValueError('Shared Map16 behavior must be Walkable or Solid.')
    for key,(room,alt) in enumerate(KEYS):
        at=record_offset(room,alt);ptr=0x4000+at%0x4000
        if bytes(data[BASE+0x1800+key*3:BASE+0x1803+key*3])!=bytes((at//0x4000,ptr&255,ptr>>8)):
            raise ValueError('Shared Map16 room directory differs.')
        if data[ROOM_FLAGS+key]!=int(any(data[at:at+10])):raise ValueError('Shared Map16 room flag differs from its placements.')
    positions=bytes(y*10+x if x<10 else 255 for y in range(8) for x in range(16))
    if bytes(data[BASE+0x1B20:BASE+0x1BA0])!=positions:raise ValueError('Shared Map16 cell-index table differs.')
    for start,end in ((0x1E76,0x2576),(0x3A00,0x3B00)):
        if data[BASE+start:BASE+end]!=data[tiles.START+start:tiles.START+end]:
            raise ValueError('Shared Map16 page-00 mirror differs.')
    from windfish.rom import windfish_script_engine as custom
    if any(v==3 for v in data[BEHAVIORS:BEHAVIORS+256]) and not custom.enabled(data):raise ValueError('Custom collision engine is missing.')
    custom.validate(data)
    from windfish.rom import windfish_room_map16 as room_tables
    room_tables.validate(data)
    return True


def locations(data,room,tile):
    if not isinstance(tile,int) or not 0<=tile<512:raise ValueError('Tile IDs must be 000–1FF.')
    if tile>=256:
        if not enabled(data):raise ValueError('Reopen the ROM to enable the shared Map16 page.')
        from windfish.rom.windfish_room_map16 import offsets
        at,attr=offsets(data,room)
        return at+4*(tile&255),attr+4*(tile&255)
    return tiles.definition_offset(data,room)+tile*4,tiles.attribute_offset(data,room)+tile*4


def definition_changes(data,tile,pieces,attributes,behavior=None,*,room=None):
    if not enabled(data) or not 0x100<=tile<0x200:raise ValueError('Choose a shared page-01 tile.')
    if len(pieces)!=4 or len(attributes)!=4 or any(type(v) is not int or not 0<=v<256 for v in (*pieces,*attributes)):
        raise ValueError('Enter four tile IDs and four attribute bytes.')
    result=[]
    at,attr=locations(data,room,tile) if room is not None else (DEFINITIONS+4*(tile&255),ATTRIBUTES+4*(tile&255))
    for start,values in ((at,pieces),(attr,attributes)):
        result.extend((start+i,data[start+i],v) for i,v in enumerate(values) if data[start+i]!=v)
    if behavior is not None:
        from windfish.rom import windfish_script_engine as runtime
        if runtime.enabled(data) and data[runtime.TILES+(tile&255)] and behavior!=3:
            raise ValueError("Remove this tile script with the standalone inserter before changing its static behavior.")
        if behavior not in (0,2,3):raise ValueError('Choose Walkable, Solid or an installed Custom handler.')
        if behavior==3:
            from windfish.rom import windfish_script_engine as custom
            if not custom.enabled(data) or not int.from_bytes(data[custom.TABLE+(tile&255)*2:custom.TABLE+(tile&255)*2+2],'little'):
                raise ValueError('Insert a handler for this tile before selecting Custom.')
        at=BEHAVIORS+(tile&255)
        if data[at]!=behavior:result.append((at,data[at],behavior))
    return result


def cells(data,room,alternate=False):
    from windfish.rendering.windfish_overworld_render import direct_map
    _,result=direct_map(data,room,alternate)
    if not enabled(data):return result
    at=record_offset(room,alternate)
    if not any(data[at:at+10]):return result
    physical,_=expanded_cells(data,room,alternate)
    for i in range(80):
        if data[at+i//8]&(1<<(i&7)):
            tile=data[at+10+i]
            if physical[i] in (data[at+90+i],proxy(data[BEHAVIORS+tile])):result[i]=256+tile
    return result


def paint_changes(data,room,alternate,placements):
    """Only page metadata changes for page 01; page 00 clears that metadata."""
    from windfish.rendering.windfish_overworld_render import direct_map
    if not enabled(data):raise ValueError('Reopen the ROM to enable the shared Map16 page.')
    at=record_offset(room,alternate);trial=bytearray(data[at:at+RECORD_SIZE])
    physical,_=expanded_cells(data,room,alternate)
    start,_=direct_map(data,room,alternate);edits={}
    for x,y,tile in placements:
        if not (type(x) is int and type(y) is int and 0<=x<10 and 0<=y<8 and type(tile) is int and 0<=tile<512):
            raise ValueError('Use room cells X=0–9, Y=0–7 and tiles 000–1FF.')
        i=y*10+x;mask=1<<(i&7)
        if tile>=256:
            trial[i//8]|=mask;trial[10+i]=tile&255;trial[90+i]=physical[i]
        else:
            trial[i//8]&=255^mask;trial[10+i]=0;trial[90+i]=0
            edits[start+i]=tile
    edits.update({at+i:v for i,v in enumerate(trial) if data[at+i]!=v})
    edits[flag_offset(room,alternate)]=int(any(trial[:10]))
    return [(offset,data[offset],v) for offset,v in sorted(edits.items()) if data[offset]!=v]


def rebase_changes(data,room,alternate=False):
    if not enabled(data):return []
    at=record_offset(room,alternate)
    if not any(data[at:at+10]):return []
    physical,_=expanded_cells(data,room,alternate)
    return [(at+90+i,data[at+90+i],physical[i]) for i in range(80)
            if data[at+i//8]&(1<<(i&7)) and data[at+90+i]!=physical[i]]


def drawing_changes(data,placements):
    """Batch 9-bit tile stamps with room-tagged edits for normal history."""
    grouped={}
    for room,x,y,tile,alt in placements:grouped.setdefault((room,bool(alt and room in ALTERNATES)),[]).append((x,y,tile))
    result=[]
    for (room,alt),values in grouped.items():
        result.extend((at,old,new,room,alt) for at,old,new in paint_changes(data,room,alt,values))
    return result


def physical_cells(data,room,alternate=False):
    physical,sources=expanded_cells(data,room,alternate)
    # Collision objects are authoritative. Shared art never creates or
    # replaces physical terrain during rendering.
    return physical,sources


def combine_native_graphics(data,room,alternate,changes,graphics):
    """A native combined placement explicitly replaces the visual page too."""
    if not enabled(data):return changes
    trial=bytearray(data);touched=set()
    for at,old,new in changes:trial[at]=new;touched.add(at)
    for at,old,new in paint_changes(trial,room,alternate,graphics):trial[at]=new;touched.add(at)
    return [(at,data[at],trial[at]) for at in sorted(touched) if data[at]!=trial[at]]


def proxy(behavior):return 0 if behavior==3 else behavior
