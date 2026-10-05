#!/usr/bin/env python3
"""
updater.py -- keeps this Pi's copy of Equalize up to date, from its releases
on GitHub.

    python3 updater.py check            is there a newer release? (writes config/update.json)
    python3 updater.py check --auto     the same, and install it if automatic updates are on
    python3 updater.py apply [vX.Y.Z]   install the newest release (or that one)

A release is a numbered tag on GitHub (v1.4.0): a fixed version that has
been tested, never "whatever the code is today". The Pi asks GitHub which
tags exist (the repository is public, so no password is needed), and
updating moves this copy forward to that exact tag.

It is careful:
- If any of the program's own files have been changed on this Pi, it stops
  and says which: it never overwrites an edit. Settings, photos, the Spotify
  login and the panel's own settings are not program files and are never
  touched.
- After updating it restarts the program and checks it stays running. If
  it doesn't, it goes back to the version before, and says so.

Runs as root (it restarts services), by equalize-update.timer every night
and by the control panel's "Update now" button. Standard library only.
"""

import fcntl
import json
import os
import pwd
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---- what differs between Equalize and Spotipi Photo ---------------------
NAME = "Equalize"
REPO_URL = "https://github.com/captaincomplex/equalize.git"
STATUS_PATH = os.path.join(ROOT, "config", "update.json")
STATE_PATH = os.path.join(ROOT, "config", "state.json")
LOCK_PATH = "/run/equalize-update.lock"
# Services that must still be running after an update, if they were before.
# The display ones only need to not have crashed: the panel can be handed to
# the other program while the update runs, which stops them on purpose.
SERVICES = ["equalize-web", "equalize-door", "equalize", "equalize-spotify-watch"]
DISPLAYS = ["equalize"]


def after_update():
    """Bring the running system in line with the new code. Equalize's
    installer does that (services, AirPlay settings, the panel switch), in
    its question-free mode, keeping every earlier answer."""
    return subprocess.run(["bash", os.path.join(ROOT, "install_pi.sh"), "--update"],
                          cwd=ROOT).returncode == 0
# ---------------------------------------------------------------------------

TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
HEALTHY_FOR_S = 10                 # each service up, without restarting, this long ...
HEALTH_WAIT_S = 90                 # ... within this long, or the update is undone


def say(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- git
def _owner():
    return pwd.getpwuid(os.stat(ROOT).st_uid).pw_name


def git(*args, check=True, raw=False):
    """git in this folder, as the person who owns it, so the files it writes
    stay theirs (and git's 'dubious ownership' check is satisfied)."""
    cmd = ["git", "-C", ROOT] + list(args)
    if os.geteuid() == 0 and _owner() != "root":
        cmd = ["runuser", "-u", _owner(), "--"] + cmd
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError("git %s: %s" % (args[0], (r.stderr or r.stdout).strip()[:300]))
    return r.stdout if raw else r.stdout.strip()


def releases():
    """{(1, 4, 0): ("v1.4.0", commit)} for every release on GitHub."""
    out = git("ls-remote", "--tags", "--refs", REPO_URL)
    found = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        tag = ref.rsplit("/", 1)[-1]
        m = TAG.match(tag)
        if m:
            found[tuple(int(x) for x in m.groups())] = (tag, sha)
    return found


def version_name():
    """This copy's version: its release tag, or how far past one it is."""
    try:
        return git("describe", "--tags", "--match", "v[0-9]*")
    except RuntimeError:
        return git("rev-parse", "--short", "HEAD")


def local_changes():
    """Program files changed on this Pi (git's own list), [] if none."""
    out = git("status", "--porcelain", "--untracked-files=no", raw=True)
    return [line[3:] for line in out.splitlines() if line.strip()]


def is_ancestor(a, b):
    return subprocess.run((["runuser", "-u", _owner(), "--"] if os.geteuid() == 0 and _owner() != "root" else [])
                          + ["git", "-C", ROOT, "merge-base", "--is-ancestor", a, b]).returncode == 0


# ---------------------------------------------------------------- status
def read_status():
    try:
        with open(STATUS_PATH) as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def write_status(**changes):
    st = read_status()
    st.update(changes)
    tmp = STATUS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, STATUS_PATH)
    return st


def auto_updates_on():
    try:
        with open(STATE_PATH) as f:
            return bool((json.load(f) or {}).get("auto_update", True))
    except (OSError, ValueError):
        return True


# ---------------------------------------------------------------- check
def check():
    """Ask GitHub for the newest release. Returns the status written."""
    now = int(time.time())
    try:
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            return write_status(checked=now, available=None,
                                error="This copy wasn't installed with git, so it can't update itself. "
                                      "Reinstall it with git clone (see the README).")
        rel = releases()
        current = version_name()
        if not rel:
            return write_status(checked=now, current=current, latest=None, available=None, error=None)
        tag, sha = rel[max(rel)]
        head = git("rev-parse", "HEAD")
        newer = sha != head
        if newer:
            git("fetch", "--quiet", REPO_URL, "refs/tags/%s:refs/tags/%s" % (tag, tag))
            newer = not is_ancestor(sha, head)          # already past it: nothing to do
        return write_status(checked=now, current=current, latest=tag,
                            available=tag if newer else None, error=None)
    except Exception as e:                               # no network, GitHub down...
        return write_status(checked=now, error="Couldn't check for updates: %s" % e)


# ---------------------------------------------------------------- apply
def _services_running():
    return [s for s in SERVICES if _active(s)]


def _active(unit):
    return subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0


def _ok(unit):
    if unit in DISPLAYS:                         # handed over is fine; crashed is not
        return subprocess.run(["systemctl", "is-failed", "--quiet", unit]).returncode != 0
    return _active(unit)


def _restarts(unit):
    out = subprocess.run(["systemctl", "show", "-p", "NRestarts", "--value", unit],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else 0


def healthy(units, wait_s=HEALTH_WAIT_S, steady_s=HEALTHY_FOR_S):
    """True once every unit has been running, without restarting, for
    steady_s seconds; False if that hasn't happened within wait_s."""
    if not units:
        return True
    start = time.time()
    since, counts = None, None
    while time.time() - start < wait_s:
        now_counts = {u: _restarts(u) for u in units}
        if all(_ok(u) for u in units) and (counts is None or now_counts == counts):
            since = since or time.time()
            if time.time() - since >= steady_s:
                return True
        else:
            since = None
        counts = now_counts
        time.sleep(2)
    return False


def apply(tag=None):
    """Install a release; undo it if the program doesn't come back."""
    st = check()
    tag = tag or st.get("available")
    if not tag:
        say("Nothing to install: %s" % (st.get("error") or "already up to date (%s)" % st.get("current")))
        return True
    changed = local_changes()
    if changed:
        write_status(error="Not updated: these files have been changed on this Pi, and an update "
                           "would overwrite them: %s" % ", ".join(changed[:6]))
        say(read_status()["error"])
        return False
    git("fetch", "--quiet", REPO_URL, "refs/tags/%s:refs/tags/%s" % (tag, tag))
    before = git("rev-parse", "HEAD")
    before_name = version_name()
    if not is_ancestor(before, tag):
        write_status(error="Not updated: this copy has its own history that %s doesn't include." % tag)
        say(read_status()["error"])
        return False
    must_run = _services_running()                       # these must be running again after
    say("%s: updating %s -> %s" % (NAME, before_name, tag))
    write_status(updating=tag, error=None)
    git("merge", "--ff-only", "--quiet", tag)
    if after_update() and healthy(must_run):
        write_status(updating=None, current=version_name(), available=None,
                     last="Updated to %s on %s." % (tag, time.strftime("%d %b %Y at %H:%M")))
        say("%s: now on %s" % (NAME, tag))
        return True
    # it didn't come back: go back to what was running before
    say("%s: %s didn't start properly -- going back to %s" % (NAME, tag, before_name))
    git("reset", "--hard", "--quiet", before)             # program files only; nothing was edited
    after_update()
    healthy(must_run)
    write_status(updating=None, current=version_name(), available=tag,
                 error="%s didn't start properly, so this Pi went back to %s. Nothing else changed."
                       % (tag, before_name))
    return False


def main(argv):
    if not argv or argv[0] not in ("check", "apply"):
        print(__doc__)
        return 2
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)                  # one update at a time
        if argv[0] == "check":
            st = check()
            say("%s %s; newest release %s%s" % (NAME, st.get("current"), st.get("latest"),
                                                 "; " + st["error"] if st.get("error") else ""))
            if "--auto" in argv and st.get("available") and auto_updates_on():
                return 0 if apply(st["available"]) else 1
            return 0
        return 0 if apply(argv[1] if len(argv) > 1 else None) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
