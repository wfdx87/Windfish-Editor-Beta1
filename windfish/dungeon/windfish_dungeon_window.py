"""Separate Dungeon Editor window with room navigation and editing."""
import hashlib
import tkinter as tk
from tkinter import ttk,messagebox
from PIL import Image,ImageDraw,ImageTk
import windfish.rendering.windfish_dungeon_render as dungeon
from windfish.dungeon.windfish_dungeon_draw import DungeonDrawMixin
from windfish.dungeon.windfish_dungeon_metadata import DungeonMetadataMixin
from windfish.dungeon.windfish_dungeon_collisions import DungeonCollisionMixin
import windfish.dungeon.windfish_dungeon_visuals as visuals
from windfish.dungeon.windfish_dungeon_sprites import DungeonSpriteMixin


from windfish.app.windfish_gui_shared import add_overlay_menu, bind_overlay_shortcuts


class DungeonWindow(DungeonSpriteMixin,DungeonMetadataMixin,DungeonCollisionMixin,DungeonDrawMixin,tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner)
        self.sprite_mode=tk.BooleanVar(value=False);self.show_sprites=tk.BooleanVar(value=True);self.show_sprite_ids=tk.BooleanVar(value=False)
        self.sprite_brush=None
        self.sprite_id=tk.IntVar(value=0);self.sprite_selector=None;self.selected_sprite=None;self._sprite_drag=None;self._sprite_images={}
        self.graphics_window=None
        self.names_window=None;self.layout_window=None
        self.properties_window=None;self.show_properties=tk.BooleanVar(value=False)
        self.direct_draw=tk.BooleanVar(value=False);self.draw_tile=tk.IntVar(value=0)
        self.draw_size=(1,1);self.draw_values=None;self.tile_map_selection=None;self._tile_anchor=None;self._tile_target=None
        self._collision_drag=None;self.collision_direction=tk.StringVar(value='Single');self.collision_length=tk.IntVar(value=1);self.collision_combined=tk.BooleanVar(value=True)
        self.add_collisions=tk.BooleanVar(value=False)
        self.collision_mode=tk.BooleanVar(value=False);self.view_collisions=tk.BooleanVar(value=False)
        self.collision_selector=None;self.collision_brush=None;self.selected_collision=None
        self.tile_selector=None;self._draw_drag=False;self._draw_last=None
        self.owner=owner;self.data=None;self._digest=None
        self.title('Windfish Editor — Dungeon Editor')
        self.geometry('1100x880');self.minsize(920,800)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self._render_cache=None;self._atlas_revision=None;self._atlas_parts={}
        self.map_id=0;self.room=1;self._images={};self._sideviews=frozenset();self._atlas=None;self._atlas_key=None;self._panning=False
        self.zoom=tk.IntVar(value=3);self.entire=tk.BooleanVar(value=False)
        self.all_rooms=tk.BooleanVar(value=False)
        self.bank_choice=tk.StringVar(value='Dungeon A');self._navigation='bank'
        self.room_borders=tk.BooleanVar(value=False);self.collapsed=tk.BooleanVar(value=False)
        self.map_choice=tk.StringVar()
        self.room_choice=tk.StringVar()
        menu=tk.Menu(self);file=tk.Menu(menu,tearoff=False)
        file.add_command(label='Save ROM',command=self.save_rom)
        file.add_separator()
        file.add_command(label='Close Dungeon Editor',command=self.close)
        menu.add_cascade(label='File',menu=file)
        view=tk.Menu(menu,tearoff=False)
        view.add_checkbutton(label='View Full Dungeon',variable=self.entire,command=self.toggle_full_dungeon)
        view.add_checkbutton(label='View All Room IDs',variable=self.all_rooms,command=self.toggle_all_room_ids)
        view.add_separator()
        overlay_variables = (self.room_borders, self.show_sprites, self.show_sprite_ids, self.view_collisions)
        add_overlay_menu(view, overlay_variables, self.draw, borders_label='View Room Borders')
        view.add_separator()
        for n in range(1,5):view.add_radiobutton(label=f'Zoom {n}×',value=n,variable=self.zoom,command=self.change_view)
        view.add_separator()
        view.add_command(label='Room GFX Settings…',command=self.open_graphics_settings)
        view.add_checkbutton(label='Room Properties…',variable=self.show_properties,command=self.toggle_properties)
        edit=tk.Menu(menu,tearoff=False)
        edit.add_command(label='Undo',accelerator='Ctrl+Z',command=self.undo);edit.add_command(label='Redo',accelerator='Ctrl+Y',command=self.redo)
        edit.add_separator();edit.add_checkbutton(label='Edit Room Tiles',variable=self.direct_draw,command=self.toggle_direct_draw)
        edit.add_checkbutton(label='Edit Room Sprites',variable=self.sprite_mode,command=self.toggle_sprite_mode)
        edit.add_checkbutton(label='Edit Room Collisions',variable=self.collision_mode,command=self.toggle_collision_mode)
        from windfish.app.windfish_room_actions import install as install_room_actions
        install_room_actions(self,edit,dungeon=True)
        menu.add_cascade(label='Edit',menu=edit);menu.add_cascade(label='View',menu=view)
        editors=tk.Menu(menu,tearoff=False)
        editors.add_command(label='Tile Selector…',command=self.open_tile_selector)
        editors.add_command(label='Collision Selector…',command=self.open_collision_selector)
        editors.add_command(label='Sprite Selector…',command=self.open_sprite_selector)
        editors.add_separator()
        editors.add_command(label='Edit Dungeon Names…',command=self.open_dungeon_names)
        editors.add_command(label='Dungeon Map Table Editor…',command=self.open_dungeon_layout)
        menu.add_cascade(label='Editors',menu=editors)
        from windfish.app.windfish_collision_settings import install_menu
        install_menu(self, menu)
        self.configure(menu=menu)
        body=ttk.Frame(self);body.pack(fill='both',expand=True)
        sidebar=ttk.Frame(body);sidebar.pack(side='right',fill='y',padx=16,pady=16)
        side_canvas=tk.Canvas(sidebar,width=270,highlightthickness=0)
        side_scroll=ttk.Scrollbar(sidebar,orient='vertical',command=side_canvas.yview)
        side_canvas.configure(yscrollcommand=side_scroll.set)
        side_scroll.pack(side='right',fill='y');side_canvas.pack(side='left',fill='y',expand=True)
        side=ttk.Frame(side_canvas)
        side_canvas.create_window(0,0,window=side,anchor='nw',width=270)
        side.bind('<Configure>',lambda event:side_canvas.configure(scrollregion=side_canvas.bbox('all')))
        selector_heading=ttk.Frame(side);selector_heading.pack(fill='x')
        ttk.Label(selector_heading,text='Room bank',font=('TkDefaultFont',11,'bold')).pack(side='left')
        ttk.Checkbutton(selector_heading,text='Show Alternate Rooms',variable=self.collapsed,command=self.load_dungeon).pack(side='right')
        self.bank_combo=ttk.Combobox(side,state='readonly',textvariable=self.bank_choice,
            values=['Dungeon A','Dungeon B','Color rooms'])
        self.bank_combo.pack(fill='x',pady=6);self.bank_combo.bind('<<ComboboxSelected>>',self.change_bank)
        self.bank_grid=tk.Canvas(side,width=256,height=256,background='#202028',highlightthickness=0)
        self.bank_grid.pack(pady=4);self.bank_grid.bind('<Button-1>',self.click_bank)
        self.map_combo=ttk.Combobox(side,state='readonly',width=24,textvariable=self.map_choice,
            values=[self.map_label(m,name) for m,name in dungeon.DUNGEONS])
        self.map_combo.pack(fill='x',pady=6);self.map_combo.bind('<<ComboboxSelected>>',self.change_dungeon)
        ttk.Label(side,text='Room ID').pack(anchor='w')
        self.room_combo=ttk.Combobox(side,state='readonly',width=8,textvariable=self.room_choice)
        self.room_combo.pack(fill='x',pady=6);self.room_combo.bind('<<ComboboxSelected>>',self.change_room)
        self.minimap=tk.Canvas(side,width=256,height=192,background='#202028',highlightthickness=0)
        self.minimap.pack(pady=8);self.minimap.bind('<Button-1>',self.click_minimap)
        ttk.Button(side,text='Recalculate Collisions',command=self.calculate_collisions).pack(fill='x',pady=8)
        holder=ttk.Frame(body);holder.pack(side='left',fill='both',expand=True)
        self.canvas=tk.Canvas(holder,background='#202028',highlightthickness=0)
        xs=ttk.Scrollbar(holder,orient='horizontal',command=self.scroll_x)
        ys=ttk.Scrollbar(holder,orient='vertical',command=self.scroll_y)
        self.canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
        self.canvas.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew')
        holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
        self.canvas.bind('<Button-1>',self.click_room)
        self.canvas.bind('<Double-Button-1>',self.enter_room)
        self.canvas.bind('<B1-Motion>',lambda event:self.sprite_motion(event) if self.sprite_mode.get() else self.collision_motion(event) if self.collision_mode.get() else self.tile_left_motion(event) if self.direct_draw.get() else None)
        self.canvas.bind('<ButtonRelease-1>',lambda event:self.sprite_release(event) if self.sprite_mode.get() else self.collision_release(event) if self.collision_mode.get() else self.tile_left_release(event) if self.direct_draw.get() else None)
        self.canvas.bind('<Button-3>',lambda event:self.sprite_place(event) if self.sprite_mode.get() else self.collision_paint_press(event) if self.collision_mode.get() else self.paint_press(event) if self.direct_draw.get() else None)
        self.canvas.bind('<B3-Motion>',lambda event:self.collision_paint_drag(event) if self.collision_mode.get() else self.paint_motion(event))
        self.canvas.bind('<ButtonRelease-3>',self.finish_draw)
        self.canvas.bind('<Motion>',self.collision_hover)
        self.canvas.bind('<Leave>',lambda event:self.canvas.delete('tool-ghost'))
        self.canvas.bind('<Escape>',self.collision_escape)
        self.canvas.bind('<Delete>',lambda event:self.sprite_delete(event) if self.sprite_mode.get() else self.delete_collision(event))
        self.canvas.bind('<Configure>',lambda event:self.change_view())
        self.canvas.bind('<ButtonPress-2>',self.pan_start)
        self.canvas.bind('<B2-Motion>',self.pan_move)
        self.canvas.bind('<ButtonRelease-2>',self.pan_end)
        for key,dx,dy in (('Left',-1,0),('Right',1,0),('Up',0,-1),('Down',0,1)):
            self.bind('<'+key+'>',lambda event,x=dx,y=dy:self.navigate(event,x,y))
        for key,delta in (('plus',1),('equal',1),('KP_Add',1),('minus',-1),('KP_Subtract',-1)):
            self.bind('<'+key+'>',lambda event,d=delta:self.zoom_key(event,d))
        bind_overlay_shortcuts(self, overlay_variables, self.draw)
        self.bind('<FocusIn>',self.focus_refresh)
        self.bind_history_shortcuts(self)
        self.map_choice.set(self.map_label(*dungeon.DUNGEONS[0]))
        self.refresh_document(force=True)

    @staticmethod
    def map_label(map_id,name):return f'{map_id:02X} — {name}'

    def bind_history_shortcuts(self,widget):
        for key,operation in (('<Control-z>',self.undo),('<Control-y>',self.redo),('<Control-Shift-Z>',self.redo)):
            def invoke(event,action=operation):
                action();return 'break'
            widget.bind(key,invoke)

    def undo(self):
        self.finish_draw();self.owner.undo();self.refresh_document()

    def redo(self):
        self.finish_draw();self.owner.redo();self.refresh_document()

    def save_rom(self):
        self.finish_draw();self.owner.save_rom();self.refresh_document()

    def apply_room_changes(self,changes):
        root=self.owner
        if self.data is None or root.document is None or root.data is not self.data:
            raise ValueError('The active ROM changed. Refresh Room Properties.')
        if any(self.data[at]!=old for at,old,new in changes):raise ValueError('Room data changed before Apply.')
        if not changes:return
        root.end_stroke()
        for at,old,new in changes:
            root.history.record(at,old,new,root.room,False);self.data[at]=new
        root.history.commit();root.show_room();self.refresh_document()

    def open_graphics_settings(self):
        if self.graphics_window is None:
            from windfish.dungeon.windfish_dungeon_graphics import DungeonGraphics
            self.graphics_window=DungeonGraphics(self)
        else:self.graphics_window.deiconify();self.graphics_window.lift();self.graphics_window.refresh()

    def toggle_properties(self):
        if self.show_properties.get():
            if self.properties_window is None:
                from windfish.dungeon.windfish_dungeon_properties import DungeonProperties
                self.properties_window=DungeonProperties(self)
            else:self.properties_window.deiconify();self.properties_window.lift()
        elif self.properties_window is not None:self.properties_window.close()

    def refresh_properties(self):
        if self.properties_window is not None:self.properties_window.refresh()

    def close(self):
        self.finish_draw()
        if self.graphics_window is not None:self.graphics_window.close()
        if self.sprite_selector is not None:self.sprite_selector.close()
        if self.tile_selector is not None:self.tile_selector.close()
        if self.collision_selector is not None:self.collision_selector.close()
        if self.properties_window is not None:self.properties_window.close()
        for window in (self.names_window,self.layout_window):
            if window is not None:window.close()
        self.owner.dungeon_window=None;self.destroy()

    def focus_refresh(self,event):
        if event.widget==self:self.refresh_document()

    def sync_if_new_document(self):
        if self.data is not self.owner.data:self.refresh_document(force=True)

    def refresh_document(self,force=False):
        data=self.owner.data
        digest=hashlib.sha256(data).digest() if data is not None else None
        if not force and data is self.data and digest==self._digest:return
        document_changed=data is not self.data
        self.selected_sprite=None;self._sprite_drag=None;self._sprite_images.clear()
        self.finish_draw();self.selected_collision=None;self._collision_drag=None;self._tile_anchor=None
        if data is not self.data:
            self.sprite_mode.set(False);self.sprite_brush=None
            self.direct_draw.set(False);self.collision_mode.set(False);self.collision_brush=None;self.canvas.configure(cursor='')
        if data is None or not visuals.enabled(data):
            self.direct_draw.set(False);self.canvas.configure(cursor='')
        self.data=data;self._digest=digest
        if document_changed:
            self._images.clear();self._atlas=None;self._atlas_key=None;self._render_cache=None;self._atlas_parts={};self._atlas_revision=None
        self.refresh_metadata_windows()
        document=self.owner.document
        name=' — '+document.path.name if document is not None else ''
        self.title('Windfish Editor — Dungeon Editor'+name)
        if data is None:
            self.canvas.delete('all');self.minimap.delete('all');self.minimap.pack_forget();self.bank_grid.delete('all')
            self.refresh_properties()
            if self.graphics_window is not None:self.graphics_window.refresh()
            if self.tile_selector is not None:self.tile_selector.refresh()
            return
        self._names=dungeon.dungeon_names(data)
        self.map_combo.configure(values=[self.map_label(m,self._names[m]) for m,_ in dungeon.DUNGEONS])
        self.map_choice.set(self.map_label(self.map_id,self._names[self.map_id]))
        self._contexts,self._context_sides=dungeon.room_contexts(data)
        self.load_dungeon(center=document_changed)

    def change_dungeon(self,event=None):
        self.map_id=int(self.map_choice.get().split()[0],16)
        self.bank_choice.set('Color rooms' if self.map_id==255 else 'Dungeon B' if self.map_id>=6 else 'Dungeon A')
        if self.map_id!=6:self.collapsed.set(False)
        self.room=-1;self.load_dungeon()

    def change_bank(self,event=None):
        group=self.bank_choice.get()
        choices=[(m,n) for m,n in dungeon.DUNGEONS if
            ('Color rooms' if m==255 else 'Dungeon B' if m>=6 else 'Dungeon A')==group]
        if self.map_id not in [m for m,n in choices]:
            self.map_choice.set(self.map_label(choices[0][0],self._names[choices[0][0]]));self.change_dungeon()
        self._navigation='bank'

    def click_bank(self,event):
        if self.data is None:return
        x=event.x//16;y=event.y//16
        if 0<=x<16 and 0<=y<16 and y*16+x in self._rooms:
            self._navigation='bank';self.select_room(y*16+x)

    def select_room(self,room,center=True):
        self.selected_sprite=None;self._sprite_drag=None
        self.selected_collision=None;self._collision_drag=None;self._tile_anchor=None
        self.room=room
        candidates=self._contexts.get((dungeon.room_bank(self.map_id),room),())
        layouts=[m for m in candidates if m in dict(dungeon.DUNGEONS)]
        if layouts and self.map_id not in layouts:
            self.map_id=layouts[0];self.collapsed.set(False)
            self.map_choice.set(self.map_label(self.map_id,self._names[self.map_id]))
            self.load_dungeon(center=center)
        elif center:self.change_view()
        else:self.draw()
        self.room_choice.set(f'{room:02X}');self.canvas.focus_set()

    def map_view(self):return self.entire.get() or self.all_rooms.get()

    def render_context(self,room):
        candidates=self._contexts.get((dungeon.room_bank(self.map_id),room),())
        # Viewing mode must not change a room's palette/graphics context.
        # Keep the selected level for its actual layout members; resolve houses,
        # caves and other non-members from incoming warp evidence instead.
        member = room in getattr(self, '_dungeon_layout', ())
        m = self.map_id if member else (candidates[0] if candidates else self.map_id)
        return m,(m,room) in self._context_sides


    def zoom_key(self,event,delta):
        if isinstance(event.widget,(ttk.Entry,tk.Entry)):return
        self.zoom.set(max(1,min(4,self.zoom.get()+delta)));self.change_view();return 'break'

    def load_dungeon(self,center=True):
        if self.data is None:return
        try:
            self._dungeon_layout=dungeon.map_layout(self.data,self.map_id,self.collapsed.get())
            self._cols=16 if self.all_rooms.get() and self.map_id!=255 else 8
            self._rows=self._cols
            ids=tuple(range(22 if self.map_id==255 else 256))
            self._layout=(ids+(None,)*(self._cols*self._rows-len(ids))) if self.all_rooms.get() else self._dungeon_layout
            if getattr(self,'_structure_digest',None)!=self._digest:
                self._templates=dungeon.templates(self.data);self._doors=dungeon.doors(self.data);self._structure_digest=self._digest
            self._rooms=list(range(22 if self.map_id==255 else 256))
            if not self._rooms:raise ValueError('This dungeon layout contains no rooms.')
            if self.room not in self._rooms:self.room=next((r for r in self._dungeon_layout if r is not None),self._rooms[0])
            self.room_combo.configure(values=[f'{r:02X}' for r in self._rooms]);self.room_choice.set(f'{self.room:02X}')
            if center:self.change_view()
            else:self.draw()
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', f'Cannot load dungeon: {exc}', parent=self);self.canvas.delete('all')

    def change_room(self,event=None):
        try:room=int(self.room_choice.get(),16)
        except ValueError:return
        self.select_room(room)

    def room_image(self,room):
        context,sideview=self.render_context(room)
        key=(context,room,0,sideview)
        if self._render_cache is None:
            from windfish.rendering.windfish_render_cache import DungeonRenderCache
            self._render_cache=DungeonRenderCache()
        result=self._render_cache.get(self.data,self._digest,context,room,sideview,self._templates,self._doors)
        if (dungeon.room_bank(self.map_id),room) not in self._contexts:
            return result[0],result[1],result[2]+('No known room context: using selected dungeon fallback.',)
        return result

    def draw_minimap(self):
        self.bank_grid.delete('all');self.minimap.delete('all')
        for room in self._rooms:
            x=room%16*16;y=room//16*16
            fill='#526076' if room in self._dungeon_layout else '#343b47'
            self.bank_grid.create_rectangle(x,y,x+16,y+16,fill='#9a7540' if room==self.room else fill,outline='#202028')
            self.bank_grid.create_text(x+8,y+8,text=f'{room:02X}',fill='white',font=('TkDefaultFont',7))
        if self.room not in self._dungeon_layout:
            self.minimap.pack_forget()
            return
        self.minimap.pack(pady=8)
        for i,room in enumerate(self._dungeon_layout):
            if room is None:continue
            x=i%8*32;y=i//8*24
            self.minimap.create_rectangle(x,y,x+32,y+24,fill='#9a7540' if room==self.room else '#526076',outline='#202028')
            self.minimap.create_text(x+16,y+12,text=f'{room:02X}',fill='white',font=('TkDefaultFont',8))

    def preview(self,room):
        try:return self.room_image(room)
        except (ValueError,IndexError) as exc:
            image=Image.new('RGB',(160,128),'#352830');draw=ImageDraw.Draw(image)
            draw.text((8,8),f'Room {room:02X}\nPreview unavailable',fill='white')
            try:record=dungeon.read_room(self.data,self.map_id,room)
            except (ValueError,IndexError):record=None
            return image,record,(str(exc),)

    def draw(self):
        if self.data is None or not hasattr(self,'_layout'):return
        self.refresh_properties()
        if self.graphics_window is not None:self.graphics_window.refresh()
        self.canvas.delete('all');self.draw_minimap()
        if self.tile_selector is not None:self.tile_selector.refresh()
        if self.collision_selector is not None:self.collision_selector.refresh()
        im=self.preview(self.room)[0] if not self.map_view() else None
        zoom=self.zoom.get();self._origin=(16,16)
        if self.map_view():
            world_width,world_height=self._cols*160,self._rows*128
            self.canvas.configure(scrollregion=(0,0,world_width*zoom+32,world_height*zoom+32))
            # Crop before scaling, so a 16x16 room bank does not create a giant
            # zoomed bitmap just to display a small viewport while panning.
            vx=int(self.canvas.canvasx(0));vy=int(self.canvas.canvasy(0))
            left=max(0,(vx-16)//zoom);top=max(0,(vy-16)//zoom)
            right=min(world_width,max(left+1,(vx+self.canvas.winfo_width()-16+zoom-1)//zoom))
            bottom=min(world_height,max(top+1,(vy+self.canvas.winfo_height()-16+zoom-1)//zoom))
            if right>left and bottom>top:
                from windfish.rendering.windfish_viewport import compose
                def fetch(index):
                    room=self._layout[index]
                    if room is None:return None
                    part=self.preview(room)[0]
                    if self.room_borders.get():
                        part=part.copy();ImageDraw.Draw(part).rectangle((0,0,159,127),outline='white')
                    return part
                image=compose(self._cols,self._rows,(left,top,right,bottom),fetch).resize(((right-left)*zoom,(bottom-top)*zoom),Image.Resampling.NEAREST)
                self.photo=ImageTk.PhotoImage(image)
                self.canvas.create_image(16+left*zoom,16+top*zoom,image=self.photo,anchor='nw')
            index=next((i for i,r in enumerate(self._layout) if r==self.room),None)
            if index is not None and self.room_borders.get():
                x=16+index%self._cols*160*zoom;y=16+index//self._cols*128*zoom
                self.canvas.create_rectangle(x+1,y+1,x+160*zoom-1,y+128*zoom-1,outline='white',width=2)
        else:
            image=im.resize((160*zoom,128*zoom),Image.Resampling.NEAREST)
            if self.room_borders.get():ImageDraw.Draw(image).rectangle((0,0,image.width-1,image.height-1),outline='white',width=max(1,zoom))
            self.photo=ImageTk.PhotoImage(image);self.canvas.create_image(16,16,image=self.photo,anchor='nw')
            self.canvas.configure(scrollregion=(0,0,image.width+32,image.height+32))
            self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)
        self.draw_sprite_overlay();self.draw_collision_overlay();self.draw_tile_selection()
        if self.sprite_selector is not None:self.sprite_selector.refresh()

    def center_selected_room(self):
        if self.data is None or not hasattr(self,'_layout') or not self.map_view():return
        index=next((i for i,r in enumerate(self._layout) if r==self.room),None)
        if index is None:return
        z=self.zoom.get();world_w=self._cols*160*z+32;world_h=self._rows*128*z+32
        self.canvas.configure(scrollregion=(0,0,world_w,world_h))
        width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height())
        cx=16+(index%self._cols+0.5)*160*z
        cy=16+(index//self._cols+0.5)*128*z
        left=max(0,min(cx-width/2,max(0,world_w-width)))
        top=max(0,min(cy-height/2,max(0,world_h-height)))
        self.canvas.xview_moveto(left/world_w);self.canvas.yview_moveto(top/world_h)

    def toggle_full_dungeon(self):
        if self.entire.get():self.all_rooms.set(False)
        self.load_dungeon()

    def toggle_all_room_ids(self):
        self._navigation='bank' if self.all_rooms.get() else 'layout'
        if self.all_rooms.get():self.entire.set(False)
        self.load_dungeon()

    def change_view(self):
        self.finish_draw();self._panning=False;self.center_selected_room();self.draw()

    def scroll_x(self,*args):self.canvas.xview(*args);self.draw()
    def scroll_y(self,*args):self.canvas.yview(*args);self.draw()

    def pan_start(self,event):
        if not self.map_view():return
        self._panning=True;self.canvas.scan_mark(event.x,event.y);return 'break'

    def pan_move(self,event):
        if not self.map_view() or not self._panning:return
        self.canvas.scan_dragto(event.x,event.y,gain=1);self.draw();return 'break'

    def pan_end(self,event):
        self._panning=False

    def click_minimap(self,event):
        if self.data is None or not hasattr(self,'_layout'):return
        x=event.x//32;y=event.y//24
        if 0<=x<8 and 0<=y<8 and self._dungeon_layout[y*8+x] is not None:
            self._navigation='layout';self.select_room(self._dungeon_layout[y*8+x])

    def click_room(self,event):
        if self.sprite_mode.get():return self.sprite_click(event)
        if self.collision_mode.get():return self.collision_click(event)
        if self.direct_draw.get():return self.tile_left_press(event)
        if not self.map_view() or self.data is None or not hasattr(self,'_layout'):return
        px=int(self.canvas.canvasx(event.x))-16;py=int(self.canvas.canvasy(event.y))-16
        if px<0 or py<0:return
        x=px//(160*self.zoom.get());y=py//(128*self.zoom.get())
        if 0<=x<self._cols and 0<=y<self._rows and self._layout[y*self._cols+x] is not None:
            self._navigation='bank' if self.all_rooms.get() else 'layout';self.select_room(self._layout[y*self._cols+x],center=False)

    def enter_room(self,event):
        if self.sprite_mode.get():return self.sprite_double_click(event)
        if self.sprite_mode.get() or self.direct_draw.get() or self.collision_mode.get():return 'break'
        if self.map_view():
            self.click_room(event);self.entire.set(False);self.all_rooms.set(False);self.load_dungeon()

    def navigate(self,event,dx,dy):
        if isinstance(event.widget,(ttk.Combobox,ttk.Entry,tk.Entry)) or self.data is None:return
        layout=tuple(self._rooms) if self._navigation=='bank' else self._dungeon_layout
        cols=16 if self._navigation=='bank' else 8
        index=next((i for i,r in enumerate(layout) if r==self.room),None)
        if index is None:return 'break'
        x=index%cols+dx;y=index//cols+dy
        if 0<=x<cols and 0<=y and y*cols+x<len(layout) and layout[y*cols+x] is not None:
            self.select_room(layout[y*cols+x])
            if self.map_view():self.center_selected_room();self.draw()
        return 'break'
