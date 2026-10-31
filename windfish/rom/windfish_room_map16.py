"""Optional per-room Page-01 artwork tables, sharing the existing 2 KiB pool.

Assignments occupy bank 76:4C00-4CFF. Zero uses the global Page-01 table;
40-FF selects a normal reusable definition/attribute set. Behaviors and
handler IDs remain global. Neither VRAM bank loading nor collisions change.
"""
from windfish.rom import windfish_room_tiles as tiles

ASSIGNMENTS=0x1D8C00


def enabled(data):
    from windfish.rom import windfish_shared_map16 as shared
    return shared.version(data)>=3


def room_set(data,room):
    if not isinstance(room,int) or not 0<=room<256:raise ValueError('Room must be 00-FF.')
    return data[ASSIGNMENTS+room] if enabled(data) else 0


def offsets(data,room):
    from windfish.rom import windfish_shared_map16 as shared
    selected=room_set(data,room)
    at=tiles.set_offset(selected) if selected else shared.DEFINITIONS
    return at,at+1024


def users(data,set_id):
    """Include both pages: editing a reusable table affects every assignment."""
    return sum(tiles.room_set(data,r)==set_id for r in range(256))+sum(room_set(data,r)==set_id for r in range(256))


def validate(data):
    if not enabled(data):return
    for value in data[ASSIGNMENTS:ASSIGNMENTS+256]:
        if value and (value<0x40 or data[tiles.FLAGS+value-0x40]!=1):
            raise ValueError('Page-01 room table references an uninitialized Map16 set.')


def assign_set(data,room,set_id):
    if not enabled(data):raise ValueError('Reopen this ROM to enable room-specific Page-01 tables.')
    room_set(data,room)
    if set_id:tiles.set_offset(set_id)
    out=bytearray(data)
    if set_id and not out[tiles.FLAGS+set_id-0x40]:
        at=tiles.set_offset(set_id)
        if any(v!=255 for v in out[at:at+2048]):raise ValueError('Unused Map16 table storage is occupied.')
        source,attr=offsets(data,room)
        out[at:at+1024]=data[source:source+1024]
        out[at+1024:at+2048]=data[attr:attr+1024]
        out[tiles.FLAGS+set_id-0x40]=1
    out[ASSIGNMENTS+room]=set_id
    validate(out)
    return tiles.changes_between(data,out)


def import_table(data,room,pieces,attrs):
    """Import privately unless this room already owns its table exclusively."""
    selected=room_set(data,room);out=bytearray(data)
    if not selected or users(data,selected)>1:
        # Prefer A0-FF for Page 1; existing tables and Page-00 assignments are
        # never relocated or reinterpreted. The remaining pool is a fallback.
        selected=next((i for i in (*range(0xA0,256),*range(0x40,0xA0)) if not data[tiles.FLAGS+i-0x40]),None)
        if selected is None:raise ValueError('No unused Map16 table remains.')
        for at,old,new in assign_set(out,room,selected):out[at]=new
    at,attr=offsets(out,room)
    out[at:at+1024]=pieces;out[attr:attr+1024]=attrs
    validate(out)
    return tiles.changes_between(data,out),selected


def helpers(asm,call):
    """Bank-76 leaf: return room Page-01 definition base HL and ROM bank A.

    Preserves BC/DE, clobbers HL and flags. The selector saves HL itself.
    Pointer, full redraw and scrolling attribute paths use the same resolver.
    """
    resolve=asm(['c5 d5 f0 f6 6f 26 4c 7e fe 40',(0x38,'global'),
        'd6 40 4f e6 07 07 07 07 c6 40 67 2e 00 '
        '79 cb 3f cb 3f cb 3f c6 48',(0x18,'done'),
        ('label','global'),'21 00 50 3e 76',('label','done'),'d1 c1 c9'])
    if len(resolve)>0xC0:raise ValueError('Page-01 table resolver exceeds its slot.')
    return {0x4240:resolve}


def wrap_collision_reader(original,asm,call,jp):
    """Redirect only reads of bank-76 Page-01 art, including live replacements.

    The old reader moves to 4860. Bounds leave behavior tables, physics,
    scripts and every other ROM read unchanged. Preserve BC/DE/HL as before.
    """
    wrapper=asm(['fe 76',(0x20,'ordinary'),'f5 7c fe 50',(0x38,'outside'),
        'fe 58',(0x30,'outside'),'f1 c5 d5 e5 54 5d f0 f6 6f 26 4c 3e 76',call(0x4860),
        'fe 40',(0x38,'global'),'d6 40 4f e6 07 07 07 07 c6 40 47 '
        '7a e6 07 80 67 6b 79 cb 3f cb 3f cb 3f c6 48',call(0x4860),
        'e1 d1 c1 c9',('label','global'),'e1 d1 c1 3e 76 '+jp(0x4860),
        ('label','outside'),'f1',('label','ordinary'),jp(0x4860)])
    if len(wrapper)>0x60 or len(original)>0x20:raise ValueError('Page-01 collision reader exceeds its slot.')
    return wrapper,original
