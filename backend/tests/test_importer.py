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
    summary, data = parse('4242 4242 4242 4242|12|2035|123\n4242424242424242|12|2035|999\n1234567890123456|12|2035|123','cards')
    assert summary['valid'] == 1 and summary['duplicates'] == 1 and len(summary['errors']) == 1
    assert data[0]['masked'] == '**** **** **** 4242'
    assert '1234567890123456' not in str(summary)
