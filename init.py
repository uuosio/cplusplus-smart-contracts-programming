import os
import hashlib
import marshal
from uuoskit import uuosapi, wallet, config

if os.path.exists('test.wallet'):
    os.remove('test.wallet')
psw = wallet.create('test')

# python_contract
# active key of ceyelqpjeeia
wallet.import_key('test', '5JfZz1kXF8TXsxQgwfsvZCUBeTQefYSsCLDSbSPmnbKQfFmtBny')

# test_account1
# active key of wkpmdjdsztyu
wallet.import_key('test', '5Jaz37nnxbpAiAGQEsyxtnGfCPTJFjX9Wn6zv7V41Ko6DXSqhd9')

# test_account2
# active key of ebvjmdibybgq
wallet.import_key('test', '5KiVDjfHMHXzxrcLqZxGENrhCcCXBMSXP7paPbJWiMCDRMbStsF')

uuosapi.set_node('http://127.0.0.1:8888')
uuosapi.set_node('https://api.testnet.eos.io')

config.setup_eos_test_network()

python_contract = config.python_contract
test_account1 = 'wkpmdjdsztyu'
test_account2 = 'ebvjmdibybgq'

def run_test_code(code):
    code = uuosapi.mp_compile(python_contract, code)
    uuosapi.deploy_python_contract(python_contract, code, b'', deploy_type=1)
    r = uuosapi.push_action(python_contract, 'sayhello', b'hello,world', {python_contract:'active'})
    print(r['processed']['action_traces'][0]['console'])
