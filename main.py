import asyncio
import base64
import json
from io import StringIO
from urllib.parse import urljoin

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BASE_URL = "https://portaldatransparencia.gov.br/"
URL = f"{BASE_URL}pessoa-fisica/busca/lista?pagina=1&tamanhoPagina=10"

SEARCH_TERM = "1.638.008.751-7"

INPUT_ID = "termo"

BENEFICIOS = [
    "Auxílio Brasil",
    "Auxílio Emergencial",
    "Beneficiário de Bolsa Família",
    "Novo Bolsa Família"
]

async def start_browser(playwright):
    browser = await playwright.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
    )
    page = await context.new_page()
    await page.goto(URL, wait_until="domcontentloaded")
    
    return browser, context, page

async def accept_cookies(page):
    try:
        await page.locator("#accept-all-btn").click(timeout=3000)
    except PlaywrightTimeoutError:
        pass
    
async def search_person(page, search_term):
    await page.locator(f"#{INPUT_ID}").fill(search_term)
    await page.locator("#box-busca-refinada").wait_for(state="attached")
    await page.get_by_role("button", name="Refine a Busca").click()
    
    try:
        await page.locator("#box-busca-refinada").wait_for(state="visible", timeout=10000)
    except PlaywrightTimeoutError:
        await page.get_by_role("button", name="Refine a Busca").click()

    await page.locator("#btnConsultarPF").click()
    await page.locator("#infoTermo").filter(has_text=search_term).wait_for()
  
async def open_person_page(page):
    await page.locator("#resultados a.link-busca-nome").first.click()
    await accept_cookies(page)
    await page.get_by_role("button", name="Recebimentos de recursos").click()
    
async def take_screenshot(page):
    screenshot_bytes = await page.screenshot(full_page=True)
    screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    return screenshot_base64 
    
async def get_person_data(page):
    name = (
        await page.locator('strong:has-text("Nome")')
        .locator("..")
        .locator("span")
        .inner_text()
    ).strip()
    
    cpf = (
        await page.locator('strong:has-text("CPF")')
        .locator("..")
        .locator("span")
        .inner_text()
    ).strip()
    
    location = (
        await page.locator('strong:has-text("Localidade")')
        .locator("..")
        .locator("span")
        .inner_text()
    ).strip()
   
    return {
        "name": name,
        "cpf": cpf,
        "location": location,
    }
   
async def get_benefits_metadata(page):
    benefits_metadata = []
    await page.locator("#loadingcollapse-3").wait_for(state="hidden")
    tables = await page.locator(".br-table").all()

    for table in tables:
        table_name = (await table.locator("strong").inner_text()).strip()

        if table_name not in BENEFICIOS:
            continue

        amount_received = (await table.locator("tbody tr td:nth-child(4)").inner_text()).strip()
        href = await table.locator("a").get_attribute("href")
        details_link = urljoin(BASE_URL, href)

        benefits_metadata.append(
            {
                "name": table_name,
                "amountReceived": amount_received,
                "detailLink": details_link,
            }
        )
    
    return benefits_metadata

async def get_benefits(context, benefits_metadata):
    benefits = []
    detail_page = await context.new_page()

    for benefit in benefits_metadata:
        details = await get_benefit_details(detail_page, benefit["detailLink"])
        benefits.append({
            "name": benefit["name"],
            "amountReceived": benefit["amountReceived"],
            "details": details
        })

    await detail_page.close()
    
    return benefits

async def get_benefit_details(detail_page, detail_link) -> list[dict]:
    await detail_page.goto(
        detail_link,
        wait_until="domcontentloaded",
        referer=BASE_URL,
    )

    await detail_page.locator("#accept-all-btn").click(timeout=3000)

    table = detail_page.locator("section.dados-detalhados table").first
    await table.wait_for(state="visible", timeout=10000)
    table_html = await table.evaluate("tableElement => tableElement.outerHTML")
    dataframe = pd.read_html(StringIO(table_html))[0].fillna("")
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    return dataframe.to_dict(orient="records")

def save_as_json(person_data, benefits, screenshot):
    data = {
        "personData": person_data,
        "benefits": benefits,
        "screenshot": screenshot,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def end_browser(browser, context):
    await context.close()
    await browser.close()

async def main() -> None:
    async with async_playwright() as playwright:
        browser, context, page = await start_browser(playwright)

        await accept_cookies(page)
        await search_person(page, SEARCH_TERM)
        await open_person_page(page)
        
        screenshot = await take_screenshot(page)
        person_data = await get_person_data(page)
        benefits_metadata = await get_benefits_metadata(page)
        benefits = await get_benefits(context, benefits_metadata)

        save_as_json(person_data, benefits, screenshot)
        
        await end_browser(browser, context)


if __name__ == "__main__":
    asyncio.run(main())
