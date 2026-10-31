"""Overworld sprite-list edits with validated expanded storage and legacy guards."""
from windfish.overworld.windfish_sprites import read_room_sprites, BANK_END

def snapshot_room_capacities(data):
    """Session-only original capacities; no pointer edits or inferred free space."""
    capacities = {}
    starts = {}
    for room in range(256):
        info = read_room_sprites(data, room)
        capacities[room] = len(info['sprites'])
        starts.setdefault(info['start'], []).append(room)
    shared = {room for rooms in starts.values() if len(rooms)>1 for room in rooms}
    return capacities, shared


def replace_room_sprites(data, room, records, capacities, shared):
    """Rewrite only this room's original record area + terminator.

    Refuse shared streams, no-capacity rooms, and out-of-bounds edits.
    Return byte changes for existing StrokeHistory undo/redo.
    """
    from windfish.rom.windfish_sprite_storage import enabled, replace_overworld_room
    if any(not (0 <= eid <= 0xFA) for _, _, eid in records):
        raise ValueError('Sprite IDs FB–FE are unsupported; FF is reserved.')
    if enabled(data):
        return replace_overworld_room(data, room, records)
    if room in shared:
        raise ValueError('This room shares its sprite list with another room; editing is disabled for safety.')
    from windfish.rom.windfish_sprite_limits import check_room_sprite_count
    check_room_sprite_count(len(read_room_sprites(data, room)['sprites']), len(records))
    capacity = capacities.get(room, 0)
    if capacity == 0:
        raise ValueError('This room originally had no sprite slots.')
    if len(records) > capacity:
        raise ValueError('No unused sprite slots remain in this room.')
    for x,y,sprite_id in records:
        if not (0 <= x < 10 and 0 <= y < 8 and 0 <= sprite_id <= 0xFA):
            raise ValueError('Invalid sprite position or ID.')
    info = read_room_sprites(data, room)
    start = info['start']
    if info['end'] > start + capacity*2 + 1:
        raise ValueError('Sprite list exceeds original room capacity.')
    # Ensure the original allocation does not overlap another list start.
    expected_end = start + capacity*2 + 1
    if expected_end > BANK_END:
        raise ValueError('Sprite data extends outside its ROM bank.')
    output = bytearray()
    for x,y,sprite_id in records:
        output.extend(((y << 4) | x, sprite_id))
    output.extend(b'\xFF' * (expected_end - start - len(output)))
    changes=[]
    for offset, after in enumerate(output, start):
        before=data[offset]
        if before != after:
            changes.append((offset,before,after))
    for offset, before, after in changes:
        data[offset]=after
    return changes
