from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.install import MODEL, extract_model, install_model, model_complete


FILES = ('am/final.mdl', 'conf/mfcc.conf', 'conf/model.conf',
         'graph/HCLr.fst', 'graph/Gr.fst')


class InstallerTests(unittest.TestCase):
    def test_bundled_install_and_repeat_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'bundled').mkdir()
            with zipfile.ZipFile(root / 'bundled' / f'{MODEL}.zip', 'w') as z:
                for name in FILES:
                    z.writestr(f'{MODEL}/{name}', b'fixture')
            with patch('urllib.request.urlopen', side_effect=AssertionError('No download expected')):
                install_model(root)
                self.assertTrue(model_complete(root / 'models' / MODEL))
                install_model(root)

    def test_rejects_traversal_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr(f'{MODEL}/../../outside', b'bad')
            with self.assertRaises(ValueError):
                extract_model(archive, Path(tmp) / 'output')
            self.assertFalse((Path(tmp) / 'outside').exists())

    def test_rejects_incomplete_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'incomplete.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr(f'{MODEL}/am/final.mdl', b'fixture')
            with self.assertRaises(ValueError):
                extract_model(archive, Path(tmp) / 'output')

    def test_does_not_overwrite_existing_partial_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'models' / MODEL
            target.mkdir(parents=True)
            marker = target / 'user-file'
            marker.write_text('preserve')
            with self.assertRaises(RuntimeError):
                install_model(tmp)
            self.assertEqual(marker.read_text(), 'preserve')
