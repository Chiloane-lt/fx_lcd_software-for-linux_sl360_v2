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
parser.add_argument('--mode', choices = ['image', 'video'], required = True)
parser.add_argument('path')

args = parser.parse_args()

if not os.path.isfile(args.path):
    parser.error(f"файл не найден: {args.path}")

if args.mode == 'image':
    images_bytes = get_images_bytes(args.path)
    blob = prepare_blob(images_bytes)
    chunks = prepare_chunks(blob)
    send_commands()
    send_image(chunks)
else:
    print("video mode will be available soon")
