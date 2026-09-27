import argparse
import getpass
from backend.store import migrate
from backend.auth import initialize

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['migrate','init-admin'])
args = parser.parse_args()
migrate()
if args.command == 'init-admin':
    password = getpass.getpass('管理员密码（至少12位）: ')
    if password != getpass.getpass('再次输入: '):
        raise SystemExit('两次输入不一致')
    initialize(password)
    print('管理员初始化成功')
