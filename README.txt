# Windfish Editor — Beta 1

A level editor for Link’s Awakening DX Rev2.

## Requirements

Python 3.10 or newer, Tkinter, and Pillow.

Install Pillow with:
`python -m pip install Pillow`

Run:
`python run-windfish-editor.py`

## Credits

zladx — LADX Disassembly  
https://github.com/zladx/LADX-Disassembly

## AI Disclosure

Windfish was developed with assistance from ChatGPT.

No ROMs are included. Only use legally obtained copies of ROMs that you own.

## How to Use

Run Windfish and open a clean English Rev2 ROM. A dialog will explain that Windfish will expand the ROM to 2 MiB and install custom code.

The Edit menu contains three editing modes: Tiles, Sprites, and Collisions. Choose a mode, then open the corresponding Tile Selector, Sprite Selector, or Collision Selector from the Editors menu.

Select a tile, sprite, or collision, then use the right mouse button to place it. Some sprites use placeholder graphics, and sprites in a few rooms may not render in the editor at all. These can still appear correctly in-game, provided the appropriate sprite tileset is selected. This limitation is related to the original game’s graphics-reuse settings.

Make sure to add collisions manually or use the Recalculate Collisions button. Recalculation only processes Map16 Page 0; collisions for Page 1 must be placed manually.

Each overworld room can have independent BG tileset graphics and palette settings. The original game did not provide the same flexibility.

In Room GFX Settings, changing the sprite slot IDs is not recommended because those graphics are still shared with other rooms. You can change the sprite tileset bank if you understand how the settings work.

Room Properties was one of Windfish’s first interfaces. Use it to add or edit warps and change room music and animation settings.

In single-room view, navigate using the arrow keys or the room selector on the right.

With View Full Overworld enabled, use the + and − keys to zoom in and out. Editing in this view is supported, although single-room view is recommended. You can also right-click and drag across the room selector to display a row or rectangular group of rooms.

The Dungeon Editor controls are largely the same as those in the overworld editor.

Use the Palette Editor to change room palettes. Palette set IDs 00–1E are the original shared palettes and cannot be edited. Palette set IDs 1F–3F are editable.

You can edit the original text, but Windfish does not expand or repack the original dialog storage. Add a new dialog ID when you need additional text space. Using those new IDs in-game currently requires a script or another change that references them.

The custom collision API is not included and will be released separately.

A more detailed user guide is in development.