from backend.importer import parse

def test_account_normalization():
    summary, data = parse('  user@example.com  |  pass123 \n\nUSER@example.com----other\nbad\nx@example.com|\nhi@example.com----abc', 'accounts')
    assert summary['total'] == 5
    assert summary['valid'] == 2
    assert summary['duplicates'] == 1
    assert len(summary['errors']) == 2
    assert data[0] == {'email':'user@example.com','password':'pass123'}
    assert 'pass123' not in str(summary)

def test_csv_and_cards():
    summary, data = parse('email,password\n"a@example.com","a,b"','accounts')
    assert data[0]['password'] == 'a,b'
    summary, data = parse('4242 4242 4242 4242|12|2035|123\n4242424242424242|12|2035|999\nbad-number|12|2035|123','cards')
    assert summary['valid'] == 1 and summary['duplicates'] == 1 and len(summary['errors']) == 1
    assert data[0]['masked'] == '**** **** **** 4242'
    assert '1234567890123456' not in str(summary)

def test_ambiguous_csv_is_not_guessed():
    summary,data=parse('a@example.com,"unterminated','accounts')
    assert not data and len(summary['errors'])==1
    summary,data=parse('existing@example.com|pass','accounts',['existing@example.com'])
    assert not data and summary['duplicates']==1


def test_nodes_formats_dedup_and_safe_errors():
    summary,data=parse('http://user:node-secret@LOCALHOST:18888\nhttp://user:changed@localhost:18888\nnode,SOCKS5,localhost,1080,,\nsocks5://user:hidden@localhost:1081\nhttp://user:very-secret@bad:wrong','networks')
    assert summary['valid']==2 and summary['duplicates']==1 and len(summary['errors'])==2
    assert data[0]['host']=='localhost' and data[0]['password']=='node-secret'
    assert all(secret not in str(summary) for secret in ('node-secret','hidden','very-secret'))
    assert 'SOCKS5' in summary['errors'][0]['reason']


def test_fixture_limit_belongs_to_adapter():
    from backend.tasks.data_contract import validate_data
    summary,data=parse('5555555555554444|12|2035|123','cards')
    assert summary['valid']==1  # Official synthetic test number, outside five local fixtures.
    local={'environment':'Sandbox','authorized':True,'adapter':'sandbox','base_url':'http://localhost:8080'}
    assert validate_data(local,data[0])
    qa=dict(local,adapter='contract_binding',base_url='https://qa.example.test')
    assert not validate_data(qa,data[0])
    assert validate_data(dict(qa,environment='Production'),data[0])
    assert validate_data(dict(qa,authorized=False),data[0])


def test_dirty_numeric_formats_normalize_to_same_record():
    samples=[
        '4242 4242 4242 4242|7|35|123',
        '4242-4242-4242-4242;07;2035;123',
        '4242424242424242\t7\t35\t123',
        '4242424242424242:7:2035:123',
        '4242 4242 4242 4242 7 35 123',
        '４２４２４２４２４２４２４２４２｜０７｜２０３５｜１２３',
        '\ufeff42424242\u200b42424242|07|35|123',
        '"4242424242424242", "07", "2035", "123"',
        '4242424242424242|7/35|123',
        '4242424242424242,07/2035,123',
        '4242 4242 4242 4242 7 / 35 123',
    ]
    summary,data=parse('\n'.join(samples),'cards')
    assert summary['valid']==1 and summary['duplicates']==len(samples)-1
    assert not summary['errors'] and not summary['warnings']
    assert data[0]['month']=='07' and data[0]['year']=='2035' and data[0]['cvc']=='123'
    assert 'year_full' not in data[0]


def test_expired_data_is_warning_not_error():
    from datetime import datetime
    today=datetime.now()
    summary,data=parse(f'4242424242424242|01/00|123\n4000000000000002|{today.month}|{today.year}|123','cards')
    assert summary['valid']==2 and not summary['errors']
    assert len(summary['warnings'])==1 and summary['warnings'][0]['line']==1
    assert summary['warnings'][0]['code']=='EXPIRED_TEST_DATA'
    assert data[0]['year']=='2000' and data[0]['month']=='01'
    assert data[0]['number'] not in str(summary) and '123' not in str(summary)


def test_expiry_errors_stay_errors_and_headers_are_ignored():
    summary,data=parse('"number","expiry","cvc"\n4242424242424242|13/35|123\n4242424242424242|12/350|123\n4242424242424242|12/35|abc\n4242424242424242|12/35|123|extra','cards')
    assert summary['total']==4 and len(summary['errors'])==4 and not data
    assert not summary['warnings']
    assert '4242424242424242' not in str(summary)


def test_credentials_preserve_delimiters_and_unicode():
    for line,password in [
        ('a@example.com|pw|with,delimiters----Ａ','pw|with,delimiters----Ａ'),
        ('a@example.com----pw|with----pipes','pw|with----pipes'),
        ('a@example.com,"pw,with|pipe"','pw,with|pipe'),
        ('a@example.com\tpw｜wide','pw｜wide'),
        ('a@example.com｜pwＡ','pwＡ'),
    ]:
        summary,data=parse('\ufeff'+line,'accounts')
        assert summary['valid']==1 and not summary['errors']
        assert data[0]['password']==password
        assert password not in str(summary)
