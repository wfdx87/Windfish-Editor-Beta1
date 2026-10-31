"""Dungeon/interior BG animation preview using the resolved room context."""
from windfish.rendering.windfish_animation_editor import AnimationPage, NAMES, SPECIAL, frame_address
import windfish.rendering.windfish_dungeon_render as dungeon


def animated_tiles(data, context, cells):
    mapping=dungeon.chunk(data, dungeon.COLOR_FORMATION if context==255 else dungeon.FORMATION, 1024)
    return sorted({tile for tile in cells if any(0x6C<=part<=0x6F for part in mapping[tile*4:tile*4+4])})


class DungeonAnimationPage(AnimationPage):
    def __init__(self, properties, tabs):
        super().__init__(properties, tabs, dungeon=True)

    def refresh(self):
        o=self.owner.owner
        self.images=[];self.tick=0
        self.preview.itemconfigure(self.preview_item,image='')
        self.status.set('No ROM loaded.')
        if o.data is None:return
        try:
            context,sideview=o.render_context(o.room)
            record=dungeon.read_room(o.data,context,o.room)
            aid=record.animation
            self.status.set(f'Room {o.room:02X} • Map {context:02X} • {aid:02X} — {NAMES[aid] if aid<18 else "Unknown"}')
            if sideview:
                self.status.set(self.status.get()+'\nSide-view rooms do not use landscape BG animation.')
                return
            cells=dungeon.layout(o.data,record,o._templates,o._doors)
            from windfish.dungeon.windfish_dungeon_visuals import apply_to_cells
            cells=apply_to_cells(o.data,context,o.room,cells)
            tiles=animated_tiles(o.data,context,cells) if aid else []
            if not tiles:
                self.status.set(self.status.get()+'\nNo animated 16×16 tiles in this room.')
                return
            self.status.set(self.status.get()+'\nAnimated 16×16 tiles: '+', '.join(f'{t:02X}' for t in tiles))
            if aid in SPECIAL or not 0<=aid<18:
                sheet,_=dungeon.tile_sheet(o.data,context,o.room)
                self.images=[self.gallery_photo(sheet,tiles)]
                self.status.set(self.status.get()+'\nStatic tile preview. This group uses special runtime logic.')
            else:
                at=frame_address(o.data,aid)
                self.delay=267 if aid in (2,3,5,11,12) else (67 if aid in (9,10,13) else 133)
                for frame in range(4):
                    raw=bytes(o.data[at+frame*64:at+(frame+1)*64])
                    sheet,_=dungeon.tile_sheet(o.data,context,o.room,animation_frame=raw)
                    self.images.append(self.gallery_photo(sheet,tiles))
                if aid in (4,6):self.images=[self.images[i] for i in (0,1,2,3,3,3,2,1)]
            self.toggle_frames()
        except (ValueError,IndexError) as exc:
            self.status.set(self.status.get()+'\n'+str(exc))
