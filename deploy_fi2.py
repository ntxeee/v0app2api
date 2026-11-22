import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=30, banner_timeout=30, auth_timeout=30,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})

cmds = [
    "apt-get install -y -qq git > /dev/null 2>&1; which git",
    "pip3 install --break-system-packages -q fastapi uvicorn pydantic 2>&1 | tail -2",
    "cd /opt && rm -rf v0app2api && git clone https://github.com/ntxeee/v0app2api.git 2>&1",
    "ls /opt/v0app2api/",
    "cd /opt/v0app2api && pkill -f 'uvicorn api.app' 2>/dev/null; nohup python3 -m uvicorn api.app:app --host 0.0.0.0 --port 8900 > /tmp/v0app2api.log 2>&1 & sleep 3 && curl -s http://127.0.0.1:8900/health",
]
for cmd in cmds:
    print("$ " + cmd[:70], flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print("  " + out[:300], flush=True)
    if err and "warning" not in err.lower() and "Cloning" not in err:
        print("  ERR: " + err[:200], flush=True)
ssh.close()
print("\nDONE")