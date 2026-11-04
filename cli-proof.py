import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import signal
import subprocess
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--checkout', type=Path, required=True)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--udid', required=True)
args = parser.parse_args()
checkout = args.checkout.resolve()
source = Path(__file__).resolve().parent
out = args.workspace.resolve() / ('cli-' + uuid.uuid4().hex[:12])
out.mkdir(parents=True)
state = out / 'state'
session = 'fill-cli-' + out.name
bundle = 'com.callstack.fillcli.' + out.name.replace('-', '')
derived = checkout / '.tmp/nov4-cli-derived'
env = {**os.environ, 'AGENT_DEVICE_STATE_DIR': str(state), 'AGENT_DEVICE_XCUITEST_ARCHS': 'arm64', 'AGENT_DEVICE_XCUITEST_INCLUDE_UNIT_TESTS': '0', 'AGENT_DEVICE_XCUITEST_DESTINATION': 'generic/platform=iOS Simulator', 'AGENT_DEVICE_IOS_RUNNER_DERIVED_PATH': str(derived)}
installed = False
opened = False
booted_here = False
sequence = 0
transcript = []
cases = []

def interrupted(signum, frame):
    raise KeyboardInterrupt()

for signum in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
    signal.signal(signum, interrupted)

def run(command, **kwargs):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{command[:3]}: exit {result.returncode}: {result.stderr[-1600:]} {result.stdout[-1600:]}')
    return result

def cli(command, label, target=True, timeout=180):
    global sequence
    sequence += 1
    prefix = ['node', str(checkout / 'bin/agent-device.mjs'), '--state-dir', str(state), '--json']
    if target:
        prefix += ['--session', session, '--platform', 'ios', '--udid', args.udid]
    argv = prefix + [str(x) for x in command]
    result = subprocess.run(argv, cwd=checkout, env=env, capture_output=True, text=True, timeout=timeout)
    key = f'{sequence:03d}-{label}'
    (out / (key + '-argv.json')).write_text(json.dumps(argv, indent=2))
    (out / (key + '-stdout.json')).write_text(result.stdout)
    (out / (key + '-stderr.log')).write_text(result.stderr)
    response = json.loads(result.stdout)
    entry = {'key': key, 'command': [str(x) for x in command], 'target': target, 'exitCode': result.returncode, 'response': response}
    transcript.append(entry)
    (out / 'transcript.json').write_text(json.dumps(transcript, indent=2))
    assert result.returncode == 0 and response['success'], entry
    return response['data']

def selector(name):
    return f'id="proof.{name}"'

def wait(name, attribute, value):
    return cli(['wait', selector(name) + ' ' + attribute + '=' + json.dumps(value), '5000'], 'wait-' + name)

def get(name):
    return cli(['get', 'attrs', selector(name)], 'get-' + name)['node']

def counts(label):
    return {key: int(value) for key, value in re.findall(r'(taps|selections|rejected|targetFocus|neighbourFocus)=(\d+)', label)}

try:
    head = run(['git', 'rev-parse', 'HEAD'], cwd=checkout).stdout.strip()
    assert not run(['git', 'status', '--porcelain=v1'], cwd=checkout).stdout
    assert not state.exists()
    for label, command in [('build', ['pnpm', 'build']), ('native-build', ['pnpm', 'build:xcuitest:ios'])]:
        result = run(command, cwd=checkout, env=env, timeout=600)
        (out / (label + '.log')).write_text(result.stdout + result.stderr)
    assert not run(['git', 'status', '--porcelain=v1'], cwd=checkout).stdout
    metadata = json.loads((derived / '.agent-device-runner-cache.json').read_text())
    assert not any('AGENT_DEVICE_RUNNER_UNIT_TESTS' in flag for flag in metadata['runnerSandboxBuildArgs'])
    app = out / 'FillWitness.app'
    app.mkdir()
    (app / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': bundle, 'CFBundleExecutable': 'FillWitness', 'CFBundleName': 'FillWitness', 'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1', 'CFBundleShortVersionString': '1.0', 'LSRequiresIPhoneOS': True, 'UILaunchScreen': {}, 'UIDeviceFamily': [1, 2]}))
    sdk = run(['xcrun', '--sdk', 'iphonesimulator', '--show-sdk-path']).stdout.strip()
    run(['xcrun', 'swiftc', '-sdk', sdk, '-target', 'arm64-apple-ios17.0-simulator', '-parse-as-library', source / 'Fixture.swift', '-o', app / 'FillWitness'], timeout=120)
    run(['codesign', '--force', '--sign', '-', app], timeout=30)
    run(['node', '-e', '0'])
    listing = json.loads(run(['xcrun', 'simctl', 'list', 'devices', '-j']).stdout)
    runtime, device = next((runtime, d) for runtime, group in listing['devices'].items() for d in group if d['udid'] == args.udid)
    booted_here = device['state'] == 'Shutdown'
    if booted_here:
        run(['xcrun', 'simctl', 'boot', args.udid], timeout=90)
    run(['xcrun', 'simctl', 'bootstatus', args.udid, '-b'], timeout=180)
    run(['xcrun', 'simctl', 'install', args.udid, app], timeout=90)
    installed = True
    opened = True
    cli(['open', bundle, '--relaunch'], 'open', timeout=360)
    runner_log = state / 'sessions' / session / 'runner.log'
    launch = next(line.strip() for line in runner_log.read_text(errors='replace').splitlines() if 'xcodebuild test-without-building ' in line)
    parts = shlex.split(launch)
    assert Path(parts[parts.index('-derivedDataPath') + 1]).resolve() == derived.resolve()
    assert Path(parts[parts.index('-xctestrun') + 1]).resolve().parent == (derived / 'Build/Products').resolve()
    assert parts[parts.index('-only-testing') + 1] == 'AgentDeviceRunnerUITests/RunnerTests/testCommand'
    status = cli(['daemon', 'status'], 'daemon-status', target=False)
    assert status['state'] == 'running' and status['ownership'] == 'detached'
    provenance = {'head': head, 'device': device, 'runtime': runtime, 'session': session, 'bundle': bundle, 'runnerMetadata': metadata, 'cliSha256': hashlib.sha256((checkout / 'bin/agent-device.mjs').read_bytes()).hexdigest(), 'builtJavascript': {str(p.relative_to(checkout)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((checkout / 'dist').rglob('*.js'))}, 'freshStateDirectory': True, 'runnerLaunchVerified': True, 'productionEntrypoint': 'AgentDeviceRunnerUITests/RunnerTests/testCommand', 'daemonVersion': status['version']}
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    for key, mode, text, expected_taps in [
        ('focused-empty-fill', 'focusedEmpty', 'benchmark', 0),
        ('focused-prefilled-replace', 'focusedSeed', 'benchmark', 0),
        ('focused-clear', 'focusedSeed', '', 0),
        ('unfocused-prefilled-replace', 'seed', 'benchmark', 2),
        ('unfocused-clear', 'seed', '', 2),
        ('secure-unfocused-replace', 'secure', 'benchmark', 2),
        ('secure-unfocused-clear', 'secure', '', 2),
        ('secure-focused-replace', 'focusedSecure', 'benchmark', 1),
        ('secure-focused-clear', 'focusedSecure', '', 1),
    ]:
        start = len(transcript)
        focused = mode.startswith('focused')
        secure = 'secure' in mode.lower()
        seed = '' if mode.lower().endswith('empty') else 'seedvalue'
        cli(['click', selector(mode)], key + '-prepare')
        wait('state', 'label', 'Prepared ' + mode)
        wait('actual', 'label', f'Actual:{seed} Neighbour:untouched')
        wait('field', 'focused', focused)
        before_field = get('field')
        before_witness = get('witness')
        initial = counts(before_witness['label'])
        assert initial['taps'] == initial['selections'] == initial['rejected'] == 0
        assert initial['targetFocus'] == int(focused) and initial['neighbourFocus'] == 0
        assert before_field['type'] == ('SecureTextField' if secure else 'TextField')
        assert before_field.get('password', False) == secure
        if secure:
            assert before_field['value'] and set(before_field['value']) == {'\u2022'} and before_field['value'] != seed
        rect = before_field['rect']
        point = [rect['x'] + rect['width'] / 2, rect['y'] + rect['height'] / 2]
        offset = runner_log.stat().st_size
        fill = cli(['fill', *[str(x) for x in point], text], key + '-fill')
        wait('actual', 'label', f'Actual:{text} Neighbour:untouched')
        wait('neighbour', 'value', 'untouched')
        after_field = get('field')
        actual = get('actual')
        after_witness = get('witness')
        observed = counts(after_witness['label'])
        assert actual['label'] == f'Actual:{text} Neighbour:untouched'
        assert observed['targetFocus'] == 1 and observed['neighbourFocus'] == 0
        assert observed['taps'] - initial['taps'] == expected_taps, (key, initial, observed)
        excerpt = runner_log.read_bytes()[offset:].decode(errors='replace')
        (out / (key + '-runner.log')).write_text(excerpt)
        ids = re.findall(r'AGENT_DEVICE_RUNNER_COMMAND_ACCEPTED command=type commandId=(\S+)', excerpt)
        assert len(ids) == 1
        assert 'AGENT_DEVICE_RUNNER_COMMAND_COMPLETED command=type commandId=' + ids[0] + ' ok=1' in excerpt
        reused = 'evidence=current-input-reports-keyboard-focus polls=0' in excerpt
        assert reused == focused
        cases.append({'case': key, 'requested': text, 'beforeField': before_field, 'beforeWitness': before_witness, 'afterField': after_field, 'actual': actual, 'afterWitness': after_witness, 'focusReused': reused, 'fieldTapCount': observed['taps'] - initial['taps'], 'commands': transcript[start:], 'fillResponse': fill})
        (out / 'cases.json').write_text(json.dumps(cases, indent=2))
        print(key, 'passed', flush=True)
    assert len(cases) == 9
finally:
    errors = []
    if opened:
        for command, label, target in [(['close'], 'close', True), (['daemon', 'stop', '--clean'], 'daemon-clean', False)]:
            try:
                cli(command, label, target, timeout=90)
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
    print('CLI proof cleanup complete', flush=True)
