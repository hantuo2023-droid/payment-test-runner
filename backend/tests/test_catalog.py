import pytest
from fastapi import HTTPException
from backend.catalog import Task, validate_task, export_file

def task(**kwargs):
    return Task(name='test',environment='QA',base_url='http://localhost:8080',login_url='http://localhost:8080/login',target_url='http://localhost:8080/settings/payments',**kwargs)

def test_urls_no_fallback():
    assert validate_task(task()) == 'sandbox'
    invalid = task()
    invalid.target_url = ''
    with pytest.raises(HTTPException): validate_task(invalid)
    invalid.target_url = 'https://preply.com/en/settings/payments'
    with pytest.raises(HTTPException): validate_task(invalid)

def test_csv_formula_escape():
    result = export_file([{'email':'=danger'}],['email'],'test')
    assert b"'=danger" in result.body
