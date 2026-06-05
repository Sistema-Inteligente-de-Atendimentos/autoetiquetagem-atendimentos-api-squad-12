from app.core.taxonomy import (
    CATEGORIAS_FIXAS,
    calcular_score_final,
    montar_categorias,
    validar_classificacao,
)


# ---------- calcular_score_final ----------

def test_score_media_simples():
    q = {"empatia": 7, "clareza": 8, "objetividade": 9, "resolutividade": 6}
    assert calcular_score_final(q) == 7.5


def test_score_todos_dez():
    q = {"empatia": 10, "clareza": 10, "objetividade": 10, "resolutividade": 10}
    assert calcular_score_final(q) == 10.0


def test_score_qualidade_vazia():
    assert calcular_score_final({}) == 0.0


def test_score_ignora_campos_invalidos():
    q = {"empatia": "abc", "clareza": 8, "objetividade": 8, "resolutividade": 8}
    # empatia inválida vira 0 → (0+8+8+8)/4 = 6.0
    assert calcular_score_final(q) == 6.0


# ---------- validar_classificacao ----------

def test_categoria_fora_da_taxonomia_vira_outros():
    r = validar_classificacao({"categoria": "Cobrança"})
    assert r["categoria"] == "Outros"


def test_categoria_normaliza_acento_e_caixa():
    r = validar_classificacao({"categoria": "financeiro"})
    assert r["categoria"] == "Financeiro"


def test_sentimento_normalizado():
    r = validar_classificacao({"sentimento": "negativo"})
    assert r["sentimento"] == "Negativo"


def test_criticidade_normalizada():
    r = validar_classificacao({"criticidade": "alta"})
    assert r["criticidade"] == "Alta"


def test_valores_ausentes_usam_padrao():
    r = validar_classificacao({})
    assert r["categoria"] == "Outros"
    assert r["sentimento"] == "Neutro"
    assert r["criticidade"] == "Média"


def test_score_final_recalculado_na_validacao():
    r = validar_classificacao({
        "qualidade": {"empatia": 6, "clareza": 6, "objetividade": 6, "resolutividade": 6}
    })
    assert r["qualidade"]["score_final"] == 6.0


def test_categoria_customizada_aceita():
    r = validar_classificacao({"categoria": "Jurídico"}, categorias=["Financeiro", "Jurídico"])
    assert r["categoria"] == "Jurídico"


# ---------- montar_categorias ----------

def test_montar_categorias_sem_extras():
    assert montar_categorias() == list(CATEGORIAS_FIXAS)


def test_montar_categorias_com_extra():
    cats = montar_categorias(["Jurídico"])
    assert "Jurídico" in cats
    assert len(cats) == len(CATEGORIAS_FIXAS) + 1


def test_montar_categorias_nao_duplica_fixa():
    cats = montar_categorias(["Financeiro", "Outros"])
    # ambas já são fixas → nada adicionado
    assert len(cats) == len(CATEGORIAS_FIXAS)
