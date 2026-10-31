"""Indoor sprite rendering and map editing using the shared sprite definitions."""
import tkinter as tk
from windfish.rom.windfish_sprite_limits import SpriteLimitError, LIMIT_TITLE
from tkinter import ttk,messagebox
from PIL import Image,ImageTk
import windfish.dungeon.windfish_dungeon_room_data as rooms
import windfish.rendering.windfish_dungeon_render as dungeon
from windfish.rendering.windfish_sprite_render import render_sprite_result,sprite_draw_offset
from windfish.rendering.windfish_sprite_vram import loaded_vram_provider
from windfish.rendering.windfish_sprite_palettes import gbc_rgb
from windfish.rendering.windfish_sprite_definitions import SPRITE_DEFINITIONS
from windfish.rendering.windfish_sprite_names import SPRITE_NAMES
from windfish.app.windfish_sprite_display import highlight_sprite,draw_sprite_hex


def object_palettes(data,map_id,room,sideview=False):
    # palettes.asm 21:41B4: shared six OBJ palettes, then the room record's two.
    at=dungeon.palette_offset(data,map_id,sideview,room)
    raw=bytes(data[0x85518:0x85548])+bytes(data[at+64:at+80])
    if len(raw)!=64:raise ValueError('Missing indoor OBJ palettes.')
    colors=tuple(gbc_rgb(int.from_bytes(raw[i:i+2],'little')) for i in range(0,64,2))
    return tuple(colors[i:i+4] for i in range(0,32,4))


def render_result(data,map_id,room,sprite_id,frame=None,sideview=False):
    loaded=rooms.loaded_sprite_graphics(data,map_id,room)
    def provider(definition):
        return loaded_vram_provider(data,loaded,graphics_overrides=definition.graphics_overrides,
                                    graphics_sources=definition.graphics_sources)
    return render_sprite_result(data,room,sprite_id,frame,provider=provider,
                                palettes=object_palettes(data,map_id,room,sideview))


class DungeonSpriteSelector(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.frame=0;self.key=None
        self.title('Sprite Selector');self.geometry('735x300');self.resizable(False,False);self.transient(owner)
        self.protocol('WM_DELETE_WINDOW',self.close);owner.bind_history_shortcuts(self)
        left=ttk.Frame(self);left.pack(side='left',fill='both',expand=True,padx=10,pady=10)
        self.list=tk.Listbox(left,exportselection=False);scroll=ttk.Scrollbar(left,command=self.list.yview)
        self.list.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.list.pack(fill='both',expand=True)
        for value in range(0xFB):self.list.insert('end',f'{value:02X} — {SPRITE_NAMES.get(value,"Unknown sprite")}')
        self.list.selection_set(owner.sprite_id.get());self.list.see(owner.sprite_id.get());self.list.bind('<<ListboxSelect>>',self.choose)
        right=ttk.Frame(self,width=260);right.pack(side='right',fill='both',padx=10,pady=10);right.pack_propagate(False)
        self.preview=ttk.Label(right,anchor='center');self.preview.pack(fill='x',pady=8)
        buttons=ttk.Frame(right);buttons.pack();ttk.Button(buttons,text='<',width=4,command=lambda:self.cycle(-1)).pack(side='left')
        self.label=ttk.Label(buttons);self.label.pack(side='left',padx=10)
        ttk.Button(buttons,text='>',width=4,command=lambda:self.cycle(1)).pack(side='left')
        self.message=ttk.Label(right,wraplength=240);self.message.pack(fill='x',pady=8)
        ttk.Label(right,text='Left: select / drag\nRight: place sprite\nDelete: remove selected',justify='left').pack(anchor='w')
        ttk.Button(right,text='Replace selected sprite',command=owner.sprite_replace).pack(anchor='w',pady=4)
        self.refresh()
    def close(self):self.owner.sprite_selector=None;self.destroy()
    def choose(self,event=None):
        selection=self.list.curselection()
        if not selection:return
        self.owner.sprite_brush=selection[0];self.owner.sprite_id.set(selection[0]);self.frame=0;self.key=None
        self.owner.sprite_mode.set(True);selected=self.owner.selected_sprite
        self.owner.toggle_sprite_mode();self.owner.selected_sprite=selected;self.owner.draw();self.refresh()
    def cycle(self,delta):
        from windfish.app.windfish_sprite_display import cycle_preview_frame
        self.frame=cycle_preview_frame(self.owner.sprite_id.get(),self.frame,delta);self.key=None;self.refresh()
    def refresh(self):
        owner=self.owner
        if owner.data is None:return
        m,side=owner.render_context(owner.room);sid=owner.sprite_id.get()
        if getattr(self,'last_id',None)!=sid:
            self.frame=0;self.last_id=sid
            self.list.selection_clear(0,'end');self.list.selection_set(sid);self.list.see(sid)
        key=(owner._digest,m,owner.room,sid,self.frame,side)
        if key==self.key:return
        self.key=key
        try:
            result=render_result(owner.data,m,owner.room,sid,self.frame,side)
            image=result.image
            if image is not None:
                scale=max(1,min(4,96//max(image.size)));self.photo=ImageTk.PhotoImage(image.resize((image.width*scale,image.height*scale),Image.Resampling.NEAREST))
                self.preview.configure(image=self.photo)
            definition=SPRITE_DEFINITIONS.get(sid);count=len(definition.frames) if definition else 1
            self.label.configure(text=f'Frame {self.frame+1}/{count}');self.message.configure(text=result.message)
        except (ValueError,IndexError) as exc:self.message.configure(text=str(exc))


class DungeonSpriteMixin:
    def toggle_sprite_mode(self):
        self.finish_draw();self.selected_sprite=None;self._sprite_drag=None
        self.selected_collision=None;self._collision_drag=None;self.tile_map_selection=None;self._tile_anchor=None
        if self.sprite_mode.get() and self.data is None:self.sprite_mode.set(False)
        if self.sprite_mode.get():
            self.direct_draw.set(False);self.collision_mode.set(False);self.show_sprites.set(True)
        self.canvas.configure(cursor='crosshair' if self.sprite_mode.get() else '');self.draw()
    def open_sprite_selector(self):
        if self.sprite_selector is None:self.sprite_selector=DungeonSpriteSelector(self)
        else:self.sprite_selector.deiconify();self.sprite_selector.lift()
    def draw_sprite_overlay(self):
        self._sprite_photos=[]
        if not (self.show_sprites.get() or self.show_sprite_ids.get()):return
        z=self.zoom.get();canvas=self.canvas
        visible=(canvas.canvasx(0),canvas.canvasy(0),canvas.canvasx(canvas.winfo_width()),canvas.canvasy(canvas.winfo_height()))
        slots=enumerate(self._layout) if self.map_view() else ((0,self.room),)
        for slot,room in slots:
            if room is None:continue
            ox=16+(slot%self._cols*160*z if self.map_view() else 0);oy=16+(slot//self._cols*128*z if self.map_view() else 0)
            if ox>visible[2] or oy>visible[3] or ox+160*z<visible[0] or oy+128*z<visible[1]:continue
            m,side=self.render_context(room)
            try:entries=rooms.sprites(self.data,m,room)
            except (ValueError,IndexError):continue
            for index,(xy,sid) in enumerate(entries):
                x,y=xy&15,xy>>4
                if not 0<=x<10 or not 0<=y<8:continue
                if self._sprite_drag and self.selected_sprite and self.selected_sprite[:3]==(m,room,index):x,y=self._sprite_drag
                key=(m,room,sid,side)
                try:
                    if key not in self._sprite_images:self._sprite_images[key]=render_result(self.data,m,room,sid,sideview=side).image
                    image=self._sprite_images[key]
                    if image is None:continue
                    dx,dy=sprite_draw_offset(sid, indoor=True);px=ox+(x*16+dx)*z;py=oy+(y*16+dy)*z
                    selected=self.sprite_mode.get() and self.selected_sprite is not None and self.selected_sprite[:3]==(m,room,index)
                    if selected:image=highlight_sprite(image)
                    photo=ImageTk.PhotoImage(image.resize((image.width*z,image.height*z),Image.Resampling.NEAREST));self._sprite_photos.append(photo)
                    if self.show_sprites.get():canvas.create_image(px,py,image=photo,anchor='nw')
                    if self.show_sprite_ids.get():draw_sprite_hex(canvas,ox+x*16*z,oy+y*16*z,sid,z,selected)
                except (ValueError,IndexError):continue
    def sprite_click(self,event):
        self.selected_sprite=None;self._sprite_drag=None;cell=self.draw_cell(event)
        if cell is not None:
            room,x,y=cell
            if room!=self.room:self.select_room(room,center=False)
            m,_=self.render_context(room)
            try:
                entries=rooms.sprites(self.data,m,room)
                for index,(xy,sid) in reversed(list(enumerate(entries))):
                    if xy==y*16+x:
                        self.selected_sprite=(m,room,index,entries);self.sprite_id.set(sid);self.sprite_brush=sid;break
            except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        self.canvas.focus_set()
        if getattr(event,'state',0)&4:
            self._sprite_drag=None;self.sprite_delete();return 'break'
        self.draw();return 'break'
    def sprite_motion(self,event):
        if self.selected_sprite is None:return
        cell=self.draw_cell(event)
        if cell is not None and cell[0]==self.selected_sprite[1]:self._sprite_drag=cell[1:];self.draw()
        return 'break'
    def sprite_release(self,event):
        if self.selected_sprite and self._sprite_drag:
            m,room,index,entries=self.selected_sprite;x,y=self._sprite_drag;sid=entries[index][1]
            self._sprite_drag=None
            try:
                self.apply_room_changes(rooms.sprite_changes(self.data,m,room,index,(x,y,sid),expected=entries))
                self.selected_sprite=(m,room,index,rooms.sprites(self.data,m,room));self.draw()
            except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        return 'break'
    def sprite_place(self,event):
        cell=self.draw_cell(event)
        if cell is None:return 'break'
        room,x,y=cell
        if getattr(self,'sprite_brush',None) is None:
            messagebox.showerror('Room editing', 'Choose a sprite on the map or in Sprite Selector first.', parent=self);return 'break'
        if self.sprite_brush>=0xFB:
            messagebox.showerror('Room editing', 'FB–FE are unsupported sprite IDs; FF is reserved. Choose 00–FA.', parent=self);return 'break'
        if room!=self.room:self.select_room(room,center=False)
        m,_=self.render_context(room)
        try:
            self.apply_room_changes(rooms.sprite_changes(self.data,m,room,values=(x,y,self.sprite_brush)))
            entries=rooms.sprites(self.data,m,room)
            self.selected_sprite=(m,room,len(entries)-1,entries);self.draw()
        except SpriteLimitError as exc:
            messagebox.showwarning(LIMIT_TITLE, str(exc), parent=self)
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        return 'break'
    def sprite_double_click(self,event):
        if getattr(event,'state',0)&4:return 'break'
        self.sprite_click(event);self._sprite_drag=None
        if self.selected_sprite is None:return 'break'
        m,room,index,entries=self.selected_sprite;xy,sid=entries[index]
        from windfish.app.windfish_sprite_display import build_sprite_id_dialog,bind_sprite_id_dialog
        choices=[f'{i:02X} — {SPRITE_NAMES.get(i,"Unknown sprite")}' for i in range(0xFB)]
        dialog,value,combo,buttons=build_sprite_id_dialog(self,room,xy&15,xy>>4,choices,
            f'{sid:02X} — {SPRITE_NAMES.get(sid,"Unknown sprite")}')
        def accept():
            try:
                new_id=int(value.get()[:2],16)
                if not 0<=new_id<0xFB:raise ValueError('Choose a sprite ID from 00–FA.')
                self.apply_room_changes(rooms.sprite_changes(self.data,m,room,index,(xy&15,xy>>4,new_id),expected=entries))
                self.sprite_id.set(new_id);self.sprite_brush=new_id
                self.selected_sprite=(m,room,index,rooms.sprites(self.data,m,room));self.draw();dialog.destroy()
            except (ValueError,IndexError) as exc:messagebox.showwarning('Cannot change sprite',str(exc),parent=dialog)
        bind_sprite_id_dialog(dialog,combo,buttons,accept)
        return 'break'

    def sprite_replace(self):
        if self.selected_sprite:
            m,room,index,entries=self.selected_sprite;xy,_=entries[index]
            try:self.apply_room_changes(rooms.sprite_changes(self.data,m,room,index,(xy&15,xy>>4,self.sprite_id.get()),expected=entries))
            except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)

    def sprite_delete(self,event=None):
        if self.selected_sprite:
            m,room,index,entries=self.selected_sprite
            try:self.apply_room_changes(rooms.sprite_changes(self.data,m,room,index,remove=True,expected=entries))
            except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        return 'break'
