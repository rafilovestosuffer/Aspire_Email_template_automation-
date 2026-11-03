"""Opt-in small paid GPT smoke test. Run: python -m scripts.smoke_ai --live.

Uses neutral sample copy, saves previews locally, and never changes review data.
Four requests total: translation, redesign, wording, and its copy-editing pass.
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import requests
from app.main import app  # loads server-side .env
from app import provider, translate

SOURCE = ('<html><head><style>p { line-height: 1.6; }</style></head><body>'
          '<h1>{{brand_name}} workshop update</h1><p>Hello {{first_name}},</p>'
          '<p>Your team workshop is scheduled for 12 November at 10:00. '
          'The guide contains the agenda and preparation notes. Please read it before the session.</p>'
          '<p><a href="{{training_url}}">Read the workshop guide</a></p>'
          '<p>Thank you,<br>The learning team</p></body></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Authorize four small billable GPT requests')
    args = parser.parse_args()
    if not args.live:
        parser.error('No API calls made. Pass --live to run the paid smoke test.')
    model = 'openai/gpt-4.1-mini'
    usages = []
    post = requests.post

    def record(*args, **kwargs):
        result = post(*args, **kwargs)
        try:
            usages.append(result.json().get('usage', {}))
        except ValueError:
            usages.append({})
        return result

    directory = Path('data/previews')
    directory.mkdir(parents=True, exist_ok=True)
    results = {}
    with patch('requests.post', side_effect=record):
        results['bangla'] = translate.translate_and_brand(SOURCE, 'Acme Learning', 'Bangla', model=model)
        print('Bangla:', results['bangla']['mode'], flush=True)
        results['editorial'] = translate.make_redesign(SOURCE, 'Acme Learning', 0, model=model,
            humanize=False, copy_length='expanded', design_style='editorial', palette='teal')
        print('Redesign:', results['editorial']['mode'], flush=True)
        results['wording'] = translate.make_variant(SOURCE, 'Acme Learning', 0, model=model,
                                                    humanize=True, copy_length='expanded')
        print('Wording:', results['wording']['mode'], flush=True)
    for name, result in results.items():
        (directory / f'{name}.html').write_text(result['html'], encoding='utf-8')
    summary = {name: {k: v for k, v in result.items() if k not in ('html', 'mjml')}
               for name, result in results.items()}
    summary['usage'] = usages
    summary['reported_cost_usd'] = sum(u.get('cost') or 0 for u in usages)
    (directory / 'smoke-results.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if any(result['mode'] != 'openrouter' for result in results.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
