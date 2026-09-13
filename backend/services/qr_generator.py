from io import BytesIO

import qrcode

from ..config import BASE_URL


def join_url(public_id: str) -> str:
    return f"{BASE_URL}/join/{public_id}"


def create_qr_png(public_id: str) -> bytes:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=4)
    qr.add_data(join_url(public_id))
    qr.make(fit=True)
    image = qr.make_image(fill_color="#07111f", back_color="#ffffff")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
