@echo off
:: Se placer dans le dossier du script
cd /d "%~dp0"

:: Lancer l'application Streamlit
echo Lancement de l'Assistant Comptabilité IA...
streamlit run app.py

:: Pause en cas d'erreur pour voir le message
if %errorlevel% neq 0 pause
