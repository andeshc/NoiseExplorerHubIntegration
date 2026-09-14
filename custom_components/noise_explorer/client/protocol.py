"""Wire format recovered from Explorer Hub 1.0.7.052119.

See docs/PROTOCOL.md for evidence and limits. Do not log decrypted frames.
"""

import base64
import hashlib
import json
import secrets
import string

from cryptography.hazmat.primitives import padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

DEFAULT_URL = "wss://noise-cmibro.xunkids.com:8555/svc/pipe"
PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCHlQ1eMFOWFHAF0d278lqmQvskvIjnOgk9"
    "QpMoeddV0ZsEyEe/8EjNpp+xzLa6ScftZLBJy1KIPUku1gqacAv1Cr91vS5GPrPGSEowH34"
    "ErGHCmJ6v+TV0CX+GA5l+cXsIB6qjsqeDwsuL9qy69v4bgDxwwb4BTqj4yrtC6iIhIwIDAQAB"
)


def md5(value: str) -> str:
    """The app's StrUtil.getMD5 uses uppercase, zero-padded hexadecimal."""
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest().upper()


def login_payload(email: str, password: str, client_id: str, timezone: str) -> dict:
    return {
        "ectr": "",
        "ect": "",
        "Type": 102,
        "ads": f"Android_com.noise.explorer_{client_id}_14_0_1.0.7.052119_HomeAssistant",
        "Uuid": md5(email),
        "Name": md5(email),
        "Password": md5(password),
        "countryCode": "HI",
        "region": "global",
        "loginType": 0,
        "domainCheck": 1,
        "timezone": timezone,
    }


class Codec:
    """RSA-wrapped session key followed by AES-CBC encrypted WebSocket frames."""

    def __init__(self, key: bytes | None = None):
        self.key = (
            key
            or "".join(
                secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
            ).encode()
        )
        if len(self.key) != 16:
            raise ValueError("Session key must be 16 bytes")

    def encrypt(self, message: dict) -> bytes:
        padder = padding.PKCS7(128).padder()
        data = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode()
        padded = padder.update(data) + padder.finalize()
        encryptor = Cipher(algorithms.AES(self.key), modes.CBC(self.key)).encryptor()
        return encryptor.update(padded) + encryptor.finalize()

    def handshake(self, message: dict) -> str:
        key = serialization.load_der_public_key(base64.b64decode(PUBLIC_KEY))
        return json.dumps(
            {
                "PT1": base64.b64encode(key.encrypt(self.key, rsa_padding.PKCS1v15())).decode(),
                "PT2": base64.b64encode(self.encrypt(message)).decode(),
            },
            separators=(",", ":"),
        )

    def decode(self, data: str | bytes) -> dict:
        if isinstance(data, str):
            if data.lstrip().startswith("{"):
                value = json.loads(data)
                if "PT2" not in value:
                    return value
                data = value["PT2"]
            data = base64.b64decode(data, validate=True)
        decryptor = Cipher(algorithms.AES(self.key), modes.CBC(self.key)).decryptor()
        padded = decryptor.update(data) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        value = json.loads(unpadder.update(padded) + unpadder.finalize())
        if not isinstance(value, dict):
            raise ValueError("Expected a protocol object")
        return value
