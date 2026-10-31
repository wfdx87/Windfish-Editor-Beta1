"""Native four-frame animation graphics and Overworld Properties UI."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
from windfish.rendering.windfish_overworld_render import u16, animation_id, graphics, render, direct_map, SPECIAL_MAP

NAMES = ('None', 'Counter', 'Tide', 'Village', 'Dungeon 1', 'Underground',
         'Lava', 'Dungeon 2 / scrolling', 'Warp', 'Water currents', 'Waterfall',
         'Slow waterfall', 'Water dungeon', 'Light beam', 'Crystal blocks',
         'Bubbles', 'Weather vane', 'Photo')
SPECIAL = {0, 1, 7, 17}


def frame_address(data, aid):
    if aid in SPECIAL or not 0 <= aid < len(NAMES):
        raise ValueError('This animation uses special runtime logic; frame editing is unavailable.')
    # Locate the actual dispatch table, allowing revision-dependent code offsets.
    start = bytes(data).find(b'\xf0\xa4\xc7', 0x1B00, 0x1C40)
    if start < 0:
        raise ValueError('Animation dispatch table not recognized.')
    routine = u16(data, start + 3 + aid * 2)
    if not 0x1B00 <= routine < 0x2000:
        raise ValueError('Animation routine is outside the supported range.')
    # Supported routines select a graphics page using LD H, immediate.
    code = bytes(data[routine:routine + 32])
    index = code.find(b'\x26')
    if index < 0 or index + 1 >= len(code):
        raise ValueError('Animation graphics page not recognized.')
    page = code[index + 1]
    if not 0x6A <= page <= 0x77:
        raise ValueError('Animation graphics page is outside the native frame bank.')
    at = 0xB0000 + (page - 0x40) * 0x100
    if at + 256 > len(data):
        raise ValueError('Animation graphics are missing from this ROM.')
    return at


def source_tiles(data, room, special):
    from windfish.rom.windfish_room_tiles import is_custom
    raw = graphics(data, room, special)[2]
    custom = is_custom(data, room)
    if custom:
        raw = bytes(data[0xB0800:0xB1000]) + bytes(raw[0x100:])
    return [bytes(raw[((tid ^ 0x80) if custom else ((tid + 0x10) & 255))*16:
                           ((tid ^ 0x80) if custom else ((tid + 0x10) & 255))*16+16])
            for tid in range(256)]


def animated_room_tiles(data, room, special=False):
    """Unique 16x16 definitions present in this layout that use animated slots."""
    from windfish.rom.windfish_room_tiles import definition_offset
    at = definition_offset(data, room)
    cells = direct_map(data, room, special)[1]
    return sorted({tile for tile in cells
                   if any(0x6C <= part <= 0x6F
                          for part in data[at+tile*4:at+tile*4+4])})


def tile_gallery(sheet, tile_ids):
    columns = min(6, len(tile_ids))
    image = Image.new('RGB', (max(1, columns)*64,
                              max(1, (len(tile_ids)+5)//6)*70), '#eeeeee')
    draw = ImageDraw.Draw(image)
    for i, tile in enumerate(tile_ids):
        x, y = (i % 6)*64, (i // 6)*70
        crop = sheet.crop((tile%16*16, tile//16*16,
                           tile%16*16+16, tile//16*16+16))
        image.paste(crop.resize((48,48), Image.Resampling.NEAREST), (x+8,y))
        draw.text((x+23,y+50), f'{tile:02X}', fill='black')
    return image


class AnimationPage:
    def __init__(self, owner, tabs, dungeon=False):
        self.owner = owner
        self.page = ttk.Frame(tabs, padding=8)
        tabs.add(self.page, text='BG Animation')
        row = ttk.Frame(self.page); row.pack(fill='x')
        ttk.Label(row, text='Animation ID').pack(side='left', padx=(0, 8))
        owner.room_animation_var = owner.fields['Animation'] if dungeon else tk.StringVar()
        owner.room_animation_combo = ttk.Combobox(row, textvariable=owner.room_animation_var,
            state='readonly', width=6, values=[f'{v:02X}' for v in range(18)])
        owner.room_animation_combo.pack(side='left')
        owner.room_animation_combo.bind('<<ComboboxSelected>>', owner.apply if dungeon else owner.change_room_animation)
        if dungeon: owner.controls.append(owner.room_animation_combo)
        self.status = tk.StringVar()
        ttk.Label(self.page, textvariable=self.status, wraplength=420).pack(anchor='w', pady=6)
        preview_box = ttk.Frame(self.page); preview_box.pack(fill='x')
        self.preview = tk.Canvas(preview_box, width=390, height=140,
                                 highlightthickness=0)
        scroll = ttk.Scrollbar(preview_box, command=self.preview.yview)
        self.preview.configure(yscrollcommand=scroll.set)
        self.preview.pack(side='left', fill='x', expand=True)
        scroll.pack(side='right', fill='y')
        self.preview_item = self.preview.create_image(0, 0, anchor='nw')
        self.show_frames = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.page, text='Animate tiles', variable=self.show_frames,
                        command=self.toggle_frames).pack(anchor='w', pady=6)
        self.photos = []; self.images = []; self.tick = 0; self.job = None
        self.page.bind('<Destroy>', self.destroy, add='+')
        self.animate()

    def destroy(self, event):
        if event.widget is self.page and self.job is not None:
            self.page.after_cancel(self.job); self.job = None

    def animate(self):
        if self.images and self.show_frames.get():
            self.preview.itemconfigure(self.preview_item, image=self.images[self.tick % len(self.images)])
            self.tick += 1
        self.job = self.page.after(getattr(self, 'delay', 130), self.animate)

    def toggle_frames(self):
        self.tick = 0
        if self.images:
            self.preview.itemconfigure(self.preview_item, image=self.images[0])

    def gallery_photo(self, sheet, tile_ids):
        gallery = tile_gallery(sheet, tile_ids)
        self.preview.configure(scrollregion=(0,0,*gallery.size),
                               height=min(210, gallery.height))
        return ImageTk.PhotoImage(gallery)

    def refresh(self):
        o = self.owner
        self.images = []; self.photos = []; self.preview.itemconfigure(self.preview_item, image='')
        try:
            special = bool(o.alternate.get() and o.room in SPECIAL_MAP)
            aid = animation_id(o.data, o.room, special)
            self.status.set(f'Room {o.room:02X} • {aid:02X} — {NAMES[aid] if aid < 18 else "Unknown"}')
            tile_ids = animated_room_tiles(o.data, o.room, special) if aid else []
            self.status.set(self.status.get() + ('\nAnimated 16×16 tiles: ' + ', '.join(f'{t:02X}' for t in tile_ids) if tile_ids else '\nNo animated 16×16 tiles in this room.'))
            if aid in SPECIAL or not 0 <= aid < 18:
                self.images = [self.gallery_photo(render(o.data, o.room, special, scale=1)[1], tile_ids)] if tile_ids else []
                if self.images: self.preview.itemconfigure(self.preview_item, image=self.images[0])
                self.status.set(self.status.get() + '\nStatic tile preview. This group uses special runtime logic.')
                self.toggle_frames()
                return
            at = frame_address(o.data, aid)
            self.delay = 267 if aid in (2,3,5,11,12) else (67 if aid in (9,10,13) else 133)
            for frame in range(4):
                raw = bytes(o.data[at+frame*64:at+(frame+1)*64])
                sheet = render(o.data, o.room, special, scale=1, animation_frame=raw)[1]
                if tile_ids: self.images.append(self.gallery_photo(sheet, tile_ids))
            if aid in (4, 6) and self.images:
                self.images = [self.images[i] for i in (0,1,2,3,3,3,2,1)]
            if self.images:
                self.preview.itemconfigure(self.preview_item, image=self.images[0])
            self.tick = 0
        except (ValueError, IndexError) as exc:
            self.status.set(self.status.get() + '\n' + str(exc))
        self.toggle_frames()

