#!/usr/bin/env python3

import argparse
import json
import struct
import zlib
from datetime import datetime, timezone


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

# PolyTrack part IDs
PART_NAMES = {
    0: "Straight",
    1: "TurnSharp",
    2: "SlopeUp",
    3: "SlopeDown",
    4: "Slope",
    5: "Start",
    6: "Finish",
    7: "Turn",
    8: "TurnWide",
    9: "StraightLong",
    10: "StraightWide",
    11: "TurnSharpWide",
    12: "SlopeUpWide",
    13: "SlopeDownWide",
    14: "SlopeWide",
    15: "Pillar",
    16: "PillarWide",
    17: "PillarTop",
    18: "PillarMiddle",
    19: "PillarTop",
    20: "PillarMiddle",
    21: "PillarBottom",
    22: "Wall",
    23: "WallWide",
    24: "Plane",
    25: "Plane",
    26: "PlaneWall",
    27: "PlaneWallWide",
    28: "Block",
    29: "Block",
    30: "BlockWide",
    31: "BlockCorner",
    32: "BlockCornerWide",
    33: "PlaneTurn",
    34: "PlaneTurnWide",
    35: "PlaneSlope",
    36: "PlaneSlopeWide",
    37: "PlaneSlopeUp",
    38: "PlaneSlopeDown",
    39: "PlaneSlopeUpWide",
    40: "Slope",
    41: "SlopeCorner",
    42: "SlopeCornerWide",
    43: "SlopeTransition",
    44: "SlopeTransitionWide",
    45: "WallSlope",
    46: "WallSlopeWide",
    47: "PillarSlope",
    48: "PillarSlopeWide",
    49: "Checkpoint",
    50: "CheckpointWide",
    51: "Finish",
    52: "Checkpoint",
    53: "HalfBlock",
    54: "HalfBlockWide",
    55: "QuarterBlock",
    56: "QuarterBlockWide",
    57: "Corner",
    58: "CornerWide",
    59: "InnerCorner",
    60: "InnerCornerWide",
    61: "OuterCorner",
    62: "OuterCornerWide",
    63: "OuterCornerWide",
    64: "Start",
    65: "CheckpointWide",
    66: "PlaneStart",
    67: "PlaneFinish",
    68: "BlockSlopedDown",
    69: "BlockSlopedDownWide",
    70: "BlockSlopedUp",
    71: "BlockSlopedUp",
    72: "BlockSlopedUpWide",
    73: "Finish",
    74: "FinishWide",
    75: "PlaneCheckpoint",
    76: "PlaneFinish",
    77: "PlaneCheckpointWide",
    78: "PlaneFinishWide",
    79: "PlaneTurn",
    80: "PlaneTurnWide",
    81: "PlaneWall",
    82: "PlaneWallWide",
    83: "PlaneSlope",
    84: "Slope",
    85: "PlaneSlopeWide",
    86: "PlaneSlopeUp",
    87: "PlaneSlopeDown",
    88: "PlaneSlopeUpWide",
    89: "PlaneSlopeDownWide",
    90: "Start",
    91: "StartWide",
    92: "PlaneStart",
    93: "PlaneStartWide",
    94: "Finish",
    95: "FinishWide",
    96: "Intersection",
    97: "IntersectionLong",
    98: "IntersectionX",
    99: "IntersectionY",
    100: "IntersectionYLong",
}


CHECKPOINT_IDS = {
    52,
    65,
    75,
    77,
}

START_IDS = {
    5,
    91,
    92,
    93,
}


def custom_decode(data):
    """
    PolyTrack's custom 5/6-bit decoder.

    Characters use the alphabet:
    ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789

    Values whose bits 1..4 are all set use 5 bits.
    Everything else uses 6 bits.
    """

    values = []

    for char in data:
        try:
            value = ALPHABET.index(char)
        except ValueError:
            raise ValueError(
                f"Invalid PolyTrack character: {char!r}"
            )

        if (value & 30) == 30:
            values.append((value & 31, 5))
        else:
            values.append((value, 6))

    output = bytearray()

    bit_buffer = 0
    bit_count = 0

    for value, bits in values:
        bit_buffer |= value << bit_count
        bit_count += bits

        while bit_count >= 8:
            output.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8

    if bit_count > 0:
        output.append(bit_buffer & 0xFF)

    return bytes(output)


def inflate(data):
    """
    Decompress a raw DEFLATE stream.
    """

    try:
        return zlib.decompress(data, -15)
    except zlib.error:
        # Some streams may contain a zlib header.
        return zlib.decompress(data)


def read_u8(data, offset):
    return data[offset], offset + 1


def read_u16(data, offset):
    value = struct.unpack_from("<H", data, offset)[0]
    return value, offset + 2


def read_u32(data, offset):
    value = struct.unpack_from("<I", data, offset)[0]
    return value, offset + 4


def read_i32(data, offset):
    value = struct.unpack_from("<i", data, offset)[0]
    return value, offset + 4


def read_string(data, offset, length):
    value = data[offset:offset + length].decode("utf-8")
    return value, offset + length


def decode_polytrack2(filename):
    with open(filename, "rb") as f:
        raw = f.read()

    # ---------------------------------------------------------
    # 1. Check PolyTrack2 header
    # ---------------------------------------------------------

    if not raw.startswith(b"PolyTrack2"):
        raise ValueError(
            "This does not appear to be a PolyTrack2 track file."
        )

    # The first 10 characters are "PolyTrack2".
    encoded = raw[10:].decode("ascii")

    # ---------------------------------------------------------
    # 2. First custom decoding
    # ---------------------------------------------------------

    compressed_1 = custom_decode(encoded)

    # ---------------------------------------------------------
    # 3. First DEFLATE decompression
    # ---------------------------------------------------------

    encoded_2 = inflate(compressed_1).decode("utf-8")

    # ---------------------------------------------------------
    # 4. Second custom decoding
    # ---------------------------------------------------------

    compressed_2 = custom_decode(encoded_2)

    # ---------------------------------------------------------
    # 5. Second DEFLATE decompression
    # ---------------------------------------------------------

    binary = inflate(compressed_2)

    offset = 0

    # ---------------------------------------------------------
    # 6. Metadata
    # ---------------------------------------------------------

    name_length, offset = read_u8(binary, offset)

    name, offset = read_string(
        binary,
        offset,
        name_length
    )

    author_length, offset = read_u8(binary, offset)

    if author_length:
        author, offset = read_string(
            binary,
            offset,
            author_length
        )
    else:
        author = None

    modified_flag, offset = read_u8(binary, offset)

    if modified_flag:
        timestamp, offset = read_u32(binary, offset)

        last_modified = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        ).isoformat()
    else:
        last_modified = None

    metadata = {
        "name": name,
        "author": author,
        "lastModified": last_modified,
    }

    # ---------------------------------------------------------
    # 7. Track header
    # ---------------------------------------------------------

    environment_id, offset = read_u8(binary, offset)

    environments = {
        0: "Summer",
        1: "Winter",
        2: "Desert",
    }

    environment = environments.get(
        environment_id,
        f"Unknown ({environment_id})"
    )

    sun_direction, offset = read_u8(binary, offset)

    if sun_direction >= 180:
        raise ValueError(
            f"Invalid sun direction: {sun_direction}"
        )

    base_x, offset = read_i32(binary, offset)
    base_y, offset = read_i32(binary, offset)
    base_z, offset = read_i32(binary, offset)

    packing, offset = read_u8(binary, offset)

    x_width = packing & 3
    y_width = (packing >> 2) & 3
    z_width = (packing >> 4) & 3

    if not (1 <= x_width <= 4):
        raise ValueError("Invalid X coordinate width")

    if not (1 <= y_width <= 4):
        raise ValueError("Invalid Y coordinate width")

    if not (1 <= z_width <= 4):
        raise ValueError("Invalid Z coordinate width")

    # ---------------------------------------------------------
    # 8. Track pieces
    # ---------------------------------------------------------

    parts = []

    def read_packed_uint(width):
        nonlocal offset

        value = 0

        for i in range(width):
            byte, offset = read_u8(binary, offset)
            value |= byte << (8 * i)

        return value

    while offset < len(binary):

        part_id, offset = read_u8(binary, offset)

        count, offset = read_u32(binary, offset)

        for _ in range(count):

            x = (
                read_packed_uint(x_width)
                + base_x
            )

            y = (
                read_packed_uint(y_width)
                + base_y
            )

            z = (
                read_packed_uint(z_width)
                + base_z
            )

            rotation_byte, offset = read_u8(
                binary,
                offset
            )

            rotation = rotation_byte & 3

            rotation_axis = (
                rotation_byte >> 2
            ) & 7

            color, offset = read_u8(
                binary,
                offset
            )

            checkpoint_order = None
            start_order = None

            if part_id in CHECKPOINT_IDS:
                checkpoint_order, offset = read_u16(
                    binary,
                    offset
                )

            if part_id in START_IDS:
                start_order, offset = read_u32(
                    binary,
                    offset
                )

            axis_names = {
                0: "YPositive",
                1: "YNegative",
                2: "XPositive",
                3: "XNegative",
                4: "ZPositive",
                5: "ZNegative",
            }

            parts.append({
                "x": x,
                "y": y,
                "z": z,
                "partId": part_id,
                "part": PART_NAMES.get(
                    part_id,
                    f"Unknown ({part_id})"
                ),
                "rotation": rotation,
                "rotationAxis": rotation_axis,
                "rotationAxisName": axis_names.get(
                    rotation_axis,
                    f"Unknown ({rotation_axis})"
                ),
                "color": color,
                "checkpointOrder": checkpoint_order,
                "startOrder": start_order,
            })

    # ---------------------------------------------------------
    # 9. Return decoded track
    # ---------------------------------------------------------

    return {
        "format": "PolyTrack2",
        "metadata": metadata,
        "track": {
            "environment": environment,
            "environmentId": environment_id,
            "sunDirection": sun_direction,
            "baseCoordinates": {
                "x": base_x,
                "y": base_y,
                "z": base_z,
            },
            "coordinateWidths": {
                "x": x_width,
                "y": y_width,
                "z": z_width,
            },
            "parts": parts,
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Decode PolyTrack .track files"
    )

    parser.add_argument(
        "input",
        help="Input .track file"
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON file"
    )

    args = parser.parse_args()

    result = decode_polytrack2(args.input)

    if args.output:
        output_file = args.output
    else:
        output_file = args.input.rsplit(
            ".",
            1
        )[0] + ".json"

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )

    print(f"Decoded: {args.input}")
    print(f"Name:   {result['metadata']['name']}")
    print(f"Author: {result['metadata']['author']}")
    print(
        f"Parts:  "
        f"{len(result['track']['parts'])}"
    )
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()