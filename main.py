import sys
from image import get_images_bytes
from image import prepare_blob
from core import prepare_chunks
from core import send_commands
from core import send_image

path = sys.argv[1]
images_bytes = get_images_bytes(path)

blob = prepare_blob(images_bytes)

chunks = prepare_chunks(blob)

send_commands()
send_image(chunks)