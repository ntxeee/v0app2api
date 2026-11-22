import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=30, banner_timeout=30, auth_timeout=30,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})
print("SSH OK")

cmds = [
    "which python3 && python3 --version",
    "pip3 install -q fastapi uvicorn pydantic 2>&1 | tail -3",
    "cd /opt && rm -rf v0app2api && git clone https://github.com/ntxeee/v0app2api.git 2>&1 | tail -3",
    "cd /opt/v0app2api && pkill -f 'uvicorn api.app' 2>/dev/null; nohup python3 -m uvicorn api.app:app --host 0.0.0.0 --port 8900 > /tmp/v0app2api.log 2>&1 & sleep 3 && curl -s http://127.0.0.1:8900/health",
]
for cmd in cmds:
    print("\n$ " + cmd[:80])
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip()[:300])
    if err.strip() and "warning" not in err.lower():
        print("ERR:", err.strip()[:200])

ssh.close()
print("\nDONE")