from app.services.chat_parser import dividir_mensagens


def test_divide_cliente_atendente():
    msgs = dividir_mensagens("Cliente: Oi. Atendente: Olá.")
    assert msgs == [("cliente", "Oi."), ("atendente", "Olá.")]


def test_varios_turnos():
    texto = "Cliente: Erro 401. Atendente: Token expirou. Cliente: Funcionou!"
    msgs = dividir_mensagens(texto)
    assert len(msgs) == 3
    assert msgs[0][0] == "cliente"
    assert msgs[1][0] == "atendente"
    assert msgs[2][1] == "Funcionou!"


def test_texto_sem_marcador_vira_uma_mensagem():
    msgs = dividir_mensagens("Apenas um texto solto sem rótulos.")
    assert len(msgs) == 1
    assert msgs[0][0] == "cliente"


def test_texto_vazio_retorna_lista_vazia():
    assert dividir_mensagens("") == []
    assert dividir_mensagens("   ") == []


def test_marcadores_minusculos():
    msgs = dividir_mensagens("cliente: ola. atendente: oi.")
    assert len(msgs) == 2
    assert msgs[0][0] == "cliente"
    assert msgs[1][0] == "atendente"


def test_reconhece_nome_proprio_como_remetente():
    # quando o nome do atendente é informado, "Júlia:" deve mapear para atendente
    texto = "Cliente: Preciso de ajuda. Júlia: Claro, vou ajudar."
    msgs = dividir_mensagens(texto, atendente_nome="Júlia")
    assert any(r == "atendente" and "ajudar" in c for r, c in msgs)
