import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from app import design, htmlsafe, mjml_engine, provider, translate
from app.main import app


class ContentTests(unittest.TestCase):
    def test_redesign_batch_keeps_exact_original_and_two_related_designs(self):
        source = '<p>Original &amp; unchanged {{first_name}}</p>'
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'FACTORY_DB': directory + '/test.sqlite3'}), patch('app.translate.make_redesign', return_value={'html': '<p>New layout</p>', 'mode': 'mock', 'kind': 'redesign'}):
            client = TestClient(app)
            first = client.post('/api/redesign', json={'template_html': source, 'amount': 2}).json()
            self.assertEqual(first['source']['html'], source)
            self.assertEqual(first['source']['status'], 'pending')
            self.assertEqual(len(first['variants']), 2)
            self.assertTrue(all(v['of_source'] == first['source']['id'] for v in first['variants']))
            self.assertEqual(len({v['comparison_id'] for v in first['variants']}), 1)
            again = client.post('/api/redesign', json={'template_html': source, 'source_id': first['source']['id'], 'amount': 2}).json()
            self.assertEqual(again['source']['id'], first['source']['id'])
            self.assertNotEqual(again['variants'][0]['comparison_id'], first['variants'][0]['comparison_id'])
            changed = client.post('/api/redesign', json={'template_html': '<p>Edited input</p>', 'source_id': first['source']['id'], 'amount': 2}).json()
            self.assertNotEqual(changed['source']['id'], first['source']['id'])
            from app import store
            self.assertEqual(store.get(first['source']['id'])['html'], source)

    def test_translation_preserves_markup_css_comments_and_urls(self):
        source = ('<!doctype html><html><head><style>p { color: red }</style></head>'
                  '<body><!-- Outlook --><p title="keep">Hello &amp; welcome {{first_name}}</p>'
                  '<a href="{{training_url}}">Open guide</a></body></html>')
        def complete(key, model, messages, **kwargs):
            texts = json.loads(messages[1]['content'])['texts']
            self.assertEqual(texts, ['Hello & welcome ⦑PH0⦒', 'Open guide'])
            self.assertEqual(kwargs['schema']['required'], ['texts'])
            return json.dumps({'texts': ['স্বাগতম ⦑PH0⦒', 'নির্দেশিকা খুলুন']})
        with patch('app.provider.complete', side_effect=complete):
            result = translate.translate_and_brand(source, '', 'Bangla', api_key='test', model='test')
        self.assertEqual(result['mode'], 'openrouter')
        self.assertEqual(result['html'], source.replace('Hello &amp; welcome {{first_name}}',
                                                       'স্বাগতম {{first_name}}').replace('Open guide', 'নির্দেশিকা খুলুন'))

    def test_translation_rejects_missing_moved_or_invented_tokens(self):
        source = '<p>Hello {{first_name}}</p><p>Welcome</p>'
        for texts in (['Hello', 'Welcome'], ['Hello', 'Welcome ⦑PH0⦒'],
                      ['Hello ⦑PH0⦒ {{new_token}}', 'Welcome'], ['only one']):
            with self.subTest(texts=texts), patch('app.provider.complete', return_value=json.dumps({'texts': texts})):
                result = translate.translate_and_brand(source, '', 'Bangla', api_key='test')
                self.assertEqual(result['mode'], 'error')
                self.assertEqual(result['html'], source)

    def test_entities_without_semicolons_do_not_corrupt_following_markup(self):
        source = '<p>A &amp B &#38 C</p><p>Next</p>'
        with patch('app.provider.complete', side_effect=lambda key, model, messages, **kw: messages[1]['content']):
            result = translate.translate_and_brand(source, '', 'English', api_key='test')
        self.assertEqual(result['mode'], 'openrouter')
        self.assertEqual(translate.Structure(result['html']).events, translate.Structure(source).events)
        self.assertIn('<p>Next</p>', result['html'])

    def test_wording_and_tone_cannot_change_layout_or_styles(self):
        source = '<style>p{color:red}</style><p>Hello {{first_name}}</p>'
        for changed in ('<div>Hello ⦑PH0⦒</div>', source.replace('red', 'blue').replace('{{first_name}}', '⦑PH0⦒')):
            with patch('app.provider.complete', return_value=changed):
                result = translate.make_variant(source, '', 0, api_key='test', humanize=False)
                self.assertEqual(result['mode'], 'error')
                self.assertEqual(result['html'], source)

    def test_provider_failure_never_becomes_successful_redesign(self):
        with patch('app.mjml_engine.available', return_value=True), patch('app.provider.complete', side_effect=ValueError('Rate limited')):
            result = translate.make_redesign('<p>Welcome</p>', '', 0, api_key='test')
        self.assertEqual(result['mode'], 'error')
        self.assertIn('Rate limited', result['error'])

    def test_provider_errors_do_not_expose_response_body(self):
        response = Mock(status_code=401, text='private-provider-details')
        with patch('requests.post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'API key rejected') as context:
                provider.complete('private-key', 'model', [])
        self.assertNotIn('private', str(context.exception))

    def test_truncated_response_is_rejected(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'length', 'message': {'content': '<p>partial'}}]}
        with patch('requests.post', return_value=response), self.assertRaisesRegex(ValueError, 'incomplete'):
            provider.complete('test', 'model', [])

    def test_every_layout_palette_compiles_and_escapes_content(self):
        if not mjml_engine.available():
            self.skipTest('MJML unavailable')
        content = {'brand': 'Acme & Co', 'headline': 'A helpful update', 'greeting': 'Hello {{first_name}},',
                   'preheader': 'Preview', 'body_blocks': ['A clear message.', '<b>Literal text</b>'],
                   'cta_href': '{{training_url}}', 'cta_label': 'Open guide', 'footer_note': 'Training sample.'}
        for layout in design.ARCHETYPES:
            for palette in design.PALETTES:
                with self.subTest(layout=layout['key'], palette=palette['name']):
                    mjml, key, color = design.build_mjml(content, 0, layout['key'], palette['name'])
                    html = mjml_engine.compile_mjml(mjml)
                    self.assertTrue(htmlsafe.check(html)[0])
                    self.assertIn('{{training_url}}', html)
                    self.assertIn('&lt;b&gt;', html)
                    self.assertEqual((key, color), (layout['key'], palette['name']))

    def test_configuration_is_public_but_key_is_not(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'private-key', 'OPENROUTER_TRANSLATION_MODEL': 'translation-model'}):
            response = TestClient(app).get('/api/health')
        self.assertEqual(response.json()['models']['translation'], 'translation-model')
        self.assertNotIn('private-key', response.text)

    def test_unknown_design_is_rejected_before_generation(self):
        with patch('app.translate.make_redesign') as generate:
            response = TestClient(app).post('/api/redesign', json={'template_html': '<p>Hi</p>', 'design_style': 'unknown'})
        self.assertEqual(response.status_code, 422)
        generate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
