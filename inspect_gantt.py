import asyncio
from playwright.async_api import async_playwright
import pathlib

async def inspect():
    html = pathlib.Path(r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\docs\TR5_Pre-Op_Simulation_Gantt.html').resolve()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(html.as_uri())
        await page.wait_for_timeout(6000)
        svg_html = await page.inner_html('.gantt-wrap')
        out = pathlib.Path(r'C:\tr_dash-main\gantt_dump.html')
        out.write_text(svg_html, encoding='utf-8')
        print('DUMPED', len(svg_html), 'chars to', out)
        await browser.close()

asyncio.run(inspect())
