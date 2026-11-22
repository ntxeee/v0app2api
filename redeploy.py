import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=20, banner_timeout=20, auth_timeout=20,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})

cmds = [
    "cd /opt/v0app2api && git pull 2>&1 | tail -3",
    "pkill -f 'uvicorn api.app' 2>/dev/null; sleep 1; cd /opt/v0app2api && python3 -m uvicorn api.app:app --host 0.0.0.0 --port 8900 &",
    "sleep 4 && curl -s http://127.0.0.1:8900/health",
    "curl -s http://127.0.0.1:8900/ | head -5",
]
for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    if out:
        print(out[:200])
ssh.close()
print("DONE")