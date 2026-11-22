import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=20, banner_timeout=20, auth_timeout=20,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})

# kill old
ssh.exec_command("pkill -f uvicorn")[1].read()
time.sleep(2)

# start with setsid to fully detach
stdin, stdout, stderr = ssh.exec_command("cd /opt/v0app2api && setsid python3 -m uvicorn api.app:app --host 0.0.0.0 --port 8900 </dev/null >/tmp/v0app2api.log 2>&1 &")
stdout.channel.recv_exit_status()
time.sleep(5)

# check
stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8900/health")
health = stdout.read().decode().strip()
print("health:", health)

stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8900/ | wc -c")
size = stdout.read().decode().strip()
print("gallery page bytes:", size)

if not health:
    stdin, stdout, stderr = ssh.exec_command("cat /tmp/v0app2api.log | tail -5")
    print("LOG:", stdout.read().decode()[:300])

ssh.close()