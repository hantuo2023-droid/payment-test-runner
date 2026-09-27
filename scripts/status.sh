#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
require_docker
dc ps
dc exec -T backend python -c "import urllib.request,json; d=json.load(urllib.request.urlopen('http://localhost:8000/api/health')); [print(k.title().ljust(15), 'Healthy' if d[k] else 'FAILED') for k in ('backend','database','worker','disk')]; assert all(d[k] for k in ('backend','database','worker','disk'))"
dc exec -T frontend node -e "fetch('http://localhost:3000/').then(r=>{if(!r.ok)process.exit(1);console.log('Frontend        Healthy')}).catch(()=>process.exit(1))"
dc exec -T backend python -c "import asyncio; from backend.runs import probe_browser; r=asyncio.run(probe_browser({'target_url':'http://sandbox:8080/settings/payments'},{'protocol':'Direct'})); assert r['connected'],r; print('Chromium        Healthy'); print('Network         Healthy'); print('Mode            LIVE')"
