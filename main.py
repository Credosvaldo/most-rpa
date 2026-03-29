import asyncio
import base64
import json
import unicodedata
from io import StringIO
from urllib.parse import urljoin

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BASE_URL = "https://portaldatransparencia.gov.br/"
URL = f"{BASE_URL}pessoa-fisica/busca/lista?pagina=1&tamanhoPagina=10"
HEADLESS = False

SEARCH_TERM = "1.638.008.751-7"
publicServers = True
socialProgramBeneficiary = True
federalGovernmentPaymentCardHolder = True
civilDefenseCardHolder = True
activeSanction = True
officialPropertyOccupant = True
federalGovernmentContract = True
publicFundBeneficiary = True
invoiceIssuer = True

INPUT_ID = "termo"

BENEFICIOS = [
    "Auxílio Brasil",
    "Auxílio Emergencial",  
    "Beneficiário de Bolsa Família",
    "Novo Bolsa Família"
]

def normalize_column_name(name):
    """Remove acentos e espaços de nomes de colunas, mantendo português."""
    # Remove acentos
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    )
    # Converte para camelCase, removendo espaços extras
    parts = normalized.strip().split()
    if not parts:
        return ""

    first = parts[0].lower()
    rest = ''.join(part.capitalize() for part in parts[1:])
    return f"{first}{rest}"

def parse_brl_currency_to_float(value: str) -> float:
    """Converte valores como 'R$ 4.760,00' para 4760.00."""
    cleaned = value.replace("R$", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    return float(cleaned)

async def start_browser(playwright):
    print("Iniciando navegador...")
    browser = await playwright.chromium.launch(
        headless=HEADLESS,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    )
    page = await context.new_page()
    await page.goto(URL, wait_until="domcontentloaded")
    
    return browser, context, page

async def accept_cookies(page):
    print("Aceitando cookies...")
    try:
        await page.locator("#accept-all-btn").click(timeout=3000)
    except PlaywrightTimeoutError:
        pass

async def filter_options(page):
    if publicServers:
        await page.locator("#servidorPublico").check(force=True)
    if socialProgramBeneficiary:
        await page.locator("#beneficiarioProgramaSocial").check(force=True)
    if federalGovernmentPaymentCardHolder:
        await page.locator("#portadorCPGF").check(force=True)
    if civilDefenseCardHolder:
        await page.locator("#portadorCPDC").check(force=True)
    if activeSanction:
        await page.locator("#sancaoVigente").check(force=True)
    if officialPropertyOccupant:
        await page.locator("#ocupanteImovelFuncional").check(force=True)
    if federalGovernmentContract:
        await page.locator("#possuiContrato").check(force=True)
    if publicFundBeneficiary:
        await page.locator("#favorecidoRecurso").check(force=True)
    if invoiceIssuer:
        await page.locator("#emitenteNfe").check(force=True)

async def search_person(page, search_term):
    print("Buscando pessoa...")
    await page.locator(f"#{INPUT_ID}").wait_for(state="visible")
    await page.locator(f"#{INPUT_ID}").fill(search_term)
    await page.locator("#box-busca-refinada").wait_for(state="attached")
    await page.get_by_role("button", name="Refine a Busca").click()
    
    try:
        await page.locator("#box-busca-refinada").wait_for(state="visible", timeout=1000)
    except PlaywrightTimeoutError:
        await page.get_by_role("button", name="Refine a Busca").click()

    await filter_options(page)
    await page.locator("#btnConsultarPF").click()
    await page.wait_for_function("() => document.getElementById('resultados').textContent.trim() === ''")
    await page.locator("#infoTermo").filter(has_text=search_term).wait_for()
  
async def open_person_page(page):
    print("Abrindo página da pessoa...")
    await page.wait_for_function('() => !document.querySelector("#resultados a.link-busca-nome")?.textContent?.includes("A AI PIRAHA")')
    await page.locator("#resultados a.link-busca-nome").first.click()
    await accept_cookies(page)
    await page.get_by_role("button", name="Recebimentos de recursos").click()
    
    try:
        await page.locator("#accordion-recebimentos-recursos").wait_for(state="visible", timeout=1000)
    except PlaywrightTimeoutError:
        await page.get_by_role("button", name="Recebimentos de recursos").click()
        await page.locator("#accordion-recebimentos-recursos").wait_for(state="visible", timeout=1000)

async def take_screenshot(page):
    print("Tirando screenshot da página de benefícios...")
    screenshot_bytes = await page.screenshot(full_page=True)
    screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
    return screenshot_base64 
    
async def get_person_data(page):
    print("Extraindo dados pessoais...")
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
    print("Extraindo metadados dos benefícios...")
    benefits_metadata = []
    
    print("Aguardando carregamento dos benefícios...")
    await page.locator("#loadingcollapse-3").wait_for(state="hidden")
    
    print("Localizando tabelas de benefícios...")
    tables = await page.locator(".br-table").all()


    print(f"Encontradas {len(tables)} tabelas. Filtrando por benefícios relevantes...")
    for table in tables:
        table_name = (await table.locator("strong").inner_text()).strip()

        if table_name not in BENEFICIOS:
            continue
        
        print(f"Extraindo metadados do benefício: {table_name}...")

        amount_received_text = (await table.locator("tbody tr td:nth-child(4)").inner_text()).strip()
        amount_received = parse_brl_currency_to_float(amount_received_text)
        print(f"Valor recebido: {amount_received}")
        
        href = await table.locator("a").get_attribute("href")
        print(f"Link de detalhes encontrado: {href}")
        
        details_link = urljoin(BASE_URL, href)
        print(f"Link de detalhes completo: {details_link}")

        benefits_metadata.append(
            {
                "name": table_name,
                "amountReceived": amount_received,
                "detailLink": details_link,
            }
        )
    
    return benefits_metadata

async def get_benefits(context, benefits_metadata):
    print("Extraindo detalhes dos benefícios...")
    benefits = []
    detail_page = await context.new_page()
    print("Navegando para a página de detalhes do benefício...")

    for benefit in benefits_metadata:
        print(f"Obtendo detalhes para o benefício: {benefit['name']}...")
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

    print("Aceitando cookies na página de detalhes...")
    await detail_page.locator("#accept-all-btn").click(timeout=3000)

    print("Localizando tabela de detalhes...")
    table = detail_page.locator("section.dados-detalhados table").first
    
    print("esperando tabela de detalhes ficar visível...")
    await table.wait_for(state="visible", timeout=10000)
    
    print("Extraindo dados da tabela de detalhes...")
    table_html = await table.evaluate("tableElement => tableElement.outerHTML")
    
    print("Convertendo tabela HTML para DataFrame...")
    dataframe = pd.read_html(StringIO(table_html))[0].fillna("")
    dataframe.columns = [normalize_column_name(str(column).strip()) for column in dataframe.columns]
    return dataframe.to_dict(orient="records")

def save_as_json(person_data, benefits, screenshot):
    print("Salvando dados em JSON...")
    data = {
        "name": person_data["name"],
        "cpf": person_data["cpf"],
        "location": person_data["location"],
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
