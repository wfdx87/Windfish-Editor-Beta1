"""Read-only room graphics sheet in the tile map editor's signed ID order."""
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk
from windfish.rendering.windfish_overworld_render import graphics,palette,SPECIAL_MAP


def room_tile_sheet(data,room,special=False,bank=0,palette_index=2):
    """256 raw BG pieces, no metatile flips; selected room BG palette for display.

    Match the custom definition editor's GBC signed IDs: 00–7F use $9000,
    80–FF use $8800. Include shared graphics plus room/ExGFX and the same
    fixed animation frame as the main renderer. This never alters ROM data.
    """
    gfx=graphics(data,room,special)[2]
    raw=bytes(data[0xB0800:0xB1000])+bytes(gfx[0x100:])
    if bank not in (0,1):raise ValueError('VRAM bank must be 0 or 1.')
    if bank==1:
        from windfish.rom.windfish_vram_bank1 import background_data
        raw=background_data(data,room)
    if palette_index not in range(8):raise ValueError('BG palette must be 0–7.')
    start=palette_index*4
    colors=palette(data,room)[2][start:start+4]
    sheet=Image.new('RGB',(128,128));pixels=sheet.load()
    for tile in range(256):
        at=(tile^128)*16
        for y in range(8):
            lo,hi=raw[at+y*2:at+y*2+2]
            for x in range(8):
                bit=7-x;value=((lo>>bit)&1)|(((hi>>bit)&1)<<1)
                pixels[tile%16*8+x,tile//16*8+y]=colors[value]
    return sheet


def open_tile_viewer(owner):
    existing=owner.catalog_windows.get('8x8')
    if existing is not None and existing.winfo_exists():
        existing.deiconify();existing.lift();return
    win=tk.Toplevel(owner);win.title('8x8 Tile Viewer');win.transient(owner);win.resizable(False,False)
    owner.catalog_windows['8x8']=win
    bank=tk.IntVar(value=0)
    palette_index=tk.IntVar(value=2)
    controls=ttk.Frame(win,padding=4);controls.pack(fill='x')
    ttk.Label(controls,text='VRAM bank').pack(side='left')
    bank_combo=ttk.Combobox(controls,textvariable=bank,values=(0,1),state='readonly',width=3)
    bank_combo.pack(side='left',padx=6)
    ttk.Label(controls,text='BG palette').pack(side='left')
    palette_combo=ttk.Combobox(controls,textvariable=palette_index,values=tuple(range(8)),state='readonly',width=3)
    palette_combo.pack(side='left',padx=6)
    canvas=tk.Canvas(win,width=256,height=256,highlightthickness=0)
    canvas.pack()
    status=tk.StringVar();ttk.Label(win,textvariable=status,anchor='w',padding=(4,4)).pack(fill='x')
    def close():
        owner.catalog_windows.pop('8x8',None);win.destroy()
    win.protocol('WM_DELETE_WINDOW',close)
    def refresh(event=None):
        if owner.data is None:
            canvas.delete('all');status.set('Open a ROM first.');return
        try:
            special=owner.alternate.get() and owner.room in SPECIAL_MAP
            sheet=room_tile_sheet(owner.data,owner.room,special,bank.get(),palette_index.get())
            canvas.photo=ImageTk.PhotoImage(sheet.resize((256,256),Image.Resampling.NEAREST))
            canvas.delete('all');canvas.create_image(0,0,anchor='nw',image=canvas.photo)
            status.set(f'Room {owner.room:02X} · Bank {bank.get()} · BG palette {palette_index.get()} · Read-only')
        except (ValueError,IndexError) as exc:
            canvas.delete('all');status.set(str(exc))
    def hover(event):
        if owner.data is None or not 0<=event.x<256 or not 0<=event.y<256:return
        tile=event.y//16*16+event.x//16
        address=0x9000+(tile if tile<128 else tile-256)*16
        status.set(f'Tile {tile:02X} · Bank {bank.get()} · VRAM ${address:04X} · Read-only')
    bank_combo.bind('<<ComboboxSelected>>',refresh)
    palette_combo.bind('<<ComboboxSelected>>',refresh)
    canvas.bind('<Button-1>',lambda event:canvas.focus_set())
    canvas.bind('<Motion>',hover);canvas.bind('<Leave>',lambda event:status.set(f'Room {owner.room:02X} · Bank {bank.get()} · BG palette {palette_index.get()} · Read-only'))
    win.bind('<<WindfishRoomChanged>>',refresh);win.bind('<<WindfishRomChanged>>',refresh)
    refresh()
    canvas.focus_set()
