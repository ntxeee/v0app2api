import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=20, banner_timeout=20, auth_timeout=20,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})

# start cloudflared in background with explicit log path
stdin, stdout, stderr = ssh.exec_command(
    "cd /tmp && cloudflared tunnel --url http://127.0.0.1:8900 > /tmp/cf.log 2>&1 & echo $!",
    timeout=10)
pid = stdout.read().decode().strip()
print("cloudflared pid:", pid)

# wait and read log
time.sleep(10)
stdin, stdout, stderr = ssh.exec_command("cat /tmp/cf.log | grep -i 'trycloudflare\\|error\\|ERR' | head -5")
out = stdout.read().decode().strip()
print(out if out else "no URL yet, waiting more...")

if not out or "trycloudflare" not in out:
    time.sleep(10)
    stdin, stdout, stderr = ssh.exec_command("cat /tmp/cf.log | tail -10")
    print(stdout.read().decode()[:500])

ssh.close()