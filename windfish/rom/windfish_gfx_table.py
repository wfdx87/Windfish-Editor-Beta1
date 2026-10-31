"""Portable raw GFX tables: 256 definitions, TL/TR/BL/BR, three bytes each.

Each record is tile ID, CGB attribute flags (bits 3..7), palette (0..7).
Flags retain bank, unused bit 4, X/Y flips and priority. No pixel/color data.
"""
import windfish.rom.windfish_room_tiles as tiles
SIZE=256*4*3


def export_table(data,room,*,page=0):
    tiles.validate(data)
    from windfish.rom.windfish_shared_map16 import locations
    at,attr=locations(data,room,256*page)
    pieces=data[at:at+1024];attributes=data[attr:attr+1024]
    if len(pieces)!=1024 or len(attributes)!=1024:raise ValueError('Incomplete tile definition table.')
    return bytes(value for piece,flags in zip(pieces,attributes) for value in (piece,flags&0xF8,flags&7))


def decode_table(raw):
    if len(raw)!=SIZE:raise ValueError(f'GFX table must be exactly {SIZE:,} bytes (256 definitions).')
    pieces=bytearray();attributes=bytearray()
    for i in range(0,SIZE,3):
        piece,flags,palette=raw[i:i+3]
        if flags&7:raise ValueError(f'Record {i//3}: flags byte must use bits 3–7 only.')
        if palette>7:raise ValueError(f'Record {i//3}: palette must be 00–07.')
        pieces.append(piece);attributes.append(flags|palette)
    return pieces,attributes


def import_changes(data,room,raw,*,page=0):
    pieces,attributes=decode_table(raw)
    tiles.validate(data)
    if page:
        from windfish.rom import windfish_shared_map16 as shared
        if page!=1 or not shared.enabled(data):raise ValueError('Shared page is not available.')
        from windfish.rom.windfish_room_map16 import import_table
        return import_table(data,room,pieces,attributes)
    if tiles.version(data)!=2:raise ValueError('Reopen this ROM and install the expanded editing capabilities first.')
    from windfish.rom.windfish_room_map16 import users
    out=bytearray(data);chosen=tiles.room_set(data,room)
    if not chosen or users(data,chosen)>1:
        chosen=next((value for value in range(0x40,256) if not data[tiles.FLAGS+value-0x40]),None)
        if chosen is None:raise ValueError('No unused custom 16×16 set remains. Free a set before importing.')
        for at,old,new in tiles.assign_set(data,room,chosen):out[at]=new
    at=tiles.definition_offset(out,room);attr=tiles.attribute_offset(out,room)
    out[at:at+1024]=pieces;out[attr:attr+1024]=attributes
    tiles.validate(out)
    return tiles.changes_between(data,out),chosen
