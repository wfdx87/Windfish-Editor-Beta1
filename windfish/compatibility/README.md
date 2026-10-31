# Optional patch integrations

Core editing and rendering modules use `api.py` and `events.py`. They must not
import patch implementation modules directly. Each patch owns its signatures,
relocated addresses, code checks and migration rules in a dedicated folder.
These adapters do not imply general support for arbitrary patched ROMs.

- `vwf/`: original VWF detection/profile validation, sprite frame mappings,
  dialogue codec/layout, event operands, and editing-engine installation data.
  `standalone_hud.py` handles the combined VWF+HUD source layout, so it belongs
  here rather than in the HUD-only adapter.
- `hud_on_top/`: optional HUD detection plus the integration installer snapshot.
  The standalone HUD release is a separate project; it is not built or released
  by this package.
- `api.py`: the stable internal entry point for engine/layout operations,
  logical sprite-frame resolution, text services and optional HUD detection.
- `events.py`: the event-layout entry point for the existing event tools.

VWF is currently the only alternate engine adapter. The API preserves the
existing native/VWF semantics; it is not a generic plug-in loader and does not
claim automatic support for additional patches or combinations. When adding
another adapter, extend the shared entry points with explicit detection and
validation, then add that adapter's own address maps and compatibility tests.
Keep optional independent patches composable; do not assume one patch implies
another is installed. Do not search a user's ROM for plausible frame tables or
relax source verification to enable an unverified layout.

Patch adapters may call shared ROM utilities (checksums, text character data)
and other compatibility adapters where a verified combination requires it.
Keep imports lazy where ROM installation and dialogue services depend on each
other. Preserve atomic private-buffer installation and immutable native address
constants; avoid process-global switches.

The boundary test prevents core modules from importing patch implementation
packages. Changes must preserve validation failures, ROM output and previews,
not merely make imports succeed.
