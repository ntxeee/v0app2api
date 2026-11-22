#!/bin/bash
# 部署到 FI 服务器: ssh root@fi-hel03.altare.global -p 25194
set -e
apt-get update -qq && apt-get install -y -qq python3 python3-pip git > /dev/null 2>&1
cd /opt
if [ -d v0app2api ]; then cd v0app2api && git pull; else git clone https://github.com/ntxeee/v0app2api.git && cd v0app2api; fi
pip3 install -q fastapi uvicorn pydantic
mkdir -p data
# 启动 (端口 8900)
pkill -f "uvicorn api.app" 2>/dev/null || true
nohup python3 -m uvicorn api.app:app --host 0.0.0.0 --port 8900 > /tmp/v0app2api.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:8900/health
echo ""
echo "DEPLOYED: http://$(hostname -I | awk '{print $1}'):8900"
echo "API docs: http://$(hostname -I | awk '{print $1}'):8900/docs"