import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=20, banner_timeout=20, auth_timeout=20,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})

cmds = [
    # download cloudflared
    "curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared && cloudflared --version",
    # start quick tunnel (no account needed, gives public URL)
    "pkill -f 'cloudflared tunnel' 2>/dev/null; nohup cloudflared tunnel --url http://127.0.0.1:8900 > /tmp/cloudflared.log 2>&1 &",
    # wait for URL to appear in log
    "sleep 8 && grep -o 'https://[a-z0-9-]*\\.trycloudflare\\.com' /tmp/cloudflared.log | head -1",
]
for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print("$", cmd[:70])
    if out:
        print(" ", out[:200])
    if err and "warning" not in err.lower():
        print("  ERR:", err[:150])
ssh.close()