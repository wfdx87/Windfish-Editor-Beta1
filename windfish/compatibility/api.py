"""Native Rev2 address boundary; third-party engines are currently unsupported."""
class _NoHud:
    @staticmethod
    def validate(data):return None
    @staticmethod
    def description(data):return 'Original bottom HUD'
top_hud=_NoHud()
def is_vwf(data):return False
def ready(data):return True
def require_native(data,feature):
    from windfish.rom.windfish_identifiers import reject_patches
    reject_patches(data)
def sprite_frame(data,offset,expected):return offset,expected
def sprite_hooks(data,native):return native
def backups(data,native):return native
def bg_custom(data,native):return native
def indoor_bg_table(data,native):return native
def door_table(data,native):return native
def bank20_table(data,native):return native
def sprite_bank_table(data,native):return native
def fine_collision_table(data,native):return native
def graphics_dma_entry(data,native):return native
def map16_layout(data,native):return native
def custom_collision_layout(data,native):return native
def transition_tile_layout(data,native):return dict(native)
def original_bg_selector(data,room):
    r=8 if room==7 else room
    return 0x82E7B+(((r>>1)&7)|((r>>2)&0xF8))
def world_map_offsets(data):
    return {'regions':0x5901,'lookup':0x5941,'special':0x5991,'tiles':0x81697,'attributes':0x81797}
