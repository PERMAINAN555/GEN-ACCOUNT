# lib/proto.py
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

XOR_KEY = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
           0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]


def write_varint(value: int) -> bytes:
    out = []
    while value > 127:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def write_varint_field(f, v):
    return write_varint((f << 3) | 0) + write_varint(v)


def write_string_field(f, v):
    b = v.encode("utf-8") if isinstance(v, str) else v
    return write_varint((f << 3) | 2) + write_varint(len(b)) + b


def write_bytes_field(f, v):
    return write_varint((f << 3) | 2) + write_varint(len(v)) + v


def assemble_proto(fields):
    data = bytearray()
    for k, v in fields.items():
        if isinstance(v, int):
            data.extend(write_varint_field(k, v))
        elif isinstance(v, str):
            data.extend(write_string_field(k, v))
        elif isinstance(v, bytes):
            data.extend(write_bytes_field(k, v))
    return bytes(data)


def read_varint(data, offset):
    r, s = 0, 0
    while True:
        b = data[offset]; offset += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80):
            break
        s += 7
    return r, offset


def parse_proto(data):
    out = {}
    off = 0
    while off < len(data):
        try:
            tag, off = read_varint(data, off)
        except Exception:
            break
        f = tag >> 3
        w = tag & 0x7
        if f == 0:
            break
        try:
            if w == 0:
                v, off = read_varint(data, off)
                out[f] = v
            elif w == 2:
                ln, off = read_varint(data, off)
                val = data[off:off + ln]
                off += ln
                try:
                    out[f] = val.decode("utf-8")
                except Exception:
                    out[f] = val.hex()
            else:
                break
        except Exception:
            break
    return out


def aes_encrypt(plain):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain, AES.block_size))


def aes_decrypt(ciphertext):
    if not ciphertext or len(ciphertext) % 16 != 0:
        return ciphertext
    try:
        try:
            return unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(ciphertext),
                         AES.block_size)
        except ValueError:
            return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(ciphertext)
    except Exception:
        return ciphertext


def xor_open_id(open_id: str) -> bytes:
    b = open_id.encode("utf-8")
    return bytes(x ^ XOR_KEY[i % len(XOR_KEY)] for i, x in enumerate(b))
