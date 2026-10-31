"""Read-only Photo Album tab and its graphics sheet."""
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk
from windfish.rendering.windfish_pictures import PHOTOS,render_picture,extract_picture_gfx


def open_picture_viewer(owner,parent):
    if owner.data is None:return
    win=ttk.Frame(parent)
    frame=ttk.Frame(win,padding=12);frame.pack(fill='both',expand=True)
    left=ttk.Frame(frame);left.grid(row=0,column=0,sticky='nw',padx=(0,16))
    right=ttk.Frame(frame);right.grid(row=0,column=1,sticky='nw')
    selection=tk.StringVar(value=PHOTOS[0][0])
    photo_combo=ttk.Combobox(right,textvariable=selection,values=tuple(p[0] for p in PHOTOS),state='readonly')
    photo_combo.pack(fill='x',pady=(0,8))
    def selected():return next(i for i,p in enumerate(PHOTOS) if p[0]==selection.get())
    controls=ttk.Frame(right);controls.pack(anchor='w',pady=(0,8))
    ttk.Label(controls,text='Zoom').pack(side='left')
    zoom=tk.StringVar(value='3');combo=ttk.Combobox(controls,textvariable=zoom,values=('1','2','3'),state='readonly',width=3)
    combo.pack(side='left',padx=6)
    preview=ttk.Label(left);preview.pack()
    sheet=ttk.Label(right);sheet.pack(pady=8)
    status=tk.StringVar(value='Full picture background. Dialogue and cinematic fades are not shown.')
    ttk.Label(left,textvariable=status,wraplength=480).pack(anchor='w',pady=(8,0))
    def refresh(event=None):
        if owner.data is None:return
        try:
            image=render_picture(owner.data,selected());scale=int(zoom.get())
            preview.photo=ImageTk.PhotoImage(image.resize((160*scale,144*scale),Image.Resampling.NEAREST))
            preview.configure(image=preview.photo,text='')
            from windfish.rendering.windfish_pictures import _spec
            spec=_spec(owner.data,selected());raw=extract_picture_gfx(owner.data,selected())
            palat=spec['palettes'];palette=[]
            for i in range(4):
                word=int.from_bytes(owner.data[palat+i*2:palat+i*2+2],'little')
                palette.append(tuple(((word>>s)&31)*8 for s in (0,5,10)))
            atlas=Image.new('RGB',(128,128),'#555555')
            for i in range(len(raw)//16):
                for y in range(8):
                    lo,hi=raw[i*16+y*2:i*16+y*2+2]
                    for x in range(8):
                        bit=7-x;value=((lo>>bit)&1)|(((hi>>bit)&1)<<1)
                        atlas.putpixel((i%16*8+x,i//16*8+y),palette[value])
            sheet.photo=ImageTk.PhotoImage(atlas.resize((256,256),Image.Resampling.NEAREST));sheet.configure(image=sheet.photo)
            status.set('Full picture background. Dialogue and cinematic fades are not shown.')
        except (ValueError,IndexError) as exc:
            preview.configure(image='',text='Photo unavailable');status.set(str(exc))
    photo_combo.bind('<<ComboboxSelected>>',refresh)
    combo.bind('<<ComboboxSelected>>',refresh)
    win.bind('<<WindfishRomChanged>>',refresh)
    win.refresh_photo=refresh
    win.selected_photo=selected
    refresh()
    return win
