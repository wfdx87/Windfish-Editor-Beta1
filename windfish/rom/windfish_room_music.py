"""Native Rev2 room/default music tables; no audio or engine patch installation.

Outdoor entries are room-local. Indoor entries are shared by effective map
context, with native Color/Camera Shop substitutions. Runtime scripts may
supersede the default; these operations do not force playback or edit songs.
"""
TRACKS = {
    0x00: 'None',
    0x01: 'Title Screen',
    0x02: 'Minigame',
    0x03: 'Game Over',
    0x04: 'Mabe Village',
    0x05: 'Overworld',
    0x06: 'Tal Tal Range',
    0x07: 'Shop',
    0x08: 'Raft Ride Rapids',
    0x09: 'Mysterious Forest',
    0x0A: 'Inside Building',
    0x0B: 'Animal Village',
    0x0C: 'Fairy Fountain',
    0x0D: 'Title Screen No Intro',
    0x0E: 'Bowwow Kidnapped',
    0x0F: 'Obtain Sword',
    0x10: 'Obtain Item',
    0x11: 'File Select',
    0x12: 'Egg Maze',
    0x13: 'Kanalet Castle',
    0x14: 'Tail Cave',
    0x15: 'Bottle Grotto',
    0x16: 'Key Cavern',
    0x17: 'Anglers Tunnel',
    0x18: 'After Boss',
    0x19: 'Boss',
    0x1A: 'Title Cutscene',
    0x1B: 'Obtain Instrument',
    0x1C: 'Intro Wake Up',
    0x1D: 'Overworld Swordless',
    0x1E: 'Dream Shrine Sleep',
    0x1F: 'Southern Shrine',
    0x20: 'Instrument Full Moon Cello',
    0x21: '2D Underground',
    0x22: 'Owl',
    0x23: 'Final Boss',
    0x24: 'Dream Shrine Bed',
    0x25: 'Heart Container',
    0x26: 'Cave',
    0x27: 'Obtain Powerup',
    0x28: 'Instrument Conch Horn',
    0x29: 'Instrument Sea Lilys Bell',
    0x2A: 'Instrument Surf Harp',
    0x2B: 'Instrument Wind Marimba',
    0x2C: 'Instrument Coral Triangle',
    0x2D: 'Instrument Organ Of Evening Calm',
    0x2E: 'Instrument Thunder Drum',
    0x2F: 'Marin Sing',
    0x30: 'Manbos Mambo',
    0x31: 'Overworld Intro',
    0x32: 'Mr Write House',
    0x33: 'Ulrira',
    0x34: 'Tarin Bees',
    0x35: 'Mamu Frog Song',
    0x36: 'Monkeys Building Bridge',
    0x37: 'Christine House',
    0x38: 'Totaka Unused',
    0x39: 'Turtle Rock Entrance Boss',
    0x3A: 'Fisherman Under Bridge',
    0x3B: 'Obtain Item Unused',
    0x3C: 'File Select Totaka',
    0x3D: 'Ending',
    0x3E: 'Moblin Hideout',
    0x3F: 'Island Disappear',
    0x40: 'Richard House',
    0x41: 'Egg Ballad Default',
    0x42: 'Egg Ballad Bell',
    0x43: 'Egg Ballad Harp',
    0x44: 'Egg Ballad Marimba',
    0x45: 'Egg Ballad Triangle',
    0x46: 'Egg Ballad Organ',
    0x47: 'Egg Ballad All',
    0x48: 'Ghost House',
    0x49: 'Active Power Up',
    0x4A: 'Learn Ballad',
    0x4B: 'Catfishs Maw',
    0x4C: 'Open Anglers Tunnel',
    0x4D: 'Marin On Beach',
    0x4E: 'Marin Beach Talk',
    0x4F: 'Marin Unused',
    0x50: 'Miniboss',
    0x51: 'Kanalet Castle Copy',
    0x52: 'Tail Cave Copy',
    0x53: 'Dream Shrine Dream',
    0x54: 'Eagle Boss Transition',
    0x55: 'Rooster Revival',
    0x56: 'L2 Sword',
    0x57: 'Henhouse',
    0x58: 'Face Shrine',
    0x59: 'Wind Fish',
    0x5A: 'Turtle Rock',
    0x5B: 'Eagles Tower',
    0x5C: 'Eagle Boss Loop',
    0x5D: 'Final Boss Intro',
    0x5E: 'Boss Defeat',
    0x5F: 'Final Boss Defeat',
    0x60: 'File Select Zelda',
    0x61: 'Color Dungeon',
    0xFF: 'Silence',
}
TRACKS[0] = 'No new track request (special)'
TRACKS[0xFF] = 'Silence / stop (special)'


def label(track):
    return f'{track:02X} — {TRACKS.get(track, "Unknown existing track")}'


def validate(data):
    from windfish.compatibility import api as profile
    vwf=profile.is_vwf(data)
    if vwf:profile.validate_identity(data)
    if not vwf and (len(data) not in (0x100000, 0x200000) or data[0x13F:0x143] != b'AZLE'
            or data[0x14C] != 2):
        raise ValueError('Music editing requires English Link’s Awakening DX Rev2.')
    signatures = ((0x8146, bytes.fromhex('f0 bc a7 28 04 af e0 bc c9')),
                  (0x815D, bytes.fromhex('21 00 40')),
                  (0x818F, bytes.fromhex('21 00 41')))
    if any(bytes(data[at:at+len(raw)]) != raw for at, raw in signatures):
        raise ValueError('Custom music selector detected; native music editing is unavailable.')


def setting(data, room, context=None, sideview=False):
    """Return native table address, value and user-facing scope for this room."""
    validate(data)
    if not isinstance(room, int) or not 0 <= room <= 255:
        raise ValueError('Invalid room ID.')
    if context is None:
        at = 0x8000 + room
        scope = f'Overworld room {room:02X}; alternate layouts share this setting.'
    else:
        if context not in tuple(range(32)) + (255,):
            raise ValueError('Unsupported indoor map context.')
        index = 9 if context == 255 else 15 if context == 16 and room == 0xB5 else context
        at = 0x8100 + index
        scope = f'Shared indoor map-context default: {context:02X} (table entry {index:02X}). '
        scope += 'Changing this affects every room using that entry.'
        if context == 255:
            scope += ' Color Dungeon shares native entry 09.'
        if context == 16 and room == 0xB5:
            scope += ' Camera Shop uses entry 0F, shared with Trendy Game context.'
        if sideview and index < 10:
            scope += ' This side-view area normally overrides the default with 21 — 2D Underground.'
    return at, data[at], scope


def changes(data, room, track, context=None, sideview=False, expected=None):
    if track not in TRACKS:
        raise ValueError('Choose a named music track or a supported special value.')
    at, old, scope = setting(data, room, context, sideview)
    if expected is not None and expected != (at, old):
        raise ValueError('Music setting changed. Reload Room Properties before applying.')
    return [] if old == track else [(at, old, track)]
