"""Read-only palette presentation shared by both Room Properties windows."""
import tkinter as tk
from tkinter import ttk


def build_palette_view(page,refresh):
    ttk.Label(page,text='ROM palette data — read only',font=('TkDefaultFont',10,'bold')).pack(anchor='w')
    ttk.Label(page,text='RGB555: 0BBBBBGGGGGRRRRR  •  2 bytes per color (little-endian)',wraplength=420).pack(anchor='w',pady=(2,5))
    container=ttk.Frame(page);container.pack(fill='both',expand=True)
    canvas=tk.Canvas(container,bg='#f0f0f0',highlightthickness=0)
    scroll=ttk.Scrollbar(container,orient='vertical',command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set);canvas.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
    canvas.bind('<Configure>',lambda event:refresh())
    canvas.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-int(event.delta/120),'units'))
    canvas.bind('<Button-4>',lambda event:canvas.yview_scroll(-1,'units'))
    canvas.bind('<Button-5>',lambda event:canvas.yview_scroll(1,'units'))
    return canvas


def draw_palette_view(canvas,data,bg_offset,obj_offsets,bg_heading,obj_heading):
    canvas.delete('all');font=('Consolas',9);y=8
    for kind,heading in (('BG',bg_heading),('OBJ',obj_heading)):
        canvas.create_text(8,y,anchor='nw',font=('TkDefaultFont',10,'bold'),text=heading);y+=23
        for row in range(8):
            canvas.create_text(5,y+12,text=str(row),anchor='w',font=font)
            for col,x in enumerate((55,147,239,331)):
                off=bg_offset+(row*4+col)*2 if kind=='BG' else obj_offsets[row*4+col]
                value=int.from_bytes(data[off:off+2],'little')
                rgb=tuple(((value>>shift)&31)<<3 for shift in (0,5,10))
                canvas.create_rectangle(x,y,x+19,y+19,fill='#%02X%02X%02X'%rgb,outline='#666',tags=())
                canvas.create_text(x+24,y+2,anchor='nw',font=font,text=f'{value:04X}')
                canvas.create_text(x,y+23,anchor='nw',font=('Consolas',8),text=f'{off:05X}')
            y+=49
        y+=15
    canvas.create_text(8,y,anchor='nw',font=('TkDefaultFont',8),text='Each swatch: RGB555 hex (top), ROM file offset (bottom).');y+=24
    canvas.create_text(8,y,anchor='nw',font=('TkDefaultFont',8),text='OBJ color 0 is transparent for sprites. Runtime palettes may differ.')
    canvas.configure(scrollregion=(0,0,430,y+26))
