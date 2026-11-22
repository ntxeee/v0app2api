import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})
# check what's wrong
stdin, stdout, stderr = ssh.exec_command("cat /tmp/v0app2api.log | tail -5; echo '---'; ps aux | grep uvicorn | grep -v grep", timeout=10)
print(stdout.read().decode().strip())
# start fresh
stdin, stdout, stderr = ssh.exec_command("cd /opt/v0app2api && python3 -m uvicorn api.app:app --host 0.0.0.0 --port 8900 &", timeout=5)
stdout.channel.recv_exit_status()
time.sleep(5)
stdin, stdout, stderr = ssh.exec_command("curl -s --max-time 5 http://127.0.0.1:8900/health", timeout=10)
print("health:", stdout.read().decode().strip())
ssh.close()