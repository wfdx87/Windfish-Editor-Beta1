"""Guarded overworld animation header editing, including alternate layouts."""
from windfish.overworld.windfish_collision_objects import read_room_objects
from windfish.rom.windfish_collision_storage import enabled,replacement_changes


def animation_changes(data,room,alternate,value,expected=None):
    if not isinstance(value,int) or not 0<=value<=0x11:raise ValueError('Animation must be 00–11.')
    record=read_room_objects(data,room,alternate)
    if expected is not None and expected!=(record.start,record.header):raise ValueError('Room header changed. Select the room again.')
    if record.header[0]==value:return []
    if not enabled(data):raise ValueError('Reopen the ROM and install the expanded editing capabilities first.')
    raw=bytes((value,))+bytes(data[record.start+1:record.end])
    return replacement_changes(data,room,alternate,raw)
