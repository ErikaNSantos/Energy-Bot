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
    btn1 = KeyboardButton("❄️ Artolfo")
    btn2 = KeyboardButton("🌀 Versares")
    btn3 = KeyboardButton("🚿 Shauna")
    btn4 = KeyboardButton("🧺 Morrisse")
    btn5 = KeyboardButton("🔴 Desligar Algo")
    btn6 = KeyboardButton("📊 Relatório (/invoice)")
    
    teclado.add(btn1, btn2, btn3, btn4, btn5, btn6)
    bot.reply_to(mensagem, "Olá! Quem vamos monitorar agora?", reply_markup=teclado)

def criar_menu_aparelho(mensagem, categoria_dicionario, prefixo_apelido):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    
    for nome_opcao in POTENCIAS[categoria_dicionario].keys():
        markup.add(InlineKeyboardButton(nome_opcao, callback_data=f"{prefixo_apelido}|{nome_opcao}"))
    
    bot.reply_to(mensagem, f"Configurar {prefixo_apelido}:", reply_markup=markup)

# --- 3. HANDLERS DE COMANDO ---

@bot.message_handler(func=lambda m: m.text == "❄️ Artolfo")
def menu_ac(m):
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

@bot.callback_query_handler(func=lambda call: "|" in call.data and not call.data.startswith("stop_"))
def processar_escolha(call):
    prefixo, opcao = call.data.split("|", 1)
    mapa_categorias = {
        "Artolfo": "Ar Condicionado",
        "Versares": "Ventilador",
        "Shauna": "Chuveiro",
        "Morrisse": "Máquina de Lavar"
    }
    
    if prefixo not in mapa_categorias:
        return 
        
    categoria_tecnica = mapa_categorias[prefixo]
    valor = POTENCIAS[categoria_tecnica][opcao]
    user_id = call.from_user.id
    
    conn = conectar_banco()
    cursor = conn.cursor()
    
    if categoria_tecnica == "Máquina de Lavar":
        preco_kwh = carregar_tarifa()
        custo = valor * preco_kwh
        cursor.execute("""
            INSERT INTO historico_uso 
            (user_id, aparelho_nome, detalhe, consumo_kwh_estimado, duracao_minutos)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, categoria_tecnica, opcao, valor, 0))
        msg = f"✅ {prefixo} (Máquina) registrada!\nCiclo: {opcao}\n⚡ Energia: {valor} kWh\n💰 Custo: R$ {custo:.2f}"
    else:
        if valor == 0:
             msg = f"⏸️ {prefixo} está descansando (0W)."
        else:
            try:
                cursor.execute("""
                    INSERT INTO sessoes_ativas (user_id, aparelho_nome, detalhe) 
                    VALUES (?, ?, ?)
                """, (user_id, categoria_tecnica, f"{opcao}|{valor}"))
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
        apelido_display = nome_tecnico
        if nome_tecnico == "Ar Condicionado": apelido_display = "Artolfo"
        if nome_tecnico == "Ventilador": apelido_display = "Versares"
        if nome_tecnico == "Chuveiro": apelido_display = "Shauna"
        markup.add(InlineKeyboardButton(f"Desligar {apelido_display}", callback_data=f"stop_{nome_tecnico}"))
        
    bot.reply_to(mensagem, "Quem você quer desligar?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("stop_"))
def executar_desligamento(call):
    aparelho_tecnico = call.data.split("_")[1]
    user_id = call.from_user.id
    
    conn = conectar_banco()
    cursor = conn.cursor()
    
    cursor.execute("SELECT timestamp_inicio, detalhe FROM sessoes_ativas WHERE user_id = ? AND aparelho_nome = ?", (user_id, aparelho_tecnico))
    sessao = cursor.fetchone()
    
    if sessao:
        inicio = datetime.strptime(sessao[0], '%Y-%m-%d %H:%M:%S')
        fim = datetime.now()
        duracao_segundos = (fim - inicio).total_seconds()
        duracao_minutos = duracao_segundos / 60
        
        detalhe = sessao[1]
        modo, potencia = detalhe.split("|")
        potencia = float(potencia)
        
        consumo_kwh = (potencia * (duracao_segundos / 3600)) / 1000
        preco_kwh = carregar_tarifa()
        custo = consumo_kwh * preco_kwh
        
        cursor.execute("DELETE FROM sessoes_ativas WHERE user_id = ? AND aparelho_nome = ?", (user_id, aparelho_tecnico))
        cursor.execute("""
            INSERT INTO historico_uso (user_id, aparelho_nome, detalhe, consumo_kwh_estimado, duracao_minutos)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, aparelho_tecnico, modo, consumo_kwh, duracao_minutos))
        
        apelido = aparelho_tecnico
        if aparelho_tecnico == "Ar Condicionado": apelido = "Artolfo"
        elif aparelho_tecnico == "Ventilador": apelido = "Versares"
        elif aparelho_tecnico == "Chuveiro": apelido = "Shauna"
        
        msg = f"✅ {apelido} Desligado!\n⏱️ Duração: {duracao_minutos:.1f} min\n⚡ Consumo: {consumo_kwh:.3f} kWh\n💰 Custo: R$ {custo:.2f}"
    else:
        msg = "⚠️ Erro: Sessão não encontrada."

    conn.commit()
    conn.close()
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)

# --- 6. RELATÓRIO /INVOICE ---

@bot.message_handler(commands=['invoice'])
@bot.message_handler(func=lambda m: m.text == "📊 Relatório (/invoice)")
def gerar_fatura(mensagem):
    user_id = mensagem.from_user.id
    conn = conectar_banco()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT aparelho_nome, SUM(consumo_kwh_estimado), SUM(duracao_minutos)
        FROM historico_uso 
        WHERE user_id = ? AND strftime('%m', timestamp) = strftime('%m', 'now')
        GROUP BY aparelho_nome
    """, (user_id,))
    
    dados = cursor.fetchall()
    conn.close()
    
    if not dados:
        bot.reply_to(mensagem, "Ainda não há registros para este mês. Economia total! 🍃")
        return
    
    tarifa = carregar_tarifa()
    total_kwh = 0
    total_reais = 0
    
    texto = "🧾 **FATURA PARCIAL DO MÊS**\n\n"
    for aparelho, kwh, minutos in dados:
        custo = kwh * tarifa
        total_kwh += kwh
        total_reais += custo
        
        apelido = aparelho
        if aparelho == "Ar Condicionado": apelido = "❄️ Artolfo"
        elif aparelho == "Ventilador": apelido = "🌀 Versares"
        elif aparelho == "Chuveiro": apelido = "🚿 Shauna"
        elif aparelho == "Máquina de Lavar": apelido = "🧺 Morrisse"
        
        texto += f"{apelido}:\n   ⚡ {kwh:.2f} kWh | 💰 R$ {custo:.2f}\n"
    
    # Adicionando o fator de ajuste (10% para microondas e luzes)
    fator_ajuste = total_reais * 0.10
    total_final = total_reais + fator_ajuste
    
    texto += f"\n---------------------------\n"
    texto += f"🔹 Subtotal: R$ {total_reais:.2f}\n"
    texto += f"➕ Ajuste (10%): R$ {fator_ajuste:.2f}\n"
    texto += f"💰 **TOTAL A PAGAR: R$ {total_final:.2f}**\n"
    texto += f"\n*Tarifa aplicada: R$ {tarifa:.2f}/kWh*"
    
    bot.reply_to(mensagem, texto, parse_mode="Markdown")

if __name__ == "__main__":
    print("Entrando no modo de espera (polling)...")
    bot.polling()
