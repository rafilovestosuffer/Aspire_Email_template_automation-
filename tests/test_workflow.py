import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from app.main import app
from app import store, translate


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'FACTORY_DB': self.temp.name + '/test.sqlite3'})
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_review_localization_export_and_revocation(self):
        seed = self.client.post('/api/seeds', json={'template_html':'<p>Hello {{first_name}}</p>'}).json()
        request = {'variant_id':seed['id'], 'languages':['bn']}
        self.assertEqual(self.client.post('/api/generate', json=request).status_code, 409)
        review = {'actor':'Reviewer', 'status':'approved'}
        self.assertEqual(self.client.post(f"/api/items/{seed['id']}/review", json=review).status_code, 200)
        with patch('app.translate.translate_and_brand', return_value={'html':'<p>হ্যালো {{first_name}}</p>', 'mode':'openrouter', 'model':'test'}) as model:
            result = self.client.post('/api/generate', json=request).json()['results'][0]
            self.client.post('/api/generate', json=request)
            self.assertEqual(model.call_count, 1)
        self.assertEqual(self.client.get('/api/export').json()['items'], [])
        self.client.post(f"/api/items/{result['id']}/review", json=review)
        self.assertEqual(len(self.client.get('/api/export').json()['items']), 1)
        self.assertEqual(len(TestClient(app).get('/api/workspace').json()['variants']), 1)
        self.client.post(f"/api/items/{seed['id']}/review", json={**review,'status':'rejected'})
        self.assertEqual(self.client.get('/api/export').json()['items'], [])
        self.assertEqual(store.get(result['id'])['status'], 'pending')

    def test_mock_cannot_be_approved(self):
        item = store.save({'html':'test','mode':'mock'})
        response = self.client.post(f"/api/items/{item['id']}/review",json={'actor':'Reviewer','status':'approved'})
        self.assertEqual(response.status_code,409)

    def test_invalid_language_and_legacy_bypass(self):
        self.assertEqual(self.client.post('/api/generate',json={'template_html':'anything','languages':['bn']}).status_code,422)
        seed = store.save({'html':'<p>Test</p>','mode':'source','company':''})
        store.review(seed['id'],'approved','Reviewer')
        self.assertEqual(self.client.post('/api/generate',json={'variant_id':seed['id'],'languages':['invalid']}).status_code,422)

    def test_validation(self):
        original='<p>Hello {{first_name}}</p><a href="{{phishing_link}}">Continue</a>'
        masked, toks=translate._mask(original)
        self.assertIn('{{first_name}}',translate.validated_output(masked,masked.replace('Hello','Hola'),toks))
        for bad in (masked.replace('⦑PH0⦒','Joe'),masked.replace('⦑PH0⦒','⦑PH0⦒⦑PH0⦒'),masked.replace('<p>','<p onclick="bad()">'),masked+'{{new_token}}'):
            with self.assertRaises(ValueError):
                translate.validated_output(masked,bad,toks)

    def test_library_and_ui(self):
        with patch('app.library.records', return_value=[
            {'id':'2','name':'Example','subject':'Hello','html':'<p>Hello</p>','needs_recovery':False},
            {'id':'3','name':'Incomplete','subject':'','html':'partial','needs_recovery':True},
        ]):
            listing=self.client.get('/api/library?q=Example').json()
            self.assertEqual(listing['matched'],1)
            self.assertNotIn('html',listing['items'][0])
            self.assertEqual(self.client.get('/api/library/3').status_code,409)
            self.assertEqual(self.client.get('/api/library/2').json()['html'],'<p>Hello</p>')
        page=self.client.get('/')
        self.assertEqual(page.status_code,200)
        self.assertIn('Download approved translations',page.text)

    def test_audit_is_append_only(self):
        item=store.save({'html':'test','mode':'source'})
        store.review(item['id'],'approved','Reviewer')
        import sqlite3
        with store.connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM events')

    def test_windows_csv_preserves_characters(self):
        from pathlib import Path
        from app import library
        path=Path(self.temp.name)/'export.csv'
        path.write_bytes('Template Name,Email Subject,Email body\nExample,Hello,<p>© Brand</p>\n'.encode('cp1252'))
        library.records.cache_clear()
        try:
            with patch.object(library,'PATH',path):
                self.assertEqual(library.records()[0]['html'],'<p>© Brand</p>')
        finally:
            library.records.cache_clear()

    def test_selected_export_and_audit(self):
        sources=[]
        for name in ('One','Two'):
            source=store.save({'html':'<p>Hello</p>','mode':'source','company':'','title':name})
            store.review(source['id'],'approved','Reviewer')
            child=store.save({'html':'<p>Hola</p>','mode':'openrouter','code':'es'},source['id'])
            store.review(child['id'],'approved','Reviewer')
            sources.append(source)
        data=self.client.get('/api/export',params={'source_ids':sources[0]['id']}).json()
        self.assertEqual(len(data['items']),1)
        self.assertEqual(data['sources'][0]['title'],'One')
        self.assertFalse(data['sendable'])
        self.assertEqual(len(self.client.get('/api/activity').json()['events']),4)

    def test_rejected_translation_gets_new_attempt(self):
        source=store.save({'html':'<p>Hello</p>','mode':'source','company':''})
        store.review(source['id'],'approved','Reviewer')
        old=store.save({'html':'<p>Bad</p>','mode':'openrouter','code':'es'},source['id'])
        store.review(old['id'],'rejected','Reviewer')
        with patch('app.translate.translate_and_brand',return_value={'html':'<p>Hola</p>','mode':'openrouter'}):
            result=self.client.post('/api/generate',json={'variant_id':source['id'],'languages':['es']}).json()['results'][0]
        self.assertNotEqual(old['id'],result['id'])
        self.assertEqual(result['status'],'pending')
        self.assertEqual(store.get(old['id'])['status'],'rejected')

    def test_concurrent_generation_is_blocked(self):
        from app.main import generation_lock
        with generation_lock:
            response=self.client.post('/api/variants',json={'template_html':'<p>Test</p>'})
        self.assertEqual(response.status_code,409)

    def test_library_pagination(self):
        rows=[{'id':str(n),'name':f'Item {n}','subject':'','html':'body','needs_recovery':False} for n in range(120)]
        with patch('app.library.records',return_value=rows):
            d=self.client.get('/api/library?offset=100&limit=50').json()
            self.assertEqual(d['matched'],120)
            self.assertEqual(len(d['items']),20)
            self.assertEqual(d['items'][0]['id'],'100')
        self.assertEqual(self.client.get('/api/library?offset=-1').status_code,422)


class HumanizeLayerTests(unittest.TestCase):
    """The humanization pass that makes a generated variant read human-written.
    No real API: requests.post is mocked so the two-pass plumbing and the
    fail-closed guarantee are checked without any provider call or cost."""

    @staticmethod
    def _echo_post(record):
        """A fake OpenRouter that returns the (masked) user content unchanged, so the
        structure/placeholder validators pass. Records each call's system prompt."""
        def fake_post(url, headers=None, json=None, timeout=None):
            record.append(json['messages'][0]['content'])
            masked = json['messages'][1]['content']
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            resp.json = lambda: {'choices': [{'message': {'content': masked}}]}
            return resp
        return fake_post

    def test_humanize_runs_second_pass_and_preserves_placeholders(self):
        tpl = '<p>Hello {{first_name}}, verify at <a href="{{phishing_link}}">link</a>.</p>'
        prompts = []
        with patch('requests.post', side_effect=self._echo_post(prompts)):
            out = translate.make_variant(tpl, 'Acme', 0, api_key='k', model='m')
        self.assertEqual(len(prompts), 2)                       # variant pass + humanize pass
        self.assertTrue(out['humanized'])
        self.assertEqual(out['humanize_prompt_version'], 'humanize-v1')
        self.assertIn('human copy editor', prompts[1])          # 2nd call is the humanize prompt
        self.assertIn('{{first_name}}', out['html'])            # frozen placeholders survive
        self.assertIn('{{phishing_link}}', out['html'])

    def test_humanize_is_fail_closed(self):
        tpl = '<p>Hello {{first_name}}</p>'
        state = {'n': 0}

        def fake_post(url, headers=None, json=None, timeout=None):
            state['n'] += 1
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            if state['n'] == 1:                                 # variant pass succeeds
                masked = json['messages'][1]['content']
                resp.json = lambda: {'choices': [{'message': {'content': masked}}]}
                return resp
            raise RuntimeError('humanize provider down')        # humanize pass fails

        with patch('requests.post', side_effect=fake_post):
            out = translate.make_variant(tpl, 'Acme', 0, api_key='k', model='m')
        self.assertFalse(out['humanized'])                      # layer skipped, not fatal
        self.assertEqual(out['mode'], 'openrouter')             # base variant still returned
        self.assertIn('humanize_error', out)
        self.assertIn('{{first_name}}', out['html'])            # base variant left intact

    def test_humanize_false_skips_second_pass(self):
        tpl = '<p>Hi {{first_name}}</p>'
        prompts = []
        with patch('requests.post', side_effect=self._echo_post(prompts)):
            out = translate.make_variant(tpl, 'Acme', 0, api_key='k', model='m', humanize=False)
        self.assertEqual(len(prompts), 1)                       # only the variant pass ran
        self.assertFalse(out['humanized'])

    def test_humanize_cannot_introduce_new_placeholder(self):
        """The humanize pass is bound by the same closed-vocabulary gate: a rewrite that
        injects a new {{token}} is rejected and the base variant is kept (fail-closed)."""
        tpl = '<p>Hello {{first_name}}</p>'
        state = {'n': 0}

        def fake_post(url, headers=None, json=None, timeout=None):
            state['n'] += 1
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            masked = json['messages'][1]['content']
            if state['n'] == 2:                                 # humanize pass smuggles a new token
                masked = masked + '{{smuggled_token}}'
            resp.json = lambda: {'choices': [{'message': {'content': masked}}]}
            return resp

        with patch('requests.post', side_effect=fake_post):
            out = translate.make_variant(tpl, 'Acme', 0, api_key='k', model='m')
        self.assertFalse(out['humanized'])
        self.assertNotIn('{{smuggled_token}}', out['html'])     # rejected by validated_variant


class HtmlSafeTests(unittest.TestCase):
    """The injection gate that every redesign must pass before it is stored."""

    def test_blocks_injection(self):
        from app import htmlsafe
        bad = ['<script>alert(1)</script>', '<a href="javascript:x">y</a>',
               '<iframe src="https://e"></iframe>', '<img src=x onerror="e()">',
               '<form action="https://e"><input></form>', '<a href="http://x">y</a>',
               '<a href="data:text/html,x">y</a>', '<base href="https://e">',
               '<a href="vbscript:x">y</a>', '<object data="https://e"></object>']
        for h in bad:
            self.assertFalse(htmlsafe.check(h)[0], f'should block: {h}')
            with self.assertRaises(htmlsafe.UnsafeHtml):
                htmlsafe.assert_safe(h)

    def test_allows_safe_and_tokens(self):
        from app import htmlsafe
        for h in ['<div style="x"><a href="https://ok.com">a</a></div>',
                  '<a href="{{phishing_link}}">go</a>', '<a href="mailto:a@b.com">m</a>',
                  '<a href="#top">top</a>', '<p>Hello {{first_name}}</p>']:
            self.assertTrue(htmlsafe.check(h)[0], f'should allow: {h}')

    def test_real_mjml_output_passes_gate(self):
        from app import design, mjml_engine, htmlsafe
        if not mjml_engine.available():
            self.skipTest('mjml engine not installed')
        content = {'brand': 'Acme', 'preheader': 'p', 'headline': 'Hi', 'greeting': 'Hello,',
                   'body_blocks': ['One.', 'Two.'], 'cta_label': 'Go',
                   'cta_href': '{{phishing_link}}', 'footer_note': 'f'}
        for i in range(4):
            mjml, key, _ = design.build_mjml(content, i)
            html = mjml_engine.compile_mjml(mjml)
            self.assertTrue(htmlsafe.check(html)[0], f'archetype {key} should pass the gate')
            self.assertIn('<table', html)


class RedesignTests(unittest.TestCase):
    """Redesign mode: curated archetypes + local MJML, gated and fail-closed."""

    SRC = ('<html><body><table><tr><td>{{brand_name}}</td></tr>'
           '<tr><td><p>Hello {{first_name}},</p>'
           '<p>We detected a new sign-in to your {{brand_name}} account. Verify now.</p>'
           '<p><a href="{{phishing_link}}">Verify account</a></p></td></tr></table></body></html>')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Clear the key so endpoint-level redesign runs in deterministic mock mode (no network).
        self.env = patch.dict(os.environ, {'FACTORY_DB': self.temp.name + '/t.sqlite3',
                                            'OPENROUTER_API_KEY': ''})
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _need_engine(self):
        from app import mjml_engine
        if not mjml_engine.available():
            self.skipTest('mjml engine not installed')

    def test_mock_redesign_preserves_tokens_and_is_safe(self):
        self._need_engine()
        from app import htmlsafe
        seen = set()
        for i in range(4):
            out = translate.make_redesign(self.SRC, 'Acme', i, humanize=False)
            self.assertEqual(out['mode'], 'mock')
            self.assertEqual(out['kind'], 'redesign')
            self.assertIn('<table', out['html'])
            for tok in ('{{brand_name}}', '{{first_name}}', '{{phishing_link}}'):
                self.assertIn(tok, out['html'], f"{tok} must survive ({out['archetype']})")
            self.assertTrue(htmlsafe.check(out['html'])[0])
            seen.add(out['archetype'])
        self.assertEqual(len(seen), 4)                      # all four archetypes rotate

    def test_endpoint_creates_drafts_not_approvable(self):
        self._need_engine()
        r = self.client.post('/api/redesign', json={'template_html': self.SRC,
                              'company_name': 'Acme', 'amount': 2, 'humanize': False}).json()
        self.assertEqual(r['count'], 2)
        self.assertTrue(r['has_engine'])
        for v in r['variants']:
            self.assertEqual(v['kind'], 'redesign')
            self.assertEqual(v['mode'], 'mock')
            self.assertEqual(v['status'], 'pending')
        resp = self.client.post(f"/api/items/{r['variants'][0]['id']}/review",
                                json={'actor': 'R', 'status': 'approved'})
        self.assertEqual(resp.status_code, 409)             # mock is never approvable

    def test_engine_missing_fails_closed(self):
        with patch('app.mjml_engine.available', return_value=False):
            out = translate.make_redesign(self.SRC, 'Acme', 0, humanize=False)
        self.assertEqual(out['mode'], 'error')
        self.assertIn('engine', out['error'].lower())

    def test_unsafe_compiled_output_fails_closed(self):
        self._need_engine()
        with patch('app.mjml_engine.compile_mjml',
                   return_value='<html><body><script>x()</script></body></html>'):
            out = translate.make_redesign(self.SRC, 'Acme', 0, humanize=False)
        self.assertEqual(out['mode'], 'error')              # gate rejects; nothing unsafe stored

    def test_llm_extraction_path(self):
        self._need_engine()
        from app import htmlsafe

        def fake_post(url, headers=None, json=None, timeout=None):
            sysmsg = json['messages'][0]['content']
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            if 'extract the CONTENT' in sysmsg:
                payload = ('{"preheader":"Review","headline":"Security notice",'
                           '"greeting":"Hi there,","body_blocks":["Please review your activity."],'
                           '"cta_label":"Review activity","footer_note":"Training."}')
                resp.json = lambda: {'choices': [{'message': {'content': payload}}]}
            else:                                           # humanize pass echoes masked content
                masked = json['messages'][1]['content']
                resp.json = lambda: {'choices': [{'message': {'content': masked}}]}
            return resp

        with patch('requests.post', side_effect=fake_post):
            out = translate.make_redesign(self.SRC, 'Acme', 1, api_key='k', model='m', humanize=True)
        self.assertEqual(out['mode'], 'openrouter')
        self.assertEqual(out['extraction'], 'llm')
        self.assertTrue(out['humanized'])
        self.assertIn('{{phishing_link}}', out['html'])     # action-link token placed by us
        self.assertIn('{{brand_name}}', out['html'])
        self.assertTrue(htmlsafe.check(out['html'])[0])

    def test_content_injection_is_escaped(self):
        self._need_engine()
        from app import htmlsafe

        def fake_post(url, headers=None, json=None, timeout=None):
            payload = ('{"preheader":"p","headline":"<script>alert(1)</script> Alert",'
                       '"greeting":"Hi,","body_blocks":["Body <b>x</b> & more"],'
                       '"cta_label":"Go","footer_note":"f"}')
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            resp.json = lambda: {'choices': [{'message': {'content': payload}}]}
            return resp

        with patch('requests.post', side_effect=fake_post):
            out = translate.make_redesign(self.SRC, 'Acme', 0, api_key='k', model='m', humanize=False)
        self.assertEqual(out['mode'], 'openrouter')
        self.assertNotIn('<script>', out['html'].lower())   # injected markup escaped, not live
        self.assertTrue(htmlsafe.check(out['html'])[0])

    def test_redesign_concurrency_blocked(self):
        from app.main import generation_lock
        with generation_lock:
            resp = self.client.post('/api/redesign', json={'template_html': '<p>Hi</p>'})
        self.assertEqual(resp.status_code, 409)


if __name__=='__main__':
    unittest.main()
