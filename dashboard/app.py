import streamlit as st
import pandas as pd
import sqlite3
import json
import os
import sys

import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from core import relatorio

# --- caminhos e config ---
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DB = os.path.join(RAIZ, 'data', 'logs.db')
CONFIG = os.path.join(RAIZ, 'data', 'config.json')

with open(CONFIG, encoding='utf-8') as f:
    CFG = json.load(f)

APARELHOS = CFG['aparelhos']
TARIFA = CFG['tarifa_base'] + CFG['adicional_bandeira']
USER_ID = 2101460041

AMBAR = "#F0A028"
GRAFITE = "#1a1d23"
# tons para diferenciar aparelhos, todos na família quente/neutra da paleta
CORES = ["#F0A028", "#E36414", "#8FB8DE", "#5C7A99", "#C9A227"]

DOW = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']


def rotulo(nome):
    a = APARELHOS.get(nome, {})
    return f"{a.get('emoji', '')} {a.get('apelido', nome)}".strip()


@st.cache_data
def carregar():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM historico_uso WHERE user_id = ?", conn,
                     params=(USER_ID,), parse_dates=['timestamp'])
    conn.close()
    if df.empty:
        return df
    df['apelido'] = df['aparelho_nome'].map(lambda n: APARELHOS.get(n, {}).get('apelido', n))
    df['mes'] = df['timestamp'].dt.strftime('%Y-%m')
    df['dia'] = df['timestamp'].dt.date
    df['hora'] = df['timestamp'].dt.hour
    df['dow'] = df['timestamp'].dt.dayofweek
    df['custo'] = df['consumo_kwh_estimado'] * TARIFA
    return df


def aplicar_tema(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#e8e8e8',
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(gridcolor='#2a2f38', zeroline=False)
    fig.update_yaxes(gridcolor='#2a2f38', zeroline=False)
    return fig


# ============ PÁGINA ============
st.set_page_config(page_title="Energy Bot", layout="wide", page_icon="⚡")
st.title("⚡ Energy Bot — Consumo de energia")

df = carregar()
if df.empty:
    st.warning("Sem dados no banco ainda.")
    st.stop()

meses = sorted(df['mes'].unique())
sel = st.sidebar.selectbox("Período", ["Todos os meses"] + meses, index=len(meses))
st.sidebar.caption(f"Tarifa: R$ {TARIFA:.2f}/kWh")

dff = df if sel == "Todos os meses" else df[df['mes'] == sel]

# --- KPIs ---
kwh_total = dff['consumo_kwh_estimado'].sum()
custo_total = kwh_total * TARIFA
por_ap = dff.groupby('apelido')['consumo_kwh_estimado'].sum().sort_values(ascending=False)
campeao = por_ap.index[0] if not por_ap.empty else "—"

# variação vs mês anterior (só quando um mês está selecionado)
delta_txt = None
if sel != "Todos os meses":
    idx = meses.index(sel)
    if idx > 0:
        ant = meses[idx - 1]
        kwh_ant = df[df['mes'] == ant]['consumo_kwh_estimado'].sum()
        if kwh_ant > 0:
            var = (kwh_total - kwh_ant) / kwh_ant * 100
            delta_txt = f"{var:+.0f}% vs {ant}"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Consumo", f"{kwh_total:.1f} kWh", delta_txt)
c2.metric("Custo estimado", f"R$ {custo_total:.2f}")
c3.metric("Maior consumidor", campeao)
c4.metric("Registros", f"{len(dff)}")

st.divider()

# --- linha 1: série temporal + breakdown ---
col_a, col_b = st.columns([2, 1])

with col_a:
    st.subheader("Consumo diário")
    serie = dff.groupby('dia')['consumo_kwh_estimado'].sum().reset_index()
    fig = px.area(serie, x='dia', y='consumo_kwh_estimado')
    fig.update_traces(line_color=AMBAR, fillcolor='rgba(240,160,40,0.15)')
    fig.update_layout(yaxis_title='kWh/dia', xaxis_title=None)
    st.plotly_chart(aplicar_tema(fig), use_container_width=True)

with col_b:
    st.subheader("Por aparelho")
    pa = por_ap.sort_values().reset_index()
    pa.columns = ['apelido', 'kwh']
    fig = px.bar(pa, x='kwh', y='apelido', orientation='h',
                 color='apelido', color_discrete_sequence=CORES)
    fig.update_layout(showlegend=False, xaxis_title='kWh', yaxis_title=None)
    st.plotly_chart(aplicar_tema(fig), use_container_width=True)

# --- linha 2: heatmap hora x dia da semana ---
st.subheader("Quando a energia é usada (hora × dia da semana)")
heat = dff.groupby(['dow', 'hora'])['consumo_kwh_estimado'].sum().reset_index()
pivot = heat.pivot(index='dow', columns='hora', values='consumo_kwh_estimado').fillna(0)
pivot = pivot.reindex(range(7))
pivot.index = DOW
fig = px.imshow(pivot, aspect='auto', color_continuous_scale='Oranges',
                labels=dict(x='Hora', y='', color='kWh'))
st.plotly_chart(aplicar_tema(fig), use_container_width=True)

# --- linha 3: comparação mensal (sempre todos os meses) ---
st.subheader("Comparação mês a mês")
mensal = df.groupby(['mes', 'apelido'])['consumo_kwh_estimado'].sum().reset_index()
fig = px.bar(mensal, x='mes', y='consumo_kwh_estimado', color='apelido',
             color_discrete_sequence=CORES)
fig.update_layout(yaxis_title='kWh', xaxis_title=None, barmode='stack')
st.plotly_chart(aplicar_tema(fig), use_container_width=True)

# --- fatura detalhada (só com mês selecionado) ---
if sel != "Todos os meses":
    st.divider()
    st.subheader(f"Fatura de {sel}")
    r = relatorio.resumo_mensal(DB, USER_ID, sel, CFG)
    f1, f2, f3 = st.columns(3)
    f1.metric("Aparelhos", f"{r['kwh_aparelhos']:.1f} kWh",
              f"R$ {r['kwh_aparelhos'] * r['tarifa']:.2f}")
    f2.metric("Carga basal", f"{r['basal_kwh']:.1f} kWh",
              f"R$ {r['basal_kwh'] * r['tarifa']:.2f}")
    f3.metric("Total da fatura", f"R$ {r['custo_total']:.2f}",
              f"inclui R$ {r['cip']:.2f} de iluminação pública", delta_color="off")
