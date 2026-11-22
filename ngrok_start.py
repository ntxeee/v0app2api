import paramiko, sys, io, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("fi-hel03.altare.global", port=25194, username="root", password="Mlkjzasd10",
            timeout=20, banner_timeout=20, auth_timeout=20,
            look_for_keys=False, allow_agent=False,
            disabled_algorithms={"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]})
ssh.exec_command("ngrok config add-authtoken 3MSZNWCBWddOhWbbeSEfXhnVIWd_3AYHA82NVUHrUMmKmVck5")[1].read()
ssh.exec_command("pkill ngrok")[1].read()
time.sleep(2)
ssh.exec_command("cd /tmp && setsid ngrok http 8900 --log=stdout </dev/null >/tmp/ngrok.log 2>&1 &")[1].channel.recv_exit_status()
time.sleep(10)
stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:4040/api/tunnels")
raw = stdout.read().decode()
try:
    d = json.loads(raw)
    for t in d.get("tunnels", []):
        print("PUBLIC URL:", t.get("public_url"))
    if not d.get("tunnels"):
        print("no tunnels, log:")
        stdin, stdout, stderr = ssh.exec_command("tail -8 /tmp/ngrok.log")
        print(stdout.read().decode()[:400])
except Exception:
    print("raw:", raw[:200])
    stdin, stdout, stderr = ssh.exec_command("tail -8 /tmp/ngrok.log")
    print(stdout.read().decode()[:400])
ssh.close()