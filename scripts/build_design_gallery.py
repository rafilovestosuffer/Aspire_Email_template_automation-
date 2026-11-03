"""Build the offline gallery: python -m scripts.build_design_gallery. No API calls."""
from html import escape
from pathlib import Path

from app import design, mjml_engine


def main():
    content = {
        'brand': '{{brand_name}}', 'preheader': 'A few details before the team workshop.',
        'headline': 'Your workshop details are ready', 'greeting': 'Hello {{first_name}},',
        'body_blocks': ['Your team workshop is scheduled for 12 November at 10:00. '
                        'The guide includes the agenda and preparation notes.',
                        'Please take a moment to read through the guide before the session.'],
        'cta_label': 'Read the workshop guide', 'cta_href': '{{training_url}}',
        'footer_note': 'Thank you, The learning team.',
    }
    original = ('<html><body style="margin:0;background:#eef1f7;color:#1b2a4a;font:15px/1.7 Arial">'
                '<div style="padding:32px;text-align:center;font-size:12px;letter-spacing:2px">{{brand_name}}</div>'
                '<div style="padding:32px 28px;background:white;text-align:center">'
                f'<h2 style="font-size:23px;line-height:1.4">{content["headline"]}</h2>'
                f'<p>{content["greeting"]}</p>'
                + ''.join(f'<p>{text}</p>' for text in content['body_blocks']) +
                '<p style="margin-top:30px"><span style="display:inline-block;background:#334155;color:white;'
                'padding:12px 24px;border-radius:30px;font-weight:bold">Read the workshop guide</span></p>'
                f'</div><p style="text-align:center;font-size:12px;padding:18px">{content["footer_note"]}</p></body></html>')

    def panel(title, caption, html):
        return (f'<article><header><div><h2>{escape(title)}</h2><p>{escape(caption)}</p></div></header>'
                f'<iframe title="{escape(title)}" sandbox srcdoc="{escape(html, quote=True)}"></iframe></article>')

    layouts = []
    for i, layout in enumerate(design.ARCHETYPES):
        markup, key, palette = design.build_mjml(content, i, layout['key'])
        layouts.append(panel(layout['label'], palette.title() + ' palette · same content',
                             mjml_engine.compile_mjml(markup)))
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ASAT · Layout gallery</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f3f5f9;color:#192840;font:15px/1.5 system-ui,sans-serif}
main{max-width:1240px;margin:auto;padding:36px 24px 60px}nav{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}
nav b{font-size:12px;letter-spacing:2px}a{color:#2454d6;text-decoration:none;font-weight:600}h1{font-size:36px;line-height:1.15;letter-spacing:-1px;margin:12px 0}
.intro{max-width:690px;color:#617089;margin-bottom:24px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}
article{min-width:0;background:#fff;border:1px solid #dce3ee;border-radius:16px;overflow:hidden;box-shadow:0 10px 32px #17264108}
header{padding:16px 22px;border-bottom:1px solid #e3e8f0}h2{font-size:15px;margin:0}header p{font-size:12px;color:#6a7890;margin:4px 0 0}
iframe{display:block;width:100%;height:780px;border:0;background:#fff}details{margin-top:28px}summary{cursor:pointer;padding:20px 0;font-size:18px;font-weight:650}
.note{font-size:12px;color:#68778b;padding:16px 0}@media(max-width:780px){.grid{grid-template-columns:1fr}main{padding:24px 12px}h1{font-size:28px}}
</style></head><body><main><nav><b>ASAT / LAYOUT GALLERY</b><a href="/">Back to studio ↗</a></nav>
<h1>Same message. A stronger visual hierarchy.</h1><p class="intro">Compare the previous centered layout with the new signature design: a bold header, a highlighted message, and a distinct action area. These are offline layout previews using identical sample copy.</p><div class="grid">'''
    page += panel('Previous centered layout', 'Original structure · reference', original) + layouts[0]
    page += '</div><details><summary>Explore five more design directions</summary><div class="grid">'
    page += ''.join(layouts[1:])
    page += ('</div></details><p class="note">No AI calls. Recipient and link placeholders remain unchanged. '
             'Existing saved drafts keep their original layout; create a new redesign to use the updated styles.</p></main></body></html>')
    target = Path(__file__).resolve().parents[1] / 'app/static/designs.html'
    target.write_text(page, encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
