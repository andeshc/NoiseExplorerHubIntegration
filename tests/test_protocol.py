import base64
import json

import pytest
from client.protocol import Codec, login_payload, md5


def test_login_matches_app_uppercase_hash_and_fields():
    result = login_payload("parent@example.test", "password", "client01", "UTC+05:30")
    assert md5("password") == "5F4DCC3B5AA765D61D8327DEB882CF99"
    assert result["Name"] == result["Uuid"] == md5("parent@example.test")
    assert result["Type"] == 102 and result["loginType"] == 0
    assert result["countryCode"] == "HI" and result["region"] == "global"
    assert "parent@example.test" not in json.dumps(result)


@pytest.mark.parametrize(
    "message", [{"CID": 1, "SN": 5}, {"PL": {"name": "हेलो", "x": 0}}, {"PL": [1, 2]}]
)
def test_codec_all_frame_types(message):
    codec = Codec(b"0123456789abcdef")
    encrypted = codec.encrypt(message)
    assert codec.decode(encrypted) == message
    assert codec.decode(base64.b64encode(encrypted).decode()) == message
    assert codec.decode(json.dumps(message)) == message
    handshake = json.loads(codec.handshake(message))
    assert len(base64.b64decode(handshake["PT1"])) == 128
    assert codec.decode(handshake["PT2"]) == message
    assert codec.decode(json.dumps(handshake)) == message


def test_bad_ciphertext_fails_closed():
    with pytest.raises(ValueError):
        Codec().decode(b"bad-frame")
    with pytest.raises(ValueError):
        Codec(b"short")


def test_random_key_per_connection():
    assert Codec().key != Codec().key


def test_aes_ciphertext_matches_independent_openssl_vector():
    # Produced independently using openssl enc -aes-128-cbc with the app's
    # key=IV convention, PKCS7 padding, and UTF-8 {"CID":1,"SN":5} without LF.
    expected = "j5nn881OlEa3yvh5D7FFdcnwJvPo2dEd8XYyrI3Zw8E="
    encrypted = Codec(b"0123456789abcdef").encrypt({"CID": 1, "SN": 5})
    assert base64.b64encode(encrypted).decode() == expected
