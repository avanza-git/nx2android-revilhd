"""shader_split.mtarc_members: MT Framework ARC archives of version 7 (The Great Ace Attorney Chronicles) and 9 (Resident Evil HD), built here, and an unknown version refused"""
import struct, sys, unittest, zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_shader_split_cmp import load_split   # noqa: E402


def arc(ver, members):
    esz, plen = {7: (0x90, 0x80), 9: (0x54, 0x40)}[ver]
    head, body, off = b'ARC\0' + struct.pack('<HH', ver, len(members)), b'', 0x8000
    ents = b''
    for path, data, packed in members:
        stored = zlib.compress(data) if packed else data
        p = path.encode('latin-1').ljust(plen, b'\0')
        if ver == 7: ents += p + struct.pack('<4I', 0x7808EA10, len(stored), len(data) | 0x40000000, off + len(body))
        else: ents += p + struct.pack('<5I', 0x7808EA10, len(stored), len(data), 2, off + len(body))
        body += stored
    d = head + ents
    assert len(d) == 8 + esz * len(members)
    return d.ljust(off, b'\0') + body


class MtArc(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.s = load_split()

    MEMBERS = [('movie\\fullscreen', b'x' * 16, True), ('sc\\NX_64\\root', b'SPK\0' + bytes(range(200)), True), ('raw\\stored', b'abc', False)]

    def check(self, ver):
        got = list(self.s.mtarc_members(arc(ver, self.MEMBERS), '/t.arc'))
        self.assertEqual(got, [(p.replace('\\', '/'), d) for p, d, _ in self.MEMBERS])

    def test_version_7(self): self.check(7)
    def test_version_9(self): self.check(9)

    def test_unknown_version(self):
        d = bytearray(arc(9, self.MEMBERS)); d[4] = 8
        with self.assertRaises(SystemExit): list(self.s.mtarc_members(bytes(d), '/t.arc'))


if __name__ == '__main__':
    unittest.main()
