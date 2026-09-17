#!/usr/bin/env python3
"""Install tested, immutable Docker assets from stable GitHub releases."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

REPO = 'foffano/ECO-NATIVE'
APP = Path('/srv/apps/eco-native')
BACKUPS = Path('/srv/backups/eco-native')
ASSET = 'eco-native-linux-amd64.tar.gz'


def version(tag):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('Invalid stable release tag')
    return tuple(map(int, tag[1:].split('.')))


def validate_manifest(data, tag):
    version(tag)
    if (data.get('schema') != 1 or data.get('tag') != tag
            or data.get('image') != f'eco-native:{tag}'
            or data.get('architecture') != 'amd64' or data.get('asset') != ASSET
            or not re.fullmatch(r'[a-f0-9]{40}', data.get('revision', ''))
            or not re.fullmatch(r'[a-f0-9]{64}', data.get('sha256', ''))):
        raise ValueError('Invalid release manifest')
    return data


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'eco-native-updater'}), timeout=60)


def run(*args, capture=False):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE if capture else None).stdout


def compose(*args, capture=False):
    return run('docker', 'compose', '--project-directory', str(APP), '-f', str(APP / 'compose.yml'), *args, capture=capture)


def health():
    return json.loads(compose('exec', '-T', 'app', 'python', '-c',
        'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:18765/health", timeout=10).read().decode())', capture=True))


def atomic(path, content):
    stat = path.stat() if path.exists() else None
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if stat:
            os.chown(name, stat.st_uid, stat.st_gid)
            os.chmod(name, stat.st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def update_environment(old, tag):
    lines = [line for line in old.splitlines() if not re.match(r'^(IMAGE|IMAGE_TAG)=', line)]
    return '\n'.join(lines + ['IMAGE=eco-native', f'IMAGE_TAG={tag}', ''])


def install(manifest):
    tag = manifest['tag']
    marker = APP / 'data/.maintenance'
    old = (APP / '.env').read_text()
    stopped = False
    try:
        marker.touch(mode=0o644)
        status = health()
        if status.get('maintenance') is True:
            busy = status['active_jobs'] or status['active_login_sessions']
        else:  # One-time upgrade from v0.1.44, before maintenance support.
            state = json.loads((APP / 'data/studio.json').read_text())
            busy = any(job['status'] in ('queued', 'running') for job in state.get('jobs', []))
            processes = compose('top', 'app', capture=True).lower()
            busy = busy or 'chromium' in processes or 'chrome' in processes
        if busy:
            print('Deferred: jobs or login sessions are active.', flush=True)
            return False
        stopped = True
        compose('stop', 'app')
        BACKUPS.mkdir(parents=True, exist_ok=True)
        os.chown(BACKUPS, 1000, 1000)
        os.chmod(BACKUPS, 0o700)
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        compose('run', '--rm', '--no-deps', '--entrypoint', 'python', '-v',
                f'{BACKUPS}:/backups', 'app', '-m', 'backend.maintenance', 'backup',
                f'/backups/{stamp}-before-{tag}.zip')
        atomic(APP / '.env', update_environment(old, tag))
        compose('up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '120')
        status = health()
        if status.get('version') != tag[1:] or status.get('revision') != manifest['revision']:
            raise RuntimeError('Running image does not match release')
        atomic(APP / '.env.prev', old)
        shutil.copy2(APP / 'compose.yml', APP / 'compose.yml.prev')
        atomic(APP / 'installed-release.json', json.dumps(manifest, indent=2) + '\n')
        with (APP / 'deploys.log').open('a') as log:
            log.write(f'{stamp} {tag} ok-release-updater\n')
        print(f'Deployed {tag} ({manifest["revision"]}).', flush=True)
        return True
    except BaseException:
        if stopped:
            print('Deployment failed; restoring previous image.', flush=True)
            atomic(APP / '.env', old)
            compose('up', '-d', '--pull', 'never', '--wait', '--wait-timeout', '120')
        raise
    finally:
        marker.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='Explicit stable release; also retries a failed update')
    args = parser.parse_args()
    os.umask(0o077)
    with (APP / '.deploy.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another deployment is running.')
            return
        endpoint = 'tags/' + args.tag if args.tag else 'latest'
        if args.tag:
            version(args.tag)
        with request(f'https://api.github.com/repos/{REPO}/releases/{endpoint}') as response:
            release = json.load(response)
        tag = release['tag_name']
        version(tag)
        if release['draft'] or release['prerelease']:
            raise ValueError('Only published stable releases are accepted')
        current = re.search(r'^IMAGE_TAG=(.+)$', (APP / '.env').read_text(), re.M).group(1)
        if version(tag) <= version(current):
            print(f'Already current: {current}.')
            return
        failed = APP / '.failed-release'
        if not args.tag and failed.exists() and failed.read_text().strip() == tag:
            print(f'{tag} previously failed; inspect journal and retry explicitly.')
            return
        assets = {asset['name']: asset for asset in release['assets']}
        if ASSET not in assets or 'release-manifest.json' not in assets:
            print(f'{tag}: waiting for tested Docker assets.')
            return
        prefix = f'https://github.com/{REPO}/releases/download/{tag}/'
        for name in (ASSET, 'release-manifest.json'):
            if assets[name]['browser_download_url'] != prefix + name:
                raise ValueError('Unexpected artifact URL')
        with request(prefix + 'release-manifest.json') as response:
            manifest = validate_manifest(json.load(response), tag)
        if shutil.disk_usage('/var/tmp').free < max(6 * 1024**3, assets[ASSET]['size'] * 4):
            raise RuntimeError('Insufficient free disk space for safe update')
        with tempfile.TemporaryDirectory(prefix='eco-native-release-', dir='/var/tmp') as directory:
            archive = Path(directory) / ASSET
            digest = hashlib.sha256()
            with request(prefix + ASSET) as response, archive.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != manifest['sha256']:
                raise ValueError('Docker archive checksum mismatch')
            run('docker', 'load', '-i', str(archive))
        labels = json.loads(run('docker', 'image', 'inspect', manifest['image'], '--format', '{{json .Config.Labels}}', capture=True))
        if labels.get('org.opencontainers.image.version') != tag[1:] or labels.get('org.opencontainers.image.revision') != manifest['revision']:
            raise ValueError('Docker image labels do not match manifest')
        run('docker', 'run', '--rm', '--init', '--network', 'none', '--shm-size=1g',
            '--memory=4g', '--cpus=2', manifest['image'], 'python', '-m', 'backend.smoke_browser')
        try:
            if install(manifest):
                failed.unlink(missing_ok=True)
        except BaseException:
            atomic(failed, tag + '\n')
            raise


if __name__ == '__main__':
    main()
