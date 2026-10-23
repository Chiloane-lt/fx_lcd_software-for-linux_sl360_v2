#!/usr/bin/env python
import sys
import argparse
import os

from image import get_images_bytes, prepare_blob, get_gif_frames
from core import prepare_chunks, send_commands, send_image, send_gif

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

parser = argparse.ArgumentParser(prog = 'lcd_software',
                                description = 'sets your image to lcd display')

parser.add_argument(
    '--mode',
    choices=['image', 'gif', 'video'],
    required=True,
    help='Mode: image - display a still image, gif - play an animated GIF, video - video playback (not yet available)',
)
parser.add_argument('path', help="path to your image/video")
parser.add_argument('--rotate', type=int, default=0, choices = [0, 90, 180, 270,], help="clockwise rotation")
parser.add_argument(
    '--debug-timing',
    action='store_true',
    help='Print GIF frame transmission timing for debugging',
)
parser.add_argument(
    '--chunk-delay',
    type=float,
    default=0.0,
    metavar='SECONDS',
    help='Delay between GIF USB chunks in seconds (default: 0.0)',
)

args = parser.parse_args()

if not os.path.isfile(args.path):
    parser.error(f"file dont exests: {args.path}")

if args.mode == 'image':
    try:
        images_bytes = get_images_bytes(args.path, rotate=args.rotate)
        blob = prepare_blob(images_bytes)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    chunks = prepare_chunks(blob)
    send_commands()
    send_image(chunks)

elif args.mode == 'gif':
    try:
        frames = [
            (prepare_chunks(prepare_blob(jpeg_bytes)), duration_ms)
            for jpeg_bytes, duration_ms
            in get_gif_frames(args.path, rotate=args.rotate)
        ]

        if not frames:
            parser.error("The GIF contains no frames.")

    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    send_commands()
    send_gif(
        frames,
        debug_timing=args.debug_timing,
        chunk_delay=args.chunk_delay,
    )

else:
    print("Video mode will be available soon.")
