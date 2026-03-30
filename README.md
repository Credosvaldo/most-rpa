# Desafio Full Stack Developer - Python (RPA e Hiperautomacao)

## 1) Resumo da entrega
Este repositorio contem a implementacao da **Parte 1 (obrigatoria)** do desafio: um robo em Python que acessa o Portal da Transparencia, consulta pessoa fisica por termo de busca (CPF/NIS/nome), coleta dados de beneficios, gera evidencia da tela em Base64 e retorna tudo em JSON por meio de uma API HTTP.

> Status da entrega:
- Parte 1: implementada
- Parte 2 (bonus): nao implementada neste repositorio
- API: preparada para deploy online (Render)

---

## 2) Acesso a api

https://most-rpa.onrender.com/run/<TERMO DE BUSCA>

## 3) Escopo implementado (Parte 1)

### Objetivo atendido
- Navegar no Portal da Transparencia (Pessoa Fisica)
- Buscar por termo informado na rota
- Aplicar filtros opcionais de busca refinada
- Entrar no primeiro resultado encontrado
- Coletar dados gerais da pessoa:
  - nome
  - CPF (mascarado conforme exibicao do portal)
  - localidade
- Coletar beneficios de interesse:
  - Auxilio Brasil
  - Auxilio Emergencial
  - Beneficiario de Bolsa Familia
  - Novo Bolsa Familia
- Acessar pagina de detalhes de cada beneficio e coletar tabela de parcelas
- Capturar screenshot da pagina e converter para Base64
- Retornar resposta JSON consolidada
- Persistir tambem um arquivo local `data.json` com o mesmo resultado

### Requisitos tecnicos atendidos
- Linguagem: Python
- Automacao: Playwright (modo headless)
- API HTTP: Flask
- Tratamento de parsing tabular: pandas + lxml
- Execucao em container: Docker
- Execucao de API com Gunicorn (threads habilitadas para concorrencia)

---

## 4) Arquitetura da solucao

### Componentes principais
- API Flask recebe requisicao REST
- Funcao assincrona principal executa fluxo Playwright
- Extracao de detalhes usa uma nova aba de navegador para cada beneficio
- Screenshot e serializacao final retornam no payload JSON

### Fluxo simplificado
1. Cliente chama endpoint de consulta
2. API inicia navegador Chromium headless
3. Robo abre pagina de busca e aceita cookies
4. Robo preenche termo + filtros opcionais
5. Robo abre primeiro resultado e sessao de recebimentos
6. Robo coleta dados da pessoa e beneficios
7. Robo abre detalhes de cada beneficio e extrai tabela
8. Robo gera screenshot Base64
9. API retorna JSON final

---

## 5) Endpoints da API

### Healthcheck
- Metodo: GET
- Rota: `/health`
- Resposta esperada:

```json
{
  "status": "ok"
}
```

### Consulta principal
- Metodo: GET
- Rota: `/run/<search_term>`
- Exemplo:
  - `/run/16380087517`
  - `/run/NOME COMPLETO`

#### Query params de filtros opcionais
Todos aceitam valores como: `true|false`, `1|0`, `yes|no`, `on|off`.

- `publicServers`
- `socialProgramBeneficiary`
- `federalGovernmentPaymentCardHolder`
- `civilDefenseCardHolder`
- `activeSanction`
- `officialPropertyOccupant`
- `federalGovernmentContract`
- `publicFundBeneficiary`
- `invoiceIssuer`

Exemplo com filtro social:

`/run/SOBRENOME?socialProgramBeneficiary=true`

---

## 6) Exemplo de resposta (sucesso)

```json
{
  "name": "PEDRO CIRSO PEDRO",
  "cpf": "***.791.728-**",
  "location": "NOVO HORIZONTE - SP",
  "benefits": [
    {
      "name": "Auxilio Emergencial",
      "amountReceived": 5650.0,
      "details": [
        {
          "mesDeDisponibilizacao": "10/2021",
          "parcela": "16a",
          "uf": "SP",
          "municipio": "NOVO HORIZONTE",
          "enquadramento": "EXTRA CADUN",
          "valor(r$)": 25000,
          "observacao": "Nao ha"
        }
      ]
    }
  ],
  "screenshot": "<base64>"
}
```

---

## 7) Exemplo de erro
Em caso de falha durante automacao, a API responde:

```json
{
  "status": "error",
  "message": "<detalhe da excecao>"
}
```

HTTP status: `500`

---

## 8) Como executar localmente

## Requisitos
- Python 3.10+
- pip
- Navegadores Playwright instalados

## Passos
1. Criar e ativar ambiente virtual
2. Instalar dependencias
3. Instalar browsers do Playwright
4. Subir API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
python main.py
```

API disponivel em: `http://localhost:8000`

Teste rapido:

```bash
curl http://localhost:8000/health
```

---

## 9) Como executar com Docker

```bash
docker build -t most-rpa .
docker run --rm -p 8000:8000 most-rpa
```

A imagem usa base oficial Playwright Python e inicia Gunicorn com suporte a threads.

---

## 10) Deploy no Render

A aplicacao esta preparada para deploy como Web Service com Docker.

## Configuracao sugerida
- Runtime: Docker
- Port: `8000` (ou `PORT` injetada pelo Render)
- Health check path: `/health`

O comando de inicializacao ja esta definido no Dockerfile:

- Gunicorn
- 1 worker
- 4 threads
- bind em `0.0.0.0:${PORT:-8000}`

---

## 11) Concorrencia e modo headless

- O robo roda em modo headless (`HEADLESS = True`)
- Cada requisicao cria contexto isolado de browser
- A API com Gunicorn + threads permite atender chamadas simultaneas
- Recomendacao para carga maior: aumentar workers e ajustar timeouts no deploy

---

## 12) Decisoes tecnicas

### Por que Playwright
- Boa estabilidade para automacao moderna
- Esperas explicitas e controle fino de estados de pagina
- Captura de screenshot integrada
- Facil execucao headless em ambiente containerizado

### Por que Flask para esta entrega
- API leve e direta para expor o robo
- Curva de manutencao simples para PoC de automacao

### Parsing de detalhes com pandas
- Tabelas HTML transformadas rapidamente em JSON estruturado
- Menor complexidade manual para mapear linhas/colunas

---

## 13) Desafios enfrentados

- Variacao de carregamento e componentes dinamicos no portal
- Convivencia com popup/cookie e estados de busca refinada
- Garantir extração de beneficios apenas da lista alvo
- Normalizacao de colunas e estrutura de detalhes para JSON
- Estabilidade de automacao em headless e ambiente de deploy

---

## 14) Autor
Entrega tecnica referente ao desafio da MOST (RPA e Hiperautomacao), com foco na Parte 1 e disponibilizacao da API para testes online.
