# Setting up your word clock

*The card that goes in the box. Written for somebody who has never heard of a
Raspberry Pi and should not have to. If you set a hotspot password, add it
under step 2 — see [Building one as a gift](gifting.md).*

*A printable version, with pictures of the three states taken straight from
`provisioning.py`, is published as an Artifact:
<https://claude.ai/artifact/6Ynz7BZevBhJKWxzj11uWw>*

---

**1. Plug it in.**

After a few seconds the face shows **slow orange rings**. That means it is
working, and waiting for your Wi-Fi.

**2. Join the clock's own network.**

On your phone: **Settings → Wi-Fi**, and choose **`wordclock-setup`**.

**3. A setup page opens by itself**, the way a hotel Wi-Fi page does.

If it does not, open a browser and go to **http://wordclock-setup.local**

**4. Choose your home Wi-Fi** from the list and enter its password.

**5. Watch the clock.**

| | |
| --- | --- |
| Blue sweeping across | connecting |
| A green flash | it worked |
| The time | done |

Your phone goes back to your usual Wi-Fi on its own.

**6. Make it yours.**

Visit **http://wordclock.local:8080** from any phone or laptop on your Wi-Fi to
change colours and brightness, pick an animation for each hour, or have the
background follow your local weather.

---

## If something looks wrong

| What you see | What it means |
| --- | --- |
| Orange rings, still | It is waiting for step 2. Nothing is broken. |
| Blue sweep, then orange rings again | The Wi-Fi password was probably wrong. Try step 2 again. |
| Nothing at all | Check it is plugged in properly. |
| `wordclock.local` will not load | Make sure you are on the same Wi-Fi as the clock. |

**Changed your Wi-Fi, or moved house?** Leave the clock plugged in. After a few
minutes the orange rings come back on their own — then start again from step 2.
