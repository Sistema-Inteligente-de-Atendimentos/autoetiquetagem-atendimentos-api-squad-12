from app.routes.categorias import normalizar_url_planilha

ID = "1SIL181AULJxQ3HucvbR7wyI4KHGs5lMaVs5d82hX-eE"
EXPORT = f"https://docs.google.com/spreadsheets/d/{ID}/export?format=csv&gid=0"


def test_url_de_edicao_vira_export():
    url = f"https://docs.google.com/spreadsheets/d/{ID}/edit?usp=sharing"
    assert normalizar_url_planilha(url) == EXPORT


def test_url_com_gid_no_hash():
    url = f"https://docs.google.com/spreadsheets/d/{ID}/edit#gid=123"
    assert normalizar_url_planilha(url) == f"https://docs.google.com/spreadsheets/d/{ID}/export?format=csv&gid=123"


def test_url_ja_export_mantem():
    assert normalizar_url_planilha(EXPORT) == EXPORT


def test_apenas_o_id():
    assert normalizar_url_planilha(ID) == EXPORT


def test_url_vazia():
    assert normalizar_url_planilha("") == ""


def test_url_nao_reconhecida_retorna_original():
    outra = "https://exemplo.com/planilha.csv"
    assert normalizar_url_planilha(outra) == outra
