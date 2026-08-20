import hid
import time

def prepare_chunks(blob: bytes) -> list[bytes]:
    #Making chunks from blob
    
    #Cutting blob to chunks
    chunks = []
    for chunk in range (0, len(blob), 1024):
        chunks.append(blob[chunk:chunk+1024])
    
    #Добиваем последний чанк(не знаю как на английском)
    chunks[-1] = chunks[-1].ljust(1024, b"\x00")
    return chunks

def send_commands() -> None:
    #Opening device
    dev = hid.device()
    dev.open(0x2000,0x3000)
    
    #Sending spesial commands
    report = "00"
    crt = "4352540000"
    dis = bytes.fromhex(report + crt + "444953").ljust(1025,b"\x00")
    lig = bytes.fromhex(report + crt + "4c4947000062").ljust(1025,b"\x00")
    
    dev.write(dis)
    dev.write(lig)
    #dev.write(lig)

    dev.close()

def send_image(chunks) -> None:
    dev = hid.device()
    dev.open(0x2000,0x3000)
    #Writing data
    while True:
        for chunk in chunks:
            dev.write(b"\x00" + chunk)
            time.sleep(0.003)