"""Keep generic ARM builds on Dropshot and NVIDIA-dependent builds on Goran.

Inspect the full evaluated derivation graph before starting any build. Unknown or
incomplete graph entries stop release validation. SSH aliases are trusted host
configuration; no identities or credentials are embedded in this module.
"""
import json
import os
import platform
import re
import socket
import subprocess
from urllib.parse import urlsplit

NVIDIA_NAME = re.compile(r'(?:^|[-_.+0-9])(?:lib)?(nvidia|cuda|cudnn|cublas|cufft|curand|cusolver|cusparse|cupti|nvcc|nccl|tensorrt|cutlass)(?:$|[-_.+0-9])', re.I)
NVIDIA_FLAGS = re.compile(r'(cuda|nvidia|cudnn|nccl|tensorrt)', re.I)
TRUE_VALUES = {'1', 'true', 'yes', 'on', 'enabled'}
ARM_ALIASES = {'dropshot-arm-linux', 'dropshot-arm-test', 'dropshot-linux-builder'}


def normalize_graph(graph):
    """Accept legacy absolute-path maps and Nix JSON v4, failing closed."""
    if not isinstance(graph, dict):
        raise ValueError('Invalid derivation graph')
    if 'version' not in graph and 'derivations' not in graph:
        return graph
    if type(graph.get('version')) is not int or graph['version'] != 4:
        raise ValueError('Unsupported derivation graph version')
    if set(graph) != {'version', 'derivations'} or not isinstance(graph['derivations'], dict):
        raise ValueError('Invalid versioned derivation graph')
    def absolute(name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]{32}-[^/\n]+\.drv', name):
            raise ValueError('Invalid derivation basename')
        return '/nix/store/' + name
    result = {}
    for name, drv in graph['derivations'].items():
        path = absolute(name)
        if (not isinstance(drv, dict) or type(drv.get('version')) is not int
                or drv['version'] != 4 or not isinstance(drv.get('env'), dict)
                or not isinstance(drv.get('inputs'), dict)
                or not isinstance(drv['inputs'].get('drvs'), dict)):
            raise ValueError('Invalid v4 derivation entry')
        dependencies = {}
        for child, info in drv['inputs']['drvs'].items():
            if (not isinstance(info, dict) or set(info) != {'outputs', 'dynamicOutputs'}
                    or not isinstance(info['outputs'], list)
                    or not all(isinstance(output, str) for output in info['outputs'])
                    or info['dynamicOutputs'] != {}):
                raise ValueError('Unsupported dynamic or malformed derivation dependency')
            dependencies[absolute(child)] = info['outputs']
        env = dict(drv['env'])
        structured = drv.get('structuredAttrs')
        if structured is not None:
            if not isinstance(structured, dict):
                raise ValueError('Invalid structured derivation attributes')
            env['__json'] = json.dumps(structured)
        result[path] = dict(drv, env=env, inputDrvs=dependencies)
    return result


def is_nvidia(drv):
    env = drv.get('env', {})
    if '__json' in env:
        try:
            structured = json.loads(env['__json'])
        except (TypeError, ValueError) as error:
            raise ValueError('Invalid structured derivation attributes') from error
        if not isinstance(structured, dict):
            raise ValueError('Structured derivation attributes must be an object')
        env = dict(env, **structured)
    if NVIDIA_NAME.search(str(env.get('name', drv.get('name', '')))):
        return True
    features = env.get('requiredSystemFeatures', '')
    if isinstance(features, list):
        features = ' '.join(features)
    if any(NVIDIA_FLAGS.search(feature) for feature in str(features).split()):
        return True
    # Generic builder scripts often mention optional CUDA support. Inspect only
    # explicit enabled flags, not arbitrary script text or dependency paths.
    return any(NVIDIA_FLAGS.search(key) and str(value).lower() in TRUE_VALUES
               for key, value in env.items())


def classify(graph, roots):
    """Return NVIDIA-dependent roots; reject incomplete/cyclic graphs."""
    done = {}
    active = set()
    def visit(path):
        if path in done:
            return done[path]
        if path in active:
            raise ValueError(f'Cyclic derivation graph: {path}')
        if path not in graph:
            raise ValueError(f'Incomplete derivation graph: {path}')
        drv = graph[path]
        if (not isinstance(drv, dict) or not isinstance(drv.get('inputDrvs'), dict)
                or not isinstance(drv.get('env'), dict)):
            raise ValueError(f'Invalid derivation graph entry: {path}')
        active.add(path)
        # Visit every dependency even after finding a GPU dependency, so a
        # partial graph cannot escape the completeness check through any().
        dependencies = [visit(child) for child in drv.get('inputDrvs', {})]
        active.remove(path)
        done[path] = is_nvidia(drv) or any(dependencies)
        return done[path]
    return {path: visit(path) for path in roots}


def endpoint(value, lane):
    parsed = urlsplit(value)
    allowed = {'arm': ARM_ALIASES, 'nvidia': {'goran'}, 'x86': {'edberg'}}[lane]
    if (parsed.scheme != 'ssh-ng' or parsed.hostname not in allowed or
            parsed.port is not None or parsed.path not in ('', '/') or
            parsed.query or parsed.fragment or parsed.password):
        raise ValueError(f'{lane} builds require an authenticated SSH alias for {sorted(allowed)}')
    return value


def plan(graph, roots, system, environ=None, hostname=None, machine=None):
    environ = os.environ if environ is None else environ
    marked = classify(graph, roots)
    gpu = [path for path in roots if marked[path]]
    generic = [path for path in roots if not marked[path]]
    commands = []
    if system == 'x86_64-linux':
        if gpu:
            raise ValueError('NVIDIA-dependent x86 builds are prohibited: only ARM Goran is authorized')
        if 'FLEET_X86_STORE' in environ:
            store = endpoint(environ['FLEET_X86_STORE'], 'x86')
            if generic:
                commands.append(('edberg', ['nix', 'build', '--no-link', '--eval-store', 'auto',
                    '--store', store, '--option', 'builders', '', *[path + '^*' for path in generic]]))
        else:
            hostname = socket.gethostname().split('.')[0] if hostname is None else hostname
            machine = platform.machine() if machine is None else machine
            if hostname != 'armstrong' or machine != 'x86_64':
                raise ValueError('Generic x86 validation must build on Armstrong')
            if generic:
                commands.append(('armstrong', ['nix', 'build', '--no-link', '--option', 'builders', '',
                                                *[path + '^*' for path in generic]]))
    elif system == 'aarch64-linux':
        for lane, paths, variable, host in (
                ('arm', generic, 'FLEET_ARM_STORE', 'dropshot'),
                ('nvidia', gpu, 'FLEET_NVIDIA_STORE', 'goran')):
            if paths:
                store = endpoint(environ.get(variable, ''), lane)
                commands.append((host, ['nix', 'build', '--no-link', '--eval-store', 'auto',
                    '--store', store, '--option', 'builders', '', *[path + '^*' for path in paths]]))
    else:
        raise ValueError('Unsupported build system')
    return commands


def build(roots, system):
    roots = sorted(set(roots))
    if not roots:
        return []
    graph = normalize_graph(json.loads(subprocess.check_output(
        ['nix', 'derivation', 'show', '--recursive', *roots], text=True)))
    commands = plan(graph, roots, system)
    # Resolve and validate every route before starting any build.
    for host, command in commands:
        print(json.dumps({'buildHost': host, 'system': system, 'derivations': [arg for arg in command if arg.endswith('^*')]}), flush=True)
        subprocess.run(command, check=True)
    return [host for host, _ in commands]
