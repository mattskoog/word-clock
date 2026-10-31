# Changelog

Versions the clock reports in its **Updates** panel. The newest is first.

## 2.0.0 — Update checker + bug squashes

The first version the clock can name. Earlier builds report a commit hash
instead, and will keep doing so until they update once.

**The clock updates itself**

- An **Updates** panel showing the version running and, when there is one, the
  version on offer with a line describing what it brings.
- It checks twice a day on its own, and on a button. Checking is automatic;
  applying is always a press, because a clock in someone else's house cannot
  be rescued remotely if an update goes wrong.
- Applying records the running commit first. If the clock does not answer
  within ninety seconds of restarting, the previous version is restored and
  restarted.
- Updates that change `requirements.txt` or `install.sh` are flagged rather
  than applied, since reinstalling would overwrite an LED pin or web port
  chosen at install time.

**Setting up a clock without a terminal**

- The face shows its network state while being set up: amber rings while it is
  broadcasting, a blue sweep while connecting, green when it joins. Driven by
  comitup's callback, so a clock waiting to be configured no longer looks
  broken.
- The clock adopts the time zone of whatever device opens its web interface,
  which keeps a clock right for an owner who would never think to set it.

**Fixes**

- Backgrounds ship at 2% rather than 25%. On real LEDs the usable range is
  roughly 1-3%, so every clock has been shipping an order of magnitude too
  bright.
- The background brightness slider is shaped for that range: squared travel
  and a 10% ceiling, so 1-3% sits across the middle instead of in the first
  three notches.
- The web preview is gamma-corrected. LEDs are linear light and CSS colours
  are not, so a dim background that looked right on the wall was invisible in
  the browser.
- The hourly animation and network state changes are logged, so what the face
  did is answerable from the journal rather than by inference.
