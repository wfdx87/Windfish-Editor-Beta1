"""Clickable inventory-style room-layout grid with native bank/room selectors."""
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk
import windfish.rendering.windfish_dungeon_render as dungeon
from windfish.dungeon.windfish_dungeon_minimap import tile_image,record as map_record,BRUSHES

BANK_LABELS={'A':'Dungeon A','B':'Dungeon B','Color':'Color rooms'}


class LayoutGridMixin:
    def build_layout_grid(self,parent):
        self.cells=[tk.StringVar(value='00') for i in range(64)]
        self.layout_canvas=tk.Canvas(parent,width=320,height=320,background='#282840',highlightthickness=0)
        self.layout_canvas.pack(anchor='w');self.layout_canvas.bind('<Button-1>',self.select_layout_cell)
        self.cell_heading=tk.StringVar();ttk.Label(parent,textvariable=self.cell_heading).pack(anchor='w',pady=(6,2))
        selectors=ttk.Frame(parent);selectors.pack(anchor='w')
        self.cell_bank=tk.StringVar();self.cell_room=tk.StringVar()
        ttk.Label(selectors,text='Bank').grid(row=0,column=0,sticky='w')
        ttk.Label(selectors,text='Room (hex)').grid(row=0,column=1,sticky='w',padx=10)
        self.cell_bank_combo=ttk.Combobox(selectors,textvariable=self.cell_bank,state='disabled',width=16)
        self.cell_bank_combo.grid(row=1,column=0,sticky='w')
        self.cell_room_combo=ttk.Combobox(selectors,textvariable=self.cell_room,state='disabled',width=8)
        self.cell_room_combo.grid(row=1,column=1,sticky='w',padx=10)
        self.cell_room_combo.bind('<<ComboboxSelected>>',self.assign_layout_cell)
        actions=ttk.Frame(parent);actions.pack(anchor='w',pady=(8,0))
        self.remove_room_button=ttk.Button(actions,text='Remove Room',command=self.remove_layout_room,state='disabled')
        self.remove_room_button.pack(side='left')
        self.clear_rooms_button=ttk.Button(actions,text='Clear All Rooms',command=self.clear_layout_rooms,state='disabled')
        self.clear_rooms_button.pack(side='left',padx=(8,0))
    def select_layout_cell(self,event):
        if self._expected is None or not 0<=event.x<320 or not 0<=event.y<320:return
        self.show_assignment(event.y//40*8+event.x//40);self.draw_layout_grid()
    def refresh_cell_selectors(self):
        from windfish.dungeon.windfish_dungeon_metadata import layout_owner
        data=self.owner.data
        for button in (self.remove_room_button,self.clear_rooms_button):
            button.configure(state='normal' if data is not None and self._expected is not None else 'disabled')
        if data is None or self._expected is None:
            for widget in (self.cell_bank_combo,self.cell_room_combo):widget.configure(state='disabled')
            self.cell_bank.set('');self.cell_room.set('');self.layout_canvas.delete('all');return
        context=layout_owner(self.selected);bank=dungeon.room_bank(context);self.cell_bank.set(BANK_LABELS[bank])
        self.cell_bank_combo.configure(state='readonly',values=[BANK_LABELS[bank]])
        existing=set(self._expected[1]);choices=[]
        used={int(var.get(),16) for i,var in enumerate(self.cells) if i!=self._focused_cell and int(var.get(),16)!=0}
        for room in range(22 if context==255 else 256):
            if room in used:continue
            other=self._owners.get((bank,room),set())-{context}
            if room and other and room not in existing:continue
            try:
                if room:dungeon.read_room(data,context,room)
            except (ValueError,IndexError):continue
            choices.append(f'{room:02X}')
        self.cell_room_combo.configure(state='readonly',values=choices)
        self.cell_room.set(self.cells[self._focused_cell].get())
        self.cell_heading.set(f'Row {self._focused_cell//8+1}, column {self._focused_cell%8+1}')
    def assign_layout_cell(self,event=None):
        if self._expected is None or self.owner.data is None:return
        from windfish.dungeon.windfish_dungeon_metadata import layout_owner,layout_changes
        context=layout_owner(self.selected);bank=dungeon.room_bank(context)
        if self.cell_bank.get()!=BANK_LABELS[bank]:
            self.status.set('This native dungeon layout uses one bank for all cells.');self.refresh_cell_selectors();return
        try:
            room=int(self.cell_room.get(),16)
            values=[int(var.get(),16) for var in self.cells];values[self._focused_cell]=room
            layout_changes(self.owner.data,self.selected,values,self._expected)
        except (ValueError,IndexError) as exc:
            self.status.set(str(exc));self.refresh_cell_selectors();return
        self.cells[self._focused_cell].set(f'{room:02X}')
        self.status.set('Draft updated. Save applies the room layout to the ROM buffer.')
        self.show_assignment(self._focused_cell);self.draw_layout_grid()
    def remove_layout_room(self):
        if self._expected is None or self.owner.data is None:return
        self.cells[self._focused_cell].set('00')
        self.show_assignment(self._focused_cell);self.draw_layout_grid()
        note=' Color Dungeon boss room 00 remains at its native fixed cell.' if self.selected==255 and self._focused_cell==25 else ''
        self.status.set('Room removed from draft. Save applies the change.'+note)
    def clear_layout_rooms(self):
        if self._expected is None or self.owner.data is None:return
        for var in self.cells:var.set('00')
        self.show_assignment(self._focused_cell);self.draw_layout_grid()
        note=' Color Dungeon boss room 00 remains at its native fixed cell.' if self.selected==255 else ''
        self.status.set('All room assignments cleared from draft. Save applies the changes.'+note)
    def draw_layout_grid(self):
        data=self.owner.data;self.layout_canvas.delete('all')
        if data is None or self._expected is None:return
        try:tiles=map_record(data,self.selected)[1]
        except ValueError:tiles=None
        if hasattr(self,'refresh_map_preview'):tiles=self.refresh_map_preview()
        self.layout_photos={}
        for tile in BRUSHES:self.layout_photos[tile]=ImageTk.PhotoImage(tile_image(data,tile).resize((40,40),Image.Resampling.NEAREST))
        for i,var in enumerate(self.cells):
            room=int(var.get(),16);assigned=room!=0 or self.selected==255 and i==25
            tile=(tiles[i] if tiles is not None else 0xEF) if assigned else 0x7D
            x=i%8*40;y=i//8*40
            if tile in self.layout_photos:self.layout_canvas.create_image(x,y,image=self.layout_photos[tile],anchor='nw')
            if assigned:
                self.layout_canvas.create_rectangle(x+1,y+1,x+23,y+15,fill='#202028',outline='')
                self.layout_canvas.create_text(x+3,y+2,anchor='nw',text=f'{room:02X}',fill='white',font=('Consolas',8,'bold'))
            self.layout_canvas.create_rectangle(x,y,x+40,y+40,outline='#ffff55' if i==self._focused_cell else '#777777',width=3 if i==self._focused_cell else 1)
