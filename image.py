from PIL import Image
from io import BytesIO

#Convertes and resizes users image
def get_images_bytes(path: str | None = None, rotate: int = 0) -> bytes:
    #Preparing image
    img = Image.open(path)
    #user can rotate image
    if rotate:
        img = img.rotate(-rotate, expand = True)
    if img.size != (480, 480):
        print("resizing image")
        img = img.resize((480, 480))
    img = img.convert("RGB")
    #Getting images bytes
    buffer = BytesIO()
    img.save(buffer, "JPEG", quality = 80, subsampling=2, dpi=(96, 96))
    jpeg_bytes = buffer.getvalue()
    return jpeg_bytes

#Prepares blob
def prepare_blob (jpeg_bytes: bytes) -> bytes:
    #Making blobs head
    
    #Vendors special commands
    crt = "4352540000"
    dra = "4452410000"

    #Two bytes shows jpeg and heads lenght to display
    two_bytes = (len(jpeg_bytes) + 32).to_bytes(2, "big")
    
    head = bytes.fromhex(crt) + bytes.fromhex(dra) + two_bytes + b"\xb1" + b"\x00" * 19
    
    #Making blob
    blob = head + jpeg_bytes
    
    return blob