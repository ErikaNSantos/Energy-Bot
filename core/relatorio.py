# Cálculo do resumo mensal. Sem dependência de Telegram: recebe caminho do
# banco e período, devolve um dict com os números. Testável e reaproveitável.

import sqlite3
import calendar
from datetime import datetime, timezone

from core import energia


def mes_anterior(ano_mes):
    ano, mes = map(int, ano_mes.split('-'))
    if mes == 1:
        return f"{ano - 1}-12"
    return f"{ano}-{mes - 1:02d}"


def resumo_mensal(db_path, user_id, ano_mes, cfg):
    tarifa = cfg['tarifa_base'] + cfg['adicional_bandeira']

    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("""SELECT aparelho_nome, SUM(consumo_kwh_estimado)
                   FROM historico_uso
                   WHERE user_id = ? AND strftime('%Y-%m', timestamp) = ?
                   GROUP BY aparelho_nome ORDER BY 2 DESC""", (user_id, ano_mes))
    aparelhos = cur.fetchall()

    ant = mes_anterior(ano_mes)
    cur.execute("""SELECT SUM(consumo_kwh_estimado) FROM historico_uso
                   WHERE user_id = ? AND strftime('%Y-%m', timestamp) = ?""", (user_id, ant))
    kwh_anterior = cur.fetchone()[0] or 0
    conn.close()

    ano, mes = map(int, ano_mes.split('-'))
    dias_mes = calendar.monthrange(ano, mes)[1]
    agora = datetime.now(timezone.utc)
    eh_corrente = (ano_mes == agora.strftime('%Y-%m'))

    cb = cfg['carga_basal']
    basal_h = energia.basal_kwh_hora(cb['geladeira_kwh_mes'], cb['outros_w'], dias_mes)
    # mês em curso: basal proporcional aos dias já decorridos.
    # mês fechado: basal do mês inteiro.
    horas = energia.horas_decorridas_mes(agora) if eh_corrente else dias_mes * 24
    basal_kwh = basal_h * horas

    kwh_aparelhos = sum(k for _, k in aparelhos)
    kwh_total = kwh_aparelhos + basal_kwh
    cip = cfg.get('iluminacao_publica', 0.0)

    r = {
        'periodo': ano_mes,
        'eh_corrente': eh_corrente,
        'tarifa': tarifa,
        'aparelhos': aparelhos,
        'kwh_aparelhos': kwh_aparelhos,
        'basal_kwh': basal_kwh,
        'kwh_total': kwh_total,
        'cip': cip,
        'custo_energia': kwh_total * tarifa,
        'custo_total': kwh_total * tarifa + cip,
        'kwh_anterior': kwh_anterior,
        'mes_anterior': ant,
    }

    if eh_corrente:
        proj_kwh = energia.projecao_mes(kwh_total, agora)
        r['proj_kwh'] = proj_kwh
        r['proj_custo'] = proj_kwh * tarifa + cip
        r['proj_aparelhos'] = energia.projecao_mes(kwh_aparelhos, agora)

    return r
