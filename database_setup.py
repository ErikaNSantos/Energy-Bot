import sqlite3
import os


def criar_banco_dados():
    caminho_pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    caminho_banco = os.path.join(caminho_pasta, 'logs.db')

    if not os.path.exists(caminho_pasta):
        os.makedirs(caminho_pasta)

    conexao = sqlite3.connect(caminho_banco)
    cursor = conexao.cursor()

    # WAL permite leitura concorrente com escrita: a thread de vigia e os
    # handlers do bot acessam o banco ao mesmo tempo sem travar um ao outro
    cursor.execute("PRAGMA journal_mode=WAL")

    # ja_alertado: marca se o aviso de "esqueceu de desligar" já foi enviado,
    # pra não repetir o alerta a cada ciclo da vigia
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessoes_ativas (
        user_id INTEGER,
        aparelho_nome TEXT,
        detalhe TEXT,
        timestamp_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
        ja_alertado INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, aparelho_nome)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_uso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        aparelho_nome TEXT,
        detalhe TEXT,
        consumo_kwh_estimado REAL,
        duracao_minutos REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conexao.commit()
    conexao.close()
    print(f"Banco criado em: {caminho_banco}")


if __name__ == "__main__":
    criar_banco_dados()
