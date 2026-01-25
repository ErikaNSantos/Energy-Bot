import sqlite3
import os

def criar_banco_dados():
    # Define o caminho AUTOMATICAMENTE: Pasta do projeto / data / logs.db
    caminho_pasta = os.path.join(os.getcwd(), 'data')
    caminho_banco = os.path.join(caminho_pasta, 'logs.db')

    if not os.path.exists(caminho_pasta):
        os.makedirs(caminho_pasta)

    print(f"Conectando ao banco em: {caminho_banco}")

    conexao = sqlite3.connect(caminho_banco)
    cursor = conexao.cursor()

    #Guarda quem ligou, o que ligou e quando, além de garantir que a tabela existe e que não há duplicatas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessoes_ativas (
        user_id INTEGER,
        aparelho_nome TEXT,
        detalhe TEXT, -- Aqui guardamos a potência (Ex: "Frio|750")
        timestamp_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, aparelho_nome)
                   )
    ''')

    #Agora cria a tabela que guarda quem desligou o que e quando
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_uso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        aparelho_nome TEXT,
        detalhe TEXT,  -- Ex: "Gear 3|50" ou "Pesado"
        consumo_kwh_estimado REAL,
        duracao_minutos REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conexao.commit()
    conexao.close()
    print(f"Banco de dados 'logs.db' criado com sucesso em: {os.path.join(os.path.expanduser('~'), 'Documentos', 'Projetos_Python', 'projeto_energia', 'data')}")

if __name__ == "__main__":
    criar_banco_dados()        