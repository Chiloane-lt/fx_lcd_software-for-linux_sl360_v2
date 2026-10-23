#!/usr/bin/env python
import sys
import argparse
import os

from image import get_images_bytes
from image import prepare_blob
from core import prepare_chunks
from core import send_commands
from core import send_image

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

parser = argparse.ArgumentParser(prog = 'lcd_software',
                                description = 'sets your image to lcd display')
parser.add_argument('--mode', choices = ['image', 'video'], required = True, help="chose mode: image - sets image to display, video - sets video to display(will be available soon) ")
parser.add_argument('path', help="path to your image/video")
parser.add_argument('--rotate', type=int, default=0, choices = [0, 90, 180, 270,], help="clockwise rotation")

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
else:
    print("video mode will be available soon")
