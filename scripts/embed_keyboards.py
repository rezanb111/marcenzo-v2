#!/usr/bin/env python3
import base64, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
path = ROOT / 'keyboards/inline.py'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(base64.b64decode(open(__file__, 'rb').read().split(b"DATA_START\n", 1)[1].split(b"\nDATA_END", 1)[0] if False else b''))
# Direct write:
B64 = open(__file__).read().split('B64 = '''')[1].rsplit("'''", 1)[0] if False else None
