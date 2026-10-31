"""Room-aware previews of ROM collision tiles and overworld macro presets."""
from windfish.overworld.windfish_collision_objects import COLLISION_TYPES, MACRO_TABLES

MACRO_NAMES = {0xF5:'Tree',0xF6:'Two-door house',0xF7:'Large house',
               0xF8:"Catfish’s Maw entrance",0xF9:'Palace entrance',
               0xFA:'Stone pig head',0xFB:'Palm tree',0xFC:'Walled pit',0xFD:'Small house'}
TILE_NAMES = {value: name.split(' — ')[0] for name,value in COLLISION_TYPES.items()}


def preset_tiles(data, obj):
    """Return (x,y,tile ID) cells for the baseline preset preview."""
    if obj < 0xF5:
        return [(0,0,obj)]
    if obj == 0xF5:
        return [(0,0,0x25),(1,0,0x26),(0,1,0x27),(1,1,0x28)]
    at=0x90000+MACRO_TABLES[obj]-0x4000
    offsets=[]
    while data[at]!=255:
        offsets.append(data[at]);at+=1
    # 1F is a cell left of the third row, rather than column 15.
    return [((-1 if offset&15==15 else offset&15),
             (offset>>4)+1 if offset&15==15 else offset>>4, data[at+1+i])
            for i,offset in enumerate(offsets)]

