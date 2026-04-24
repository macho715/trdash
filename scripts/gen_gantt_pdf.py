import pathlib, time
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML_PATH = next((ROOT / 'docs').glob('*/TR5_Pre-Op_Simulation_Gantt.html'))
PDF_PATH = HTML_PATH.with_name('TR5_Pre-Op_Simulation_Gantt_A3.pdf')

HTML = HTML_PATH.resolve().as_uri()
PDF_OUT = str(PDF_PATH)

SCALE_JS = """() => {
  const wrap = document.querySelector('.gantt-wrap');
  const svg  = document.querySelector('.gantt-wrap svg');
  if (!svg || !wrap) return 'no svg';
  svg.removeAttribute('width'); svg.removeAttribute('height');
  svg.style.transform = ''; svg.style.width = ''; svg.style.height = '';
  const wW = wrap.clientWidth, wH = wrap.clientHeight;
  const vb = svg.viewBox.baseVal;
  const svgW = (vb && vb.width)  ? vb.width  : svg.getBoundingClientRect().width;
  const svgH = (vb && vb.height) ? vb.height : svg.getBoundingClientRect().height;
  if (!svgW || !svgH) return 'no dim';
  const scale = Math.min(wW / svgW, wH / svgH);
  svg.style.width = svgW + 'px'; svg.style.height = svgH + 'px';
  svg.style.transform = 'scale(' + scale + ')'; svg.style.transformOrigin = 'top left';
  return 'scaled ' + svgW.toFixed(0) + 'x' + svgH.toFixed(0) + ' -> ' + scale.toFixed(3);
}"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1587, 'height': 1123})
    page.goto(HTML, wait_until='networkidle', timeout=30000)
    page.wait_for_selector('.gantt-wrap svg', timeout=15000)
    time.sleep(3)
    result = page.evaluate(SCALE_JS)
    print(f'Scale: {result}')
    time.sleep(1)
    page.pdf(path=PDF_OUT, width='420mm', height='297mm',
             print_background=True, prefer_css_page_size=True, page_ranges='1')
    browser.close()

import os
print(f'PDF: {PDF_OUT} ({os.path.getsize(PDF_OUT)/1024:.1f} KB)')
