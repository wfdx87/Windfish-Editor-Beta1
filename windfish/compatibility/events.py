"""Native Rev2 event locations."""
def is_vwf(data):return False
def require_editable(data):
    from windfish.rom.windfish_identifiers import reject_patches
    if data is not None:reject_patches(data)
def forest(data,native_dialogue):return 0xBAC8,0x149B3,0x149E8,native_dialogue
def keyholes(data,native):return 0xAFD2,native
def owl(data,native):return native
def fragment(data,at,raw):return at,raw
