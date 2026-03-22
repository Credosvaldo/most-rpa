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

async def em_verificacao_humana(page) -> bool:
    challenge_title = page.get_by_text("Let's confirm you are human")
    try:
        return await challenge_title.is_visible(timeout=3000)
    except PlaywrightTimeoutError:
        return False
    

async def extrair_lista_detalhes_beneficio(detail_page, benefit) -> list[dict]:
    details_link = benefit["detailLink"]

    await detail_page.goto(
        details_link,
        wait_until="domcontentloaded",
        referer=BASE_URL,
    )

    await detail_page.locator("#accept-all-btn").click(timeout=3000)


    if await em_verificacao_humana(detail_page):
        return []

    table = detail_page.locator("section.dados-detalhados table").first
    await table.wait_for(state="visible", timeout=10000)
    table_html = await table.evaluate("tableElement => tableElement.outerHTML")
    dataframe = pd.read_html(StringIO(table_html))[0].fillna("")
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    return dataframe.to_dict(orient="records")



async def main() -> None:
    async with async_playwright() as playwright:
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

        # Pesquisar pessoa fisica
        await page.locator("#accept-all-btn").click()
        await page.locator("#termo").fill(SEARCH_TERM)
        await page.get_by_role("button", name="Refine a Busca").click()
        await page.locator("#btnConsultarPF").click()
        
        
        await page.locator("#infoTermo").filter(has_text=SEARCH_TERM).wait_for()

        await page.locator("#resultados a.link-busca-nome").first.click()
        await page.locator("#accept-all-btn").click()
        await page.get_by_role("button", name="Recebimentos de recursos").click()

        # Tirar print da tela
        screenshot_bytes = await page.screenshot(full_page=True)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Obter dados pessoais
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
        
        benefits = []

        # Obter dados dos benefícios
        await page.locator("#loadingcollapse-3").wait_for(state="hidden")
        tables = await page.locator(".br-table").all()

        for table in tables:
            table_name = (await table.locator("strong").inner_text()).strip()

            if table_name not in BENEFICIOS:
                continue

            amount_received = (await table.locator("tbody tr td:nth-child(4)").inner_text()).strip()
            href = await table.locator("a").get_attribute("href")
            details_link = urljoin(BASE_URL, href)

            benefits.append(
                {
                    "name": table_name,
                    "amountReceived": amount_received,
                    "detailLink": details_link,
                }
            )
        
        
        detail_page = await context.new_page()

        for benefit in benefits:
            details = await extrair_lista_detalhes_beneficio(detail_page, benefit)
            benefit["details"] = details

        await detail_page.close()

        # Salvar dados em JSON
        data = {
            "name": name,
            "cpf": cpf,
            "location": location,
            "benefits": benefits,
            "screenshot": screenshot_base64,
            "lastUpdate": pd.Timestamp.now().isoformat(),
        }

        with open("data.json", "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        await page.wait_for_timeout(3000)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
