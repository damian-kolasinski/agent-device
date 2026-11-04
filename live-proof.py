import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import shlex
import statistics
import subprocess
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--head', type=Path, required=True)
parser.add_argument('--base', type=Path, required=True)
parser.add_argument('--udid', required=True)
parser.add_argument('--rounds', type=int, default=5)
args = parser.parse_args()
source = Path(__file__).resolve().parent
out = args.workspace.resolve() / ('run-' + uuid.uuid4().hex[:12])
out.mkdir(parents=True)
versions = {'head': args.head.resolve(), 'base': args.base.resolve()}
session = 'ios-fill-proof-' + out.name
bundle = 'com.callstack.fillproof.' + out.name.replace('-', '')
current = None
booted_here = False
installed = False
records = []
cases = []

def interrupted(signum, frame):
    raise KeyboardInterrupt()

for signum in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
    signal.signal(signum, interrupted)

def run(command, **kwargs):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{command[:3]}: {result.returncode}: {result.stderr[-1800:]} {result.stdout[-1800:]}')
    return result

def environment(version):
    return {**os.environ, 'AGENT_DEVICE_STATE_DIR': str(out / version / 'state'), 'AGENT_DEVICE_XCUITEST_ARCHS': 'arm64', 'AGENT_DEVICE_XCUITEST_INCLUDE_UNIT_TESTS': '0', 'AGENT_DEVICE_XCUITEST_DESTINATION': 'generic/platform=iOS Simulator', 'AGENT_DEVICE_IOS_RUNNER_DERIVED_PATH': str(versions[version] / '.tmp/nov4-native-live-derived')}

def cli(version, *command, timeout=180):
    return run(['node', versions[version] / 'bin/agent-device.mjs', '--state-dir', out / version / 'state', *command], env=environment(version), cwd=versions[version], timeout=timeout)

def batch(version, steps, name):
    request = ['node', source / 'batch.mjs', versions[version], out / version / 'state', session, args.udid]
    result = subprocess.run([str(x) for x in request], input=json.dumps(steps), capture_output=True, text=True, env=environment(version), cwd=versions[version], timeout=180)
    (out / (name + '-request.json')).write_text(json.dumps(steps, indent=2))
    (out / (name + '-response.json')).write_text(result.stdout)
    (out / (name + '-stderr.log')).write_text(result.stderr)
    response = json.loads(result.stdout)
    assert result.returncode == 0 and response['success'], response
    assert response['data']['executed'] == response['data']['total'] == len(steps)
    assert all(row['ok'] for row in response['data']['results'])
    return response['data']['results']

def selector(name):
    return {'kind': 'selector', 'selector': f'id="proof.{name}"'}

def click(name):
    return {'command': 'click', 'input': {'target': selector(name)}}

def wait(name, key, value):
    return {'command': 'wait', 'input': {'kind': 'selector', 'selector': f'id="proof.{name}" {key}={json.dumps(value)}', 'timeoutMs': 5000}}

def get(name):
    return {'command': 'get', 'input': {'format': 'attrs', 'target': selector(name)}}

def node(row):
    return row['data']['node']

def counts(label):
    return {key: int(value) for key, value in re.findall(r'(taps|selections|rejected|targetFocus|neighbourFocus)=(\d+)', label)}

def prepare(version, mode, key):
    focused = mode.startswith('focused') or mode == 'fallback'
    value = '' if mode.lower().endswith('empty') else 'seedvalue'
    rows = batch(version, [click(mode), wait('state', 'label', 'Prepared ' + mode), wait('actual', 'label', f'Actual:{value} Neighbour:untouched'), wait('field', 'focused', focused), get('field'), get('witness')], key + '-prepare')
    field = node(rows[-2])
    witness = node(rows[-1])
    initial = counts(witness['label'])
    assert initial['taps'] == initial['selections'] == initial['rejected'] == 0, witness
    assert initial['targetFocus'] == int(focused) and initial['neighbourFocus'] == 0, witness
    secure = 'secure' in mode.lower()
    masked = 'masked' in mode.lower()
    assert field['type'] == ('SecureTextField' if secure else 'TextField'), field
    assert field.get('password', False) == secure, field
    if secure or masked:
        ax_value = field['value']
        assert ax_value and set(ax_value) == {'\u2022'} and ax_value != value, field
        if masked:
            assert len(ax_value) == max(1, len(value) // 2), field
    rect = field['rect']
    return {'x': rect['x'] + rect['width'] / 2, 'y': rect['y'] + rect['height'] / 2}, field, witness

def fill_case(version, key, mode, text, detailed=False, expected_taps=None, neighbour_transition=False):
    point, field, before = prepare(version, mode, key)
    if neighbour_transition:
        batch(version, [{'command': 'fill', 'input': {'target': {'kind': 'point', **point}, 'text': 'first'}}, wait('actual', 'label', 'Actual:first Neighbour:untouched'), click('neighbour'), wait('neighbour', 'focused', True), wait('field', 'focused', False)], key + '-switch-focus')
        reads = batch(version, [get('field'), get('witness')], key + '-before')
        field, before = node(reads[-2]), node(reads[-1])
    log = out / version / 'state/sessions' / session / 'runner.log'
    offset = log.stat().st_size
    steps = [{'command': 'fill', 'input': {'target': {'kind': 'point', **point}, 'text': text}}, wait('actual', 'label', f'Actual:{text} Neighbour:untouched'), wait('neighbour', 'value', 'untouched'), get('field'), get('actual'), get('witness')]
    rows = batch(version, steps, key + '-fill')
    after = node(rows[-1])
    actual = node(rows[-2])
    observed = counts(after['label'])
    assert actual['label'] == f'Actual:{text} Neighbour:untouched', actual
    assert observed['targetFocus'] == 1 and observed['neighbourFocus'] == 0, after
    if expected_taps is not None:
        assert observed['taps'] - counts(before['label'])['taps'] == expected_taps, (key, before, after)
    if mode == 'fallback':
        assert observed['rejected'] > 0, after
    excerpt = log.read_bytes()[offset:].decode(errors='replace')
    (out / (key + '-runner.log')).write_text(excerpt)
    assert 'AGENT_DEVICE_RUNNER_COMMAND_ACCEPTED command=type ' in excerpt, key
    assert 'AGENT_DEVICE_RUNNER_COMMAND_COMPLETED command=type ' in excerpt and 'ok=1' in excerpt, key
    reuse = 'evidence=current-input-reports-keyboard-focus polls=0' in excerpt
    if detailed:
        assert reuse == ((mode.startswith('focused') or mode == 'fallback') and not neighbour_transition), (key, reuse)
        cases.append({'case': key, 'mode': mode, 'point': point, 'requested': text, 'beforeField': field, 'beforeWitness': before, 'afterField': node(rows[-3]), 'actual': actual, 'afterWitness': after, 'focusReused': reuse, 'neighbourTransition': neighbour_transition, 'response': rows[0], 'command': steps[0]})
        (out / 'cases.json').write_text(json.dumps(cases, indent=2))
    return rows[0]['durationMs']

def attest_runner(version):
    log = out / version / 'state/sessions' / session / 'runner.log'
    command = next(line.strip() for line in log.read_text(errors='replace').splitlines() if 'xcodebuild test-without-building ' in line)
    parts = shlex.split(command)
    derived = versions[version] / '.tmp/nov4-native-live-derived'
    assert Path(parts[parts.index('-derivedDataPath') + 1]).resolve() == derived.resolve()
    assert Path(parts[parts.index('-xctestrun') + 1]).resolve().parent == (derived / 'Build/Products').resolve()
    entrypoint = parts[parts.index('-only-testing') + 1]
    assert entrypoint == 'AgentDeviceRunnerUITests/RunnerTests/testCommand'
    provenance[version]['runnerLaunch'] = {'command': 'xcodebuild test-without-building', 'entrypoint': entrypoint, 'derivedDataMatchesVersion': True, 'xctestrunFromVersionProducts': True, 'sourceCommandSha256': hashlib.sha256(command.encode()).hexdigest()}
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2))

def close(version):
    errors = []
    for command in [('--session', session, '--platform', 'ios', '--udid', args.udid, 'close'), ('daemon', 'stop', '--clean')]:
        try:
            cli(version, *command, timeout=90)
        except Exception as error:
            errors.append(str(error))
    if errors:
        raise RuntimeError(str(errors))

try:
    app = out / 'FillWitness.app'
    app.mkdir()
    (app / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': bundle, 'CFBundleExecutable': 'FillWitness', 'CFBundleName': 'FillWitness', 'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1', 'CFBundleShortVersionString': '1.0', 'LSRequiresIPhoneOS': True, 'UILaunchScreen': {}, 'UIDeviceFamily': [1, 2]}))
    sdk = run(['xcrun', '--sdk', 'iphonesimulator', '--show-sdk-path']).stdout.strip()
    run(['xcrun', 'swiftc', '-sdk', sdk, '-target', 'arm64-apple-ios17.0-simulator', '-parse-as-library', source / 'Fixture.swift', '-o', app / 'FillWitness'], timeout=120)
    run(['codesign', '--force', '--sign', '-', app], timeout=30)
    run(['node', '-e', '0'])
    listing = json.loads(run(['xcrun', 'simctl', 'list', 'devices', '-j']).stdout)
    runtime, device = next((runtime, d) for runtime, group in listing['devices'].items() for d in group if d['udid'] == args.udid)
    (out / 'device.json').write_text(json.dumps({'device': device, 'runtime': runtime, 'bundle': bundle, 'session': session}, indent=2))
    booted_here = device['state'] == 'Shutdown'
    if booted_here:
        run(['xcrun', 'simctl', 'boot', args.udid], timeout=90)
    run(['xcrun', 'simctl', 'bootstatus', args.udid, '-b'], timeout=180)
    run(['xcrun', 'simctl', 'install', args.udid, app], timeout=90)
    installed = True
    provenance = {}
    for version, checkout in versions.items():
        env = environment(version)
        assert not run(['git', 'status', '--porcelain=v1'], cwd=checkout).stdout
        state_initially_absent = not (out / version / 'state').exists()
        assert state_initially_absent
        for stage, command in [('build', ['pnpm', 'build']), ('native-build', ['pnpm', 'build:xcuitest:ios'])]:
            result = run(command, cwd=checkout, env=env, timeout=600)
            (out / (version + '-' + stage + '.log')).write_text(result.stdout + result.stderr)
        assert not run(['git', 'status', '--porcelain=v1'], cwd=checkout).stdout
        meta = json.loads((checkout / '.tmp/nov4-native-live-derived/.agent-device-runner-cache.json').read_text())
        provenance[version] = {'sha': run(['git', 'rev-parse', 'HEAD'], cwd=checkout).stdout.strip(), 'stateDirectoryInitiallyAbsent': state_initially_absent, 'runnerMetadata': meta, 'cliSha256': hashlib.sha256((checkout / 'bin/agent-device.mjs').read_bytes()).hexdigest(), 'builtJavascript': {str(p.relative_to(checkout)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((checkout / 'dist').rglob('*.js'))}}
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    current = 'head'
    opened = cli('head', '--session', session, '--platform', 'ios', '--udid', args.udid, 'open', bundle, '--relaunch', timeout=360)
    (out / 'head-open-response.json').write_text(opened.stdout)
    attest_runner('head')
    status = cli('head', 'daemon', 'status', '--json')
    (out / 'head-daemon-status.json').write_text(status.stdout)
    for key, mode, text, taps, transition in [
        ('focused-empty-fill', 'focusedEmpty', 'benchmark', 0, False),
        ('focused-prefilled-replace', 'focusedSeed', 'benchmark', 0, False),
        ('focused-clear', 'focusedSeed', '', 0, False),
        ('unfocused-prefilled-replace', 'seed', 'benchmark', 2, False),
        ('unfocused-clear', 'seed', '', 2, False),
        ('target-after-neighbour-focus', 'focusedSeed', 'second', 2, True),
        ('rejected-select-all-replace', 'fallback', 'benchmark', 1, False),
        ('rejected-select-all-clear', 'fallback', '', 1, False),
    ]:
        fill_case('head', key, mode, text, True, taps, transition)
        print(key, 'passed', flush=True)
    for mode in ['secure', 'focusedSecure', 'masked', 'focusedMasked']:
        for text in ['benchmark', '']:
            key = mode + ('-replace' if text else '-clear')
            fill_case('head', key, mode, text, True)
            print(key, 'passed', flush=True)
    close('head')
    current = None
    variants = {'empty_focused': ('focusedEmpty', 'benchmark'), 'existing_focused': ('focusedSeed', 'benchmark'), 'clear_focused': ('focusedSeed', ''), 'empty_unfocused': ('empty', 'benchmark'), 'existing_unfocused': ('seed', 'benchmark'), 'clear_unfocused': ('seed', '')}
    for index in range(args.rounds):
        order = ['head', 'base'] if index % 2 == 0 else ['base', 'head']
        names = list(variants)
        names = names[index % len(names):] + names[:index % len(names)]
        for version in order:
            current = version
            cli(version, '--session', session, '--platform', 'ios', '--udid', args.udid, 'open', bundle, '--relaunch', timeout=360)
            attest_runner(version)
            fill_case(version, f'warmup-{index}-{version}', 'focusedEmpty', 'warmup')
            for name in names:
                mode, text = variants[name]
                duration = fill_case(version, f'pair-{index + 1}-{version}-{name}', mode, text)
                records.append({'round': index + 1, 'version': version, 'variant': name, 'durationMs': duration})
                (out / 'samples.json').write_text(json.dumps(records, indent=2))
                print(version, index + 1, name, duration, flush=True)
            close(version)
            current = None
    aggregate = []
    for name in variants:
        values = {version: [r['durationMs'] for r in records if r['version'] == version and r['variant'] == name] for version in versions}
        medians = {version: statistics.median(rows) for version, rows in values.items()}
        aggregate.append({'variant': name, 'pairs': args.rounds, 'mediansMs': medians, 'reductionPercent': round(100 * (1 - medians['head'] / medians['base']), 1), 'headFasterPairs': sum(h < b for h, b in zip(values['head'], values['base'])), 'successfulCommands': {version: len(rows) for version, rows in values.items()}})
    (out / 'aggregates.json').write_text(json.dumps(aggregate, indent=2))
    print(json.dumps(aggregate, indent=2), flush=True)
finally:
    errors = []
    if current:
        try:
            close(current)
        except Exception as error:
            errors.append(str(error))
    if installed:
        try:
            run(['xcrun', 'simctl', 'uninstall', args.udid, bundle], timeout=60)
        except Exception as error:
            errors.append(str(error))
    if booted_here:
        try:
            run(['xcrun', 'simctl', 'shutdown', args.udid], timeout=90)
        except Exception as error:
            errors.append(str(error))
    (out / 'cleanup.json').write_text(json.dumps({'completed': not errors, 'errors': errors}, indent=2))
    if errors:
        raise RuntimeError(str(errors))
    print('Cleanup complete', flush=True)
