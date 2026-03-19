name: 🤖 Bot Noticias Virales - 60min Scheduler

on:
  schedule:
    # Ejecutar cada 60 minutos exactos
    - cron: '0 * * * *'
    # Alternativa: cada 60 minutos desde el inicio del run
    # - cron: '*/60 * * * *'
  
  # Ejecución manual
  workflow_dispatch:
    inputs:
      force_publish:
        description: 'Forzar publicación ignorando tiempo'
        required: false
        default: 'false'
        type: choice
        options:
          - 'false'
          - 'true'

env:
  PYTHON_VERSION: '3.11'
  # Credenciales desde secrets
  FB_PAGE_ID: ${{ secrets.FB_PAGE_ID }}
  FB_ACCESS_TOKEN: ${{ secrets.FB_ACCESS_TOKEN }}
  NEWS_API_KEY: ${{ secrets.NEWS_API_KEY }}
  NEWSDATA_API_KEY: ${{ secrets.NEWSDATA_API_KEY }}
  GNEWS_API_KEY: ${{ secrets.GNEWS_API_KEY }}
  # Rutas
  HISTORIAL_PATH: data/historial_viral.json
  ESTADO_PATH: data/estado_bot_viral.json
  # GitHub context
  GITHUB_RUN_ID: ${{ github.run_id }}
  GITHUB_RUN_NUMBER: ${{ github.run_number }}

jobs:
  bot-viral:
    runs-on: ubuntu-latest
    timeout-minutes: 8  # Límite de tiempo para evitar consumo excesivo
    
    steps:
      - name: 📥 Checkout código
        uses: actions/checkout@v4
      
      - name: 🐍 Setup Python ${{ env.PYTHON_VERSION }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      
      - name: 📦 Instalar dependencias
        run: |
          pip install --upgrade pip
          pip install requests feedparser beautifulsoup4 Pillow
      
      - name: 📂 Preparar directorios
        run: |
          mkdir -p data logs
          ls -la data/ || echo "Directorio data vacío"
      
      - name: 💾 Restaurar historial (cache)
        uses: actions/cache/restore@v4
        with:
          path: data/
          key: bot-historial-${{ github.run_id }}
          restore-keys: |
            bot-historial-
      
      - name: 🚀 Ejecutar Bot Noticias Virales
        id: bot-run
        run: |
          echo "::group::Ejecución del Bot"
          python bot_noticias_virales.py
          EXIT_CODE=$?
          echo "exit_code=$EXIT_CODE" >> $GITHUB_OUTPUT
          echo "::endgroup::"
          exit $EXIT_CODE
      
      - name: 💾 Guardar historial (cache)
        if: always()
        uses: actions/cache/save@v4
        with:
          path: data/
          key: bot-historial-${{ github.run_id }}-${{ github.run_attempt }}
      
      - name: 📤 Backup de datos (artifact)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: bot-data-run-${{ github.run_number }}
          path: |
            data/
            logs/
          retention-days: 5
          if-no-files-found: warn
      
      - name: 📊 Resumen de ejecución
        if: always()
        run: |
          echo "### 🤖 Resultado del Bot" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          if [ "${{ steps.bot-run.outputs.exit_code }}" == "0" ]; then
            echo "✅ **Bot ejecutado exitosamente**" >> $GITHUB_STEP_SUMMARY
          else
            echo "❌ **Bot falló con código ${{ steps.bot-run.outputs.exit_code }}**" >> $GITHUB_STEP_SUMMARY
          fi
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Run ID:** ${{ github.run_id }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Run Number:** ${{ github.run_number }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Hora:** $(date)" >> $GITHUB_STEP_SUMMARY

  # Job opcional: Notificación de fallos
  notify-failure:
    needs: bot-viral
    runs-on: ubuntu-latest
    if: failure()
    
    steps:
      - name: 🚨 Notificar fallo
        run: |
          echo "::error::El bot falló en la ejecución ${{ github.run_number }}"
          # Aquí puedes agregar webhook a Discord, Slack, Telegram, etc.
          # curl -X POST ${{ secrets.DISCORD_WEBHOOK }} -d '{"content":"Bot falló"}'
