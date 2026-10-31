"""Selection artwork shared by both map editors."""
from PIL import ImageOps


def highlight_sprite(sprite):
    rgba=sprite.convert('RGBA')
    rgb=ImageOps.invert(rgba.convert('RGB'))
    rgb.putalpha(rgba.getchannel('A'))
    return rgb


def draw_sprite_hex(canvas,x,y,sprite_id,zoom,selected=False,tags=()):
    canvas.create_rectangle(x,y,x+16*zoom-1,y+16*zoom-1,fill='#000000',outline='#ffffff',width=max(1,zoom),tags=tags)
    canvas.create_text(x+8*zoom,y+8*zoom,text=f'{sprite_id:02X}',anchor='center',fill='#ffffff',font=('Consolas',max(8,8*zoom),'bold'),tags=tags)
    if selected:canvas.create_rectangle(x,y,x+16*zoom-1,y+16*zoom-1,outline='#ffff33',width=max(1,zoom),tags=tags)


def cycle_preview_frame(sprite_id,current,direction):
    """Cycle window-local frame state without changing map display definitions."""
    from windfish.rendering.windfish_sprite_definitions import SPRITE_DEFINITIONS
    definition=SPRITE_DEFINITIONS.get(sprite_id)
    return (current+direction)%(len(definition.frames) if definition else 1)


def build_sprite_id_dialog(parent,room,x,y,choices,initial,warning=''):
    """Shared dialog shell; each editor retains its guarded ROM edit callback."""
    import tkinter as tk
    from tkinter import ttk
    dialog=tk.Toplevel(parent);dialog.title('Edit Sprite ID');dialog.transient(parent);dialog.resizable(False,False)
    body=ttk.Frame(dialog,padding=16);body.pack(fill='both',expand=True)
    ttk.Label(body,text=f'Room {room:02X}  |  Sprite at ({x}, {y})').pack(anchor='w',pady=(0,10))
    ttk.Label(body,text='Sprite ID:').pack(anchor='w')
    choice=tk.StringVar(value=initial)
    combo=ttk.Combobox(body,textvariable=choice,values=choices,state='readonly',width=43)
    combo.pack(fill='x',pady=(4,12))
    if warning:ttk.Label(body,text=warning,justify='left',foreground='#a05b18').pack(anchor='w',pady=(0,14))
    buttons=ttk.Frame(body);buttons.pack(fill='x')
    return dialog,choice,combo,buttons


def bind_sprite_id_dialog(dialog,combo,buttons,accept):
    from tkinter import ttk
    ttk.Button(buttons,text='Cancel',command=dialog.destroy).pack(side='right')
    ttk.Button(buttons,text='OK',command=accept).pack(side='right',padx=(0,8))
    dialog.bind('<Return>',lambda event:accept());dialog.bind('<Escape>',lambda event:dialog.destroy())
    dialog.protocol('WM_DELETE_WINDOW',dialog.destroy);dialog.grab_set();combo.focus_set()


class SpriteDisplayCache:
    """Bounded, per-window Tk sprite images reused during full-map panning.

    The caller provides the ROM's content revision once per synchronous redraw.
    A changed buffer or revision discards the old display images; zoom, selected
    state and placement-dependent frame belong in the key. Without a revision,
    direct callers bypass caching rather than risking stale artwork.
    """
    def __init__(self,limit=512):
        from collections import OrderedDict
        self.limit=limit;self.data=None;self.revision=None;self.entries=OrderedDict()

    def get(self,data,revision,key,create):
        if revision is None:return create()
        if data is not self.data or revision!=self.revision:
            self.entries.clear();self.data=data;self.revision=revision
        if key in self.entries:
            self.entries.move_to_end(key)
            return self.entries[key]
        result=create()
        self.entries[key]=result
        while len(self.entries)>self.limit:self.entries.popitem(last=False)
        return result
