"""Make a synthetic Full-shaped ZIP and exercise the compiled Mac installer."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZipFile


def main(verifier):
    with TemporaryDirectory(prefix='installer-verifier-test-') as temp:
        root = Path(temp)
        package = root / 'Fixture.zip'
        manifest = root / 'FULL_RESULTS.json'
        receipt = root / 'INSTALL_RESULTS.json'
        base = 'Fixture'
        assets = {
            'update/update.rpf/common/data/example.meta': b'<fixture>assembly add</fixture>',
            'update/x64/dlcpacks/verify_fixture/dlc.rpf': b'Synthetic placeholder for addon path validation.',
        }
        assembly = ET.Element('package', version='2.1', target='Five')
        ET.SubElement(ET.SubElement(assembly, 'metadata'), 'name').text = 'Installer fixture'
        content = ET.SubElement(assembly, 'content')
        with ZipFile(package, 'w') as archive:
            for target, payload in assets.items():
                ET.SubElement(content, 'add', source='files/' + target).text = target
                archive.writestr(f'{base}/content/files/{target}', payload)
            archive.writestr(f'{base}/assembly.xml', ET.tostring(assembly, encoding='utf-8'))
        expected = {
            'root_folder': base,
            'sha256': sha256(package.read_bytes()).hexdigest(),
            'targets': {target: {'sha256': sha256(data).hexdigest()} for target, data in assets.items()},
        }
        manifest.write_text(json.dumps(expected), encoding='utf-8')
        args = [str(verifier), str(package), str(manifest), str(receipt)]
        subprocess.run(args, check=True)
        result = json.loads(receipt.read_text(encoding='utf-8'))
        assert result == {
            'passed': True, 'full_zip_sha256': expected['sha256'],
            'verified_payloads': 2, 'installed_plugins': 0, 'addon_packs': 1,
            'iphone_tested': False,
        }
        receipt.unlink()
        expected['targets']['update/update.rpf/common/data/example.meta']['sha256'] = '0' * 64
        manifest.write_text(json.dumps(expected), encoding='utf-8')
        failed = subprocess.run(args, capture_output=True, text=True)
        assert failed.returncode != 0 and 'payload digest mismatch' in failed.stderr
        assert not receipt.exists()
        print('Passed native install/expand/checksum tests with synthetic fixtures.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('verifier', type=Path)
    main(parser.parse_args().verifier.resolve(strict=True))
