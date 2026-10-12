@echo off
title LedgerIQ - Statutory Statement Compiler
echo ========================================================
echo Starting LedgerIQ Statutory Statement Compiler...
echo ========================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
streamlit run src\fyp_module3\app.py
pause

