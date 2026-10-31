"""Placement policy, separate from decoding existing sprite-list formats."""
MAX_ROOM_SPRITES = 16
LIMIT_TITLE = 'Sprite limit reached'
LIMIT_MESSAGE = ('No room for additional sprites in the current room. '
                 'The maximum is 16 placements.')


class SpriteLimitError(ValueError):
    """An edit would grow a room beyond the supported placement limit."""


def check_room_sprite_count(previous_count, requested_count):
    """Allow repairs to oversized existing lists, but never grow them further.

    Do not cap the decoder or packer: loading, unrelated-room edits and undo
    must preserve existing hacks with more placements. This is an editor policy,
    not a claim that sixteen placements leave room for spawned game entities.
    """
    if requested_count > MAX_ROOM_SPRITES and requested_count > previous_count:
        raise SpriteLimitError(LIMIT_MESSAGE)
