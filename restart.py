import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=20, banner_timeout=20, auth_timeout=20,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})
stdin, stdout, stderr = ssh.exec_command("pkill -f uvicorn; sleep 1; cd /opt/v0app2api && nohup python3 -m uvicorn api.app:app --host 0.0.0.0 --port 8900 >/tmp/v0app2api.log 2>&1 & sleep 5; curl -s http://127.0.0.1:8900/health")
print(stdout.read().decode())
stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8900/ | head -3")
print(stdout.read().decode()[:200])
ssh.close()