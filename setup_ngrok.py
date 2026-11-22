import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=20, banner_timeout=20, auth_timeout=20,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})

cmds = [
    # install ngrok
    "curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc -o /etc/apt/trusted.gpg.d/ngrok.asc 2>/dev/null; echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' > /etc/apt/sources.list.d/ngrok.list; apt-get update -qq 2>/dev/null; apt-get install -y -qq ngrok 2>&1 | tail -2; which ngrok || (curl -sL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar xz -C /usr/local/bin && which ngrok)",
    # configure authtoken
    "ngrok config add-authtoken 3MSd088cRMbN6FxPf2F35MB8JMD_7xiHogzGeRxMxwnxYJFn8 2>&1",
    # kill old ngrok, start tunnel to 8900
    "pkill ngrok 2>/dev/null; sleep 1; cd /tmp && setsid ngrok http 8900 --log=stdout </dev/null >/tmp/ngrok.log 2>&1 &",
    # wait and get URL
    "sleep 8 && curl -s http://127.0.0.1:4040/api/tunnels | python3 -c 'import sys,json;d=json.load(sys.stdin);[print(t[\"public_url\"]) for t in d.get(\"tunnels\",[])]' 2>/dev/null || grep -o 'https://[a-z0-9-]*\\.ngrok[a-z-]*\\.app' /tmp/ngrok.log | head -1 || tail -5 /tmp/ngrok.log",
]
for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print("$", cmd[:60])
    if out:
        print(" ", out[:300])
    if err and "warning" not in err.lower() and "WARNING" not in err:
        print("  ERR:", err[:150])
ssh.close()