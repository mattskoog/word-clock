"""Updating the clock from its own web interface.

A clock given away is a clock you cannot reach. Its owner has no terminal and
no reason to want one, so "pull and restart over SSH" is not an update
mechanism for them - it is an update mechanism for you, performed at their
house.

So the clock checks for itself, twice a day, and says so in the interface. It
never applies anything on its own: a commit that breaks the render loop at
three in the morning would leave a dark clock in somebody else's home, and
nothing here could fix that remotely. Applying is always a press.

Two things make the apply survivable:

- The commit in use is recorded first, and if the service does not answer
  afterwards the working tree is reset back to it and restarted. A bad update
  costs a couple of minutes, not a house call.
- Git runs as the user that owns the checkout, never as root. The service runs
  as root, and root touching a user-owned repository both trips git's
  ownership check and leaves root-owned objects behind that break the owner's
  next pull.
"""

import os
import shutil
import subprocess
import tempfile
import threading
import time

# Twice a day. Updates arrive a few times a month at most, so checking harder
# would be noise, and checking less would mean sitting on a fix for days.
CHECK_SECONDS = 12 * 60 * 60
RETRY_SECONDS = 30 * 60
GIT_TIMEOUT = 120

PACKAGE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPOSITORY = os.path.abspath(
    os.path.join(PACKAGE_DIRECTORY, "..", "..", "..")
)
DEFAULT_HELPER = os.path.abspath(
    os.path.join(PACKAGE_DIRECTORY, "..", "..", "tools", "self-update.sh")
)

# Files whose change needs more than a restart. Surfaced to the user rather
# than acted on: reinstalling the service would overwrite a pin or a port the
# owner chose at install time.
NEEDS_ATTENTION = {
    "raspberry-pi/requirements.txt": "new Python packages",
    "raspberry-pi/install.sh": "a change to the service definition",
}


class UpdateError(Exception):
    """Something went wrong in a way worth showing the user."""


def _current_user():
    try:
        import pwd
        return pwd.getpwuid(os.geteuid()).pw_name
    except (KeyError, ImportError):
        return ""


def repository_owner(path):
    """The user that owns the checkout, so git can run as them."""
    try:
        import pwd
        return pwd.getpwuid(os.stat(path).st_uid).pw_name
    except (KeyError, OSError, ImportError):
        return ""


def _run(command):
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=GIT_TIMEOUT)
    if result.returncode != 0:
        raise UpdateError((result.stderr or result.stdout or "").strip()
                          or f"{command[0]} failed")
    return result.stdout.strip()


def git_command(repository, arguments):
    """The git invocation to use, dropping to the checkout's owner if needed."""
    command = ["git", "-C", repository, *arguments]
    owner = repository_owner(repository)
    # Running as the owner is what avoids git's "dubious ownership" refusal;
    # -c safe.directory would silence it but still leave root-owned objects.
    if owner and owner != _current_user():
        return ["sudo", "-n", "-u", owner, *command]
    return command


def _git(repository, *arguments, runner=None):
    return (runner or _run)(git_command(repository, list(arguments)))


def describe(repository, ref, runner=None):
    """A commit as the interface shows it: short id, date, subject."""
    out = _git(repository, "show", "-s", "--format=%h%x1f%cI%x1f%s", ref,
               runner=runner)
    parts = (out.split("\x1f") + ["", "", ""])[:3]
    return {"short": parts[0], "date": parts[1], "subject": parts[2]}


def branch_of(repository, runner=None):
    name = _git(repository, "rev-parse", "--abbrev-ref", "HEAD", runner=runner)
    # A detached head has no upstream to compare against.
    return "" if name == "HEAD" else name


def check(repository, fetch=True, runner=None):
    """What is running, what is available, and what applying would involve."""
    branch = branch_of(repository, runner=runner)
    if not branch:
        raise UpdateError("This clock is not on a branch, so it cannot update "
                          "itself.")
    if fetch:
        _git(repository, "fetch", "--quiet", "origin", branch, runner=runner)

    upstream = f"origin/{branch}"
    behind = int(_git(repository, "rev-list", "--count", f"HEAD..{upstream}",
                      runner=runner) or 0)
    ahead = int(_git(repository, "rev-list", "--count", f"{upstream}..HEAD",
                     runner=runner) or 0)

    notes = []
    if behind:
        changed = _git(repository, "diff", "--name-only", f"HEAD..{upstream}",
                       runner=runner).splitlines()
        notes = [reason for path, reason in NEEDS_ATTENTION.items()
                 if path in changed]
    return {
        "branch": branch,
        "running": describe(repository, "HEAD", runner=runner),
        "available": describe(repository, upstream, runner=runner),
        "behind": behind,
        # Local commits mean somebody edited this clock. A fast-forward would
        # fail, and throwing their work away silently would be worse.
        "diverged": ahead > 0,
        "notes": notes,
        "checked_at": time.time(),
        "error": "",
    }


def apply(repository, service, port, helper=DEFAULT_HELPER, status=None):
    """Start the update, detached, and return immediately.

    The restart kills this very process, so the work cannot happen inline -
    the HTTP response would never be sent. The helper is copied out of the
    checkout first, because the checkout is about to change underneath it and
    /bin/sh reads a script as it goes.
    """
    status = status or check(repository)
    if status.get("diverged"):
        raise UpdateError("This clock has changes of its own, so it will not "
                          "update itself.")
    if not status.get("behind"):
        raise UpdateError("Already up to date.")
    if not os.path.isfile(helper):
        raise UpdateError("The update helper is missing.")

    staged = os.path.join(tempfile.mkdtemp(prefix="wordclock-update-"),
                          "self-update.sh")
    shutil.copy2(helper, staged)
    os.chmod(staged, 0o755)
    subprocess.Popen(
        ["/bin/sh", staged, repository, repository_owner(repository),
         service, str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return status


class UpdateWatch:
    """Checks on its own twice a day, and on request. Never applies by itself."""

    EMPTY = {"branch": "", "running": {}, "available": {}, "behind": 0,
             "diverged": False, "notes": [], "checked_at": None, "error": ""}

    def __init__(self, repository=DEFAULT_REPOSITORY,
                 service="word_clock.service", port=8080,
                 interval=CHECK_SECONDS, helper=DEFAULT_HELPER):
        self.repository = repository
        self.service = service
        self.port = port
        self.helper = helper
        self._interval = interval
        self._lock = threading.Lock()
        self._status = dict(self.EMPTY)
        self._wake = threading.Event()
        self._thread = None

    def status(self):
        with self._lock:
            return dict(self._status)

    def check_now(self):
        """Check synchronously, for the interface's own button."""
        try:
            found = check(self.repository)
        except (UpdateError, OSError, ValueError) as error:
            with self._lock:
                self._status = dict(self._status, error=str(error),
                                    checked_at=time.time())
            return self.status()
        with self._lock:
            self._status = found
        return dict(found)

    def apply_now(self):
        return apply(self.repository, self.service, self.port,
                     helper=self.helper, status=self.check_now())

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="updates",
                                        daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            healthy = not self.check_now().get("error")
            self._wake.wait(self._interval if healthy else RETRY_SECONDS)
            self._wake.clear()
