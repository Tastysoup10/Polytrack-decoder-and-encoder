#!/usr/bin/env python3

import argparse
import json
import math
import struct
import zlib
from datetime import datetime


# ============================================================
# PolyTrack custom alphabet
# ============================================================

ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
)


# ============================================================
# PolyTrack part types containing checkpoint/start data
# ============================================================

CHECKPOINT_IDS = {
    52,   # Checkpoint
    65,   # CheckpointWide
    75,   # PlaneCheckpoint
    77,   # PlaneCheckpointWide
}

START_IDS = {
    5,    # Start
    91,   # StartWide
    92,   # PlaneStart
    93,   # PlaneStartWide
}


# ============================================================
# Exact PolyTrack custom encoder
# ============================================================

def get_bits(data, bit_position):
    """
    Equivalent to PolyTrack's module 7754 `l()` function.

    Reads up to 6 bits from a little-endian bit stream.
    """

    if bit_position >= len(data) * 8:
        raise ValueError("Bit position out of range")

    byte_index = bit_position // 8
    bit_offset = bit_position - byte_index * 8

    current = data[byte_index]

    if bit_offset <= 2 or byte_index >= len(data) - 1:
        return (
            (current & (63 << bit_offset))
            >> bit_offset
        )

    return (
        ((current & (63 << bit_offset)) >> bit_offset)
        |
        (
            (data[byte_index + 1] & (63 >> (8 - bit_offset)))
            << (8 - bit_offset)
        )
    )


def polytrack_encode(data):
    """
    Exact inverse of PolyTrack's custom encoding.

    Values 30 and 31 are encoded using 5 bits.
    All other values use 6 bits.
    """

    bit_position = 0
    output = []

    total_bits = len(data) * 8

    while bit_position < total_bits:

        value = get_bits(
            data,
            bit_position
        )

        if (value & 30) == 30:
            output.append(
                ALPHABET[value & 31]
            )
            bit_position += 5

        else:
            output.append(
                ALPHABET[value]
            )
            bit_position += 6

    return "".join(output)


# ============================================================
# DEFLATE
# ============================================================

def polytrack_deflate(data, window_bits):
    """
    PolyTrack uses Pako Deflate with:
        level=9
        memLevel=9

    These are normal zlib-wrapped streams.
    """

    compressor = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=window_bits,
        memLevel=9
    )

    return (
        compressor.compress(data)
        + compressor.flush()
    )


# ============================================================
# Binary helpers
# ============================================================

def u8(value):
    return struct.pack(
        "<B",
        value
    )


def u16(value):
    return struct.pack(
        "<H",
        value
    )


def u32(value):
    return struct.pack(
        "<I",
        value
    )


def i32(value):
    return struct.pack(
        "<i",
        value
    )


# ============================================================
# Environment
# ============================================================

ENVIRONMENTS = {
    "Summer": 0,
    "Winter": 1,
    "Desert": 2,
}


# ============================================================
# Timestamp
# ============================================================

def encode_timestamp(value):

    if value is None:
        return None

    if isinstance(value, int):
        return value

    value = value.replace(
        "Z",
        "+00:00"
    )

    dt = datetime.fromisoformat(
        value
    )

    return int(
        dt.timestamp()
    )


# ============================================================
# Build track binary
# ============================================================

def encode_track(track):

    parts = track["parts"]

    if not parts:
        raise ValueError(
            "Track has no parts."
        )

    # --------------------------------------------------------
    # Environment
    # --------------------------------------------------------

    environment_id = track.get(
        "environmentId"
    )

    if environment_id is None:

        environment = track.get(
            "environment",
            "Summer"
        )

        if isinstance(environment, str):
            if environment not in ENVIRONMENTS:
                raise ValueError(
                    f"Unknown environment: {environment}"
                )

            environment_id = ENVIRONMENTS[
                environment
            ]

        else:
            environment_id = int(
                environment
            )

    environment_id = int(
        environment_id
    )

    if not 0 <= environment_id <= 2:
        raise ValueError(
            "Invalid environment ID."
        )

    # --------------------------------------------------------
    # Sun direction
    # --------------------------------------------------------

    sun_direction = int(
        track.get(
            "sunDirection",
            0
        )
    )

    if not 0 <= sun_direction < 180:
        raise ValueError(
            "sunDirection must be 0-179."
        )

    # --------------------------------------------------------
    # Calculate bounds
    #
    # PolyTrack uses the minimum X/Y/Z as the base.
    # --------------------------------------------------------

    min_x = min(
        int(p["x"])
        for p in parts
    )

    min_y = min(
        int(p["y"])
        for p in parts
    )

    min_z = min(
        int(p["z"])
        for p in parts
    )

    max_x = max(
        int(p["x"])
        for p in parts
    )

    max_y = max(
        int(p["y"])
        for p in parts
    )

    max_z = max(
        int(p["z"])
        for p in parts
    )

    # --------------------------------------------------------
    # Exact PolyTrack width calculation
    # --------------------------------------------------------

    x_range = max_x - min_x + 1
    y_range = max_y - min_y + 1
    z_range = max_z - min_z + 1

    x_bytes = max(
        1,
        min(
            4,
            math.ceil(
                math.log2(x_range + 1) / 8
            )
        )
    )

    y_bytes = max(
        1,
        min(
            4,
            math.ceil(
                math.log2(y_range + 1) / 8
            )
        )
    )

    z_bytes = max(
        1,
        min(
            4,
            math.ceil(
                math.log2(z_range + 1) / 8
            )
        )
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    output = bytearray()

    output += u8(
        environment_id
    )

    output += u8(
        sun_direction
    )

    output += i32(
        min_x
    )

    output += i32(
        min_y
    )

    output += i32(
        min_z
    )

    packing = (
        x_bytes
        | (y_bytes << 2)
        | (z_bytes << 4)
    )

    output += u8(
        packing
    )

    # --------------------------------------------------------
    # Group by part ID
    # --------------------------------------------------------

    groups = {}

    for part in parts:

        part_id = int(
            part["partId"]
        )

        if not 0 <= part_id <= 255:
            raise ValueError(
                f"Part ID out of range: {part_id}"
            )

        groups.setdefault(
            part_id,
            []
        ).append(part)

    # --------------------------------------------------------
    # PolyTrack stores groups in ascending part ID order.
    # --------------------------------------------------------

    for part_id in sorted(groups):

        group = groups[
            part_id
        ]

        # Exact ordering used by TrackData.addPart()
        group.sort(
            key=lambda p: (
                int(p["x"]),
                int(p["y"]),
                int(p["z"]),
                int(p.get("rotation", 0)),
                int(p.get("rotationAxis", 0)),
                int(p.get("color", 0)),
                (
                    -1
                    if p.get("checkpointOrder") is None
                    else int(p["checkpointOrder"])
                ),
                (
                    -1
                    if p.get("startOrder") is None
                    else int(p["startOrder"])
                ),
            )
        )

        # Part ID
        output += u8(
            part_id
        )

        # Number of parts
        output += u32(
            len(group)
        )

        # ----------------------------------------------------
        # Individual parts
        # ----------------------------------------------------

        for part in group:

            x = int(part["x"])
            y = int(part["y"])
            z = int(part["z"])

            dx = x - min_x
            dy = y - min_y
            dz = z - min_z

            if dx < 0 or dx >= 2 ** (8 * x_bytes):
                raise ValueError(
                    f"X coordinate cannot be represented: {x}"
                )

            if dy < 0 or dy >= 2 ** (8 * y_bytes):
                raise ValueError(
                    f"Y coordinate cannot be represented: {y}"
                )

            if dz < 0 or dz >= 2 ** (8 * z_bytes):
                raise ValueError(
                    f"Z coordinate cannot be represented: {z}"
                )

            # Coordinates
            output += dx.to_bytes(
                x_bytes,
                "little"
            )

            output += dy.to_bytes(
                y_bytes,
                "little"
            )

            output += dz.to_bytes(
                z_bytes,
                "little"
            )

            # ------------------------------------------------
            # Rotation + axis
            # ------------------------------------------------

            rotation = int(
                part.get(
                    "rotation",
                    0
                )
            )

            rotation_axis = int(
                part.get(
                    "rotationAxis",
                    0
                )
            )

            if not 0 <= rotation <= 3:
                raise ValueError(
                    "Rotation must be 0-3."
                )

            if not 0 <= rotation_axis <= 7:
                raise ValueError(
                    "Rotation axis must be 0-7."
                )

            rotation_byte = (
                (3 & rotation)
                |
                ((7 & rotation_axis) << 2)
            )

            output += u8(
                rotation_byte
            )

            # ------------------------------------------------
            # Color
            # ------------------------------------------------

            color = int(
                part.get(
                    "color",
                    0
                )
            )

            if not 0 <= color <= 255:
                raise ValueError(
                    "Color must be 0-255."
                )

            output += u8(
                color
            )

            # ------------------------------------------------
            # Checkpoint order
            # ------------------------------------------------

            if part_id in CHECKPOINT_IDS:

                order = part.get(
                    "checkpointOrder"
                )

                if order is None:
                    raise ValueError(
                        f"Checkpoint part {part_id} "
                        "has no checkpointOrder."
                    )

                output += u16(
                    int(order)
                )

            # ------------------------------------------------
            # Start order
            # ------------------------------------------------

            if part_id in START_IDS:

                order = part.get(
                    "startOrder"
                )

                if order is None:
                    raise ValueError(
                        f"Start part {part_id} "
                        "has no startOrder."
                    )

                output += u32(
                    int(order)
                )

    return bytes(
        output
    )


# ============================================================
# Build metadata
# ============================================================

def encode_metadata(metadata):

    name = metadata.get(
        "name",
        ""
    )

    author = metadata.get(
        "author"
    )

    name_bytes = name.encode(
        "utf-8"
    )

    if author is None:
        author_bytes = b""
    else:
        author_bytes = author.encode(
            "utf-8"
        )

    if len(name_bytes) > 255:
        raise ValueError(
            "Track name is longer than 255 bytes."
        )

    if len(author_bytes) > 255:
        raise ValueError(
            "Author is longer than 255 bytes."
        )

    output = bytearray()

    # Name
    output += u8(
        len(name_bytes)
    )

    output += name_bytes

    # Author
    output += u8(
        len(author_bytes)
    )

    output += author_bytes

    # Last modified
    timestamp = encode_timestamp(
        metadata.get(
            "lastModified"
        )
    )

    if timestamp is None:

        output += u8(0)

    else:

        output += u8(1)

        output += u32(
            timestamp
        )

    return bytes(
        output
    )


# ============================================================
# Encode complete PolyTrack2 file
# ============================================================

def encode_polytrack2(data):

    # --------------------------------------------------------
    # Support both:
    #
    # 1. decoder JSON:
    #       metadata / track
    #
    # 2. alternate format:
    #       trackMetadata / trackData
    # --------------------------------------------------------

    metadata = data.get(
        "trackMetadata",
        data.get(
            "metadata",
            {}
        )
    )

    track = data.get(
        "trackData",
        data.get(
            "track",
            {}
        )
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata_binary = encode_metadata(
        metadata
    )

    # --------------------------------------------------------
    # Track binary
    # --------------------------------------------------------

    track_binary = encode_track(
        track
    )

    # --------------------------------------------------------
    # FIRST DEFLATE
    #
    # This is important:
    # metadata and track are pushed into the SAME
    # Deflate stream.
    #
    # Equivalent to:
    #
    #   l.push(metadata, false)
    #   l.push(track, true)
    # --------------------------------------------------------

    compressor = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=9,
        memLevel=9
    )

    first_compressed = (
        compressor.compress(
            metadata_binary
        )
        +
        compressor.compress(
            track_binary
        )
        +
        compressor.flush()
    )

    # --------------------------------------------------------
    # FIRST PolyTrack encoding
    # --------------------------------------------------------

    first_encoded = polytrack_encode(
        first_compressed
    )

    # --------------------------------------------------------
    # SECOND DEFLATE
    #
    # PolyTrack compresses the encoded string.
    # --------------------------------------------------------

    second_compressed = polytrack_deflate(
        first_encoded.encode("utf-8"),
        15
    )

    # --------------------------------------------------------
    # SECOND PolyTrack encoding
    # --------------------------------------------------------

    second_encoded = polytrack_encode(
        second_compressed
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    return (
        b"PolyTrack2"
        +
        second_encoded.encode(
            "ascii"
        )
    )


# ============================================================
# Command line
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Encode PolyTrack2 JSON into a .track file"
        )
    )

    parser.add_argument(
        "input",
        help="Input decoded JSON"
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output .track filename"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Load JSON
    # --------------------------------------------------------

    with open(
        args.input,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    # --------------------------------------------------------
    # Encode
    # --------------------------------------------------------

    track_bytes = encode_polytrack2(
        data
    )

    # --------------------------------------------------------
    # Output name
    # --------------------------------------------------------

    if args.output:

        output_file = args.output

    else:

        output_file = (
            args.input.rsplit(
                ".",
                1
            )[0]
            +
            ".track"
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    with open(
        output_file,
        "wb"
    ) as f:

        f.write(
            track_bytes
        )

    print(
        f"Encoded: {args.input}"
    )

    print(
        f"Output:  {output_file}"
    )

    print(
        f"Size:    {len(track_bytes):,} bytes"
    )


if __name__ == "__main__":
    main()