import telebot
import sqlite3
import os
import sys
import json
import io
import threading
import time
import calendar
from datetime import datetime, timezone
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from core import energia

print("Iniciando bot do Telegram...")

# --- CAMINHOS E CONFIG ---
load_dotenv()
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DB = os.path.join(RAIZ, 'data', 'logs.db')
CONFIG = os.path.join(RAIZ, 'data', 'config.json')

CHAVE_API = os.getenv("TELEGRAM_TOKEN")
if not CHAVE_API:
    print("ERRO: Token não encontrado! Crie o arquivo .env com TELEGRAM_TOKEN.")
    exit()

with open(CONFIG, encoding='utf-8') as f:
    CFG = json.load(f)

TARIFA = CFG['tarifa_base'] + CFG['adicional_bandeira']
APARELHOS = CFG['aparelhos']
BOTAO_PARA_NOME = {f"{a['emoji']} {a['apelido']}": nome for nome, a in APARELHOS.items()}

bot = telebot.TeleBot(CHAVE_API)


def conectar():
    return sqlite3.connect(DB, timeout=10)


def rotulo(nome):
    a = APARELHOS.get(nome, {})
    return f"{a.get('emoji', '')} {a.get('apelido', nome)}".strip()


# --- MENU PRINCIPAL ---
@bot.message_handler(commands=['start'])
def menu_principal(m):
    teclado = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    botoes = [KeyboardButton(f"{a['emoji']} {a['apelido']}") for a in APARELHOS.values()]
    botoes.append(KeyboardButton("🔴 Desligar Algo"))
    botoes.append(KeyboardButton("📊 Relatório"))
    teclado.add(*botoes)
    bot.reply_to(m, "Quem vamos monitorar agora?", reply_markup=teclado)


# --- ABRIR MENU DE UM APARELHO ---
@bot.message_handler(func=lambda m: m.text in BOTAO_PARA_NOME)
def abrir_aparelho(m):
    nome = BOTAO_PARA_NOME[m.text]
    a = APARELHOS[nome]
    markup = InlineKeyboardMarkup(row_width=1)
    for modo in a['potencias']:
        markup.add(InlineKeyboardButton(modo, callback_data=f"set|{nome}|{modo}"))
    bot.reply_to(m, f"Configurar {a['apelido']}:", reply_markup=markup)


# --- LIGAR / REGISTRAR ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("set|"))
def processar(c):
    _, nome, modo = c.data.split("|", 2)
    a = APARELHOS[nome]
    valor = a['potencias'][modo]
    uid = c.from_user.id

    conn = conectar()
    cur = conn.cursor()

    if a['tipo'] == 'ciclo':
        kwh = valor
        cst = energia.custo(kwh, TARIFA)
        cur.execute("""INSERT INTO historico_uso
                       (user_id, aparelho_nome, detalhe, consumo_kwh_estimado, duracao_minutos)
                       VALUES (?, ?, ?, ?, ?)""", (uid, nome, modo, kwh, 0))
        msg = f"✅ {rotulo(nome)} registrada\nCiclo: {modo}\n⚡ {kwh} kWh · 💰 R$ {cst:.2f}"
    else:
        if valor == 0:
            msg = f"⏸️ {a['apelido']} em repouso (0W)."
        else:
            try:
                cur.execute("""INSERT INTO sessoes_ativas
                               (user_id, aparelho_nome, detalhe, ja_alertado)
                               VALUES (?, ?, ?, 0)""", (uid, nome, f"{modo}|{valor}"))
                msg = f"⏱️ {rotulo(nome)} ligado\nModo: {modo} · {valor}W"
            except sqlite3.IntegrityError:
                msg = f"⚠️ {a['apelido']} já está ligado. Desligue antes."

    conn.commit()
    conn.close()
    bot.edit_message_text(msg, c.message.chat.id, c.message.message_id)
    

# --- DESLIGAR ---
@bot.message_handler(func=lambda m: m.text == "🔴 Desligar Algo")
def menu_desligar(m):
    uid = m.from_user.id
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT aparelho_nome FROM sessoes_ativas WHERE user_id = ?", (uid,))
    ativos = cur.fetchall()
    conn.close()

    if not ativos:
        bot.reply_to(m, "Tudo desligado. A casa está em silêncio. 😴")
        return

    markup = InlineKeyboardMarkup()
    for (nome,) in ativos:
        markup.add(InlineKeyboardButton(f"Desligar {APARELHOS[nome]['apelido']}",
                                        callback_data=f"stop|{nome}"))
    bot.reply_to(m, "Quem você quer desligar?", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("stop|"))
def desligar(c):
    nome = c.data.split("|", 1)[1]
    uid = c.from_user.id

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT timestamp_inicio, detalhe FROM sessoes_ativas WHERE user_id = ? AND aparelho_nome = ?",
                (uid, nome))
    s = cur.fetchone()

    if not s:
        conn.close()
        bot.edit_message_text("⚠️ Sessão não encontrada.", c.message.chat.id, c.message.message_id)
        return

    inicio = datetime.strptime(s[0], '%Y-%m-%d %H:%M:%S')
    fim = datetime.now(timezone.utc).replace(tzinfo=None)
    dur_min = (fim - inicio).total_seconds() / 60
    modo, pot = s[1].split("|")
    kwh = energia.consumo_kwh(float(pot), dur_min)
    cst = energia.custo(kwh, TARIFA)

    cur.execute("DELETE FROM sessoes_ativas WHERE user_id = ? AND aparelho_nome = ?", (uid, nome))
    cur.execute("""INSERT INTO historico_uso
                   (user_id, aparelho_nome, detalhe, consumo_kwh_estimado, duracao_minutos)
                   VALUES (?, ?, ?, ?, ?)""", (uid, nome, modo, kwh, dur_min))
    conn.commit()
    conn.close()

    msg = f"✅ {rotulo(nome)} desligado\n⏱️ {dur_min:.1f} min · ⚡ {kwh:.3f} kWh · 💰 R$ {cst:.2f}"
    bot.edit_message_text(msg, c.message.chat.id, c.message.message_id)


# --- RESET (limpa sessões órfãs) ---
@bot.message_handler(commands=['reset'])
def reset(m):
    uid = m.from_user.id
    conn = conectar()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessoes_ativas WHERE user_id = ?", (uid,))
    n = cur.rowcount
    conn.commit()
    conn.close()
    bot.reply_to(m, f"🧹 {n} sessão(ões) ativa(s) limpa(s). O histórico foi preservado.")


# --- RELATÓRIO ---
@bot.message_handler(commands=['invoice'])
@bot.message_handler(func=lambda m: m.text == "📊 Relatório")
def invoice(m):
    uid = m.from_user.id
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""SELECT aparelho_nome, SUM(consumo_kwh_estimado)
                   FROM historico_uso
                   WHERE user_id = ? AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
                   GROUP BY aparelho_nome""", (uid,))
    dados = cur.fetchall()

    cur.execute("""SELECT SUM(consumo_kwh_estimado)
                   FROM historico_uso
                   WHERE user_id = ? AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now', '-1 month')""",
                (uid,))
    kwh_anterior = cur.fetchone()[0] or 0
    conn.close()

    agora = datetime.now(timezone.utc)
    dias_mes = calendar.monthrange(agora.year, agora.month)[1]

    cb = CFG['carga_basal']
    basal_h = energia.basal_kwh_hora(cb['geladeira_kwh_mes'], cb['outros_w'], dias_mes)
    basal_kwh = basal_h * energia.horas_decorridas_mes(agora)

    kwh_aparelhos = sum(k for _, k in dados)
    kwh_total = kwh_aparelhos + basal_kwh
    custo_total = energia.custo(kwh_total, TARIFA)

    linhas = ["🧾 *Fatura parcial do mês*", ""]
    for nome, kwh in dados:
        linhas.append(f"{rotulo(nome)}: {kwh:.2f} kWh · R$ {energia.custo(kwh, TARIFA):.2f}")
    linhas.append(f"🧊 Carga basal: {basal_kwh:.2f} kWh · R$ {energia.custo(basal_kwh, TARIFA):.2f}")
    linhas.append("")
    linhas.append(f"Subtotal: {kwh_total:.2f} kWh · *R$ {custo_total:.2f}*")

    proj_total = energia.projecao_mes(kwh_total, agora)
    linhas.append(f"📈 Projeção do mês: {proj_total:.1f} kWh · *R$ {energia.custo(proj_total, TARIFA):.2f}*")

    # comparação só do que ela controla (aparelhos), basal é ~constante
    if kwh_anterior > 0:
        proj_aparelhos = energia.projecao_mes(kwh_aparelhos, agora)
        var = (proj_aparelhos - kwh_anterior) / kwh_anterior * 100
        seta = "🔺" if var > 0 else "🔻"
        linhas.append(f"{seta} {abs(var):.0f}% vs mês anterior ({kwh_anterior:.1f} kWh em aparelhos)")

    linhas.append("")
    linhas.append(f"_Tarifa aplicada: R$ {TARIFA:.2f}/kWh_")
    bot.reply_to(m, "\n".join(linhas), parse_mode="Markdown")


# --- GRÁFICO ---
@bot.message_handler(commands=['grafico'])
def grafico(m):
    uid = m.from_user.id
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""SELECT aparelho_nome, SUM(consumo_kwh_estimado)
                   FROM historico_uso
                   WHERE user_id = ? AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
                   GROUP BY aparelho_nome ORDER BY 2 DESC""", (uid,))
    dados = cur.fetchall()
    conn.close()

    if not dados:
        bot.reply_to(m, "Sem registros este mês pra plotar. 🍃")
        return

    nomes = [APARELHOS.get(n, {}).get('apelido', n) for n, _ in dados]
    valores = [k for _, k in dados]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(nomes, valores, color="#F0A028")
    ax.set_ylabel('kWh')
    ax.set_title('Consumo por aparelho — mês atual')
    for i, v in enumerate(valores):
        ax.text(i, v, f"{v:.1f}", ha='center', va='bottom')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=110)
    buf.seek(0)
    plt.close(fig)
    bot.send_photo(m.chat.id, buf)


# --- VIGIA (thread paralela que cobra o que ficou esquecido) ---
def checar_esquecidos():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT user_id, aparelho_nome, timestamp_inicio, ja_alertado FROM sessoes_ativas")
    sessoes = cur.fetchall()
    agora = datetime.now(timezone.utc).replace(tzinfo=None)

    for uid, nome, ts, alertado in sessoes:
        if alertado:
            continue
        limite = APARELHOS.get(nome, {}).get('limite_alerta_min')
        if not limite:
            continue
        inicio = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        min_ligado = (agora - inicio).total_seconds() / 60
        if min_ligado >= limite:
            bot.send_message(uid, f"⚠️ {rotulo(nome)} está ligado há {min_ligado:.0f} min. "
                                  f"Esqueceu de desligar? Use 🔴 Desligar Algo pra fechar.")
            cur.execute("UPDATE sessoes_ativas SET ja_alertado = 1 WHERE user_id = ? AND aparelho_nome = ?",
                        (uid, nome))

    conn.commit()
    conn.close()


def vigia():
    while True:
        time.sleep(60)
        try:
            checar_esquecidos()
        except Exception as e:
            print(f"[vigia] erro: {e}")


if __name__ == "__main__":
    threading.Thread(target=vigia, daemon=True).start()
    print("Vigia ativa. Entrando no modo de espera (polling)...")
    bot.polling()
