import os
import shutil
import hashlib
import marshal
import subprocess
from pyeoskit import eosapi, wallet, db
from pyeoskit import config
from pyeoskit._hello import _eosapi

db.reset()
config.main_token = 'UUOS'

if os.path.exists('test.wallet'):
    os.remove('test.wallet')
psw = wallet.create('test')

wallet.import_key('test', '5KH8vwQkP4QoTwgBtCV5ZYhKmv8mx56WeNrw9AZuhNRXTrPzgYc')
wallet.import_key('test', '5JMXaLz5xnVvwrnvAGaZKQZFCDdeU6wjmuJY1rDnXiUZz7Gyi1o')

def find_include_path():
    eosio_link = shutil.which('eosio-cpp')
    eosio_cpp = os.readlink(eosio_link)

    if eosio_cpp[:2] == '..':
        eosio_cpp = os.path.join(os.path.dirname(eosio_link), eosio_cpp)
    eosio_cpp = os.path.abspath(eosio_cpp)
    eosio_cpp = os.path.dirname(eosio_cpp)
    eosio_cpp = os.path.dirname(eosio_cpp)
    return os.path.join(eosio_cpp, 'opt/eosio.cdt/include/eosiolib/capi')


def publish_contract(account_name, code, abi):
    m = hashlib.sha256()
    code = compile(code, "contract", 'exec')
    code = marshal.dumps(code)
    m.update(code)
    code_hash = m.hexdigest()
    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        eosapi.set_contract(account_name, code, abi, 1)
    return True

#eosapi.set_nodes(['https://nodes.uuos.network:8443'])
eosapi.set_nodes(['http://127.0.0.1:8888'])

def run_test_code(code, account_name='helloworld11'):
    publish_contract(account_name, code, abi)
    try:
        r = eosapi.push_action(account_name, 'sayhello', b'hello,world', {account_name:'active'})
        print(r['processed']['action_traces'][0]['console'])
    except Exception as e:
        print(e)

def set_code(account_name, code):
    m = hashlib.sha256()
    code = compile(code, "contract", 'exec')
    code = marshal.dumps(code)
    m.update(code)
    code_hash = m.hexdigest()
    r = eosapi.get_code(account_name)
    if code_hash == r['code_hash']:
        return

    setcode = {"account":account_name,
               "vmtype": 1,
               "vmversion":0,
               "code":code.hex()
               }
    eosapi.push_action('eosio', 'setcode', setcode, {account_name:'active'})
    
    return True

def set_abi(account, abi):
    db.set_abi(account, abi)
    abi = _eosapi.pack_abi(abi)
    setabi ={'account':account, 'abi':abi.hex()}
    eosapi.push_action('eosio', 'setabi', setabi, {account:'active'})

def compile_cpp(account_name, code):
    tmp_path = f'tmp/{account_name}'
    if os.path.exists(f'{tmp_path}.cpp'):
        old_code = open(f'{tmp_path}.cpp')
        if old_code == code:
            return True
        r = open(f'{tmp_path}.cpp', 'w').write(code)

    clang_7_args = ['/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/clang-7',
     '-o',
     f'{tmp_path}.obj',
     f'{tmp_path}.cpp',
     '--target=wasm32',
     '-ffreestanding',
     '-nostdlib',
     '-fno-builtin',
     '-fno-threadsafe-statics',
     '-fno-exceptions',
     '-fno-rtti',
     '-fmodules-ts',
     '-DBOOST_DISABLE_ASSERTS',
     '-DBOOST_EXCEPTION_DISABLE',
     '-Xclang',
     '-load',
     '-Xclang',
     '/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/LLVMEosioApply.dylib',
     '-fplugin=/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/eosio_plugin.dylib',
     '-mllvm',
     '-use-cfl-aa-in-codegen=both',
     '-I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../include/libcxx',
     '-I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../include/libc',
     '-I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../include',
     '--sysroot=/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../',
     '-I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../include/eosiolib/core',
     '-I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../include/eosiolib/contracts',
     '-c',
     '-I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/capi',
     '-I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/core',
     '-O3',
     '--std=c++17',
     ]

    wasm_ld_args = ['/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/wasm-ld',
     '--gc-sections',
     '--strip-all',
     '-zstack-size=8192',
     '--merge-data-segments',
     '-e', 'apply',
     '--only-export', 'apply:function',
     '-lc++',
     '-lc',
     '-leosio',
     '-leosio_dsm',
     '-mllvm',
     '-use-cfl-aa-in-codegen=both',
     f'{tmp_path}.obj',
     '-L/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../lib',
     '-stack-first',
     '--lto-O3',
     '-o',
     f'{tmp_path}.wasm',
     '--allow-undefined-file=/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/bin/../eosio.imports']

    #%system rm test.obj test.wasm
    #%system eosio-cpp -I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/capi -I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/core -O3 -contract test -o test.obj -c test.cpp
    #%system eosio-ld test.obj -o test.wasm
    #%ls


    try:
        ret = subprocess.check_output(clang_7_args, stderr=subprocess.STDOUT)
        print(ret.decode('utf8'))
        ret = subprocess.check_output(wasm_ld_args, stderr=subprocess.STDOUT)
        print(ret.decode('utf8'))
    except subprocess.CalledProcessError as e:
        print("error (code {}):".format(e.returncode))
        print(e.output.decode('utf8'))
        return False
    return True

def publish_cpp_contract(account_name, code, abi=''):
    if not os.path.exists('tmp'):
        os.mkdir(tmp)
    assert compile_cpp(account_name, code)

    code = open(f'tmp/{account_name}.wasm', 'rb').read()
    m = hashlib.sha256()
    m.update(code)
    code_hash = m.hexdigest()

    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        print('update contract')
        r = eosapi.set_contract(account_name, code, abi, 0)

#print(find_include_path())
