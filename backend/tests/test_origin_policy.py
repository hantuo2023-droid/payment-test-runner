import asyncio
import pytest
from backend.origin_policy import origin, binding_error, authorized_origins
from backend.runs import probe_browser


def task(url, **values):
    return dict(environment='QA', authorized=True, base_url=url, login_url=url+'/login', target_url=url+'/payments', **values)


def test_exact_origin_authorization(monkeypatch):
    monkeypatch.setenv('PTR_SANDBOX_URL','http://127.0.0.1:8080')
    monkeypatch.setenv('PTR_AUTHORIZED_ORIGINS','https://qa.example.test,http://localhost:9000')
    assert not binding_error(task('https://QA.example.test:443'))
    assert not binding_error(task('http://127.0.0.1:8080'))
    for url in ('https://qa.example.test.evil.test','http://qa.example.test','https://qa.example.test:444','http://127.0.0.1:8081'):
        assert binding_error(task(url))
    changed=task('https://qa.example.test');changed['target_url']='https://elsewhere.test/payments'
    assert binding_error(changed)


def test_invalid_configuration_and_production_boundary(monkeypatch):
    monkeypatch.setenv('PTR_AUTHORIZED_ORIGINS','https://qa.example.test/path')
    with pytest.raises(ValueError):authorized_origins()
    assert binding_error(task('https://qa.example.test'))
    production=task('https://production.example.test');production['environment']='Production';production['authorized']=False
    assert not binding_error(production)
    monkeypatch.setenv('PTR_AUTHORIZED_ORIGINS','https://preply.com')
    assert binding_error(task('https://preply.com'))
    with pytest.raises(ValueError):origin('https://user:password@qa.example.test')


def test_probe_rejects_unauthorized_target_before_browser(monkeypatch):
    monkeypatch.setenv('PTR_AUTHORIZED_ORIGINS','')
    report=asyncio.run(probe_browser(task('https://not-authorized.invalid'),{'protocol':'Direct'}))
    assert not report['connected'] and not report['chromium']
