#!/usr/bin/env python3
"""Close and reopen test apps on workspaces 2–5 for each installed Omarchy theme."""
import argparse
import collections
import datetime
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {2, 3, 4, 5}
SUPPORTED = {'io.github.lgse.Strata', 'blender', 'org.gnome.Nautilus', 'gimp', 'foot'}


def command(*args):
    result = subprocess.run(args, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def ctl(*args):
    result = command('hyprctl', *args)
    if result.lower().startswith(('error', 'err:', 'failed', "couldn't")):
        raise RuntimeError(result)
    return result


def clients():
    return json.loads(ctl('-j', 'clients'))


def focus(workspace):
    if workspace not in ALLOWED:
        raise RuntimeError('Test actions are restricted to workspaces 2–5')
    ctl('dispatch', 'hl.dsp.focus({workspace=' + json.dumps(str(workspace)) + '})')


def protected_signature(window):
    return window['address'], window['pid'], window['class'], window['workspace']['id']


def verify_protected(expected, current):
    actual = {window['address']: window for window in current}
    for before in expected:
        after = actual.get(before['address'])
        if after is None or protected_signature(after) != protected_signature(before):
            raise RuntimeError('A workspace 1 window changed; stopping the test')


def target_counts(windows, workspaces):
    return collections.Counter((w['workspace']['id'], w['class']) for w in windows
                               if w['workspace']['id'] in workspaces and w.get('mapped'))


def launch_command(spec, image):
    cls = spec['class']
    if cls == 'io.github.lgse.Strata': return [str(Path.home()/'.local/bin/strata')]
    if cls == 'blender': return ['blender']
    if cls == 'org.gnome.Nautilus': return ['nautilus', '--new-window', str(Path.home())]
    if cls == 'gimp': return ['gimp', '--new-instance', '--no-splash', str(image)]
    if cls == 'foot':
        argv = ['foot', '--working-directory=' + str(Path.home())]
        return argv + (['btop'] if spec['workspace'] == 5 else [])
    raise RuntimeError('No relaunch recipe for ' + cls)


def select_image(explicit):
    if explicit:
        path = explicit.expanduser().resolve()
    else:
        images = [p for p in (Path.home()/'Pictures').iterdir()
                  if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.avif', '.tif', '.tiff'}]
        if not images: raise RuntimeError('No image found in ~/Pictures')
        path = max(images, key=lambda p: p.stat().st_mtime).resolve()
    if not path.is_file(): raise RuntimeError('GIMP image does not exist: ' + str(path))
    return path


def recording_active():
    return subprocess.run(['pgrep', '-f', '^gpu-screen-recorder'], stdout=subprocess.DEVNULL).returncode == 0


def notification(headline, milliseconds=1800):
    milliseconds = min(2500, max(1, milliseconds))
    command('omarchy', 'notification', 'send', '-u', 'critical', '-t', str(milliseconds), headline)
    # Omarchy intentionally keeps critical notifications until dismissed,
    # regardless of their requested expiry. Dismiss this exact tour label via
    # its popup API; CloseNotification alone leaves Omarchy's popup visible.
    def dismiss():
        subprocess.run(['omarchy', 'shell', 'notifications', 'dismiss', headline], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    timer = threading.Timer(milliseconds/1000, dismiss)
    timer.start()


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--record', action='store_true', help='Use Omarchy fullscreen recording without audio')
    result.add_argument('--image', type=Path, help='Image to reopen in GIMP; default: newest supported image in ~/Pictures')
    result.add_argument('--themes', nargs='+', help='Theme names; default: every installed theme')
    result.add_argument('--workspaces', nargs='+', type=int, choices=sorted(ALLOWED), default=sorted(ALLOWED))
    result.add_argument('--dry-run', action='store_true', help='Show the plan without closing apps or changing themes')
    result.add_argument('--output', type=Path, help='Results directory; default: timestamped directory under build/app-tours')
    return result


def main():
    args = parser().parse_args()
    workspaces = set(args.workspaces)
    installed = command('omarchy', 'theme', 'list').splitlines()
    original_theme = command('omarchy', 'theme', 'current')
    themes = list(dict.fromkeys(args.themes or installed))
    if not themes or any(theme not in installed for theme in themes):
        raise RuntimeError('Choose installed themes exactly as listed by omarchy theme list')
    if original_theme in themes:
        themes = [theme for theme in themes if theme != original_theme] + [original_theme]
    baseline = clients()
    specs = sorted(({'workspace': w['workspace']['id'], 'class': w['class']} for w in baseline
                    if w['workspace']['id'] in workspaces and w.get('mapped') and not w.get('hidden')),
                   key=lambda s: (s['workspace'], s['class']))
    if not specs: raise RuntimeError('No test windows found on the selected workspaces')
    unknown = {spec['class'] for spec in specs} - SUPPORTED
    if unknown: raise RuntimeError('No relaunch recipe for: ' + ', '.join(sorted(unknown)))
    protected = [w for w in baseline if w['workspace']['id'] == 1]
    for window in baseline:
        if window['workspace']['id'] in workspaces and any(w['pid'] == window['pid'] for w in protected):
            raise RuntimeError('A test app shares a process with workspace 1; leaving it untouched')
    image = select_image(args.image)
    settings_path = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))/'hyprfuego/config.json'
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    original_duration = settings.get('duration')
    duration = float(command(str(ROOT/'hyprfuego'), 'duration').split()[1])
    durations = [duration, 1.0]
    print(f'Plan: {len(themes)} themes, {len(specs)} windows on workspaces {sorted(workspaces)}.', flush=True)
    print('Per theme: ' + ' then '.join(f'{seconds:g}s' for seconds in durations) + '.', flush=True)
    print('Unsaved changes will be discarded. Workspace 1 is excluded.', flush=True)
    print('GIMP image: ' + str(image), flush=True)
    for spec in specs: print(f"  Workspace {spec['workspace']}: {launch_command(spec, image)}", flush=True)
    if args.dry_run: return
    if args.record and recording_active(): raise RuntimeError('An existing recording is active; leaving it untouched')
    expected_counts = collections.Counter((s['workspace'], s['class']) for s in specs)
    original_monitor = next(m for m in json.loads(ctl('-j', 'monitors')) if m['focused'])
    original_window = json.loads(ctl('-j', 'activewindow'))
    dnd = command('omarchy', 'shell', 'notifications', 'dndState')
    output = (args.output or ROOT/'build/app-tours'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output/'before.json').write_text(json.dumps(baseline, indent=2)+'\n')
    (output/'plan.json').write_text(json.dumps({'themes': themes, 'windows': specs, 'image': str(image),
        'original_theme': original_theme, 'durations': durations, 'audio': False,
        'discard_unsaved': True}, indent=2)+'\n')
    events = []
    recording = None
    recording_started = False
    video_directory = Path.home()/'Videos'
    environment = dict(os.environ, OMARCHY_SCREENRECORD_DIR=str(video_directory), OMARCHY_SCREENRECORD_DEBUG='true')

    def event(**fields):
        events.append({'time': datetime.datetime.now().isoformat(), **fields})
        (output/'events.json').write_text(json.dumps(events, indent=2)+'\n')

    def log_command(*argv, log_name='apps.log', timeout=90):
        with (output/log_name).open('a') as stream:
            subprocess.run(argv, stdout=stream, stderr=stream, check=True, timeout=timeout, env=environment)

    def set_duration(seconds):
        nonlocal duration
        if duration != seconds:
            log_command(str(ROOT/'hyprfuego'), 'duration', str(seconds), log_name='duration.log')
            duration = seconds

    def ensure_open():
        for spec in specs:
            counts = target_counts(clients(), workspaces)
            key = (spec['workspace'], spec['class'])
            if counts[key] >= expected_counts[key]: continue
            focus(spec['workspace'])
            before = {w['address'] for w in clients()}
            # Let Hyprland own the process so it survives the test runner and
            # attach its workspace before a slow application maps its window.
            launch = ('cd ' + shlex.quote(str(Path.home())) + ' && '
                      + shlex.join(launch_command(spec, image)) + ' >>'
                      + shlex.quote(str(output/'apps.log')) + ' 2>&1')
            ctl('dispatch', 'hl.dsp.exec_cmd(' + json.dumps(launch)
                + ',{workspace=' + json.dumps(str(spec['workspace'])+' silent') + '})')
            deadline = time.monotonic()+60
            while time.monotonic() < deadline:
                current = clients()
                verify_protected(protected, current)
                new = [w for w in current if w['address'] not in before and w['class'] == spec['class']]
                if new:
                    for window in new:
                        if window['workspace']['id'] != spec['workspace']:
                            # Slow startups may outlive an empty workspace.
                            # Move only windows created by this relaunch.
                            ctl('dispatch', 'hl.dsp.window.move({window=' + json.dumps('address:'+window['address'])
                                + ',workspace=' + json.dumps(str(spec['workspace'])) + ',follow=false})')
                    if spec['class'] != 'gimp' or any(image.stem in w['title'] for w in new): break
                time.sleep(.2)
            else: raise RuntimeError('App did not reopen correctly: ' + spec['class'])
            # Dismiss Blender's startup splash, without editing its scene.
            if spec['class'] == 'blender':
                time.sleep(.8)
                ctl('dispatch', 'hl.dsp.send_shortcut({mods="",key="Escape",window=' + json.dumps('address:'+new[0]['address']) + '})')
            event(action='reopened', workspace=spec['workspace'], app=spec['class'])
        current = clients()
        verify_protected(protected, current)
        if target_counts(current, workspaces) != expected_counts:
            raise RuntimeError('Restored app counts differ from the starting scene')

    def close_window(window, phase='test'):
        current = clients()
        verify_protected(protected, current)
        match = next((w for w in current if w['address'] == window['address']), None)
        if not match: return
        if match['workspace']['id'] not in workspaces: raise RuntimeError('Close target left the test workspaces')
        focus(match['workspace']['id'])
        ctl('dispatch', 'hl.dsp.window.close({window=' + json.dumps('address:'+match['address']) + '})')
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            if not any(w['address'] == match['address'] for w in clients()): break
            time.sleep(.1)
        else:
            # The user explicitly authorized discarding unsaved changes. Never
            # signal a process with any window outside the test workspaces.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                current = clients()
                remaining = [w for w in current if w['pid'] == match['pid']]
                if not any(w['address'] == match['address'] for w in remaining): break
                if any(w['workspace']['id'] not in workspaces for w in remaining):
                    raise RuntimeError('Discard would affect another workspace; stopping')
                os.kill(match['pid'], sig)
                time.sleep(1)
            if any(w['address'] == match['address'] for w in clients()):
                raise RuntimeError('Test window did not close')
        event(action='closed', phase=phase, duration=duration,
              workspace=match['workspace']['id'], app=match['class'])
        time.sleep(duration+.35)

    def close_all(phase='test'):
        for workspace in sorted(workspaces):
            if not any(w['workspace']['id'] == workspace for w in clients()): continue
            focus(workspace)
            for window in sorted((w for w in clients() if w['workspace']['id'] == workspace), key=lambda w: w['at'][0]):
                close_window(window, phase)

    def start_recording():
        nonlocal recording, recording_started
        if not args.record or recording_started: return
        video_directory.mkdir(parents=True, exist_ok=True)
        log_command('omarchy', 'screenrecord', '--fullscreen', log_name='recorder.log', timeout=35)
        if not recording_active(): raise RuntimeError('Omarchy recorder did not start')
        recording = Path('/tmp/omarchy-screenrecord-filename').read_text().strip()
        recording_started = True
        (output/'recording.json').write_text(json.dumps({'path': recording, 'audio': False}, indent=2)+'\n')
        print('Recording fullscreen without audio: '+recording, flush=True)

    def interrupted(signum, frame): raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    started = False
    try:
        command('omarchy', 'shell', 'notifications', 'setDnd', 'on')
        focus(specs[0]['workspace'])
        print('Real close-and-reopen tour starts in 5 seconds.', flush=True)
        time.sleep(5)
        started = True
        # Clear the old scene before recording. Each theme is applied while
        # the test workspaces are empty, so even startup-only palettes refresh.
        close_all(phase='prepare')
        for index, theme in enumerate(themes, 1):
            print(f'[{index}/{len(themes)}] {theme}', flush=True)
            if command('omarchy', 'theme', 'current') != theme:
                log_command('omarchy', 'theme', 'set', theme, log_name='themes.log')
            if ctl('configerrors'): raise RuntimeError('Hyprland configuration errors; tour stopped')
            verify_protected(protected, clients())
            for pass_number, seconds in enumerate(durations, 1):
                set_duration(seconds)
                ensure_open()
                focus(specs[0]['workspace'])
                start_recording()
                notification(f'{theme} · {index}/{len(themes)}', 1800)
                print(f'  Pass {pass_number}/2: {seconds:g}s; all apps open.', flush=True)
                close_all()
                event(theme=theme, duration=seconds, pass_number=pass_number, action='pass completed')
            event(theme=theme, action='both duration passes completed')
            print(f'  Completed both speeds for {theme}.', flush=True)
        print('All themes completed.', flush=True)
    finally:
        try:
            try:
                if command('omarchy', 'theme', 'current') != original_theme:
                    log_command('omarchy', 'theme', 'set', original_theme, log_name='themes.log')
            finally:
                try:
                    if duration != durations[0]:
                        log_command(str(ROOT/'hyprfuego'), 'duration',
                                    'default' if original_duration is None else str(original_duration),
                                    log_name='duration.log')
                        duration = durations[0]
                finally:
                    if started:
                        ensure_open()
        finally:
            if recording_started and recording_active():
                marker = Path('/tmp/omarchy-screenrecord-filename')
                if marker.exists() and marker.read_text().strip() == recording:
                    log_command('omarchy', 'screenrecord', '--stop-recording', log_name='recorder.log', timeout=25)
            command('omarchy', 'shell', 'notifications', 'setDnd', dnd)
            ctl('dispatch', 'hl.dsp.focus({workspace=' + json.dumps(str(original_monitor['activeWorkspace']['id'])) + '})')
            if original_window.get('address'):
                ctl('dispatch', 'hl.dsp.focus({window=' + json.dumps('address:'+original_window['address']) + '})')
            after = clients()
            (output/'after.json').write_text(json.dumps(after, indent=2)+'\n')
            verify_protected(protected, after)
            print('Original theme and duration restored; workspace 1 untouched. Results: '+str(output), flush=True)
    if recording:
        streams = json.loads(command('ffprobe', '-v', 'error', '-show_streams', '-of', 'json', recording))['streams']
        if not streams or any(s['codec_type'] != 'video' for s in streams): raise RuntimeError('Expected video without audio')
        print('Verified fullscreen recording has no audio: '+recording, flush=True)


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt:
        print('Hyprfuego tour stopped.', file=sys.stderr)
        sys.exit(130)
    except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as error:
        print('Hyprfuego tour: '+str(error), file=sys.stderr)
        sys.exit(1)
