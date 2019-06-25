import os
import sys
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

def find_eosio_cdt_path():
    eosio_cpp = shutil.which('eosio-cpp')
    if not eosio_cpp:
        raise "eosio.cdt not installed, please refer to https://github.com/eosio/eosio.cdt for an installation guild"
    eosio_cpp = os.path.realpath(eosio_cpp)
    eosio_cpp = os.path.dirname(eosio_cpp)
    return os.path.dirname(eosio_cpp)

def compile_cpp_file(src_path, includes = [], entry='apply'):
    tmp_path = src_path
    if os.path.exists(f'{tmp_path}.cpp') and os.path.exists(f'{tmp_path}.wasm'):
        if os.path.getmtime(f'{tmp_path}.cpp') <= os.path.getmtime(f'{tmp_path}.wasm'):
            return True
    #%system rm test.obj test.wasm
    #%system eosio-cpp -I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/capi -I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/core -O3 -contract test -o test.obj -c test.cpp
    #%system eosio-ld test.obj -o test.wasm
    #%ls
    if sys.platform == 'darwin':
        dl_sufix = 'dylib'
    else:
        dl_sufix = 'so'
    eosio_cdt_path = find_eosio_cdt_path()
    clang_7_args = [f'{eosio_cdt_path}/bin/clang-7',
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
     f'{eosio_cdt_path}/bin/LLVMEosioApply.{dl_sufix}',
     f'-fplugin={eosio_cdt_path}/bin/eosio_plugin.{dl_sufix}',
     '-mllvm',
     '-use-cfl-aa-in-codegen=both',
     f'-I{eosio_cdt_path}/bin/../include/libcxx',
     f'-I{eosio_cdt_path}/bin/../include/libc',
     f'-I{eosio_cdt_path}/bin/../include',
     f'--sysroot={eosio_cdt_path}/bin/../',
     f'-I{eosio_cdt_path}/bin/../include/eosiolib/core',
     f'-I{eosio_cdt_path}/bin/../include/eosiolib/contracts',
     '-c',
     f'-I{eosio_cdt_path}/include/eosiolib/capi',
     f'-I{eosio_cdt_path}/include/eosiolib/core',
     '-O3',
     '--std=c++17',
     ]
    for include in includes:
        clang_7_args.append(f"-I{include}")

    wasm_ld_args = [f'{eosio_cdt_path}/bin/wasm-ld',
     '--gc-sections',
     '--strip-all',
     '-zstack-size=8192',
     '--merge-data-segments',
     '-e', f'{entry}',
     '--only-export', f'{entry}:function',
     '-lc++',
     '-lc',
     '-leosio',
     '-leosio_dsm',
     '-mllvm',
     '-use-cfl-aa-in-codegen=both',
     f'{tmp_path}.obj',
     f'-L{eosio_cdt_path}/bin/../lib',
     '-stack-first',
     '--lto-O3',
     '-o',
     f'{tmp_path}.wasm',
     f'--allow-undefined-file={eosio_cdt_path}/bin/../eosio.imports']

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

def compile_cpp_src(src_path, code, includes = [], entry='apply'):
    tmp_path = src_path
    if os.path.exists(f'{tmp_path}.cpp'):
        old_code = open(f'{tmp_path}.cpp')
        if old_code == code:
            return True
    else:
        r = open(f'{tmp_path}.cpp', 'w').write(code)
    return compile_cpp_file(tmp_path, includes, entry)

def publish_cpp_contract(account_name, code, abi='', includes = [], entry='apply'):
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    assert compile_cpp_src(f'tmp/{account_name}', code, includes, entry=entry)

    code = open(f'tmp/{account_name}.wasm', 'rb').read()
    m = hashlib.sha256()
    m.update(code)
    code_hash = m.hexdigest()

    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        r = eosapi.set_contract(account_name, code, abi, 0)

def publish_cpp_contract_from_file(account_name, file_name, includes = [], entry='apply'):
    assert compile_cpp_file(file_name, includes, entry=entry)

    code = open(f'{file_name}.wasm', 'rb').read()
    m = hashlib.sha256()
    m.update(code)
    code_hash = m.hexdigest()

    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        print('update contract')
        abi = open(f'{file_name}.abi', 'r').read()
        r = eosapi.set_contract(account_name, code, abi, 0)
    return True
#print(find_include_path())
