"""The standalone desktop project must not reuse upstream signing material."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from porter import paths


class ProjectPaths(unittest.TestCase):
    def test_explicit_home_isolates_settings_tools_and_signing(self):
        with tempfile.TemporaryDirectory() as tmp:
            own = Path(tmp) / 'own'
            upstream = Path(tmp) / 'upstream'
            upstream.mkdir()
            (upstream / 'signing-key.json').write_text('upstream sentinel')
            with patch.dict(os.environ, {'RE_NATIVE_HOME': str(own), 'NX2A_HOME': str(upstream)}):
                self.assertEqual(paths.user_dir(), own)
                self.assertEqual(paths.player_tools(), own / 'toolchains')
                self.assertEqual(paths.signing_key(), own / 'signing-key.json')
                self.assertFalse(paths.signing_key().exists())
            self.assertEqual((upstream / 'signing-key.json').read_text(), 'upstream sentinel')

    def test_default_ignores_upstream_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env.pop('RE_NATIVE_HOME', None)
            env['NX2A_HOME'] = str(Path(tmp) / 'upstream')
            with patch.dict(os.environ, env, clear=True), patch.object(paths.sys, 'platform', 'darwin'), patch.object(paths.Path, 'home', return_value=Path(tmp)):
                self.assertEqual(paths.user_dir(), Path(tmp) / 'Library/Application Support/resident-evil-native')
                self.assertFalse((Path(tmp) / 'upstream').exists())
