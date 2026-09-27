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
