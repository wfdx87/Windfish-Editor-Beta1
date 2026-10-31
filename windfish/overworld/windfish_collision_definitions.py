"""Overworld object catalog and ROM physics decoding.
Names come from the disassembly's overworld constants; unnamed IDs retain
neutral labels. Runtime story, inventory and entity effects are not simulated.
"""
OBJECT_NAMES = {0: 'Solid', 1: 'Floor', 3: 'Dirt', 4: 'Short Grass', 9: 'Rocky Ground', 10: 'Tall Grass', 11: 'Path', 12: 'Tiles', 14: 'Deep water', 15: 'Water Bank Bottom', 16: 'Water Bank Top', 17: 'Water Bank Right', 19: 'Water Bank Corner Tl', 22: 'Water Bank Corner Br', 23: 'Water Bank Br', 24: 'Water Bank Bl', 25: 'Water Bank Tr', 26: 'Water Bank Tl', 27: 'Shallow Water', 32: 'Liftable Rock', 37: 'Tree Top Left', 38: 'Tree Top Right', 39: 'Tree Bottom Left', 40: 'Tree Bottom Right', 41: 'Tree Overlap Left', 42: 'Tree Overlap Right', 46: 'Cliff Corner Bl', 47: 'Cliff Bottom', 55: 'Cliff Left', 56: 'Cliff Right', 68: 'Animated Flowers', 69: 'Phone Booth Top', 77: 'Cliff Top', 92: 'Bush', 94: 'Weather Vane Base', 97: 'Well', 105: 'Hurt Tile', 110: 'Rounded Block', 111: 'Owl Statue', 128: 'Cliff Corner Tl', 129: 'Cliff Corner Tr', 130: 'Tree Bushes Bottom Left', 131: 'Tree Bushes Bottom Right', 145: 'Weather Vane Top', 186: 'Bombable Cave Door', 187: 'Giant Skull Tl', 188: 'Giant Skull Tr', 189: 'Giant Skull Bl', 190: 'Giant Skull Br', 192: 'Tail Keyhole', 194: 'Closed Gate', 198: 'Ground Stairs', 204: 'Shovel Hole', 211: 'Bush Ground Stairs', 212: 'Signpost', 216: 'Monkey Bridge Top', 217: 'Monkey Bridge Middle', 218: 'Monkey Bridge Bottom', 219: 'Monkey Bridge Built', 220: 'Weather Vane Above', 224: 'Steps', 225: 'Rocky Cave Door', 226: 'House door', 227: 'Cave Door', 232: 'Pit', 233: 'Waterfall', 245: 'Tree', 246: 'Two-door house', 247: 'Large house', 248: 'Catfish’s Maw entrance', 249: 'Palace entrance', 250: 'Stone pig head', 251: 'Palm tree', 252: 'Walled pit', 253: 'Small house'}
OBJECT_NAMES[0xA0] = 'Chest (closed)'
MACRO_SIZES = {0xF5:(2,2),0xF6:(5,3),0xF7:(3,3),0xF8:(3,2),
               0xF9:(3,2),0xFA:(2,2),0xFB:(2,2),0xFC:(5,4),0xFD:(3,2)}
# Walled pit extends one cell left in its third row.
MACRO_BOUNDS = {obj: (0,0,w-1,h-1) for obj,(w,h) in MACRO_SIZES.items()}
MACRO_BOUNDS[0xFC] = (-1,0,3,3)
ENTRANCE_OBJECTS = {0xC2,0xE1,0xCB,0xBA,0x61,0xC6,0xC5,0xE2,0xE3}
MACRO_ENTRANCES = {0xF6:2,0xF7:1,0xF8:1,0xF9:1,0xFD:1}
PROGRESS_OBJECTS = {0x5E,0x91,0xDC,0xD8,0xD9,0xDA,0xC2,0xBA,0xD3,0xA0,0xFA}
SINGLE_ONLY = ENTRANCE_OBJECTS | {0xD3} | set(range(0xF6,0xFE))
PHYSICS_NAMES = {0:'Pass-through',1:'Solid',2:'Stairs',3:'Door',4:'Ocean/switch block',
 5:'Shallow water',6:'Grass',7:'Deep water',8:'Raised ground',9:'Lowered ground',
 10:'Wide stairs',11:'Lava',0x10:'Downward ledge',0x30:'Removable obstacle',
 0x50:'Pit',0x51:'Warp pit',0x60:'Hookshotable obstacle',0x70:'Open door',
 0xB0:'Side-view water',0xB1:'Side-view ladder',0xC0:'Keyhole',
 0xE0:'Spikes',0xFE:'Unused',0xFF:'Tractor device'}


def physics_description(data,obj):
    value=data[0x20AD4+obj]
    if value in PHYSICS_NAMES:return PHYSICS_NAMES[value]
    if 0x80<=value<=0x8D:return f'Partial collision (shape {value-0x80:X})'
    if 0x90<=value<=0x9F:return f'Closed door/wall (variant {value&15:X})'
    if 0xD0<=value<=0xD3:return 'Ledge — '+('right','left','up','down')[value&3]
    if 0xF0<=value<=0xF7:return f'Conveyor (variant {value&15:X})'
    return f'Physics {value:02X}'


def fine_collision_mask(data,obj):
    value=data[0x20AD4+obj]
    if not 0x80<=value<=0x8D:return None
    from windfish.compatibility.api import fine_collision_table
    at=fine_collision_table(data,0x89CA)+(value-0x7C)*4
    return tuple(bool(v) for v in data[at:at+4])


def entrance_count(obj):
    return MACRO_ENTRANCES.get(obj,int(obj in ENTRANCE_OBJECTS))


def placement_note(obj):
    if obj in MACRO_ENTRANCES or obj in ENTRANCE_OBJECTS:
        return 'Entrances use preserved warps in placement order; destinations are unchanged.'
    if obj in PROGRESS_OBJECTS or obj==0xD3:
        return 'Behavior can depend on room/story flags; baseline preview only.'
    if obj in (0xE7,):return 'Door physics without standalone entrance registration; requires original room setup.'
    return 'Original game behavior; room-specific interactions may require matching room settings or sprites.'
