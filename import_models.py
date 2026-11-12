#!/usr/bin/env python3
"""Build the two pinned local-only standalone ped DLC RPFs from author downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import zipfile
import zlib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent

SPECS = [
    {
        'archive_bytes': 23937214,
        'archive_sha256': '805e1a7171bea854b3b4aa062525bcd19dad9687a405a06d5651f351f01f39db',
        'original_name': 'xingganmeinv', 'model': 'xingganmeinv', 'pack': 'rdebeauty',
        'resources': {
            'ydd': (3428288, '3319804ac9fb205b58075d53eb634b7caba0f4988b88e2399d03396c8498cf4f'),
            'yft': (13119, '0d10489d0578956a8f46d9c47d1eb4d23b332fce53eefe38359e81af0cfe9e2e'),
            'ymt': (804, '854e2a6f163e00c8a3ecd40142928141994730026c135e2e8b81fcca034ed05c'),
            'ytd': (14206078, '073ab86c0cc020641fa489f9dd604083bb64438bf1f52369477de07721f3827e'),
        },
        'expected_dlc_sha256': '0e10c780e8aae6e16aa67530e37afa637d2ff03204e42f8bcb552623ab23edff',
    },
    {
        'archive_bytes': 7947253,
        'archive_sha256': 'b6385a7cb9e1c4142cf4b2eb3ae6c349c194f7f92b89b92864d2a2b94831948b',
        'original_name': 'TsukushiFortuneDOA', 'model': 'tsukushifortunedoa', 'pack': 'rdetfortune',
        'resources': {
            'ydd': (2194905, '12edb249c89e17bf0e208a36d785b8b0fb0449bb9f7e46b18d0b22f84623b3df'),
            'yft': (14928, 'ce2715d0f21c811da6672f37c8fca14cecddd528f0370d6183dc8dbf3a03f8c1'),
            'ymt': (2001, 'c68034315cc76207e403f2bf486161af234bcf44f73644dde3bbe12bf08dcd36'),
            'ytd': (3339762, 'ef6f0c8e73ede45cc1023be7266d998ec08c12c81dd5e49a3fdc14e5b80e1d35'),
        },
        'expected_dlc_sha256': 'd23bfa9871830dbb6bdff9aa642b2bbf10ddd553fb1b3807c2626f6544e46dce',
        'skeleton_edit': {'offset': 3707412, 'before': 'cd' * 12, 'after': '00' * 12},
    },
]
RESOURCE_EXTS = {'ydd', 'yft', 'ymt', 'ytd'}
V14_SCRIPT_OVERLAY_BYTES = 6155264
V14_SCRIPT_OVERLAY_SHA256 = '79db674e0aba7887aa199f07675828c2710ff248a47cfd813c6e8cbafd8a31e8'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(data) + compressor.flush()


def flag_size(flags: int) -> int:
    base = 0x200 << (flags & 15)
    return base * (((flags >> 27) & 1) + ((flags >> 26) & 1) * 2 +
                   ((flags >> 25) & 1) * 4 + ((flags >> 24) & 1) * 8 +
                   ((flags >> 17) & 127) * 16 + ((flags >> 11) & 63) * 32 +
                   ((flags >> 7) & 15) * 64 + ((flags >> 5) & 3) * 128 +
                   ((flags >> 4) & 1) * 256)


class Resource:
    """Minimal legacy RSC7 reader for page flags and drawable skeleton pointers."""
    def __init__(self, raw: bytes):
        if raw[:4] != b'RSC7' or len(raw) < 16:
            raise ValueError('Expected RSC7 resource')
        self.raw = raw
        self.version, self.system_flags, self.graphics_flags = struct.unpack_from('<III', raw, 4)
        self.system_size = flag_size(self.system_flags)
        self.graphics_size = flag_size(self.graphics_flags)
        self.data = zlib.decompress(raw[16:], -15)
        if len(self.data) != self.system_size + self.graphics_size:
            raise ValueError('RSC7 decompressed size does not match page flags')
        page_map = self.ptr(8)
        if page_map is None or page_map + 10 > self.system_size:
            raise ValueError('Invalid resource page map')
        expected = (self.page_count(self.system_flags), self.page_count(self.graphics_flags))
        actual = tuple(self.data[page_map + 8:page_map + 10])
        if actual != expected:
            raise ValueError(f'Resource page map mismatch: {actual} != {expected}')

    @staticmethod
    def page_count(flags: int) -> int:
        return (((flags >> 4) & 1) + ((flags >> 5) & 3) + ((flags >> 7) & 15) +
                ((flags >> 11) & 63) + ((flags >> 17) & 127) + ((flags >> 24) & 1) +
                ((flags >> 25) & 1) + ((flags >> 26) & 1) + ((flags >> 27) & 1))

    def off(self, pointer: int):
        if pointer == 0:
            return None
        segment = pointer & 0xf0000000
        if segment not in (0x50000000, 0x60000000):
            raise ValueError(f'Unexpected RSC pointer segment: {pointer:#x}')
        offset = (pointer & 0x0fffffff) + (self.system_size if segment == 0x60000000 else 0)
        if offset >= len(self.data):
            raise ValueError('RSC pointer outside decompressed resource')
        return offset

    def ptr(self, offset: int):
        if offset < 0 or offset + 8 > len(self.data):
            raise ValueError('RSC pointer field outside decompressed resource')
        return self.off(struct.unpack_from('<Q', self.data, offset)[0])

    def drawable_skeletons(self):
        hashes, count = self.ptr(0x20), struct.unpack_from('<H', self.data, 0x28)[0]
        draw_ptr, draw_count = self.ptr(0x30), struct.unpack_from('<H', self.data, 0x38)[0]
        if count != draw_count or count > 4096 or (count and (hashes is None or draw_ptr is None)):
            raise ValueError('Unexpected YDD drawable arrays')
        result = []
        for i in range(count):
            drawable = self.ptr(draw_ptr + i * 8)
            if drawable is None:
                raise ValueError('Null drawable in YDD')
            skeleton = self.ptr(drawable + 0x18)
            if skeleton is not None:
                bones = self.ptr(skeleton + 0x20)
                bone_count = struct.unpack_from('<H', self.data, skeleton + 0x5e)[0]
                if bone_count != 104 or bones is None or bones < 16 or bones + bone_count * 80 > self.system_size:
                    raise ValueError('Unexpected selected-model skeleton layout')
                result.append((bones - 16, bone_count))
        return result


def read_original(archive: Path, spec: dict) -> dict[str, bytes]:
    if archive.stat().st_size != spec['archive_bytes'] or sha(archive.read_bytes()) != spec['archive_sha256']:
        raise ValueError(f'Original archive SHA-256/size mismatch: {archive}')
    found: dict[str, bytes] = {}

    def accept(member: str, data: bytes):
        path = PurePosixPath(member.replace('\\', '/'))
        if path.is_absolute() or '..' in path.parts:
            raise ValueError(f'Unsafe archive path: {member!r}')
        ext = path.suffix.lower().lstrip('.')
        if path.stem.casefold() != spec['original_name'].casefold() or ext not in RESOURCE_EXTS:
            return
        if ext in found:
            raise ValueError(f'Duplicate selected resource: {ext}')
        size, digest = spec['resources'][ext]
        if len(data) != size or sha(data) != digest:
            raise ValueError(f'Pinned resource SHA-256 mismatch: {path.name}')
        found[ext] = data

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            if len(z.infolist()) > 1000 or z.testzip() is not None:
                raise ValueError('ZIP CRC failure or unreasonable entry count')
            for info in z.infolist():
                if info.is_dir():
                    continue
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('ZIP symlinks are not accepted')
                if info.file_size > 64 * 1024 * 1024:
                    raise ValueError('Oversized ZIP member')
                accept(info.filename, z.read(info))
    else:
        try:
            import libarchive
            from importlib.metadata import version
        except ImportError as e:
            raise SystemExit('RAR extraction needs libarchive-c >= 5.3 and a system libarchive library') from e
        if tuple(int(x) for x in version('libarchive-c').split('.')[:2]) < (5, 3):
            raise SystemExit('RAR extraction needs libarchive-c >= 5.3')
        with libarchive.file_reader(str(archive)) as entries:
            for entry in entries:
                if not entry.isfile:
                    continue
                if entry.size > 64 * 1024 * 1024:
                    raise ValueError('Oversized RAR member')
                accept(entry.pathname, b''.join(entry.get_blocks()))
    if set(found) != RESOURCE_EXTS:
        raise ValueError(f'Archive must contain the complete pinned four-file model; found {sorted(found)}')
    return found


def normalize_tsukushi(raw: bytes, spec: dict) -> tuple[bytes, list[dict]]:
    expected = spec['skeleton_edit']
    resource = Resource(raw)
    if not any(offset + 4 == expected['offset'] for offset, _count in resource.drawable_skeletons()):
        raise ValueError('Pinned Tsukushi reserved-field offset is not a located drawable skeleton')
    data = bytearray(resource.data)
    start = expected['offset']
    end = start + len(bytes.fromhex(expected['before']))
    if data[start:end] != bytes.fromhex(expected['before']):
        raise ValueError('Pinned Tsukushi reserved bytes do not match the original')
    data[start:end] = bytes.fromhex(expected['after'])
    normalized = raw[:16] + raw_deflate(bytes(data))
    check = Resource(normalized)
    changed = [i for i, (a, b) in enumerate(zip(resource.data, check.data)) if a != b]
    intended = list(range(start, end))
    if len(check.data) != len(resource.data) or changed != intended:
        raise ValueError('Tsukushi normalization changed unexpected decompressed bytes')
    return normalized, [{'offset': start, 'length': end - start, 'before': expected['before'], 'after': expected['after']}]


def build_open_rpf(files: dict[str, bytes], *, allow_extended: bool = False) -> bytes:
    """Build an OPEN RPF7 archive; nested 7FPR files are deflated, RSC7 files stored."""
    directories = {''}
    for name in files:
        path = PurePosixPath(name)
        if not name or path.is_absolute() or str(path) != name or '\\' in name or any(p in ('.', '..') for p in path.parts):
            raise ValueError(f'Unsafe/non-canonical RPF path: {name!r}')
        directories.update(str(p) for p in path.parents if str(p) != '.')
    if directories & set(files):
        raise ValueError('RPF file also used as a directory')
    all_paths = directories | set(files)
    nodes = [{'path': '', 'name': '', 'dir': True}]
    cursor = 0
    while cursor < len(nodes):
        node = nodes[cursor]
        if node['dir']:
            children = sorted(p for p in all_paths if p and
                ((str(PurePosixPath(p).parent).replace('.', '', 1) if PurePosixPath(p).parent == PurePosixPath('.') else str(PurePosixPath(p).parent)) == node['path']))
            node['start'], node['count'] = len(nodes), len(children)
            nodes.extend({'path': p, 'name': PurePosixPath(p).name, 'dir': p in directories} for p in children)
        cursor += 1
    names = bytearray()
    for node in nodes:
        node['name_at'] = len(names)
        names.extend(node['name'].encode('utf-8') + b'\0')
    names.extend(bytes((-len(names)) % 16))
    if len(names) > 65535:
        raise ValueError('RPF name table too large')
    header_size = 16 + len(nodes) * 16 + len(names)
    body = bytearray((header_size + 511) & ~511)
    toc = bytearray()
    for node in nodes:
        name_at = node['name_at']
        if node['dir']:
            toc.extend(struct.pack('<IIII', name_at, 0x7fffff00, node['start'], node['count']))
            continue
        data = files[node['path']]
        offset = len(body) // 512
        if offset >= 0x7fffff:
            raise ValueError('RPF offset out of range')
        if data.startswith(b'RSC7'):
            if len(data) < 16:
                raise ValueError('Truncated RSC7 header')
            version, low, high = struct.unpack_from('<III', data, 4)
            if version != (((low >> 28) << 4) | (high >> 28)):
                raise ValueError('RSC7 resource version/page flags mismatch')
            payload, size, resource_bit = data, len(data), 0x80000000
        elif data.startswith(b'7FPR'):
            payload, size, low, high, resource_bit = data, 0, len(data), 0, 0
        else:
            payload = raw_deflate(data)
            size, low, high, resource_bit = len(payload), len(data), 0, 0
        if not resource_bit and size == 0 and len(payload) > 0xffffffff:
            raise ValueError('Nested archive exceeds 32-bit field')
        if resource_bit and len(payload) >= 0xffffff:
            if not allow_extended or len(payload) > 0xffffffff:
                raise ValueError('Extended RPF resource size is not enabled/supported')
            encoded = bytearray(payload)
            for shift, at in enumerate((7, 14, 5, 2)):
                encoded[at] = (len(payload) >> (8 * shift)) & 255
            payload, size = bytes(encoded), 0xffffff
        a = name_at | ((size & 0xffff) << 16)
        b = (size >> 16) | (offset << 8) | resource_bit
        toc.extend(struct.pack('<IIII', a, b, low, high))
        body.extend(payload)
        body.extend(bytes((-len(body)) % 512))
    body[:16] = struct.pack('<4sIII', b'7FPR', len(nodes), len(names), 0x4e45504f)
    body[16:16 + len(toc)] = toc
    body[16 + len(toc):16 + len(toc) + len(names)] = names
    return bytes(body)


def metadata(pack: str, model: str) -> dict[str, bytes]:
    peds = (ROOT / 'templates/peds.meta').read_text(encoding='utf-8').replace('lunav', model)
    content = (ROOT / 'templates/content.xml').read_text(encoding='utf-8')
    setup = (ROOT / 'templates/setup2.xml').read_text(encoding='utf-8')
    for old, new in [('dlc_rdeluna', 'dlc_' + pack), ('luna_peds', 'selected_peds'), ('RDELUNA', pack.upper())]:
        content = content.replace(old, new)
    for old, new in [('dlc_rdeluna', 'dlc_' + pack), ('RDELUNA', pack.upper())]:
        setup = setup.replace(old, new)
    for text in (peds, content, setup):
        ET.fromstring(text)
    return {'common/data/peds.meta': peds.encode(), 'content.xml': content.encode(), 'setup2.xml': setup.encode()}


def make_oiv(files: dict[str, bytes]) -> bytes:
    """Wrap exactly the two model DLCs and supplied menu-script overlay as NativeOIV."""
    targets = {
        'x64.rpf/levels/gta5/script/script_wasm.rpf': 'script_wasm.rpf',
        'update/x64/dlcpacks/rdebeauty/dlc.rpf': 'rdebeauty.rpf',
        'update/x64/dlcpacks/rdetfortune/dlc.rpf': 'rdetfortune.rpf',
    }
    if set(files) != set(targets):
        raise ValueError('NativeOIV must contain exactly the script overlay and two model DLCs')
    package = ET.Element('package', {'version': '2.1', 'id': '804D3D10-244D-4E32-8896-40AA30E60A2B', 'target': 'Five'})
    meta = ET.SubElement(package, 'metadata')
    ET.SubElement(meta, 'name').text = 'Selected Models Personal Import Adapter'
    version = ET.SubElement(meta, 'version')
    ET.SubElement(version, 'major').text = '1'
    ET.SubElement(version, 'minor').text = '0'
    ET.SubElement(meta, 'author').text = 'KaKa_946 / StrideR; local integration adapter'
    ET.SubElement(meta, 'description').text = (
        'Personal local install: two author archives plus supplied v1.4 phone menu script. '
        'Requires the v1.3 Rebuilt Full base. Do not redistribute author-restricted models.'
    )
    content = ET.SubElement(package, 'content')
    for target in targets:
        source = 'files/' + target
        ET.SubElement(content, 'add', {'source': source}).text = target
    assembly = ET.tostring(package, encoding='utf-8', xml_declaration=True)
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr('assembly.xml', assembly)
        for target, name in targets.items():
            z.writestr('content/files/' + target, files[target])
    result = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        expected_names = {'assembly.xml'} | {'content/files/' + path for path in targets}
        if set(z.namelist()) != expected_names or z.testzip() is not None:
            raise ValueError('NativeOIV ZIP members or CRC do not match the three-target layout')
        parsed = ET.fromstring(z.read('assembly.xml'))
        declared = {node.text: node.attrib['source'] for node in parsed.findall('content/add')}
        if declared != {path: 'files/' + path for path in targets}:
            raise ValueError('NativeOIV assembly targets do not match payload paths')
        for path in targets:
            archived = z.read('content/files/' + path)
            if sha(archived) != sha(files[path]):
                raise ValueError(f'NativeOIV payload readback mismatch: {path}')
    return result


def build_one(files: dict[str, bytes], spec: dict) -> tuple[bytes, dict]:
    files = dict(files)
    edits = []
    if 'skeleton_edit' in spec:
        files['ydd'], edits = normalize_tsukushi(files['ydd'], spec)
    else:
        # Verify the pinned model resource is readable while retaining every original byte.
        Resource(files['ydd'])
    ped_rpf = build_open_rpf({f"{spec['model']}.{ext}": raw for ext, raw in files.items()}, allow_extended=True)
    root_files = {
        'x64/models/cdimages/selected_peds.rpf': ped_rpf,
        **metadata(spec['pack'], spec['model']),
    }
    result = build_open_rpf(root_files, allow_extended=True)
    actual = sha(result)
    if actual != spec['expected_dlc_sha256']:
        raise ValueError(f"Built DLC SHA-256 mismatch for {spec['pack']}: {actual}")
    record = {'pack': spec['pack'], 'model': spec['model'],
              'bytes': len(result), 'sha256': actual, 'skeleton_reserved_edits': edits,
              'resource_sha256': {ext: sha(data) for ext, data in files.items()}}
    return result, record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sexy-beauty', required=True, type=Path, help='Original KaKa_946 ZIP from the author listing')
    p.add_argument('--tsukushi', required=True, type=Path, help='Original StrideR RAR from the author listing')
    p.add_argument('--output', type=Path, default=Path('build'),
                   help='Empty/new staging root; writes update/x64/dlcpacks/<pack>/dlc.rpf')
    p.add_argument('--script-overlay', type=Path,
                   help='Optional v1.4 script_wasm.rpf overlay; when set, also builds a 3-target NativeOIV')
    args = p.parse_args()
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        raise SystemExit('Output path must be new or an empty directory; refusing to overwrite existing files')
    # Validate both author archives before staging either DLC.
    originals = [read_original(archive, spec) for archive, spec in
                 zip((args.sexy_beauty, args.tsukushi), SPECS)]
    built = [build_one(resources, spec) for resources, spec in zip(originals, SPECS)]
    overlay = None
    if args.script_overlay is not None:
        if not args.script_overlay.is_file():
            raise SystemExit('script overlay path is not a file')
        overlay = args.script_overlay.read_bytes()
        if (len(overlay) != V14_SCRIPT_OVERLAY_BYTES or sha(overlay) != V14_SCRIPT_OVERLAY_SHA256
                or not overlay.startswith(b'7FPR')):
            raise SystemExit('script overlay is not the pinned v1.4 script_wasm.rpf RPF7 archive')
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    oiv_files = {}
    for spec, (blob, record) in zip(SPECS, built):
        rel = PurePosixPath('update/x64/dlcpacks') / spec['pack'] / 'dlc.rpf'
        target = args.output.joinpath(*rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        results.append({**record, 'file': str(target)})
        oiv_files[rel.as_posix()] = blob
    if overlay is not None:
        oiv_files['x64.rpf/levels/gta5/script/script_wasm.rpf'] = overlay
        oiv = make_oiv(oiv_files)
        oiv_path = args.output / 'Selected_Models_Personal_Import.oiv'
        oiv_path.write_bytes(oiv)
        results.append({'native_oiv': str(oiv_path), 'bytes': len(oiv), 'sha256': sha(oiv),
                        'zip_crc_readback': 'passed', 'target_sha256':
                            {path: sha(data) for path, data in sorted(oiv_files.items())}})
    report = {'outputs': results, 'contains_third_party_assets_in_source': False, 'uploaded': False}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
