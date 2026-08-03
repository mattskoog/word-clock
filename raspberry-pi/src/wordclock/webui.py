"""Local web interface for controlling the clock.

Runs a small stdlib HTTP server on a daemon thread. It never touches the LEDs
itself: requests only write to the shared Settings object, and the render loop
picks the changes up on its next tick.

Controls edit a local draft in the browser and are shown in a preview of the
clock face; nothing reaches the clock until Save is pressed.

There is no authentication, so keep this on a trusted network.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gif
import themes
import timekeeper
from clock_display_hal import ClockDisplayHAL

MAX_BODY_BYTES = 64 * 1024

# LEDs are emissive, a phone screen is not, so a linear brightness scale would
# make the preview unreadable long before the clock itself got dim.
PREVIEW_FLOOR = 0.4

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Word Clock</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  /* The page is exactly one window tall at every size: the controls column is
     the only thing that scrolls, and the save bar always rests on the bottom
     edge without floating over the content. */
  html, body { height: 100%; }
  body {
    margin: 0; padding: 20px 16px 0;
    display: flex; flex-direction: column; overflow: hidden;
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #11131a; color: #e8eaf0;
  }
  main {
    max-width: 960px; width: 100%; margin: 0 auto;
    flex: 1; min-height: 0; display: flex; flex-direction: column;
  }
  h1 { font-size: 20px; margin: 0 0 12px; }
  .layout {
    display: grid; grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr);
    gap: 0 24px; flex: 1; min-height: 0;
  }
  .preview-column { min-height: 0; }
  .controls-column { overflow-y: auto; min-height: 0; padding-bottom: 8px; }
  .controls-column section:last-child { margin-bottom: 0; }
  .clock { color: #8f97ad; font-size: 14px; margin: 12px 0 20px; text-align: center; }
  /* Set like the face itself, so the words read as the clock's own wording. */
  .phrase {
    color: #e8eaf0; margin-top: 5px; font-size: 14px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .12em;
  }
  section {
    background: #1a1d27; border: 1px solid #262a38; border-radius: 12px;
    padding: 16px; margin-bottom: 14px;
  }
  h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em;
       color: #8f97ad; margin: 0 0 12px; font-weight: 600; }
  label { display: block; font-size: 14px; color: #b9c0d0; margin-bottom: 6px; }
  .row { display: flex; gap: 10px; align-items: center; }
  .row + .row { margin-top: 14px; }
  input[type=range] { width: 100%; accent-color: #6c8cff; }
  input[type=color] { width: 46px; height: 34px; padding: 0; border: 1px solid #333a4d;
                      border-radius: 8px; background: #11131a; }
  input[type=text], select {
    width: 100%; min-width: 0; padding: 9px 10px; border-radius: 8px;
    border: 1px solid #333a4d; background: #11131a; color: #e8eaf0; font-size: 15px;
  }
  /* The native dropdown arrow sits hard against the edge and cannot be moved,
     so it is replaced with one we can position. */
  select {
    -webkit-appearance: none; -moz-appearance: none; appearance: none;
    padding-right: 36px;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%238f97ad' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 14px center;
  }
  select::-ms-expand { display: none; }
  .row > select { flex: 1; }
  .row > button { flex: none; }
  /* Keeps a control level with the field beside it rather than with the label
     stacked above it. */
  .inline { display: flex; align-items: stretch; gap: 8px; }
  .inline > select { flex: 1; }
  .inline > button { flex: none; }
  button {
    padding: 9px 14px; border-radius: 8px; border: 1px solid #333a4d;
    background: #232839; color: #e8eaf0; font-size: 14px; cursor: pointer;
  }
  button:hover:not(:disabled) { background: #2b3145; }
  button:disabled { opacity: .45; cursor: default; }
  button.primary { background: #3d5afe; border-color: #3d5afe; }
  button.primary:hover:not(:disabled) { background: #4f69ff; }
  .themes { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .themes + .row { margin-top: 16px; }
  .themes button.active { border-color: #6c8cff; background: #29314d; }
  .toggle { display: flex; justify-content: space-between; align-items: center; }
  /* A read-only indicator, deliberately not styled as a button: the display
     cannot be switched off from here. */
  .status {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 4px 11px; border-radius: 999px; font-size: 13px; font-weight: 500;
    color: #7ee0a2; background: rgba(126, 224, 162, .12);
  }
  .status::before {
    content: ''; width: 7px; height: 7px; border-radius: 50%; background: currentColor;
  }
  .status.off { color: #8f97ad; background: rgba(143, 151, 173, .14); }
  .switch { position: relative; display: inline-block; width: 46px; height: 26px; flex: none; }
  .switch input { position: absolute; opacity: 0; width: 100%; height: 100%; margin: 0; cursor: pointer; }
  .switch span {
    position: absolute; inset: 0; border-radius: 999px;
    background: #333a4d; transition: background .15s; pointer-events: none;
  }
  .switch span::before {
    content: ''; position: absolute; width: 20px; height: 20px; left: 3px; top: 3px;
    background: #e8eaf0; border-radius: 50%; transition: transform .15s;
  }
  .switch input:checked + span { background: #3d5afe; }
  .switch input:checked + span::before { transform: translateX(20px); }
  .switch input:focus-visible + span { outline: 2px solid #6c8cff; outline-offset: 2px; }
  .value { color: #8f97ad; font-variant-numeric: tabular-nums; min-width: 46px;
           text-align: right; font-size: 14px; }
  .hint { font-size: 12px; color: #767e94; margin-top: 8px; overflow-wrap: anywhere; }
  button.play { padding: 7px 11px; line-height: 1; font-size: 12px; }
  .hour-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
  .hour-row .hour {
    width: 52px; flex: none; font-size: 13px; color: #b9c0d0;
    font-variant-numeric: tabular-nums;
  }
  .hour-row select {
    flex: 1; padding: 6px 32px 6px 8px; font-size: 14px;
    background-position: right 12px center;
  }
  .hour-row .play { align-self: stretch; }
  .error { color: #ff8a8a; font-size: 13px; margin-top: 8px; overflow-wrap: anywhere; }
  .hidden { display: none; }

  /* Preview of the clock face */
  .face {
    /* minmax(0, 1fr) rather than 1fr: tracks default to a min-content floor,
       which the letters' line boxes would push past the aspect ratio. */
    display: grid; grid-template-columns: repeat(12, minmax(0, 1fr));
    grid-template-rows: repeat(11, minmax(0, 1fr));
    aspect-ratio: 12 / 11; gap: 1px; padding: 14px 10px;
    /* Width drives the face and aspect-ratio derives the height, so capping the
       width keeps the 12:11 proportions exact while the page stays one window
       tall. The 40vh cap stops the face crowding out the controls on short
       screens; the subtraction covers the heading, clock line and save bar. */
    max-width: min(520px, calc((100vh - 300px) * 12 / 11), calc(40vh * 12 / 11));
    margin: 0 auto;
    background: #08090c; border: 1px solid #2b2f3d; border-radius: 14px;
  }
  /* Without aspect-ratio the grid would collapse, so give the rows a floor. */
  @supports not (aspect-ratio: 12 / 11) {
    .face { grid-template-rows: repeat(11, minmax(1.7em, 1fr)); }
  }
  .face span {
    display: flex; align-items: center; justify-content: center;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: clamp(9px, 2.9vw, 16px); font-weight: 600; line-height: 1;
    color: #33384a; transition: color .12s linear; overflow: hidden;
  }
  /* The glow stands in for the light bleeding around a lit letter on the real
     clock, which is what makes an animation's shape readable there. */
  .face span.lit { text-shadow: 0 0 7px currentColor; }

  /* Save bar */
  .savebar {
    flex: none; margin: 0 -16px;
    background: #14161f; border-top: 1px solid #262a38;
    padding: 12px 16px;
  }
  .savebar > div {
    max-width: 960px; margin: 0 auto;
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
  }
  #save-status { font-size: 13px; color: #767e94; }
  .savebar.dirty #save-status { color: #ffc46b; }
  .savebar.saved #save-status { color: #7ee0a2; }

  /* Two columns only once both can be comfortably wide; below this the preview
     stacks above the controls. Splitting earlier squeezes the clock face.
     At this size the page becomes exactly one window tall: nothing scrolls
     except the controls column, and the save bar rests on the bottom edge. */
  @media (min-width: 900px) {
    body { padding: 24px 24px 0; }
    .layout {
      grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
      grid-template-rows: minmax(0, 1fr);
    }
    .controls-column { padding-right: 4px; }
    .themes { grid-template-columns: repeat(3, 1fr); }
    .savebar { margin: 0 -24px; }
  }
</style>
</head>
<body>
<main>
  <h1>Word Clock</h1>

  <div class="layout">
  <div class="preview-column">
  <div class="face" id="face"><!--FACE--></div>
  <div class="error" id="preview-error"></div>
  <div class="clock">
    <div id="time">--:--</div>
    <div class="phrase" id="phrase"></div>
  </div>
  </div>

  <div class="controls-column">
  <section>
    <div class="toggle">
      <h2 style="margin:0">Display</h2>
      <span id="power" class="status">On</span>
    </div>
    <div class="row" style="margin-top:14px">
      <div style="flex:1">
        <label for="brightness">Brightness</label>
        <input type="range" id="brightness" min="0" max="1" step="0.01">
      </div>
      <div class="value" id="brightness-value"></div>
    </div>
  </section>

  <section>
    <h2>Theme</h2>
    <div class="themes" id="themes"></div>
    <div class="row" id="color-row">
      <div style="flex:1"><label for="color" id="color-label">Color</label></div>
      <input type="color" id="color" title="Color at the top of the clock">
      <input type="color" id="secondary-color" title="Color at the bottom of the clock">
    </div>
    <div class="row">
      <div style="flex:1"><label for="sparkle" style="margin:0">Sparkle</label></div>
      <label class="switch">
        <input type="checkbox" id="sparkle"><span></span>
      </label>
    </div>
    <div class="row" id="speed-row">
      <div style="flex:1">
        <label for="speed">Animation speed</label>
        <input type="range" id="speed" min="0" max="0.5" step="0.005">
      </div>
      <div class="value" id="speed-value"></div>
    </div>
  </section>

  <section>
    <div class="toggle">
      <h2 style="margin:0">Cuckoo clock</h2>
      <label class="switch">
        <input type="checkbox" id="gifs-enabled" aria-label="Play an animation on the hour"><span></span>
      </label>
    </div>
    <div class="row" style="margin-top:14px">
      <div style="flex:1">
        <label for="gif-mode">On the hour, play</label>
        <select id="gif-mode">
          <option value="random">A random animation</option>
          <option value="fixed">A single animation</option>
          <option value="hourly">A different animation each hour</option>
        </select>
      </div>
    </div>
    <div class="row" id="gif-name-row">
      <div style="flex:1">
        <label for="gif-name">Animation</label>
        <div class="inline">
          <select id="gif-name"></select>
          <button id="preview-fixed" class="play" title="Play in the preview">&#9654;</button>
        </div>
      </div>
    </div>
    <div id="hour-rows"></div>
    <div class="row">
      <div style="flex:1">
        <label for="gif-duration">Play for</label>
        <input type="range" id="gif-duration" min="1" max="60" step="1">
      </div>
      <div class="value" id="gif-duration-value"></div>
    </div>
    <div class="row"><button id="play-gif">Play animation in the preview</button></div>
    <div class="hint" id="gif-status"></div>
    <div class="hint" id="gif-hint"></div>
  </section>

  <section>
    <h2>Time zone</h2>
    <div class="row">
      <select id="timezone"></select>
      <button id="detect-timezone">Detect</button>
    </div>
    <div class="hint">Picking a zone by name keeps daylight saving correct.
      <b>Detect</b> uses the time zone of the device you are reading this on.</div>
    <div class="error" id="timezone-status"></div>
  </section>
  </div>
  </div>
</main>

<div class="savebar" id="savebar">
  <div>
    <span id="save-status">No changes</span>
    <span>
      <button id="revert">Revert</button>
      <button id="save" class="primary">Save to clock</button>
    </span>
  </div>
</div>

<script>
var state = null;    // last known server state
var draft = null;    // local edits, not yet sent to the clock
var dirty = false;
var cells = null;
var previewTimer = null;
var savedTimer = null;

function el(id) { return document.getElementById(id); }
function copy(value) { return JSON.parse(JSON.stringify(value)); }

function api(path, body) {
  var options = { method: body ? 'POST' : 'GET' };
  if (body) {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(body);
  }
  return fetch(path, options).then(function (response) { return response.json(); });
}

// The clock sends colors as [r, g, b] but the picker hands back "#rrggbb", and
// a draft can hold either until it has been saved.
function toHex(color) {
  if (typeof color === 'string') return color;
  return '#' + color.map(function (channel) {
    return ('0' + Number(channel).toString(16)).slice(-2);
  }).join('');
}

/* ---------- preview ---------- */

// The letters are rendered into the page by the server, so the face is readable
// before any request completes and stays readable if one fails.
function collectCells() {
  var spans = el('face').getElementsByTagName('span');
  cells = [];
  for (var y = 0; y < spans.length / 12; y++) {
    var line = [];
    for (var x = 0; x < 12; x++) line.push(spans[y * 12 + x]);
    cells.push(line);
  }
}

function paintGrid(colors) {
  if (!cells) collectCells();
  colors.forEach(function (row, y) {
    if (!cells[y]) return;
    row.forEach(function (color, x) {
      var cell = cells[y][x];
      if (!cell) return;
      // Every pixel is shown through its letter, the way the real clock's
      // light only escapes through the letter cutouts.
      var on = color && color !== '#000000';
      cell.style.color = on ? color : '';
      cell.className = on ? 'lit' : '';
    });
  });
}

function paint(data) {
  paintGrid(data.colors);
  el('time').textContent = data.clock.time;
  el('phrase').textContent = data.clock.phrase;
}

var animationTimer = null;

// Plays an animation's frames over the preview face, then hands the face back
// to the clock. Only one can run at a time.
function playAnimationPreview(name) {
  if (!name) return;
  stopAnimationPreview();
  el('preview-error').textContent = '';
  api('/api/gif/frames', { name: name }).then(function (data) {
    if (!data.frames || !data.frames.length) {
      el('preview-error').textContent = 'Could not read "' + name + '".';
      return;
    }
    var index = 0;
    var deadline = Date.now() + Math.max(1000, (draft.gif_duration || 6) * 1000);
    (function step() {
      if (Date.now() > deadline) {
        animationTimer = null;
        refreshPreview();
        return;
      }
      var frame = data.frames[index % data.frames.length];
      paintGrid(frame.colors);
      index++;
      animationTimer = setTimeout(step, frame.delay || 100);
    })();
  }).catch(function () {
    el('preview-error').textContent = 'Could not reach the clock.';
  });
}

function stopAnimationPreview() {
  if (animationTimer) {
    clearTimeout(animationTimer);
    animationTimer = null;
  }
}

function refreshPreview() {
  if (!draft) return Promise.resolve();
  // An animation preview owns the face while it runs.
  if (animationTimer) return Promise.resolve();
  return api('/api/preview', draft).then(function (data) {
    if (!data || !data.colors) throw new Error('bad preview response');
    paint(data);
    el('preview-error').textContent = '';
  }).catch(function () {
    // Silence here is what makes a broken preview look like a hung page.
    el('preview-error').textContent =
      'Preview unavailable - could not reach the clock. The controls below still work.';
  });
}

function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(refreshPreview, 100);
}

function themeIsAnimated(name) {
  return !!(state && state.themes.some(function (theme) {
    return theme.name === name && theme.animated;
  }));
}

// Sparkle shimmers on top of any theme, so it makes the display animated too.
function isAnimated() {
  return !!draft && (themeIsAnimated(draft.theme) || !!draft.sparkle);
}

/* ---------- draft ---------- */

function markDirty() {
  dirty = true;
  el('savebar').className = 'savebar dirty';
  el('save-status').textContent = 'Unsaved changes';
  el('save').disabled = false;
  el('revert').disabled = false;
}

function changed() {
  markDirty();
  render();
  schedulePreview();
}

function setClean(message) {
  dirty = false;
  el('savebar').className = message ? 'savebar saved' : 'savebar';
  el('save-status').textContent = message || 'No changes';
  el('save').disabled = true;
  el('revert').disabled = true;
  if (message) {
    clearTimeout(savedTimer);
    savedTimer = setTimeout(function () {
      if (!dirty) setClean('');
    }, 2500);
  }
}

/* ---------- controls ---------- */

var themeButtons = null;

function renderThemes() {
  var container = el('themes');
  if (!themeButtons) {
    // Built once: rebuilding on every refresh would swallow clicks mid-press.
    themeButtons = {};
    state.themes.forEach(function (theme) {
      var button = document.createElement('button');
      button.textContent = theme.label;
      button.onclick = function () { draft.theme = theme.name; changed(); };
      container.appendChild(button);
      themeButtons[theme.name] = button;
    });
  }
  Object.keys(themeButtons).forEach(function (name) {
    themeButtons[name].className = name === draft.theme ? 'active' : '';
  });
}

var renderedGifs = null;

function renderGifs() {
  var select = el('gif-name');
  var signature = state.gifs.join('\\u0000');
  // Only rebuild when the files on disk changed, and never while the picker is
  // open, so a refresh cannot close the dropdown mid-selection.
  if (signature !== renderedGifs && document.activeElement !== select) {
    renderedGifs = signature;
    select.innerHTML = '';
    state.gifs.forEach(function (name) {
      select.appendChild(new Option(name, name));
    });
  }
  // With nothing chosen the clock plays the first animation, so show that
  // rather than leaving the picker blank.
  if (document.activeElement !== select) select.value = draft.gif_name || state.gifs[0] || '';
  el('gif-name-row').className = draft.gif_mode === 'fixed' ? 'row' : 'row hidden';
  el('hour-rows').className = draft.gif_mode === 'hourly' ? '' : 'hidden';
  renderHourRows();
  el('gif-hint').textContent = state.gifs.length
    ? state.gifs.length + ' animation(s) in ' + state.gif_directory
    : 'No animations found. Drop .gif files into ' + state.gif_directory;
}

var hourSelects = null;

function renderHourRows() {
  var container = el('hour-rows');
  if (!hourSelects) {
    hourSelects = {};
    for (var hour = 1; hour <= 12; hour++) {
      (function (hour) {
        var row = document.createElement('div');
        row.className = 'hour-row';

        var label = document.createElement('span');
        label.className = 'hour';
        label.textContent = hour + ":00";
        row.appendChild(label);

        var picker = document.createElement('select');
        picker.onchange = function () {
          draft.hour_gifs = Object.assign({}, draft.hour_gifs);
          draft.hour_gifs[String(hour)] = this.value;
          changed();
        };
        row.appendChild(picker);

        var preview = document.createElement('button');
        preview.className = 'play';
        preview.innerHTML = '&#9654;';
        preview.title = 'Preview on the clock face';
        preview.onclick = function () {
          playAnimationPreview(picker.value || state.gifs[0]);
        };
        row.appendChild(preview);

        container.appendChild(row);
        hourSelects[String(hour)] = picker;
      })(hour);
    }
  }
  Object.keys(hourSelects).forEach(function (hour) {
    var picker = hourSelects[hour];
    var wanted = (draft.hour_gifs || {})[hour] || '';
    var signature = state.gifs.join('\\u0000');
    if (picker.dataset.signature !== signature && document.activeElement !== picker) {
      picker.dataset.signature = signature;
      picker.innerHTML = '';
      picker.appendChild(new Option('Random', ''));
      state.gifs.forEach(function (name) {
        picker.appendChild(new Option(name.replace(/\\.gif$/i, ''), name));
      });
    }
    if (document.activeElement !== picker) picker.value = wanted;
  });
}

var zoneNames = null;

function buildTimezones() {
  var select = el('timezone');
  select.innerHTML = '';
  select.appendChild(new Option('System default', ''));
  var groups = {};
  zoneNames.forEach(function (name) {
    var region = name.indexOf('/') >= 0 ? name.slice(0, name.indexOf('/')) : 'Other';
    if (!groups[region]) {
      groups[region] = document.createElement('optgroup');
      groups[region].label = region;
      select.appendChild(groups[region]);
    }
    groups[region].appendChild(new Option(name.replace(/_/g, ' '), name));
  });
}

function renderTimezone() {
  var select = el('timezone');
  if (!select.options.length) return;
  var value = draft.timezone;
  var known = Array.prototype.some.call(select.options, function (option) {
    return option.value === value;
  });
  // A detected or stored zone may be an alias the picker list does not carry;
  // keep it selectable rather than silently showing something else.
  if (value && !known) select.appendChild(new Option(value.replace(/_/g, ' '), value));
  if (document.activeElement !== select) select.value = value;
}

function render() {
  el('power').textContent = draft.display_on ? 'On' : 'Off';
  el('power').className = draft.display_on ? 'status' : 'status off';
  if (document.activeElement !== el('brightness')) el('brightness').value = draft.brightness;
  el('brightness-value').textContent = Math.round(draft.brightness * 100) + '%';

  renderThemes();
  el('color').value = toHex(draft.color);
  el('secondary-color').value = toHex(draft.secondary_color);
  var usesColor = ['solid', 'gradient'].indexOf(draft.theme) >= 0;
  el('color-row').className = usesColor ? 'row' : 'row hidden';
  var isGradient = draft.theme === 'gradient';
  el('secondary-color').className = isGradient ? '' : 'hidden';
  el('color-label').textContent = isGradient ? 'Color, top to bottom' : 'Color';
  el('sparkle').checked = !!draft.sparkle;
  // Sparkle animates any theme, so the speed control applies to it too.
  el('speed-row').className = isAnimated() ? 'row' : 'row hidden';
  el('speed').value = draft.animation_speed;
  el('speed-value').textContent = Number(draft.animation_speed).toFixed(3);

  el('gifs-enabled').checked = !!draft.gifs_enabled;
  el('gif-mode').value = draft.gif_mode;
  el('gif-duration').value = draft.gif_duration;
  el('gif-duration-value').textContent = draft.gif_duration + 's';
  renderGifs();
  renderTimezone();
}

el('gifs-enabled').onchange = function () { draft.gifs_enabled = this.checked; changed(); };
el('brightness').oninput = function () { draft.brightness = Number(this.value); changed(); };
el('sparkle').onchange = function () { draft.sparkle = this.checked; changed(); };
el('speed').oninput = function () { draft.animation_speed = Number(this.value); changed(); };
el('gif-duration').oninput = function () { draft.gif_duration = Number(this.value); changed(); };
el('color').oninput = function () { draft.color = this.value; changed(); };
el('secondary-color').oninput = function () { draft.secondary_color = this.value; changed(); };
el('gif-mode').onchange = function () {
  draft.gif_mode = this.value;
  // Pin down what "one specific animation" means instead of saving an empty
  // choice that only resolves to the first file once it reaches the clock.
  if (this.value === 'fixed' && !draft.gif_name && state.gifs.length) {
    draft.gif_name = state.gifs[0];
  }
  changed();
};
el('gif-name').onchange = function () { draft.gif_name = this.value; changed(); };
el('timezone').onchange = function () {
  setStatus('', false);
  draft.timezone = this.value;
  changed();
};

el('preview-fixed').onclick = function () {
  playAnimationPreview(draft.gif_name || state.gifs[0]);
};

var gifStatusTimer = null;

function setGifStatus(message, isError) {
  var status = el('gif-status');
  status.textContent = message;
  status.className = isError ? 'error' : 'hint';
  clearTimeout(gifStatusTimer);
  if (message) gifStatusTimer = setTimeout(function () { setGifStatus(''); }, 6000);
}

// Whichever animation the current settings would play at this hour.
function animationForCurrentMode() {
  if (!state.gifs.length) return '';
  if (draft.gif_mode === 'fixed') {
    return draft.gif_name || state.gifs[0];
  }
  if (draft.gif_mode === 'hourly') {
    var assigned = (draft.hour_gifs || {})[String(state.clock.hour)] || '';
    if (assigned) return assigned;
  }
  return state.gifs[Math.floor(Math.random() * state.gifs.length)];
}

el('play-gif').onclick = function () {
  var name = animationForCurrentMode();
  if (!name) {
    setGifStatus('There are no animations to play.', true);
    return;
  }
  setGifStatus('Playing ' + name + ' in the preview above.');
  playAnimationPreview(name);
};

el('save').onclick = function () {
  el('save').disabled = true;
  api('/api/settings', draft).then(function (next) {
    state = next;
    var errors = next.errors || {};
    var failed = Object.keys(errors);
    // Whatever the clock accepted is now the truth; a rejected value would
    // otherwise sit in the draft looking as though it had been saved.
    draft = copy(next.settings);
    render();
    refreshPreview();
    if (failed.length) {
      setClean('');
      setStatus(failed.map(function (key) {
        return key + ': ' + errors[key];
      }).join('; '), true);
    } else {
      setClean('Saved to clock');
    }
  }).catch(function () {
    el('save').disabled = false;
    setStatus('Could not reach the clock.', true);
  });
};

el('revert').onclick = function () {
  draft = copy(state.settings);
  setStatus('', false);
  setClean('');
  render();
  refreshPreview();
};

/* ---------- time zone detection ---------- */

function setStatus(message, isError) {
  var status = el('timezone-status');
  status.textContent = message;
  status.className = isError ? 'error' : 'hint';
}

function tryTimezone(name, onRejected) {
  var previous = draft.timezone;
  draft.timezone = name;
  return api('/api/preview', draft).then(function (data) {
    if (data.errors && data.errors.timezone) {
      draft.timezone = previous;
      if (onRejected) return onRejected();
      setStatus(data.errors.timezone, true);
      return false;
    }
    paint(data);
    markDirty();
    render();
    return true;
  });
}

function locateByGps() {
  if (!navigator.geolocation) {
    setStatus('This browser cannot report a location. Pick a zone from the list.', true);
    return;
  }
  if (!window.isSecureContext) {
    setStatus('Browsers only share location over https, and the clock is served over ' +
              'http. Pick a zone from the list instead.', true);
    return;
  }
  setStatus('Asking for your location...', false);
  navigator.geolocation.getCurrentPosition(function (position) {
    api('/api/timezone/locate', {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude
    }).then(function (result) {
      if (!result.timezone) {
        setStatus(result.error || 'Could not match a zone to your location.', true);
        return;
      }
      tryTimezone(result.timezone).then(function () {
        setStatus('Nearest zone to your location: ' + result.timezone +
                  '. Change it above if that is not right.', false);
      });
    });
  }, function () {
    setStatus('Location request was refused. Pick a zone from the list.', true);
  }, { timeout: 10000 });
}

el('detect-timezone').onclick = function () {
  setStatus('', false);
  var guess = null;
  try {
    guess = Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch (error) {
    guess = null;
  }
  // The device's own zone is exact when it is available; asking for coordinates
  // and matching the nearest zone is the fallback.
  if (guess) {
    tryTimezone(guess, locateByGps);
  } else {
    locateByGps();
  }
};

/* ---------- startup and polling ---------- */

function pollState() {
  return api('/api/state').then(function (next) {
    state = next;
    // Never overwrite edits in progress; the clock's own values are only
    // adopted while there is nothing unsaved.
    if (!dirty) draft = copy(next.settings);
    render();
  }).catch(function () {});
}

collectCells();

api('/api/state').then(function (next) {
  state = next;
  draft = copy(next.settings);
  setClean('');
  // Draw the preview before the controls: if rendering a control ever throws,
  // that must not be what stops the preview from appearing.
  refreshPreview();
  render();
  return api('/api/timezones');
}).then(function (data) {
  zoneNames = (data && data.timezones) || [];
  buildTimezones();
  renderTimezone();
}).catch(function (error) {
  el('preview-error').textContent =
    'Could not load settings from the clock (' + error + ').';
});

setInterval(function () {
  pollState().then(function () { if (!dirty) refreshPreview(); });
}, 5000);

// Animated themes and sparkle need the preview refreshed to show movement.
setInterval(function () {
  if (isAnimated() && draft.display_on) refreshPreview();
}, 700);
</script>
</body>
</html>
"""


def _face_markup():
    """The letter grid, rendered into the page so it never depends on a fetch."""
    return "".join(
        f"<span>{letter}</span>"
        for row in ClockDisplayHAL.LETTER_ROWS
        for letter in row
    )


PAGE = PAGE_TEMPLATE.replace("<!--FACE-->", _face_markup())


def _make_handler(settings, gif_library, word_clock):

    def build_state(errors=None):
        current = settings.snapshot()
        moment = timekeeper.now(current["timezone"])
        return {
            "settings": current,
            "themes": themes.catalog(),
            "gifs": gif_library.names(),
            "gif_directory": gif_library.directory,
            "clock": {
                "time": timekeeper.describe(moment),
                "phrase": word_clock.phrase(moment),
                "hour": moment.hour % 12 or 12,
            },
            "errors": errors or {},
        }

    def build_preview(changes):
        """Render the clock face for a draft of the settings."""
        values, errors = settings.merged(changes)
        moment = timekeeper.now(values["timezone"])

        lit = {}
        if values["display_on"]:
            scale = PREVIEW_FLOOR + (1.0 - PREVIEW_FLOOR) * values["brightness"]
            for word, color in word_clock.word_colors(values, moment):
                start, end = ClockDisplayHAL.WORDS_TO_LEDS[word]
                shown = "#%02x%02x%02x" % tuple(int(channel * scale) for channel in color)
                for index in range(start, end + 1):
                    lit[index] = shown

        colors = []
        for y in range(ClockDisplayHAL.HEIGHT):
            colors.append([
                lit.get(ClockDisplayHAL.cartesian_to_word_clock_led_strip_index(x, y))
                for x in range(ClockDisplayHAL.WIDTH)
            ])

        return {
            "letters": list(ClockDisplayHAL.LETTER_ROWS),
            "colors": colors,
            "clock": {
                "time": timekeeper.describe(moment),
                "phrase": word_clock.phrase(moment),
                "hour": moment.hour % 12 or 12,
            },
            "errors": errors,
        }

    def build_animation(name):
        """An animation's frames, ready to play in the preview face."""
        path = gif_library.path_for(name)
        if not path:
            return {"error": "unknown animation", "frames": []}

        brightness = settings.get("brightness")
        scale = PREVIEW_FLOOR + (1.0 - PREVIEW_FLOOR) * brightness
        frames = []
        for grid, delay in gif.load_frames(path):
            frames.append({
                "colors": [
                    ["#%02x%02x%02x" % tuple(int(channel * scale) for channel in color)
                     for color in row]
                    for row in grid
                ],
                "delay": int(delay * 1000),
            })
        return {"name": name, "frames": frames}

    class WordClockHandler(BaseHTTPRequestHandler):
        server_version = "WordClock"
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            pass  # keep the systemd journal readable

        def _send(self, status, body, content_type):
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, payload, status=200):
            self._send(status, json.dumps(payload), "application/json")

        def _read_json(self):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self.close_connection = True
                return None
            if length <= 0:
                return {}
            if length > MAX_BODY_BYTES:
                # The body is left unread, so this connection can no longer be
                # reused for a following request.
                self.close_connection = True
                return None
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._send_json(build_state())
            elif self.path == "/api/timezones":
                # Fetched once per page load rather than folded into /api/state,
                # which the page polls every few seconds.
                self._send_json({"timezones": timekeeper.zone_names()})
            else:
                self._send_json({"error": "not found"}, status=404)

        def do_POST(self):
            body = self._read_json()
            if body is None or not isinstance(body, dict):
                self._send_json({"error": "expected a JSON object"}, status=400)
                return

            if self.path == "/api/settings":
                _, errors = settings.update(body)
                self._send_json(build_state(errors))
            elif self.path == "/api/preview":
                self._send_json(build_preview(body))
            elif self.path == "/api/gif/play":
                settings.request_gif(body.get("name") or "")
                self._send_json(build_state())
            elif self.path == "/api/gif/frames":
                self._send_json(build_animation(body.get("name") or ""))
            elif self.path == "/api/timezone/locate":
                self._locate_timezone(body)
            else:
                self._send_json({"error": "not found"}, status=404)

        def _locate_timezone(self, body):
            try:
                latitude = float(body["latitude"])
                longitude = float(body["longitude"])
            except (KeyError, TypeError, ValueError):
                self._send_json({"error": "expected numeric latitude and longitude"},
                                status=400)
                return
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                self._send_json({"error": "coordinates out of range"}, status=400)
                return
            zone = timekeeper.nearest_timezone(latitude, longitude)
            if not zone:
                self._send_json({"error": "no time zone data on this device"}, status=404)
                return
            self._send_json({"timezone": zone})

    return WordClockHandler


def start(settings, gif_library, word_clock, host="0.0.0.0", port=8080):
    """Start the web server on a daemon thread. Returns the server, or None."""
    try:
        server = ThreadingHTTPServer((host, port), _make_handler(settings, gif_library, word_clock))
    except OSError as error:
        print(f"Web interface disabled, could not listen on {host}:{port}: {error}")
        return None
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True, name="wordclock-web").start()
    print(f"Web interface listening on http://{host}:{port}")
    return server
