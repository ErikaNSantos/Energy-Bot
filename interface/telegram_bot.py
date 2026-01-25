import telebot
import sqlite3
import os
import json
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

print("Iniciando bot do Telegram...")

# --- CONFIGURAÇÕES ---
load_dotenv()

CHAVE_API = os.getenv("TELEGRAM_TOKEN") 

if not CHAVE_API:
    print("ERRO: Token não encontrado! Crie o arquivo .env ou verifique o nome da variável.")
    exit()

bot = telebot.TeleBot(CHAVE_API)

# --- 1. DICIONÁRIO DE POTÊNCIAS ---
POTENCIAS = {
    "Chuveiro": {
        "Desligado": 0,
        "⚫": 2500,
        "⚫⚫": 5500,
        "⚫⚫⚫": 7500
    },

    # Os valores considerados para o ar condicionado foram aproximados tendo como base:
    # Fonte: ACEEE (American Council for an Energy-Efficient Economy)
    # Estima-se 3-5% de aumento de consumo para cada 1°F reduzido.
    # Convertendo para Celsius (x1.8): ~5.4% a 9%.
    # Adotei 7% como média conservadora, utilizando média geométrica.
    "Ar Condicionado": {
        "Congelando (17°C a 20°C)": 900,
        "Frio (21°C a 24°C)": 750,
        "Usual (26°C)": 580              
    },
    "Máquina de Lavar": {
        "Delicado/Esporte": 0.25,
        "Rápido": 0.15,
        "Normal": 0.34,
        "Escuras/Coloridas": 0.34,
        "Brancas": 0.34,
        "Pesadas": 0.45,
        "Centrifugação": 0.10
    },
    "Ventilador": {
        "Gear 0": 0,
        "Gear 1": 35,
        "Gear 2": 42,
        "Gear 3": 50
    }
}

# --- FUNÇÕES AUXILIARES ---
def conectar_banco():
    # Garante que acha o caminho certo independente de onde roda
    caminho_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'logs.db')
    return sqlite3.connect(caminho_db)

def carregar_tarifa():
    caminho_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'config.json')
    try:
        with open(caminho_config, 'r') as f:
            config = json.load(f)
            return config.get('tarifa_base', 0.92) + config.get('adicional_bandeira', 0.0)
    except FileNotFoundError:
        return 0.95

# --- 2. MENUS E BOTÕES ---

@bot.message_handler(commands=['start'])
def menu_principal(mensagem):
    teclado = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    # Seus apelidos personalizados
    btn1 = KeyboardButton("❄️ Artolfo")
    btn2 = KeyboardButton("🌀 Versares")
    btn3 = KeyboardButton("🚿 Shauna")
    btn4 = KeyboardButton("🧺 Morrisse")
    btn5 = KeyboardButton("🔴 Desligar Algo")
    
    teclado.add(btn1, btn2, btn3, btn4, btn5)
    bot.reply_to(mensagem, "Olá! Quem vamos monitorar agora?", reply_markup=teclado)

def criar_menu_aparelho(mensagem, categoria_dicionario, prefixo_apelido):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    
    for nome_opcao in POTENCIAS[categoria_dicionario].keys():
        # Agora o prefixo será o Apelido (Ex: Artolfo|Congelando)
        markup.add(InlineKeyboardButton(nome_opcao, callback_data=f"{prefixo_apelido}|{nome_opcao}"))
    
    bot.reply_to(mensagem, f"Configurar {prefixo_apelido}:", reply_markup=markup)

# --- 3. HANDLERS DE COMANDO (Texto -> Menu) ---

# CORREÇÃO 2: O bot agora escuta o APELIDO, não o nome técnico
@bot.message_handler(func=lambda m: m.text == "❄️ Artolfo")
def menu_ac(m):
    # CORREÇÃO 3: Enviamos "Artolfo" como prefixo para bater com a lógica lá embaixo
    criar_menu_aparelho(m, "Ar Condicionado", "Artolfo")

@bot.message_handler(func=lambda m: m.text == "🌀 Versares")
def menu_vent(m):
    criar_menu_aparelho(m, "Ventilador", "Versares")

@bot.message_handler(func=lambda m: m.text == "🚿 Shauna")
def menu_chuveiro(m):
    criar_menu_aparelho(m, "Chuveiro", "Shauna")

@bot.message_handler(func=lambda m: m.text == "🧺 Morrisse")
def menu_maquina(m):
    criar_menu_aparelho(m, "Máquina de Lavar", "Morrisse")

# --- 4. PROCESSAR CLIQUES ---

@bot.callback_query_handler(func=lambda call: "|" in call.data)
def processar_escolha(call):
    prefixo, opcao = call.data.split("|", 1)
    
    # Mapa de Tradução: Apelido -> Nome Técnico no Dicionário
    mapa_categorias = {
        "Artolfo": "Ar Condicionado",
        "Versares": "Ventilador",
        "Shauna": "Chuveiro",
        "Morrisse": "Máquina de Lavar"
    }
    
    # Se clicar em "Desligar", o prefixo não vai estar aqui, então ignoramos
    if prefixo not in mapa_categorias:
        return 
        
    categoria_tecnica = mapa_categorias[prefixo]
    
    # Busca o valor usando o nome técnico
    valor = POTENCIAS[categoria_tecnica][opcao]
    user_id = call.from_user.id
    
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # LÓGICA A: MÁQUINA DE LAVAR
    if categoria_tecnica == "Máquina de Lavar":
        preco_kwh = carregar_tarifa()
        custo = valor * preco_kwh
        
        cursor.execute("""
            INSERT INTO historico_uso 
            (user_id, aparelho_nome, detalhe, consumo_kwh_estimado, duracao_minutos)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, categoria_tecnica, opcao, valor, 0))
        
        msg = f"✅ {prefixo} (Máquina) registrada!\nCiclo: {opcao}\n⚡ Energia: {valor} kWh\n💰 Custo: R$ {custo:.2f}"

    # LÓGICA B: APARELHOS DE TEMPO
    else:
        if valor == 0:
             msg = f"⏸️ {prefixo} está descansando (0W)."
        else:
            try:
                # Salva o apelido no banco pra ficar bonitinho? 
                # Sugestão: Salve o nome técnico para facilitar cálculos, use apelido só na mensagem
                cursor.execute("""
                    INSERT INTO sessoes_ativas (user_id, aparelho_nome, detalhe) 
                    VALUES (?, ?, ?)
                """, (user_id, categoria_tecnica, f"{opcao}|{valor}")) # Salvando nome técnico
                msg = f"⏱️ {prefixo} Ligado!\nModo: {opcao}\nPotência: {valor}W"
            except sqlite3.IntegrityError:
                msg = f"⚠️ {prefixo} já está trabalhando! Desligue antes."

    conn.commit()
    conn.close()
    
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)

# --- 5. DESLIGAR ---

@bot.message_handler(func=lambda m: m.text == "🔴 Desligar Algo")
def menu_desligar(mensagem):
    user_id = mensagem.from_user.id
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT aparelho_nome, detalhe FROM sessoes_ativas WHERE user_id = ?", (user_id,))
    ativos = cursor.fetchall()
    conn.close()
    
    if not ativos:
        bot.reply_to(mensagem, "Tudo desligado! A casa está em silêncio. 😴")
        return

    markup = InlineKeyboardMarkup()
    for nome_tecnico, detalhe in ativos:
        # Tenta achar o apelido para mostrar no botão de desligar
        apelido_display = nome_tecnico
        if nome_tecnico == "Ar Condicionado": apelido_display = "Artolfo"
        if nome_tecnico == "Ventilador": apelido_display = "Versares"
        if nome_tecnico == "Chuveiro": apelido_display = "Shauna"

        modo_nome = detalhe.split("|")[0]
        markup.add(InlineKeyboardButton(f"Desligar {apelido_display}", callback_data=f"stop_{nome_tecnico}"))
        
    bot.reply_to(mensagem, "Quem você quer desligar?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("stop_"))
def executar_desligamento(call):
    # O callback vem como "stop_Ar Condicionado" (nome técnico salvo no banco)
    aparelho_tecnico = call.data.split("_")[1]
    user_id = call.from_user.id
    
    conn = conectar_banco()
    cursor = conn.cursor()
    
    cursor.execute("SELECT timestamp_inicio, detalhe FROM sessoes_ativas WHERE user_id = ? AND aparelho_nome = ?", (user_id, aparelho_tecnico))
    dados = cursor

if __name__ == "__main__":
    print("Entrando no modo de espera (polling)...")
    bot.polling()