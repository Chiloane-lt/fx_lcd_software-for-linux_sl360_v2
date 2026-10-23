
from PIL import Image
from io import BytesIO

# The frame length is stored in two bytes and includes the 32-byte header.
MAX_FRAME_SIZE = (1 << 16) - 1
FRAME_HEADER_SIZE = 32
MAX_JPEG_SIZE = MAX_FRAME_SIZE - FRAME_HEADER_SIZE

START_QUALITY = 80
MIN_QUALITY = 20
QUALITY_STEP = 5


# Converts and resizes the user's image.
def get_images_bytes(path: str | None = None, rotate: int = 0) -> bytes:
    try:
        with Image.open(path) as source:
            img = source.copy()

        if rotate:
            img = img.rotate(-rotate, expand=True)

        if img.size != (480, 480):
            print("Resizing image to 480x480")
            img = img.resize((480, 480))

        img = img.convert("RGB")

        for quality in range(
            START_QUALITY, MIN_QUALITY - 1, -QUALITY_STEP
        ):
            buffer = BytesIO()
            img.save(
                buffer,
                "JPEG",
                quality=quality,
                subsampling=2,
                dpi=(96, 96),
            )
            jpeg_bytes = buffer.getvalue()
            frame_size = len(jpeg_bytes) + FRAME_HEADER_SIZE

            if len(jpeg_bytes) <= MAX_JPEG_SIZE:
                if quality != START_QUALITY:
                    print(
                        f"Image compressed to fit: JPEG quality {quality}, "
                        f"{len(jpeg_bytes):,} bytes "
                        f"(frame: {frame_size:,}/{MAX_FRAME_SIZE:,} bytes)"
                    )
                return jpeg_bytes

            print(
                f"JPEG quality {quality} is too large: "
                f"{len(jpeg_bytes):,} bytes; trying lower quality."
            )

        raise ValueError(
            f"Image is still too large at JPEG quality {MIN_QUALITY}. "
            f"JPEG size must be at most {MAX_JPEG_SIZE:,} bytes."
        )

    except Exception as exc:
        raise RuntimeError(f"Could not prepare image '{path}': {exc}") from exc


# Prepares the frame blob.
def prepare_blob(jpeg_bytes: bytes) -> bytes:
    frame_size = len(jpeg_bytes) + FRAME_HEADER_SIZE

    if frame_size > MAX_FRAME_SIZE:
        raise ValueError(
            f"Image frame is too large: {frame_size:,} bytes. "
            f"Maximum allowed is {MAX_FRAME_SIZE:,} bytes."
        )

    crt = bytes.fromhex("4352540000")
    dra = bytes.fromhex("4452410000")
    two_bytes = frame_size.to_bytes(2, "big")

    head = crt + dra + two_bytes + b"\xb1" + b"\x00" * 19
    return head + jpeg_bytes
