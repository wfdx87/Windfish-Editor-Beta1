"""Dungeon Direct Tile Draw tools and room-context tile selector."""
import hashlib
import tkinter as tk
from tkinter import ttk,messagebox
from PIL import Image,ImageTk,ImageOps
import windfish.rendering.windfish_dungeon_render as dungeon
import windfish.dungeon.windfish_dungeon_visuals as visuals
from windfish.dungeon.windfish_dungeon_collisions import placement_changes


from windfish.app.windfish_gui_shared import tile_canvas, tile_cell, tile_rectangle, tile_values, draw_tile_sheet


class DungeonTileSelector(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self._key=None
        self.title('Tile Selector');self.geometry('350x260');self.minsize(350,200)
        self.transient(owner);self.protocol('WM_DELETE_WINDOW',self.close)
        frame=ttk.Frame(self,padding=8);frame.pack(fill='both',expand=True)
        from windfish.overworld.windfish_collision_palette import build_draw_controls
        build_draw_controls(frame,owner.add_collisions,owner.calculate_collisions)
        self.label=tk.StringVar();self.cell=16
        self.canvas = tile_canvas(frame, '#202028')
        self.canvas.bind('<Button-1>',self.pick)
        self.canvas.bind('<B1-Motion>',self.extend);self.canvas.bind('<Configure>',lambda event:self.refresh())
        ttk.Label(frame,textvariable=self.label,wraplength=320).pack(anchor='w',pady=(6,0))
        self.bind('<FocusIn>',lambda event:self.owner.refresh_document() if event.widget==self else None)
        owner.bind_history_shortcuts(self);self.refresh()
        from windfish.app.windfish_selector_size import configure_bounds
        self.after_idle(lambda:configure_bounds(self,self.canvas,maximize=True))

    def close(self):self.owner.tile_selector=None;self.destroy()

    def pick(self,event):
        self.anchor = tile_cell(event.x, event.y, self.cell)
        self.extend(event)

    def extend(self,event):
        end = tile_cell(event.x, event.y, self.cell)
        left,top,right,bottom = tile_rectangle(self.anchor, end)
        self.owner.draw_tile.set(top*16+left)
        self.owner.draw_size=(right-left+1,bottom-top+1)
        self.owner.draw_values = tile_values((left, top, right, bottom))
        self.owner.tile_map_selection=None;self.refresh();self.owner.draw()

    def refresh(self):
        owner=self.owner
        if owner.data is None:self.canvas.delete('all');self.label.set('Open a ROM in the main window.');return
        context,side=owner.render_context(owner.room)
        # Visual edits do not change the source tile graphics.
        try:
            record=dungeon.read_room(owner.data,context,owner.room)
            raw,selector,warnings=dungeon.graphics(owner.data,record,side)
            key=(context,owner.room,side,raw,dungeon.attributes(owner.data,context,owner.room),dungeon.palette(owner.data,context,side,owner.room))
            if key!=self._key:
                sheet,_=dungeon.tile_sheet(owner.data,context,owner.room,side)
                self.sheet=sheet;self._key=key
        except (ValueError,IndexError) as exc:
            self.canvas.delete('all');self._key=None;self.label.set(str(exc));return
        from windfish.app.windfish_selector_size import cell_size
        self.cell=cell_size(self.canvas.winfo_width(),self.canvas.winfo_height());c=self.cell
        self.photo = draw_tile_sheet(self.canvas, self.sheet, c)
        tile=owner.draw_tile.get();x=tile%16*c;y=tile//16*c
        w,h=owner.draw_size
        self.canvas.create_rectangle(x+1,y+1,x+w*c-1,y+h*c-1,outline='#ffff55',width=3)
        self.label.set(f'Room {owner.room:02X} · Tile {tile:02X} · {w}×{h} selection · Right-click map to paste')


class DungeonDrawMixin:
    def install_visual_layer(self):
        if self.data is None:return False
        try:
            # Prepare dependencies on a private buffer, then commit once. A
            # failed install must not leave half the prerequisites installed.
            from windfish.dungeon.windfish_dungeon_storage import enabled as storage_enabled,install as install_storage
            out=self.data if storage_enabled(self.data) else install_storage(self.data)
            out=visuals.install(out)
            self.apply_room_changes([(at,old,new) for at,(old,new) in enumerate(zip(self.data,out)) if old!=new])
            return True
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self);return False

    def toggle_direct_draw(self):
        requested=self.direct_draw.get()
        self.finish_draw();self._tile_anchor=None;self._collision_drag=None
        if requested:
            if hasattr(self,"sprite_mode"):self.sprite_mode.set(False);self.selected_sprite=None;self._sprite_drag=None
            if self.data is None:
                self.direct_draw.set(False);messagebox.showerror('Room editing', 'Open a ROM before enabling Edit Room Tiles.', parent=self);return
            if not visuals.enabled(self.data) and not self.install_visual_layer():
                self.direct_draw.set(False);return
            # Installation refreshes the document and can reset mode variables.
            # Preserve the user's request after that refresh has completed.
            self.direct_draw.set(True)
            self.collision_mode.set(False);self.selected_collision=None;self._collision_drag=None;self._tile_anchor=None
        self.canvas.configure(cursor='crosshair' if self.direct_draw.get() else '');self.draw()

    def open_tile_selector(self):
        if self.tile_selector is None:self.tile_selector=DungeonTileSelector(self)
        else:self.tile_selector.deiconify();self.tile_selector.lift()

    def draw_cell(self,event):
        if self.data is None or not hasattr(self,'_layout'):return None
        z=self.zoom.get();px=int(self.canvas.canvasx(event.x))-16;py=int(self.canvas.canvasy(event.y))-16
        if px<0 or py<0:return None
        if self.map_view():
            col=px//(160*z);row=py//(128*z)
            if not 0<=col<self._cols or not 0<=row<self._rows:return None
            room=self._layout[row*self._cols+col]
            if room is None:return None
        else:
            if px>=160*z or py>=128*z:return None
            room=self.room
        return room,(px//(16*z))%10,(py//(16*z))%8

    def paint_press(self,event):
        self.owner.end_stroke();self._draw_drag=True;self._draw_last=None;self.canvas.focus_set()
        self.paint_motion(event);return 'break'

    def paint_motion(self,event):
        if not self.direct_draw.get() or not self._draw_drag:return
        cell=self.draw_cell(event)
        if cell is None:self._draw_last=None;return 'break'
        room,x,y=cell
        if cell==self._draw_last:return 'break'
        points=[(x,y)]
        if self._draw_last is not None and self._draw_last[0]==room:
            _,x0,y0=self._draw_last
            # Bresenham avoids gaps when mouse events skip across cells.
            dx=abs(x-x0);sx=1 if x0<x else -1;dy=-abs(y-y0);sy=1 if y0<y else -1;error=dx+dy;points=[]
            while True:
                points.append((x0,y0))
                if (x0,y0)==(x,y):break
                twice=2*error
                if twice>=dy:error+=dy;x0+=sx
                if twice<=dx:error+=dx;y0+=sy
        try:
            context,_=self.render_context(room)
            w,h=self.draw_size;tile=self.draw_tile.get()
            values=self.draw_values or tuple(tile+oy*16+ox for oy in range(h) for ox in range(w))
            cells=[(cx+ox,cy+oy,values[oy*w+ox]) for cx,cy in points for oy in range(h) for ox in range(w) if cx+ox<10 and cy+oy<8]
            changes=placement_changes(self.data,context,room,cells,combined=True) if self.add_collisions.get() else visuals.paint_cells_changes(self.data,context,room,cells)
            for at,old,new in changes:self.owner.history.record(at,old,new,self.owner.room,False);self.data[at]=new
            if room!=self.room:self.select_room(room,center=False)
            if changes:
                self._digest=hashlib.sha256(self.data).digest()
                self._images={key:value for key,value in self._images.items() if not (key[1]==room and dungeon.room_bank(key[0])==dungeon.room_bank(context))}
                self.owner.refresh_title();self.draw()
            self._draw_last=cell
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self);self._draw_last=None
        return 'break'

    def finish_draw(self,event=None):
        if self._draw_drag:self.owner.history.commit()
        self._draw_drag=False;self._draw_last=None

    def tile_left_press(self,event):
        self.finish_draw();cell=self.draw_cell(event)
        if cell is None:return 'break'
        room,x,y=cell
        if room!=self.room:self.select_room(room,center=False)
        sel=self.tile_map_selection
        self._tile_action='move' if sel and sel[0]==room and sel[1]<=x<sel[1]+sel[3] and sel[2]<=y<sel[2]+sel[4] else 'select'
        self._tile_anchor=cell;self._tile_target=cell
        if self._tile_action=='select':self.read_tile_selection(room,x,y,x,y)
        self.canvas.focus_set();self.draw();return 'break'

    def read_tile_selection(self,room,x0,y0,x1,y1):
        context,_=self.render_context(room);record=dungeon.read_room(self.data,context,room)
        cells=visuals.apply_to_cells(self.data,context,room,dungeon.layout(self.data,record))
        values=tuple(cells[y*10+x] for y in range(y0,y1+1) for x in range(x0,x1+1))
        self.draw_tile.set(values[0]);self.draw_size=(x1-x0+1,y1-y0+1);self.draw_values=values
        self.tile_map_selection=(room,x0,y0,*self.draw_size,values)

    def tile_left_motion(self,event):
        if self._tile_anchor is None:return 'break'
        cell=self.draw_cell(event)
        if cell is None or cell[0]!=self._tile_anchor[0]:return 'break'
        self._tile_target=cell;room,x,y=cell;_,sx,sy=self._tile_anchor
        if self._tile_action=='select':
            self.read_tile_selection(room,min(x,sx),min(y,sy),max(x,sx),max(y,sy));self.draw()
        else:
            sel=self.tile_map_selection;self.draw_tile_selection((room,sel[1]+x-sx,sel[2]+y-sy,sel[3],sel[4],sel[5]),ghost=True)
        return 'break'

    def tile_left_release(self,event):
        if self._tile_anchor is None:return
        cell=self.draw_cell(event) or self._tile_target
        sel=self.tile_map_selection
        if self._tile_action=='move' and cell and cell[0]==self._tile_anchor[0] and cell!=self._tile_anchor and sel:
            room,x,y=cell;_,sx,sy=self._tile_anchor;_,ox,oy,w,h,values=sel;nx=ox+x-sx;ny=oy+y-sy
            context,_=self.render_context(room)
            cells=[(ox+i,oy+j,0) for j in range(h) for i in range(w) if 0<=ox+i<10 and 0<=oy+j<8]
            cells += [(nx+i,ny+j,values[j*w+i]) for j in range(h) for i in range(w) if 0<=nx+i<10 and 0<=ny+j<8]
            try:
                changes=placement_changes(self.data,context,room,cells,combined=True) if self.add_collisions.get() else visuals.paint_cells_changes(self.data,context,room,cells)
                self.apply_room_changes(changes)
                # Keep only the visible part selected after an edge-clipped move.
                left=max(0,nx);top=max(0,ny);right=min(9,nx+w-1);bottom=min(7,ny+h-1)
                if left<=right and top<=bottom:self.read_tile_selection(room,left,top,right,bottom)
                else:self.tile_map_selection=None
            except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        self._tile_anchor=None;self.canvas.delete('tile-selection');self.draw();return 'break'

    def draw_tile_selection(self,sel=None,ghost=False):
        self.canvas.delete('tile-selection')
        sel=sel or self.tile_map_selection
        if not self.direct_draw.get() or sel is None:return
        room,x,y,w,h,values=sel;origin=self.room_origin(room)
        if origin is None:return
        z=self.zoom.get();sheet=self.brush_sheet(room)
        image=Image.new('RGB',(w*16,h*16))
        for j in range(h):
            for i in range(w):
                tile=values[j*w+i];image.paste(sheet.crop((tile%16*16,tile//16*16,tile%16*16+16,tile//16*16+16)),(i*16,j*16))
        if not ghost:image=ImageOps.invert(image)
        left=max(0,-x);top=max(0,-y);right=min(w,10-x);bottom=min(h,8-y)
        if left>=right or top>=bottom:return
        image=image.crop((left*16,top*16,right*16,bottom*16))
        self._tile_selection_photo=ImageTk.PhotoImage(image.resize((image.width*z,image.height*z),Image.Resampling.NEAREST))
        px=origin[0]+(x+left)*16*z;py=origin[1]+(y+top)*16*z
        self.canvas.create_image(px,py,image=self._tile_selection_photo,anchor='nw',tags='tile-selection')
        self.canvas.create_rectangle(px,py,px+image.width*z,py+image.height*z,outline='#ffff55',width=3,tags='tile-selection')
