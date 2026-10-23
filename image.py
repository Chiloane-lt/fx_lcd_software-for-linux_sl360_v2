
from PIL import Image, ImageOps
from io import BytesIO

# The frame length is stored in two bytes and includes the 32-byte header.
MAX_FRAME_SIZE = (1 << 16) - 1
FRAME_HEADER_SIZE = 32
MAX_JPEG_SIZE = MAX_FRAME_SIZE - FRAME_HEADER_SIZE

START_QUALITY = 80
MIN_QUALITY = 20
QUALITY_STEP = 5


# Converts and resizes the user's image.

def encode_image(
    img: Image.Image,
    rotate: int = 0,
    resize_mode: str = "stretch",
) -> bytes:
    img = img.convert("RGB")

    if rotate:
        img = img.rotate(-rotate, expand=True)

    target_size = (480, 480)

    if resize_mode == "stretch":
        img = img.resize(target_size)

    elif resize_mode == "fit":
        img.thumbnail(target_size, Image.Resampling.LANCZOS)

        background = Image.new("RGB", target_size, (0, 0, 0))
        x = (target_size[0] - img.width) // 2
        y = (target_size[1] - img.height) // 2
        background.paste(img, (x, y))
        img = background

    elif resize_mode == "crop":
        img = ImageOps.fit(
            img,
            target_size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

    else:
        raise ValueError(
            f"Unknown resize mode '{resize_mode}'. "
            "Choose 'stretch', 'fit', or 'crop'."
        )

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

        if len(jpeg_bytes) <= MAX_JPEG_SIZE:
            if quality != START_QUALITY:
                print(
                    f"Image compressed to fit: JPEG quality {quality}, "
                    f"{len(jpeg_bytes):,} bytes"
                )
            return jpeg_bytes

    raise ValueError(
        f"Image is too large at JPEG quality {MIN_QUALITY}. "
        f"Maximum JPEG size is {MAX_JPEG_SIZE:,} bytes."
    )


def get_images_bytes(
    path: str | None = None,
    rotate: int = 0,
    resize_mode: str = "stretch",
) -> bytes:
    try:
        with Image.open(path) as source:
            img = source.copy()

        return encode_image(img, rotate, resize_mode)

    except Exception as exc:
        raise RuntimeError(
            f"Could not prepare image '{path}': {exc}"
        ) from exc


def get_gif_frames(
    path: str,
    rotate: int = 0,
    resize_mode: str = "stretch",
):
    try:
        with Image.open(path) as gif:
            if not getattr(gif, "is_animated", False):
                raise ValueError("The selected file is not an animated GIF.")

            for frame_number in range(gif.n_frames):
                gif.seek(frame_number)

                # Copy the current frame before moving to the next one.
                frame = gif.convert("RGB").copy()
                duration_ms = max(20, int(gif.info.get("duration", 100)))

                jpeg_bytes = encode_image(frame, rotate, resize_mode)
                yield jpeg_bytes, duration_ms

    except Exception as exc:
        raise RuntimeError(
            f"Could not prepare GIF '{path}': {exc}"
        ) from exc


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
