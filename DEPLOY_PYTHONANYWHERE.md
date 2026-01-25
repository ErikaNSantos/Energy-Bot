# 🚀 Guia de Deploy: Energy-Bot no PythonAnywhere

Siga estes passos para deixar seu bot online 24h por dia:

### 1. Preparação no PythonAnywhere
1. Crie sua conta gratuita em [pythonanywhere.com](https://www.pythonanywhere.com/).
2. No painel principal, clique em **"Consoles"** e abra um console **"Bash"**.

### 2. Clonar e Instalar
No console Bash, digite os seguintes comandos:
```bash
# Clone o seu repositório
git clone https://github.com/ErikaNSantos/Energy-Bot.git
cd Energy-Bot

# Crie um ambiente virtual para organizar as bibliotecas
python3 -m venv venv
source venv/bin/activate

# Instale as bibliotecas necessárias
pip install pyTelegramBotAPI python-dotenv
```

### 3. Configurar o Token
Ainda no console, crie o arquivo com seu token do Telegram:
```bash
echo "TELEGRAM_TOKEN=seu_token_aqui" > .env
```
*(Substitua `seu_token_aqui` pelo token que você recebeu do @BotFather)*.

### 4. Rodar o Bot
Para testar, basta rodar:
```bash
python interface/telegram_bot.py
```

### 💡 Dicas Importantes para o Plano Gratuito:
*   **Renovação Diária:** No plano gratuito, o PythonAnywhere exige que você clique em um botão **"Extend expiry"** no painel de controle uma vez a cada 24h para manter o console ativo.
*   **Persistência:** Se o console fechar, o bot para. Para evitar isso, você pode configurar uma **"Scheduled Task"** no painel deles para rodar o script todos os dias, ou simplesmente manter a aba do console aberta.
*   **Whitelisting:** O PythonAnywhere gratuito permite conexões externas apenas para sites na "whitelist" deles. O Telegram (`api.telegram.org`) **está na lista**, então seu bot vai funcionar perfeitamente!
