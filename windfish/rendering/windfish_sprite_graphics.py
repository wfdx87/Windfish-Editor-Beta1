"""Windfish sprite graphics bank viewer (read-only), LADX DX Rev 2.

Shows 64 raw 8x8 2bpp tiles selected by LALE's overworld sprite bank logic.
These are raw graphics tiles, before sprite assembly.
Usage: python windfish_sprite_graphics.py path/to/rom.gbc --room 0x00
"""
from windfish.compatibility import api as profile

from dataclasses import dataclass
import argparse
from pathlib import Path
from PIL import Image, ImageTk

COLORS = [(242,248,222),(155,192,143),(78,133,102),(28,57,59)]

@dataclass(frozen=True)
class RoomSpriteGraphics:
    bank_id: int
    selectors: tuple[int, ...]
    offsets: tuple[int | None, ...]
    graphics: bytes


def graphics_source_offset(data, selector):
    """Decode one room spritesheet selector using the ROM bank overrides."""
    if selector in (0, 0xFF):
        return None
    block = selector & 0x3F
    bank = ((((selector & 0x0F) << 4) | (selector >> 4)) >> 2) & 3
    override = data[profile.sprite_bank_table(data,0x2E66) + bank]
    if override:
        bank = override | 0x20
    offset = bank * 0x4000 + block * 0x100
    if offset + 0x100 > len(data):
        raise ValueError(f'Sprite graphics outside ROM at {offset:X}')
    return offset


def load_room_sprite_graphics(data, room):
    """Read this room's current selectors and graphics, including ROM edits.

    Never resolve appearance from sprite ID alone: different rooms may load
    different graphics into the same VRAM slot (for example Crow in 00/46).
    """
    if not 0 <= room <= 255:
        raise ValueError('Room must be 00-FF')
    if len(data) < profile.bank20_table(data,0x83700):
        raise ValueError('ROM too small')
    bank_id = data[profile.bank20_table(data,0x830DB) + room]
    start = profile.bank20_table(data,0x833FB) + bank_id * 4
    selectors = tuple(0 if v == 0xFF else v for v in data[start:start+4])
    if len(selectors) != 4:
        raise ValueError('Missing sprite bank information')
    offsets = tuple(graphics_source_offset(data, value) for value in selectors)
    graphics = b''.join(bytes(0x100) if offset is None else
                        bytes(data[offset:offset+0x100]) for offset in offsets)
    return RoomSpriteGraphics(bank_id, selectors, offsets, graphics)


def sprite_bank(data, room):
    """Compatibility view for the GUI and renderers outside the 00–1F pilot."""
    loaded = load_room_sprite_graphics(data, room)
    return loaded.bank_id, list(loaded.selectors), list(loaded.offsets), loaded.graphics


def render_sheet(data, room, scale=4):
    bank_id,info,sources,graphics=sprite_bank(data,room)
    image=Image.new('RGB',(128,32)); px=image.load()
    for tile in range(64):
        at=tile*16
        for y in range(8):
            lo,hi=graphics[at+y*2:at+y*2+2]
            for x in range(8):
                bit=7-x
                px[(tile%16)*8+x,(tile//16)*8+y]=COLORS[((lo>>bit)&1)|(((hi>>bit)&1)<<1)]
    return image.resize((128*scale,32*scale),Image.Resampling.NEAREST),bank_id,info,sources

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rom',type=Path)
    ap.add_argument('--room',default='0x00',type=lambda s:int(s,0))
    ap.add_argument('--output',type=Path,help='Export PNG without opening a window')
    args=ap.parse_args()
    data=args.rom.read_bytes()
    img,bank,info,sources=render_sheet(data,args.room)
    if args.output:
        img.save(args.output)
        print(f'Room {args.room:02X}: sprite bank {bank:02X}, selectors {info}, offsets {sources}; saved {args.output}')
        return
    import tkinter as tk
    from tkinter import ttk, messagebox
    root=tk.Tk(); root.title('Windfish — Sprite Graphics Bank Viewer (read-only)')
    frame=ttk.Frame(root,padding=12);frame.pack()
    ttk.Label(frame,text='Overworld room (hex):').pack(anchor='w')
    room=tk.StringVar(value=f'{args.room:02X}')
    field=ttk.Entry(frame,textvariable=room,width=12);field.pack(anchor='w')
    display=ttk.Label(frame);display.pack(pady=12)
    details=ttk.Label(frame,justify='left');details.pack(anchor='w')
    ttk.Label(frame,text='Raw 8×8 graphics tiles, not assembled enemy/NPC sprites.').pack(pady=(12,0))
    def refresh(*_):
        try:
            r=int(room.get().strip().removeprefix('0x'),16)
            im,b,sel,offsets=render_sheet(data,r)
            photo=ImageTk.PhotoImage(im);display.configure(image=photo);display.image=photo
            details.configure(text=f'Room {r:02X}  |  Bank ID {b:02X}\nSelectors: '+', '.join(f'{s:02X}' for s in sel)+'\nROM offsets: '+', '.join('empty' if p is None else f'{p:05X}' for p in offsets))
        except Exception as exc: messagebox.showerror('Sprite graphics',str(exc))
    ttk.Button(frame,text='Load room',command=refresh).pack(pady=8)
    field.bind('<Return>',refresh)
    refresh();root.mainloop()
if __name__=='__main__': main()
