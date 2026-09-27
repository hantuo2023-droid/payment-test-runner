"""Deterministic local test site. Synthetic cards, no payments or external calls."""
import html
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()
STYLE = '<style>body{font:16px system-ui;background:#f3f5f8;color:#182431;max-width:650px;margin:70px auto}main{background:white;border:1px solid #ddd;padding:36px;border-radius:18px}label{display:block;margin:18px 0}input{display:block;padding:12px;border:1px solid #ccd5df;border-radius:6px;width:90%}button{padding:12px 24px;background:#186752;color:white;border:0;border-radius:6px;cursor:pointer}small{color:#637386}h1{margin-top:0}</style>'

@app.get('/health')
def health():
    return {'ok':True}

@app.get('/login', response_class=HTMLResponse)
def login():
    return STYLE+'''<main><small>LOCAL SANDBOX · SYNTHETIC DATA ONLY</small><h1>Log In</h1><form id="login"><label>Email<input name="email" type="email" required></label><label>Password<input name="password" type="password" required></label><button>Log In</button></form><p role="alert"></p></main><script>document.querySelector('form').onsubmit=async e=>{e.preventDefault();let f=new FormData(e.target);let r=await fetch('/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(f))});let d=await r.json();if(!r.ok){document.querySelector('[role=alert]').textContent='BAD_CREDENTIALS';return}document.querySelector('main').innerHTML='<h1>Signing in…</h1>';setTimeout(()=>location.href='/settings/payments',d.delay)}</script>'''

@app.post('/auth')
async def auth(request: Request):
    data = await request.json()
    if data.get('password') != 'sandbox-pass':
        return JSONResponse({'error':'BAD_CREDENTIALS'},status_code=401)
    response = JSONResponse({'delay':1500 if data.get('email','').startswith('delay') else 100})
    response.set_cookie('sandbox_session','synthetic-user',httponly=True,samesite='strict')
    return response

@app.get('/settings/payments', response_class=HTMLResponse)
def payments(request: Request):
    if request.cookies.get('sandbox_session') != 'synthetic-user':
        return STYLE+'''<main><h1>Loading…</h1></main><script>setTimeout(()=>location.href='/login?next=/settings/payments',700)</script>'''
    return STYLE+'''<main><small>LOCAL SANDBOX · NO REAL PAYMENTS</small><h1>Payment methods</h1><p>Manage synthetic payment fixtures in this controlled environment.</p><button id="add">Add card</button><section id="form" hidden><h2>Save a payment card</h2><form><label>Card number<input name="card_number" autocomplete="off" required></label><label>Expiry month<input name="month" required></label><label>Expiry year<input name="year" required></label><label>CVC<input name="cvc" type="password" required></label><button type="submit">Submit</button></form></section><h2 id="result" role="status"></h2></main><script>document.querySelector('#add').onclick=()=>document.querySelector('#form').hidden=false;document.querySelector('form').onsubmit=async e=>{e.preventDefault();let f=Object.fromEntries(new FormData(e.target));document.querySelector('#result').textContent='Processing…';let r=await fetch('/bind',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(f)});let d=await r.json();if(d.result==='TIMEOUT')return;e.target.reset();setTimeout(()=>{let el=document.querySelector('#result');el.dataset.result=d.result;el.textContent=d.result},300)}</script>'''

@app.post('/bind')
async def bind(request: Request):
    if request.cookies.get('sandbox_session') != 'synthetic-user':
        return JSONResponse({'error':'unauthorized'},status_code=401)
    data = await request.json()
    fixtures = {'4242424242424242':'BOUND','4000000000000002':'DECLINED','4000000000003220':'3DS_REQUIRED','4000000000000069':'INVALID_DATA','4000000000009995':'TIMEOUT'}
    result = fixtures.get(data.get('card_number'),'INVALID_DATA')
    if not all(data.get(k) for k in ('month','year','cvc')):
        result = 'INVALID_DATA'
    return {'result':result}
