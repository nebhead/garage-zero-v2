"""
Update management: version manifest parsing, GitHub (git) update checks and applying updates.

version.json format:
{
	"version": "vM.m.build",
	"releases": {
		"vM.m.build": {
			"date": "YYYY-MM-DD", "notes": "...",
			"requires_pip": bool,     # new python modules must be installed
			"requires_reboot": bool   # full system reboot needed (otherwise supervisor restart)
		}
	}
}
When updating from version A to B, the flags of every release R with A < R <= B are combined.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_FILE = 'version.json'
REQUIREMENTS_FILE = os.path.join('auto-install', 'requirements.txt')
CHECK_CACHE_SECONDS = 6 * 3600
GIT_TIMEOUT = 25  # must stay under the gunicorn worker timeout (30s)
RESTART_DELAY = 5  # seconds between update completion and restart, lets the UI read the final status

_lock = threading.Lock()
_check_cache = {'time': 0, 'result': None}
_update = {'state': 'idle', 'lines': [], 'action': None, 'error': None}

def parse_version(v):
	m = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(v).strip())
	return tuple(int(x) for x in m.groups()) if m else None

def _read_manifest_text(text):
	try:
		data = json.loads(text)
		if parse_version(data.get('version', '')) is None:
			return None
		return data
	except (ValueError, TypeError, AttributeError):
		return None

def get_local_manifest():
	try:
		with open(os.path.join(APP_DIR, MANIFEST_FILE)) as f:
			return _read_manifest_text(f.read())
	except OSError:
		return None

def get_version():
	m = get_local_manifest()
	return m['version'] if m else 'unknown'

def _git(*args, timeout=GIT_TIMEOUT):
	env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10')
	p = subprocess.run(['git', *args], cwd=APP_DIR, capture_output=True, text=True, timeout=timeout, env=env)
	return p.returncode, (p.stdout + p.stderr).strip()

def _upstream():
	"""Return the upstream ref (e.g. origin/main) for the current branch."""
	rc, out = _git('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
	if rc == 0:
		return out
	rc, branch = _git('rev-parse', '--abbrev-ref', 'HEAD')
	return f'origin/{branch}' if rc == 0 else None

def _parse_log(out):
	commits = []
	for line in out.splitlines():
		parts = line.split('\x1f')
		if len(parts) == 4:
			commits.append({'hash': parts[0], 'author': parts[1], 'date': parts[2], 'subject': parts[3]})
	return commits

LOG_FORMAT = '--pretty=format:%h%x1f%an%x1f%ad%x1f%s'

def plan_for(from_version, manifest):
	"""Combine the release flags between from_version (exclusive) and manifest version (inclusive)."""
	start = parse_version(from_version)
	end = parse_version(manifest['version']) if manifest else None
	plan = {'requires_pip': False, 'requires_reboot': False, 'notes': []}
	if not manifest or not end:
		return plan
	for ver, rel in sorted(manifest.get('releases', {}).items(), key=lambda kv: parse_version(kv[0]) or (0, 0, 0)):
		pv = parse_version(ver)
		if pv and (start is None or start < pv <= end):
			plan['requires_pip'] |= bool(rel.get('requires_pip'))
			plan['requires_reboot'] |= bool(rel.get('requires_reboot'))
			if rel.get('notes'):
				plan['notes'].append(f"{ver}: {rel['notes']}")
	return plan

def check_for_updates(force=False):
	"""Fetch from GitHub and compare. Results are cached unless force is set."""
	with _lock:
		if not force and _check_cache['result'] and time.time() - _check_cache['time'] < CHECK_CACHE_SECONDS:
			return _check_cache['result']
	result = {'ok': False, 'current': get_version(), 'latest': None, 'available': False,
			  'behind': 0, 'pending': [], 'recent': [], 'plan': None, 'error': None, 'checked': time.strftime('%Y-%m-%d %H:%M:%S')}
	try:
		upstream = _upstream()
		if not upstream:
			raise RuntimeError('Could not determine the upstream branch.')
		rc, out = _git('fetch', '--quiet', upstream.split('/')[0])
		if rc != 0:
			raise RuntimeError(f'git fetch failed: {out}')
		rc, out = _git('log', f'HEAD..{upstream}', LOG_FORMAT, '--date=short', '-n', '25')
		result['pending'] = _parse_log(out) if rc == 0 else []
		rc, out = _git('rev-list', '--count', f'HEAD..{upstream}')
		result['behind'] = int(out) if rc == 0 and out.isdigit() else len(result['pending'])
		rc, out = _git('log', 'HEAD', LOG_FORMAT, '--date=short', '-n', '10')
		result['recent'] = _parse_log(out) if rc == 0 else []
		rc, out = _git('show', f'{upstream}:{MANIFEST_FILE}')
		remote = _read_manifest_text(out) if rc == 0 else None
		result['latest'] = remote['version'] if remote else result['current']
		result['plan'] = plan_for(result['current'], remote) if result['behind'] else None
		result['available'] = result['behind'] > 0
		result['ok'] = True
	except Exception as e:
		result['error'] = str(e)
	with _lock:
		if result['ok']:
			_check_cache.update(time=time.time(), result=result)
	return result

def _log(line):
	with _lock:
		_update['lines'].append(line)

def _run_streaming(cmd):
	"""Run a command, streaming output lines to the update log. Returns exit code."""
	env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10')
	_log(f'$ {" ".join(cmd)}')
	try:
		p = subprocess.Popen(cmd, cwd=APP_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
		for line in p.stdout:
			_log(line.rstrip())
		return p.wait()
	except OSError as e:
		_log(f'Error: {e}')
		return 1

def _fail(msg):
	_log(msg)
	with _lock:
		_update.update(state='error', error=msg)

def _do_update():
	old_version = get_version()
	_log(f'Current version: {old_version}')
	upstream = _upstream()
	if not upstream:
		return _fail('Could not determine the upstream branch.')
	remote, _, branch = upstream.partition('/')
	if _run_streaming(['git', 'pull', '--ff-only', remote, branch]) != 0:
		return _fail('git pull failed. Local changes may conflict; update aborted.')

	new_manifest = get_local_manifest()
	new_version = new_manifest['version'] if new_manifest else 'unknown'
	plan = plan_for(old_version, new_manifest)
	_log(f'Updated to version: {new_version}')

	if plan['requires_pip']:
		_log('New python modules required; installing requirements...')
		if _run_streaming([sys.executable, '-m', 'pip', 'install', '-r', REQUIREMENTS_FILE]) != 0:
			return _fail('pip install failed. Update applied but dependencies are incomplete; not restarting.')

	action = 'reboot' if plan['requires_reboot'] else 'restart'
	_log('Update successful. System will reboot.' if action == 'reboot' else 'Update successful. Services will restart.')
	with _lock:
		_check_cache.update(time=0, result=None)
		_update.update(state='done', action=action)
	cmd = 'sudo -n reboot' if action == 'reboot' else 'sudo -n supervisorctl restart all'
	subprocess.Popen(['bash', '-c', f'sleep {RESTART_DELAY} && {cmd}'], cwd=APP_DIR, start_new_session=True,
					 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _worker():
	try:
		_do_update()
	except Exception as e:
		_fail(f'Unexpected error: {e}')

def start_update():
	"""Start the update in a background thread. Returns False if one is already running."""
	with _lock:
		if _update['state'] in ('running', 'done'):
			return False
		_update.update(state='running', lines=[], action=None, error=None)
	threading.Thread(target=_worker, daemon=True).start()
	return True

def get_update_status(since=0):
	with _lock:
		return {'state': _update['state'], 'lines': _update['lines'][since:], 'next': len(_update['lines']),
				'action': _update['action'], 'error': _update['error']}
