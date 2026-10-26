import json
import os
import tempfile
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import AsyncMock, patch

import numpy as np

from voice import Speaker


class VoiceStudioTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((self.path, payload, self.headers.get('Authorization')))
                self.send_response(200)
                self.send_header('Content-Type', 'audio/pcm')
                self.end_headers()
                self.wfile.write(np.array([0, 1000, -1000] * 100, dtype='<i2').tobytes())

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.dst = os.path.join(self.tmp.name, 'speech.wav')
        self.speaker = Speaker({'tts_engine': 'voicestudio', 'voice_fx': 0,
                                'voicestudio_url': f'http://127.0.0.1:{self.server.server_port}',
                                'voicestudio_voice': 'Капри', 'voice_rate': '+10%'})

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def test_http_contract_and_wav(self):
        with patch.dict(os.environ, {'VOICESTUDIO_API_KEY': 'test-only'}):
            self.assertEqual(self.speaker.render('Привет!', self.dst), self.dst)
        path, body, auth = self.requests[0]
        self.assertEqual(path, '/v1/audio/speech')
        self.assertEqual(auth, 'Bearer test-only')
        self.assertEqual(body, dict(model='omnivoice', voice='Капри', input='Привет!',
                                    language='ru', response_format='pcm', speed=1.1))
        with wave.open(self.dst) as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()),
                             (24000, 1, 2))
            self.assertGreater(audio.getnframes(), 0)

    def test_long_text_keeps_all_words_within_api_limit(self):
        text = 'слово ' * 1800
        self.speaker.render_voicestudio(text, self.dst)
        parts = [r[1]['input'] for r in self.requests]
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(0 < len(p) <= 4096 for p in parts))
        self.assertEqual(' '.join(parts).split(), text.split())

    def test_cancelled_before_request_does_not_play(self):
        self.speaker.stop()
        with patch('voice.play_mp3') as play:
            self.assertTrue(self.speaker._edge('Привет'))
        self.assertEqual(self.requests, [])
        play.assert_not_called()

    def test_api_error_falls_back_to_edge(self):
        with patch.object(self.speaker, 'render_voicestudio', side_effect=OSError('offline')), \
             patch('edge_tts.Communicate') as communicate, \
             patch('voice.decode', return_value=np.zeros(300, dtype=np.float32)):
            communicate.return_value.save = AsyncMock()
            self.assertEqual(self.speaker.render('Привет', self.dst), self.dst)
            communicate.return_value.save.assert_awaited()


if __name__ == '__main__':
    unittest.main()
