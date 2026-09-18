name: Monitorización Celador SCS

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"

jobs:
  run-bot-celador:
    runs-on: ubuntu-latest
    steps:
    - name: Descargar código del repositorio
      uses: actions/checkout@v4

    - name: Configurar entorno de Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Instalar dependencias necesarias
      run: |
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

    - name: Ejecutar el script web Celador
      env:
        TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
        TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID_CELADOR }}
      run: python tiempo_real_celador.py

    - name: Guardar estado para la siguiente ejecución
      run: |
        git config --local user.email "github-actions[bot]@users.noreply.github.com"
        git config --local user.name "github-actions[bot]"
        git add estado_celador_*.txt || true
        git commit -m "🔄 Actualizar estados Celador [Skip CI]" || true
        git push || true
