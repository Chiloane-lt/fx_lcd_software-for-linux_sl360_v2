import hid
import time

from image import prepare_blob

def prepare_chunks(blob: bytes) -> list[bytes]:
    #Making chunks from blob
    
    #Cutting blob to chunks
    chunks = []
    for chunk in range (0, len(blob), 1024):
        chunks.append(blob[chunk:chunk+1024])
    
    #finishing up the last chunk
    chunks[-1] = chunks[-1].ljust(1024, b"\x00")
    return chunks

def send_commands() -> None:
    #Opening device
    dev = hid.device()
    VID=0x2000
    PID=0x3002
    dev.open(VID,PID)
    
    #Sending spesial commands
    report = "00"
    crt = "4352540000"
    lig = bytes.fromhex(report + crt + "4c4947000064").ljust(1025,b"\x00")
    
    dev.write(lig)

    dev.close()

def send_image(chunks) -> None:
    dev = hid.device()
    VID=0x2000
    PID=0x3002
    dev.open(VID,PID)
    #Writing data
    while True:
        for chunk in chunks:
            dev.write(bytes([0]) + chunk)
            time.sleep(0.003)

def send_gif(
    frames,
    debug_timing: bool = False,
    chunk_delay: float = 0.0,
) -> None:
    dev = hid.device()
    VID = 0x2000
    PID = 0x3002

    try:
        dev.open(VID, PID)

        frame_number = 0

        while True:
            for chunks, duration_ms in frames:
                frame_number += 1
                frame_start = time.monotonic()

                for chunk in chunks:
                    dev.write(bytes([0]) + chunk)
                    if chunk_delay > 0:
                        time.sleep(chunk_delay)

                transmission_ms = (time.monotonic() - frame_start) * 1000
                remaining = duration_ms - transmission_ms

                if debug_timing:
                    print(
                        f"Frame {frame_number}: "
                        f"target={duration_ms} ms, "
                        f"transmission={transmission_ms:.1f} ms, "
                        f"wait={max(0, remaining):.1f} ms, "
                        f"chunks={len(chunks)}",
                        flush=True,
                    )

                if remaining > 0:
                    time.sleep(remaining / 1000)

    finally:
        dev.close()

def send_video(
    first_frame,
    frames,
    debug_timing: bool = False,
    chunk_delay: float = 0.0,
) -> None:
    """Stream a video to the LCD, starting with its prepared first frame."""
    from itertools import chain

    dev = hid.device()
    VID = 0x2000
    PID = 0x3002

    try:
        dev.open(VID, PID)


        for frame_number, (jpeg_bytes, duration_ms) in enumerate(
            chain((first_frame,), frames), start=1
        ):
            frame_start = time.monotonic()

            chunks = prepare_chunks(prepare_blob(jpeg_bytes))

            for chunk in chunks:
                dev.write(bytes([0]) + chunk)
                if chunk_delay > 0:
                    time.sleep(chunk_delay)

            elapsed_ms = (time.monotonic() - frame_start) * 1000
            remaining_ms = duration_ms - elapsed_ms

            if debug_timing:
                print(
                    f"Frame {frame_number}: target={duration_ms:.1f} ms, "
                    f"transmission={elapsed_ms:.1f} ms, "
                    f"wait={max(0, remaining_ms):.1f} ms",
                    flush=True,
                )

            if remaining_ms > 0:
                time.sleep(remaining_ms / 1000)

    finally:
        dev.close()
