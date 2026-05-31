"""Startup test — launches bot.py, captures output, terminates."""
import subprocess, sys, os, time, json

os.chdir(r'c:\Users\MC\Downloads\5simTelegramBot-main\5simTelegramBot-main')
RESULT = {}

def test_bot(target, name):
    p = subprocess.Popen([sys.executable, target], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(8)
    p.terminate()
    out = p.stdout.read() if p.stdout else ''
    ok = 'INFO' in out and 'ERROR' not in out
    RESULT[name] = {'ok': ok, 'output_lines': len(out.splitlines())}
    print(f"{'✅ PASS' if ok else '❌ FAIL'}: {name} ({RESULT[name]['output_lines']} log lines)")

test_bot('bot.py', 'Customer Bot')
test_bot('admin_bot.py', 'Admin Bot')

with open('startup_result.json', 'w') as f:
    json.dump(RESULT, f, indent=2)

print(f"Results saved: {RESULT}")