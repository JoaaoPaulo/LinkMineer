# ⛏️ LinkMineer — Minerador Automático de Links de Afiliados

Automatize a coleta de produtos e geração de links afiliados para **Mercado Livre**, **Amazon** e **Shopee**.

---

## 🚀 Instalação

### 1. Instale as dependências Python

```bash
pip install -r requirements.txt
```

### 2. Instale o navegador Chromium (necessário para modo real)

```bash
playwright install chromium
```

> ⚠️ Isso faz o download do Chromium (~150 MB). Necessário somente para mineração real (fora do Modo de Teste).

---

## ▶️ Como usar

O LinkMineer é um app **Flask**. O ponto de entrada é o `run.py`:

```bash
python run.py
```

Depois acesse `http://localhost:5000` no navegador.

### Variáveis de ambiente (opcionais)

Podem ser definidas no terminal ou em um arquivo `.env` na raiz do projeto:

| Variável | Padrão | Descrição |
|---|---|---|
| `PORT` | `5000` | Porta do servidor |
| `PLAYWRIGHT_HEADLESS` | `false` local / `true` no Railway | Roda o Chromium sem abrir janela |
| `ML_TRACKING_ID` | — | Tracking ID padrão do Mercado Livre |
| `AMAZON_TAG` | — | Tag de afiliado padrão da Amazon |
| `SHOPEE_ID` | — | Affiliate ID padrão da Shopee |

### Deploy (Railway)

O `Procfile` executa o `start.sh`, que instala o Chromium do Playwright e inicia o app com `python run.py` na porta definida em `$PORT`. A versão do Python está em `runtime.txt` (3.11).

---

## 🧪 Modo de Teste (sem navegador)

Marque a opção **"🧪 Modo de Teste"** na barra lateral para testar a interface e o download de planilhas **sem abrir o Chrome** e sem precisar de credenciais. Ideal para verificar se tudo está funcionando corretamente antes de usar com uma conta real.

---

## ⚙️ Configuração dos Marketplaces

| Marketplace | Campo necessário | Onde encontrar |
|---|---|---|
| **Amazon** | Tag de afiliado (ex: `seunome-20`) | [Central de Afiliados Amazon](https://associados.amazon.com.br) → Resumo → Tag padrão |
| **Mercado Livre** | Tracking ID / Matt Tool | [Programa de Afiliados ML](https://www.mercadoafiliados.com) → Ferramentas → Matt Tool |
| **Shopee** | Affiliate ID | [Shopee Affiliate](https://affiliate.shopee.com.br) → Conta → ID do afiliado |

### Autenticação

Você pode autenticar de duas formas:
- **Cookies (JSON)**: Exporte os cookies da sessão logada via DevTools do Chrome (F12 → Application → Cookies) e cole no campo.
- **Credenciais**: Usuário e senha (o Chromium abrirá para você resolver captchas/2FA manualmente se necessário).

---

## 📊 Saída

A planilha gerada contém as colunas:

| marketplace | link_produto | link_afiliado |
|---|---|---|
| Amazon | `https://www.amazon.com.br/dp/...` | `https://www.amazon.com.br/dp/...?tag=suatag-20` |
| Mercado Livre | `https://www.mercadolivre.com.br/...` | `...?tracking_id=seu_tracking` |
| Shopee | `https://shopee.com.br/...` | `...?aff_id=seu_id&aff_platform=affiliate` |

Disponível para download em **CSV** e **XLSX**.

---

## ⚠️ Observações importantes

- Os marketplaces podem bloquear acesso automatizado (captcha, bot detection). Nesses casos, o Chromium abre visivelmente para você resolver o desafio manualmente.
- Certifique-se de que sua conta de afiliado está ativa em cada marketplace antes de usar.
- Respeite os Termos de Serviço de cada marketplace ao usar este tool.
