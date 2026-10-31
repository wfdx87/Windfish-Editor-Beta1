"""Copy selected room components into the current room as one history action."""
import tkinter as tk
from tkinter import ttk,messagebox
from windfish.rom import windfish_room_copy as operations


def open_copy_dialog(window,dungeon=False):
    root=window.owner if dungeon else window
    if root.document is None:return
    if dungeon:window.finish_draw()
    else:root.end_stroke()
    destination=window.room;identity=id(root.data)
    context=window.render_context(destination)[0] if dungeon else None
    win=tk.Toplevel(window);win.title('Copy From Room');win.transient(window);win.resizable(False,False)
    frame=ttk.Frame(win,padding=12);frame.pack()
    ttk.Label(frame,text=f'Copy selected contents into current room {destination:02X}?').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,10))
    ttk.Label(frame,text='Source room ID (hex)').grid(row=1,column=0,sticky='w')
    source=tk.StringVar(value=f'{destination:02X}');entry=ttk.Entry(frame,textvariable=source,width=5);entry.grid(row=1,column=1,sticky='w',padx=8)
    bank=tk.StringVar();alternate=tk.BooleanVar(value=False)
    if dungeon:
        from windfish.rendering.windfish_dungeon_render import room_bank
        bank.set(room_bank(context))
        ttk.Label(frame,text='Source bank').grid(row=2,column=0,sticky='w',pady=5)
        ttk.Combobox(frame,textvariable=bank,values=('A','B','Color'),state='readonly',width=8).grid(row=2,column=1,sticky='w',padx=8)
    else:ttk.Checkbutton(frame,text='Use source alternate layout, if available',variable=alternate).grid(row=2,column=0,columnspan=2,sticky='w',pady=5)
    flags={}
    for row,label in enumerate(('BG','Sprites','Collisions','GFX Settings','Copy Map16'),3):
        value=tk.BooleanVar(value=False);flags[label]=value
        ttk.Checkbutton(frame,text=label,variable=value,state='disabled' if dungeon and label=='Copy Map16' else 'normal').grid(row=row,column=0,columnspan=2,sticky='w')
    ttk.Label(frame,text='Checked components replace the destination contents.\nCollisions include floor/wall templates and placements.\nGFX Settings includes animation and graphics assignments.\nCopy Map16 copies both overworld page assignments.\nShared assets are reused; indoor map-context graphics stay unchanged.\nWarps, events and rewards stay unchanged.',justify='left').grid(row=8,column=0,columnspan=2,sticky='w',pady=10)
    def accept():
        try:
            if id(root.data)!=identity or window.room!=destination:raise ValueError('The ROM or destination room changed. Reopen Copy From Room.')
            src=int(source.get(),16);kwargs=dict(bg=flags['BG'].get(),sprites=flags['Sprites'].get(),collisions=flags['Collisions'].get(),gfx=flags['GFX Settings'].get(),map16=flags['Copy Map16'].get())
            if dungeon:
                from windfish.rendering.windfish_dungeon_render import room_bank
                src_context=context if room_bank(context)==bank.get() else {'A':0,'B':6,'Color':255}[bank.get()]
                kwargs.update(source_map=src_context,destination_map=context)
            else:kwargs.update(source_alternate=alternate.get(),destination_alternate=window.alternate.get())
            edits=operations.changes(root.data,src,destination,**kwargs)
            if dungeon:
                window.selected_sprite=None;window.selected_collision=None;window.tile_map_selection=None
                window.apply_room_changes(edits)
            else:
                root.end_stroke()
                for at,old,new in edits:root.history.record(at,old,new,destination,kwargs['destination_alternate']);root.data[at]=new
                root.history.commit();root.selected_sprite=None;root.collision_selected=None;root.tile_selection=None
                root.refresh_changed_rooms([(at,old,new,destination,kwargs['destination_alternate']) for at,old,new in edits])
            win.destroy()
        except (ValueError,IndexError) as exc:messagebox.showerror('Cannot copy room',str(exc),parent=win)
    buttons=ttk.Frame(frame);buttons.grid(row=9,column=0,columnspan=2,sticky='e')
    ttk.Button(buttons,text='Copy',command=accept).pack(side='left',padx=5)
    ttk.Button(buttons,text='Cancel',command=win.destroy).pack(side='left')
    win.bind('<Return>',lambda e:accept());win.bind('<Escape>',lambda e:win.destroy())
    win.grab_set();entry.focus_set();entry.selection_range(0,'end')
