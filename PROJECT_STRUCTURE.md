# Project Structure

- windfish/app: Tk editor windows and shared actions.
- windfish/rom: ROM storage, checked engine installation and validation.
- windfish/rom/windfish_identifiers.py: central format-3 directory contract.
- windfish/rom/windfish_format_conversion.py: bounded conversion from recent native formats.
- windfish/rendering: room and asset rendering.
- windfish/overworld and windfish/dungeon: room data and editor services.
- windfish/dungeon/windfish_dungeon_events.py: native indoor room-event properties and table lookup.
- windfish/compatibility: native address boundary.