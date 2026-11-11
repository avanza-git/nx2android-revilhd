"""The GUI surfaces the useful traceback even when a frozen launcher adds noise."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from gui.runner import Porter


class RunnerErrors(TestCase):
    def finish(self, stderr, code=1):
        runner = SimpleNamespace(buf=b'', err=[stderr], event=Mock(), finished=Mock())
        Porter._done(runner, code, None)
        runner.finished.emit.assert_called_once_with(code)
        return runner.event.emit

    def test_traceback_frame_survives_frozen_launcher_noise(self):
        emitted = self.finish('Traceback (most recent call last):\n'
                              '  File "pipeline.py", line 10, in run\n'
                              'KeyError: 6\n[PYI-123:ERROR] Failed to execute script\n')
        emitted.assert_called_once_with({'ev': 'say', 'msg':
            '[RED] File "pipeline.py", line 10, in run: KeyError: 6'})

    def test_wrapper_only_error_is_still_visible(self):
        emitted = self.finish('[PYI-123:ERROR] Failed to start\n')
        self.assertIn('Failed to start', emitted.call_args.args[0]['msg'])

    def test_success_has_no_error_event(self):
        self.finish('nonfatal stderr', code=0).assert_not_called()
