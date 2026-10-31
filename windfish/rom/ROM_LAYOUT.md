# Expanded editor ROM layout

Beta 1 uses ROM format 3. Windfish installs the runtime in its reserved regions; the standalone API inserter owns user script insertion and removal. Do not reassign these regions independently.

| Region | PC start | PC end (exclusive) |
| --- | --- | --- |
| exgfx | 100000 | 120000 |
| metatiles | 120000 | 180000 |
| dungeon_rooms | 180000 | 194000 |
| dungeon_visuals | 194000 | 1B8000 |
| graphics_engine | 1B8000 | 1BC000 |
| tile_gateway | 1BC000 | 1C0000 |
| profile_metadata | 1C0000 | 1C4000 |
| sprite_storage | 1C4000 | 1C8000 |
| collision_storage | 1C8000 | 1D0000 |
| palettes_and_bg | 1D0000 | 1D4000 |
| bg_import_blocks | 1D4000 | 1D8000 |
| shared_map16_engine | 1D8000 | 1DC000 |
| reserved_collision_scripts | 1DC000 | 1E0000 |
| format_header | 1E0000 | 1E4000 |
| shared_map16_rooms | 1E4000 | 1F4000 |
| reserved_hardware | 1F4000 | 1F8000 |
| reserved_script_runtime | 1F8000 | 1FC000 |

The editor expands supported inputs to 2 MiB. Native/HUD/VWF original-ROM hooks
remain profile-specific and validated by their adapters. Shared Map16 WFM16007
retains per-room table selection and literal scrolling tile transfer. API code
and custom SRAM extensions are not part of this package.
