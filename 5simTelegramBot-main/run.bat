@echo off
cd /d "%~dp0"
set PY="C:\Users\MC\AppData\Local\Programs\Python\Python311\python.exe"

echo === سحب آخر التحديثات ===
git pull origin main

echo === تثبيت الحزم ===
%PY% -m pip install -r requirements.txt --quiet

echo === إعداد قاعدة البيانات ===
%PY% scripts/setup_pg.py

echo === تشغيل الاختبارات ===
%PY% -m pytest tests/ -v

echo === بدء تشغيل البوتات ===
start "Customer Bot" %PY% bot.py
start "Admin Bot" %PY% admin_bot.py

echo.
echo ============================================
echo تم التشغيل بنجاح
echo Customer Bot: http://localhost:5001
echo Admin Bot:    http://localhost:5002
echo.
echo لسحب التحديثات مستقبال:
echo   git pull origin main
echo ============================================
pause