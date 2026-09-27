import os
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from pydantic import BaseModel
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from backend.store import migrate, rows, DATA
from backend.auth import login, require_admin, TOKENS

@asynccontextmanager
async def lifespan(app):
    migrate()
    from backend.runner import start_worker, stop_worker
    start_worker()
    yield
    stop_worker()

app = FastAPI(title='Payment Test Runner', version='0.2.0', lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422,content={'detail':[{'field':'.'.join(str(x) for x in e['loc']),'reason':e['msg']} for e in exc.errors()]})
from backend.importer import router as import_router
app.include_router(import_router)
from backend.catalog import router as catalog_router
app.include_router(catalog_router)
from backend.runs import router as runs_router
app.include_router(runs_router)

class Login(BaseModel):
    password: str

@app.post('/api/auth/login')
def admin_login(body: Login, request: Request, response: Response):
    token = login(body.password, request.client.host)
    response.set_cookie('ptr_session', token, httponly=True, samesite='strict', secure=os.getenv('PTR_SECURE_COOKIE') == '1', max_age=28800)
    return {'ok': True}

@app.post('/api/auth/logout', dependencies=[Depends(require_admin)])
def logout(request: Request, response: Response):
    TOKENS.pop(request.cookies.get('ptr_session'), None)
    response.delete_cookie('ptr_session')
    return {'ok': True}

@app.get('/api/health')
def health():
    rows('SELECT 1')
    from backend import runner
    return {'version':'0.2.0','mode':'LIVE','backend':True,'database':True,'worker':bool(runner.THREAD and runner.THREAD.is_alive()),'disk':shutil.disk_usage(DATA).free > 100*1024*1024}
