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
default_vm_type=1

if os.path.exists('test.wallet'):
    os.remove('test.wallet')
psw = wallet.create('test')

wallet.import_key('test', '5KH8vwQkP4QoTwgBtCV5ZYhKmv8mx56WeNrw9AZuhNRXTrPzgYc')
wallet.import_key('test', '5JMXaLz5xnVvwrnvAGaZKQZFCDdeU6wjmuJY1rDnXiUZz7Gyi1o')

#eosapi.set_nodes(['https://nodes.uuos.network:8443'])
eosapi.set_nodes(['http://127.0.0.1:8888'])

def run_test_code(code, abi='', account_name='helloworld11'):
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
        raise "eosio.cdt not installed, please refer to https://github.com/eosio/eosio.cdt for an installation guide"
    eosio_cpp = os.path.realpath(eosio_cpp)
    eosio_cpp = os.path.dirname(eosio_cpp)
    return os.path.dirname(eosio_cpp)

class cpp_compiler(object):

    def __init__(self, account_name, cpp_files, includes = [], entry='apply'):
        self.cpp_files = cpp_files
        self.includes = includes
        self.entry = entry
        self.account_name = account_name
        
        for cpp_file in cpp_files:
            if not cpp_file.endswith('.cpp'):
                raise cpp_file + ' is not a cpp file'

    def compile_cpp_file(self, opts=['-O3']):
        #%system rm test.obj test.wasm
        #%system eosio-cpp -I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/capi -I/usr/local/Cellar/eosio.cdt/1.6.1/opt/eosio.cdt/include/eosiolib/core -O3 -contract test -o test.obj -c test.cpp
        #%system eosio-ld test.obj -o test.wasm
        #%ls
        if sys.platform == 'darwin':
            dl_sufix = 'dylib'
        else:
            dl_sufix = 'so'
        eosio_cdt_path = find_eosio_cdt_path()

        for cpp_file in self.cpp_files:
            tmp_path = cpp_file[:-4]
            obj_file = tmp_path + '.obj'
            
            if os.path.exists(obj_file):
                if os.path.getmtime(cpp_file) <= os.path.getmtime(obj_file):
                    continue
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
            '--std=c++17',
            ]
            print('Compiling', cpp_file)
            for opt in opts:
                clang_7_args.append(opt)
            for include in self.includes:
                clang_7_args.append(f"-I{include}")
            try:
                ret = subprocess.check_output(clang_7_args, stderr=subprocess.STDOUT)
                print(ret.decode('utf8'))
            except subprocess.CalledProcessError as e:
                print("error (code {}):".format(e.returncode))
                print(e.output.decode('utf8'))
                return None

        wasm_ld_args = [f'{eosio_cdt_path}/bin/wasm-ld',
        '--gc-sections',
        '--strip-all',
        '-zstack-size=8192',
        '--merge-data-segments',
        '-e', f'{self.entry}',
        '--only-export', f'{self.entry}:function',
        '-lc++',
        '-lc',
        '-leosio',
        '-leosio_dsm',
        '-mllvm',
        '-use-cfl-aa-in-codegen=both',
        f'-L{eosio_cdt_path}/bin/../lib',
        '-stack-first',
        '--lto-O3',
        '-o',
        f'{self.account_name}.wasm',
        f'--allow-undefined-file={eosio_cdt_path}/bin/../eosio.imports']


        for cpp_file in self.cpp_files:
            wasm_ld_args.append(cpp_file[:-4] + '.obj')
        
        eosio_pp = [
            f'{eosio_cdt_path}/bin/eosio-pp',
            '-o',
            f'{self.account_name}.wasm',
            f'{self.account_name}.wasm',
        ]
        
        print('Generating', f'{self.account_name}.wasm')
        
        try:
            ret = subprocess.check_output(wasm_ld_args, stderr=subprocess.STDOUT)
            print(ret.decode('utf8'))
            ret = subprocess.check_output(eosio_pp, stderr=subprocess.STDOUT)
            print(ret.decode('utf8'))
        except subprocess.CalledProcessError as e:
            print("error (code {}):".format(e.returncode))
            print(e.output.decode('utf8'))
            return None
        return open(f'{self.account_name}.wasm', 'rb').read()

def compile_cpp_file(account_name, src_path, includes=[], entry='apply', opts=['-O3']):
    compiler = cpp_compiler(account_name, [src_path,], includes, entry)
    return compiler.compile_cpp_file(opts)

def compile_cpp_files(account_name, src_paths, includes=[], entry='apply', opts=['-O3']):
    compiler = cpp_compiler(account_name, src_paths, includes, entry)
    return compiler.compile_cpp_file(opts)

def compile_cpp_src(account_name, code, includes = [], entry='apply', opts=['-O3']):
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    src_path = os.path.join('tmp', account_name+'.cpp')
    if os.path.exists(src_path):
        old_code = open(src_path).read()
        if old_code == code:
            tmp_path = src_path[:-4]
            wasm_file = f'{account_name}.wasm'
            if os.path.exists(f'{tmp_path}.cpp') and os.path.exists(wasm_file):
                if os.path.getmtime(f'{tmp_path}.cpp') <= os.path.getmtime(wasm_file):
                    return open(wasm_file, 'rb').read()
    with open(src_path, 'w') as f:
        f.write(code)
    return compile_cpp_file(account_name, src_path, includes, entry, opts=opts)

def publish_cpp_contract_from_file(account_name, file_name, abi=b'', includes=[], entry='apply', opts=['-O3']):
    code = compile_cpp_file(account_name, file_name, includes, entry=entry, opts=opts)
    assert code
    m = hashlib.sha256()
    m.update(code)
    code_hash = m.hexdigest()

    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        print('update contract')
#        abi = open(f'{account_name}.abi', 'r').read()
        r = eosapi.set_contract(account_name, code, abi, 0)
    return True

def publish_cpp_contract_from_files(account_name, file_names, abi = b'', includes = [], entry='apply', opts=['-O3']):
    code = compile_cpp_files(account_name, file_names, includes, entry=entry, opts=opts)
    assert code
    m = hashlib.sha256()
    m.update(code)
    code_hash = m.hexdigest()

    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        print('update contract')
        r = eosapi.set_contract(account_name, code, abi, 0)
    return True

#print(find_include_path())

def publish_cpp_contract(account_name, code, abi='', includes = [], entry='apply', opts=['-O3'],vm_type=0):
    code = compile_cpp_src(account_name, code, includes, entry=entry, opts=opts)
    code = open(f'{account_name}.wasm', 'rb').read()
    m = hashlib.sha256()
    m.update(code)
    code_hash = m.hexdigest()
    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        r = eosapi.set_contract(account_name, code, abi, vm_type)
    return True

def publish_py_contract(account_name, code, abi, vm_type=1, includes = [], entry='apply'):
    m = hashlib.sha256()
    code = compile(code, "contract", 'exec')
    code = marshal.dumps(code)
    m.update(code)
    code_hash = m.hexdigest()
    r = eosapi.get_code(account_name)
    if code_hash != r['code_hash']:
        eosapi.set_contract(account_name, code, abi, 1)
    return True

def publish_contract(account_name, code, abi, vm_type=1, includes = [], entry='apply'):
    if vm_type == 1:
        return publish_py_contract(account_name, code, abi, 1)
    else:
        return publish_cpp_contract(account_name, code, abi, includes, entry)

