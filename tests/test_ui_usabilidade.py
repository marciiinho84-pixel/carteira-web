#!/usr/bin/env python3
"""
Bateria de usabilidade — 9 cenários na interface web Streamlit.
Data: 2026-05-18
"""
import time
import requests
import json
from playwright.sync_api import sync_playwright

API = "http://localhost:8000/api/v1"
UI = "http://localhost:8501"
results = []


def log(n, status, msg):
    s = f"{status} Cenário {n}: {msg}"
    results.append(s)
    print(s, flush=True)


def api_get(endpoint):
    try:
        r = requests.get(f"{API}/{endpoint}", timeout=10)
        return r.json()
    except Exception as e:
        print(f"  [api_get error] {endpoint}: {e}")
        return None


def navigate(page, name):
    page.get_by_text(name, exact=True).first.click()
    time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    time.sleep(1)


def select_combobox(page, aria_contains, option_text):
    """Select option from Streamlit combobox by aria-label fragment."""
    cb = page.locator(f'input[role="combobox"][aria-label*="{aria_contains}"]').first
    cb.click()
    time.sleep(0.4)
    cb.fill("")
    cb.type(option_text, delay=50)
    time.sleep(1.2)
    try:
        opts = page.locator('[role="option"]')
        if opts.count() == 0:
            return False
        # Pick exact match first
        exact = opts.filter(has_text=option_text)
        if exact.count() > 0:
            exact.first.click()
        else:
            opts.first.click()
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"  [select_combobox error] {aria_contains}={option_text}: {e}")
        return False


def fill_date(page, date_str):
    """Fill date input DD/MM/YYYY."""
    di = page.locator('[data-testid="stDateInputField"]').first
    di.click()
    di.fill(date_str)
    di.press("Tab")
    time.sleep(0.5)


def fill_number(page, idx, value):
    """Fill number input by positional index."""
    ni = page.locator('[data-testid="stNumberInputField"]').nth(idx)
    ni.click()
    ni.fill(str(value))
    ni.press("Tab")
    time.sleep(0.5)


def submit_event(page):
    """Click Salvar e Recalcular and wait for engine."""
    btn = page.locator('[data-testid="stBaseButton-primary"]').filter(
        has_text="Salvar e Recalcular"
    )
    btn.wait_for(timeout=5000)
    btn.click()
    time.sleep(6)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    time.sleep(2)


def body_text(page):
    return page.inner_text("body")


# ─────────────────────────────────────────────────────────────────────────────
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(UI, wait_until="networkidle", timeout=30000)
    time.sleep(4)

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 1 — BBAS3 não está em CAD_ATIVOS
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 1 ===")
    navigate(page, "➕ Novo Evento")

    cb = page.locator('input[role="combobox"]').first
    cb.click()
    time.sleep(0.3)
    cb.fill("BBAS3")
    time.sleep(1.2)

    opts = page.locator('[role="option"]').count()
    page_body = body_text(page)

    if opts == 0 or "BBAS3" not in page_body:
        log(1, "✅",
            "BBAS3 não encontrado no dropdown — evento bloqueado (ativo não cadastrado)")
    else:
        log(1, "⚠️",
            f"BBAS3 apareceu no dropdown ({opts} opção/ões) — verificar cadastro")

    cb.click()
    cb.fill("")
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    time.sleep(0.5)

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 2 — Cadastrar BBAS3 via Configurações
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 2 ===")
    navigate(page, "⚙️ Configurações")
    time.sleep(1)
    page_body = body_text(page)

    has_add = any(kw in page_body for kw in [
        "Cadastrar novo", "Novo ativo", "Adicionar ativo", "Ticker novo",
        "cadastrar ativo", "add ativo",
    ])

    if has_add:
        log(2, "⚠️",
            "Formulário de cadastro de novo ativo encontrado — funcionalidade implementada")
    else:
        log(2, "❌",
            "Configurações não tem formulário para cadastrar novo ativo — "
            "BBAS3 não pode ser adicionado via UI (funcionalidade não implementada)")

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 3 — VENDA 50 WEGE3: PEPS + P&L
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 3 ===")
    wege_antes = next(
        (x for x in (api_get("posicoes") or []) if x["ticker"] == "WEGE3"), None
    )
    print(f"  WEGE3 antes: qtd={wege_antes['qtd'] if wege_antes else '?'}, "
          f"custo_medio={wege_antes['custo_medio'] if wege_antes else '?'}")

    navigate(page, "➕ Novo Evento")
    select_combobox(page, "Ativo", "WEGE3")
    select_combobox(page, "Tipo de Evento", "VENDA")
    fill_date(page, "18/05/2026")
    # 50 × 43.13 → P&L = 50 × (43.13 − 47.3182) = −R$209.41
    fill_number(page, 0, 50)
    fill_number(page, 1, 43.13)
    time.sleep(1)

    submit_event(page)
    page_body = body_text(page)

    wege_depois = next(
        (x for x in (api_get("posicoes") or []) if x["ticker"] == "WEGE3"), None
    )
    vendas_list = api_get("vendas") or []
    wege_vendas = [v for v in vendas_list if v.get("ticker") == "WEGE3"]
    print(f"  WEGE3 depois: {wege_depois}")
    print(f"  WEGE3 vendas: {wege_vendas}")

    if "✅" in page_body or "Evento salvo" in page_body:
        cm = wege_depois["custo_medio"] if wege_depois else None
        pnl_v = wege_vendas[-1].get("pnl_realizado") if wege_vendas else None
        pnl_ok = pnl_v is not None and abs(pnl_v - (-209.41)) < 1.0
        cm_ok = cm is not None and abs(cm - 47.3182) < 0.001
        if cm_ok and pnl_ok:
            log(3, "✅",
                f"VENDA 50 WEGE3 — custo_medio={cm:.4f} ✓, P&L={pnl_v:.2f} ✓")
        elif cm_ok:
            log(3, "⚠️",
                f"VENDA 50 WEGE3 — custo_medio={cm:.4f} ✓, P&L={pnl_v} "
                f"(esperado -209.41)")
        else:
            log(3, "❌",
                f"VENDA 50 WEGE3 — custo_medio={cm} (esperado 47.3182), "
                f"P&L={pnl_v}")
    else:
        log(3, "❌", f"VENDA 50 WEGE3 não foi salva — body snippet: "
            f"{page_body[page_body.find('Novo Evento'):page_body.find('Novo Evento')+200]}")

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 4 — JCP ITUB3 R$87: não aparece em Vendas, posição inalterada
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 4 ===")
    itub_antes = next(
        (x for x in (api_get("posicoes") or []) if x["ticker"] == "ITUB3"), None
    )

    navigate(page, "➕ Novo Evento")
    select_combobox(page, "Ativo", "ITUB3")
    select_combobox(page, "Tipo de Evento", "JCP")
    fill_date(page, "18/05/2026")
    # JCP: apenas Valor R$ (sem qtd/preco)
    fill_number(page, 0, 87.0)
    time.sleep(0.5)

    submit_event(page)
    page_body = body_text(page)

    itub_depois = next(
        (x for x in (api_get("posicoes") or []) if x["ticker"] == "ITUB3"), None
    )
    vendas_list2 = api_get("vendas") or []
    itub_vendas = [v for v in vendas_list2 if v.get("ticker") == "ITUB3"]

    saved = "Evento salvo" in page_body or "✅" in page_body
    qtd_ok = (itub_antes and itub_depois and
               itub_depois["qtd"] == itub_antes["qtd"])
    sem_venda = len(itub_vendas) == 0

    if saved and qtd_ok and sem_venda:
        log(4, "✅",
            f"JCP ITUB3 R$87 — posição inalterada (qtd={itub_depois['qtd']}), "
            f"não aparece em Vendas ✓")
    elif not saved:
        log(4, "❌", "JCP ITUB3 não foi salvo")
    elif not qtd_ok:
        log(4, "⚠️",
            f"JCP salvo mas qtd alterada: antes={itub_antes['qtd'] if itub_antes else '?'}, "
            f"depois={itub_depois['qtd'] if itub_depois else '?'}")
    else:
        log(4, "⚠️",
            f"JCP salvo, qtd OK, mas aparece em Vendas: {itub_vendas}")

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 5 — RENDIMENTO CAIXA LCI R$180: não afeta caixa FIC FUNC
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 5 ===")
    rv_antes = api_get("carteira-rv") or {}
    caixa_antes = rv_antes.get("caixa_atual", 0)

    navigate(page, "➕ Novo Evento")
    select_combobox(page, "Ativo", "CAIXA LCI")
    select_combobox(page, "Tipo de Evento", "RENDIMENTO")
    fill_date(page, "18/05/2026")
    fill_number(page, 0, 180.0)
    time.sleep(0.5)

    submit_event(page)
    page_body = body_text(page)

    rv_depois = api_get("carteira-rv") or {}
    caixa_depois = rv_depois.get("caixa_atual", 0)

    saved = "Evento salvo" in page_body or "✅" in page_body
    caixa_igual = abs(caixa_depois - caixa_antes) < 0.01

    if saved and caixa_igual:
        log(5, "✅",
            f"RENDIMENTO CAIXA LCI R$180 — caixa FIC FUNC inalterado "
            f"(R${caixa_antes:.2f} → R${caixa_depois:.2f}) ✓")
    elif saved and not caixa_igual:
        log(5, "⚠️",
            f"RENDIMENTO salvo mas caixa FIC FUNC mudou: "
            f"R${caixa_antes:.2f} → R${caixa_depois:.2f}")
    else:
        log(5, "❌", "RENDIMENTO CAIXA LCI não foi salvo")

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 6 — VENDA CAIXA FIC FUNC 800 cotas × R$2.9519
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 6 ===")
    rv_antes6 = api_get("carteira-rv") or {}
    caixa_antes6 = rv_antes6.get("caixa_atual", 0)
    pendentes_antes = len(rv_antes6.get("pendentes", []))

    navigate(page, "➕ Novo Evento")
    select_combobox(page, "Ativo", "CAIXA FIC FUNC")
    select_combobox(page, "Tipo de Evento", "VENDA")
    fill_date(page, "18/05/2026")
    # 800 cotas (disponível: ~833) × R$2.9519
    fill_number(page, 0, 800)
    fill_number(page, 1, 2.9519)
    time.sleep(1)

    submit_event(page)
    page_body = body_text(page)

    rv_depois6 = api_get("carteira-rv") or {}
    saldo_proj6 = rv_depois6.get("saldo_projetado", 0)
    pendentes6 = rv_depois6.get("pendentes", [])
    venda_fic = [x for x in pendentes6 if x.get("ativo") == "CAIXA FIC FUNC"
                 and x.get("tipo") == "VENDA"]

    saved = "Evento salvo" in page_body or "✅" in page_body
    d2_verde = any(x.get("impacto", 0) > 0 for x in venda_fic)

    if saved and d2_verde:
        log(6, "✅",
            f"VENDA CAIXA FIC FUNC 800 cotas — "
            f"saldo projetado={saldo_proj6:.2f}, "
            f"D+2 verde (impacto positivo) ✓")
    elif saved and not d2_verde:
        log(6, "⚠️",
            f"VENDA salva mas D+2 não mostra impacto positivo — "
            f"pendentes com FIC FUNC: {venda_fic}")
    else:
        log(6, "❌",
            f"VENDA CAIXA FIC FUNC não foi salva — "
            f"snippet: {page_body[:300]}")

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 7 — 3 COMPRAs TTEN3: datas diferentes → D+2 status
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 7 ===")
    compras_tten = [
        ("A", "18/05/2026"),  # hoje → D+2=20/05 → pendente → 🟡
        ("B", "13/05/2026"),  # 5 dias atrás → D+2=15/05 → liquidado → 🟢
        ("C", "17/05/2026"),  # 1 dia atrás → D+2=21/05 → pendente → 🟡
    ]

    for letra, dt in compras_tten:
        print(f"  Inserindo COMPRA TTEN3 {letra} ({dt})...")
        navigate(page, "➕ Novo Evento")
        select_combobox(page, "Ativo", "TTEN3")
        select_combobox(page, "Tipo de Evento", "COMPRA")
        fill_date(page, dt)
        fill_number(page, 0, 50)    # 50 cotas
        fill_number(page, 1, 16.35) # preço ~custo_medio
        time.sleep(1)
        submit_event(page)
        pb = body_text(page)
        saved = "Evento salvo" in pb or "✅" in pb
        print(f"  COMPRA {letra}: {'salva' if saved else 'ERRO'}")

    rv7 = api_get("carteira-rv") or {}
    pendentes7 = rv7.get("pendentes", [])
    tten_pendentes = [x for x in pendentes7 if x.get("ativo") == "TTEN3"]

    print(f"  TTEN3 no D+2 calendar: {tten_pendentes}")

    # A (18/05) → D+2=20/05 → deveria estar em pendentes (não liquidado ainda)
    # B (13/05) → D+2=15/05 → já liquidado → NÃO em pendentes
    # C (17/05) → D+2=21/05 → deveria estar em pendentes
    liquidacao_datas = sorted(set(x["liquidacao"] for x in tten_pendentes))
    tem_20_05 = any(x["liquidacao"] == "2026-05-20" for x in tten_pendentes)
    tem_21_05 = any(x["liquidacao"] == "2026-05-21" for x in tten_pendentes)
    nao_tem_15_05 = not any(x["liquidacao"] == "2026-05-15" for x in tten_pendentes)

    if tem_20_05 and tem_21_05 and nao_tem_15_05:
        log(7, "✅",
            f"3 COMPRAs TTEN3 — A(20/05 pendente🟡)✓, "
            f"B(15/05 já liquidado🟢)✓, C(21/05 pendente🟡)✓")
    else:
        log(7, "⚠️",
            f"3 COMPRAs TTEN3 — liquidações no D+2: {liquidacao_datas} "
            f"(esperado 2026-05-20 e 2026-05-21, sem 2026-05-15) "
            f"— tem_20={tem_20_05}, tem_21={tem_21_05}, sem_15={nao_tem_15_05}")

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 8 — COMPRA DIVO11 errada (R$9999), tentar editar
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 8 ===")
    navigate(page, "➕ Novo Evento")
    select_combobox(page, "Ativo", "DIVO11")
    select_combobox(page, "Tipo de Evento", "COMPRA")
    fill_date(page, "18/05/2026")
    fill_number(page, 0, 1)      # 1 cota
    fill_number(page, 1, 9999.0) # preço errado
    time.sleep(1)

    submit_event(page)
    page_body = body_text(page)
    saved_errado = "Evento salvo" in page_body or "✅" in page_body

    if saved_errado:
        # Verificar evento na lista
        eventos = api_get("eventos") or []
        divo_eventos = [e for e in eventos
                        if e.get("ativo") == "DIVO11"
                        and float(e.get("preco", 0) or 0) > 9000]
        evento_id = divo_eventos[-1]["id"] if divo_eventos else None

        # Tentar editar via UI — verificar se existe botão de edição
        navigate(page, "⚙️ Configurações")
        page_body2 = body_text(page)
        has_edit_event = any(kw in page_body2 for kw in [
            "Editar evento", "Editar DIVO11", "eventos", "Evento ID",
        ])

        if has_edit_event:
            log(8, "⚠️",
                f"COMPRA DIVO11 R$9999 salva (evento_id={evento_id}), "
                f"e interface de edição de eventos encontrada")
        else:
            log(8, "❌",
                f"COMPRA DIVO11 R$9999 salva (evento_id={evento_id}), "
                f"MAS não há interface para editar eventos — "
                f"erro não pode ser corrigido pela UI")
    else:
        log(8, "❌",
            f"COMPRA DIVO11 R$9999 não foi salva — snippet: {page_body[:200]}")

    # ═══════════════════════════════════════════════════════
    # CENÁRIO 9 — COMPRA EMBJ3 500 cotas × R$70 = R$35.000
    # ═══════════════════════════════════════════════════════
    print("\n=== CENÁRIO 9 ===")
    rv_antes9 = api_get("carteira-rv") or {}
    caixa_antes9 = rv_antes9.get("caixa_atual", 0)
    print(f"  Caixa antes: R${caixa_antes9:.2f}")

    navigate(page, "➕ Novo Evento")
    select_combobox(page, "Ativo", "EMBJ3")
    select_combobox(page, "Tipo de Evento", "COMPRA")
    fill_date(page, "18/05/2026")
    fill_number(page, 0, 500)
    fill_number(page, 1, 70.0)  # 500 × 70 = R$35,000
    time.sleep(1)

    submit_event(page)
    page_body = body_text(page)
    saved9 = "Evento salvo" in page_body or "✅" in page_body

    if saved9:
        # Navigate to Carteira RV to check alert
        navigate(page, "📊 Carteira RV")
        rv_body = body_text(page)
        rv9 = api_get("carteira-rv") or {}
        saldo9 = rv9.get("saldo_projetado", 0)
        caixa9 = rv9.get("caixa_atual", 0)
        print(f"  Caixa depois: R${caixa9:.2f}, Saldo projetado: R${saldo9:.2f}")

        alerta_neg = "ATENÇÃO" in rv_body or "caixa projetado fica em" in rv_body
        if saldo9 < 0:
            if alerta_neg:
                log(9, "✅",
                    f"COMPRA EMBJ3 500×R$70 — saldo projetado={saldo9:.2f} negativo, "
                    f"alerta vermelho exibido na Carteira RV ✓")
            else:
                log(9, "⚠️",
                    f"COMPRA EMBJ3 500×R$70 — saldo projetado={saldo9:.2f} negativo "
                    f"MAS alerta não encontrado no body")
        else:
            log(9, "⚠️",
                f"COMPRA EMBJ3 500×R$70 salva — saldo projetado={saldo9:.2f} "
                f"(esperado negativo, caixa insuficiente)")
    else:
        log(9, "❌",
            f"COMPRA EMBJ3 500×R$70 não foi salva — snippet: {page_body[:300]}")

    browser.close()

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("RESULTADOS FINAIS")
print("=" * 60)
for r in results:
    print(r)

n_ok = sum(1 for r in results if r.startswith("✅"))
n_warn = sum(1 for r in results if r.startswith("⚠️"))
n_fail = sum(1 for r in results if r.startswith("❌"))
print(f"\nResumo: {n_ok}✅ {n_warn}⚠️ {n_fail}❌  (de {len(results)} cenários)")
