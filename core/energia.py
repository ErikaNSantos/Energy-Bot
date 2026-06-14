# Cálculos de energia. Funções puras: recebem números, devolvem números.
# Sem dependência de banco ou Telegram, pra reaproveitar em qualquer interface.

import calendar
from datetime import datetime, timezone


def consumo_kwh(potencia_w, duracao_min):
    return (potencia_w * (duracao_min / 60)) / 1000


def custo(kwh, tarifa):
    return kwh * tarifa


def basal_kwh_hora(geladeira_kwh_mes, outros_w, dias_mes):
    # geladeira vem da etiqueta INMETRO em kWh/mês; converte pra kWh/hora médio
    geladeira_h = geladeira_kwh_mes / (dias_mes * 24)
    outros_h = outros_w / 1000
    return geladeira_h + outros_h


def horas_decorridas_mes(agora=None):
    agora = agora or datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (agora - inicio_mes).total_seconds() / 3600


def projecao_mes(kwh_parcial, agora=None):
    # extrapola o consumo parcial pro mês cheio, na mesma proporção
    agora = agora or datetime.now(timezone.utc)
    dias_mes = calendar.monthrange(agora.year, agora.month)[1]
    horas_passadas = horas_decorridas_mes(agora)
    if horas_passadas == 0:
        return kwh_parcial
    return kwh_parcial / horas_passadas * (dias_mes * 24)
