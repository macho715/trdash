import asyncio
from playwright.async_api import async_playwright
import pathlib

async def gen():
    html = pathlib.Path(r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\docs\TR5_Pre-Op_Simulation_Gantt.html').resolve()
    out  = pathlib.Path(r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\docs\TR5_Pre-Op_Simulation_Gantt_A3_v12.pdf').resolve()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(html.as_uri())
        await page.wait_for_timeout(5000)
        color = await page.evaluate('document.querySelector("#bd2") ? document.querySelector("#bd2").getAttribute("fill") : "NOT FOUND"')
        print('bd2 fill:', color)
        await page.pdf(path=str(out), format='A3', landscape=True, print_background=True)
        await browser.close()
    print('DONE:', out)

asyncio.run(gen())
