# Building one as a gift

A clock you keep is configured over SSH. A clock you give away cannot be: the
person unboxing it has no terminal, no idea what a Pi is, and no reason to hand
you their Wi-Fi password. This sets the clock up to ask them for it itself.

The piece that does the work is [comitup](https://davesteele.github.io/comitup/),
a Debian package that broadcasts a Wi-Fi network when it cannot find a known
one, serves a page for choosing a network, then joins it and gets out of the
way. It keeps doing that for the life of the clock, so a router change years
later needs nothing from you.

## What they do

1. Plug the clock in. It cannot find a network, so it broadcasts its own and
   the face shows slow amber rings — it is waiting for someone.
2. Join `wordclock-setup` from a phone. A page opens by itself, the way a hotel
   Wi-Fi page does.
3. Pick their network from the list, type their password.
4. The face sweeps blue while it connects, flashes green when it works, then
   starts telling the time.
5. For time zone and weather, they visit `http://wordclock.local:8080` on any
   device on their network. **Detect** sets the time zone from their phone.

They never see a terminal, and they never give anyone their password.

## Before you start

Build and test the clock exactly as in
[installation_raspberry.md](installation_raspberry.md) first. Get the LEDs
working and the web interface reachable. Only then add provisioning —
otherwise a clock that does not light up has two possible causes instead of
one.

**Build it on your phone's hotspot rather than your home Wi-Fi.** Put the
hotspot's name and password into Raspberry Pi Imager in place of your own
network. It costs nothing during the build, and it buys the best test
available at the end: switching the hotspot off makes a known network vanish,
which is exactly what happens when somebody replaces their router, and you can
switch it back on to recover SSH if anything goes wrong. Deleting your home
network, the obvious alternative, is a one-way door.

## 1. Install comitup

```bash
sudo apt-get install comitup
```

**On Bookworm this needs a newer `python3-networkmanager` than Raspberry Pi OS
ships.** Comitup publishes one in its own apt repository; follow
[Installing Comitup](https://github.com/davesteele/comitup/wiki/Installing-Comitup)
for that step. Expect it to be the fiddliest part of the whole exercise.

Also make sure nothing in `/etc/network/interfaces` refers to a Wi-Fi
interface, so NetworkManager and comitup are the only things managing it.

## 2. Name the hotspot

In `/etc/comitup.conf`:

```
ap_name: wordclock-setup
```

### Whether to set a password

`ap_password` is optional and comitup leaves the hotspot open without it. It is
worth thinking about rather than reaching for by reflex, because the hotspot is
not up briefly: it stays up until somebody configures the clock, which might be
days if it sits unopened, and it returns indefinitely after a router change.

What an open hotspot exposes is small. Somebody in range could join it and use
the portal to point the clock at another network, or change its settings on port
8080. They cannot learn the owner's Wi-Fi password — the clock is not on that
network yet, and the portal never shows stored credentials — and there is
nothing on a clock worth taking.

What a password costs is not small. Lose the card and the clock cannot be set
up at all without the person who built it, which is the kind of dependency this
whole guide exists to avoid.

So: leave it open for a normal house, where the clock will be set up within a
day or two. Set one for a flat or a dense terrace, where strangers are
permanently in range and it may broadcast for a week:

```
ap_password: <8 to 63 characters>
```

If you do, tape a copy underneath the clock as well as printing it on the card,
so a lost card is an inconvenience rather than a phone call to you.

Keep `ap_name` **different** from the hostname you set below. Both are
advertised over mDNS, and if they collide avahi renames one to
`wordclock-2.local`, which is a confusing thing for a new owner to discover.

## 3. Show the setup state on the face

Without this the clock looks broken while it waits. With it, it looks like it
is asking for something.

```bash
sudo install -m 755 tools/comitup-callback /usr/local/bin/comitup-callback
```

and in `/etc/comitup.conf`:

```
external_callback: /usr/local/bin/comitup-callback
```

Then restart both:

```bash
sudo systemctl restart comitup.service word_clock.service
```

| state | the face shows |
| --- | --- |
| `HOTSPOT` | amber rings travelling outward — broadcasting, come and find it |
| `CONNECTING` | a blue bar sweeping across — working on it |
| `CONNECTED` | the whole face green, fading out over a couple of seconds |

The two waiting states differ in **motion** as well as colour, so they can be
told apart by someone who has never seen the clock and is not looking closely.

### Why it works this way

The callback cannot draw on the face itself. The word clock service owns the
LED strip, and a second process writing to it would fight for the bus. So the
callback writes one word to `/run/wordclock/network-state` and the clock reads
it on its next tick. `/run` is a tmpfs, so the file clears on every boot and
comitup writes it afresh — a stale state would be worse than none.

This also fixes something that would otherwise be wrong. A clock that has never
reached a network has never reached NTP either, so the time it would display is
simply incorrect. Showing the setup state instead is more honest than showing a
confident wrong time.

If the file is missing, none of this applies and the clock behaves exactly as
it always has. That is the normal case for a clock already on a network, including
yours — installing this changes nothing until comitup starts writing the file.

The setup patterns also ignore a saved brightness below 30%. A clock handed
over at 2% would otherwise appear dead at the one moment it most needs to look
alive.

## When their network changes

Nothing to build here — comitup already handles it. Its state machine falls
back to the hotspot whenever it cannot get onto a known network:

- **Network disappears while connected** (router replaced, moved house): the
  connection is lost, and it goes straight back to broadcasting.
- **Known network in range but the connection fails** (same name, new
  password): the attempt fails and it returns to the hotspot.
- **While broadcasting**, it rescans and retries every three minutes, or six
  after a failed attempt. If someone is connected to the hotspot it skips that
  retry, so it will not yank the network away mid-setup.

So the honest answer to "what if they change routers" is: they plug the clock
in, wait a couple of minutes, and the orange rings come back on their own. Then
they set it up again exactly as they did the first time.

Worth knowing for the same-name-new-password case: comitup deliberately does
**not** delete a saved connection when authentication fails. So the clock keeps
the old credentials and keeps periodically retrying them — but it returns to
the hotspot between attempts every time, so it stays reachable. Entering the
new password through the portal replaces them.

## 4. Hostname

```bash
sudo raspi-config    # System Options → Hostname → wordclock
```

This is what puts the clock at `http://wordclock.local:8080` once it has
joined their network.

## 5. Before you box it up

- **Delete `raspberry-pi/wordclock.json`.** It is gitignored, so a fresh clone
  has none, but if you copied your own card you will have shipped your zip code
  and time zone. The clock writes a fresh one on first save.
- **Forget the networks you joined while building** — see Testing it below.
  Otherwise the clock rejoins one at your house, never shows the hotspot, and
  you will not have tested the thing you are relying on.
- **Change the default password** on the `comitup` (or `pi`) user.

### Testing it

Two tests, and they prove different things.

**The fallback**, with the clock on your desk: switch your phone's hotspot off.
A known network has just disappeared, which is the router-change case, and
within a couple of minutes the face should go orange by itself. Switching the
hotspot back on gets you SSH again, so this one is safe to repeat.

**The cold boot**, which is the one that counts. Look at what the clock has
saved, and delete the ones you joined during the build — your hotspot, and any
network you tried along the way:

```bash
nmcli -f NAME,TYPE connection show
```

```bash
sudo nmcli connection delete "<your phone hotspot>"
```

Delete by name, one at a time. Leave comitup's own hotspot connection alone —
it is a wifi connection too, named after `ap_name`, and it is the thing that
serves the setup page.

Then reboot and run through it as they will — phone only, no terminal. Orange
rings, join `wordclock-setup`, pick a network, blue, green, the time.

Only this proves the part nothing else can: that the captive portal actually
opens by itself on a real phone. That behaviour varies by phone and by OS
version, it is the most fragile thing in the whole arrangement, and no amount
of testing over SSH will tell you about it.

Deleting your hotspot takes SSH with it, so do this last. If you need to get
back in afterwards, set the clock up through the portal onto your hotspot
again — which is itself a rehearsal of what your friend will do.

## The card for the box

[setup_card.md](setup_card.md) is the whole thing, written for somebody who has
never heard of a Raspberry Pi: six steps, what each colour on the face means,
and what to do when their Wi-Fi changes. Print it, or hand it over as a link.

Keep it as the one source of truth rather than rewriting the steps here — if
you change the hotspot name or set a password, that is the file to edit.

## If something goes wrong

| what they see | what it means |
| --- | --- |
| Nothing at all | Power. Check the supply before anything else. |
| Orange rings forever | It is waiting — the hotspot is up and nobody has joined it. Normal after a router change. |
| Blue sweep, then orange rings again | Wrong Wi-Fi password, most likely. The rings mean it is ready for another try. |
| Time shows but `wordclock.local` will not load | mDNS. Find the clock's IP in the router's device list and use that instead. |
| Hotspot never appears | Comitup is not running, or a known network is in range. `sudo systemctl status comitup`. |

The Pi Zero W has one radio and is **2.4GHz only**. It cannot keep the hotspot
up while joined to their network — that is why the hotspot disappears, and it is
not a fault. If their router is 5GHz-only the clock cannot see it at all, so it
is worth asking before you build.

The clock's own log explains what it found at startup:

```bash
journalctl -u word_clock.service -b | head -20
```

The line `Network setup display: watching` means it is reading the state file.
`not installed` means the directory does not exist, so the clock will never show
a setup state — check the callback is installed and `external_callback` is set.
