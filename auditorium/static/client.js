// What every client surface shares: fetching the timeline, decorating appended
// content, beat arithmetic, and a requestAnimationFrame clock that drives
// seek().
//
// Three surfaces consume this — the audience view, the preview client, and the
// presenter view. They exist as separate pages because their jobs differ (D8),
// but a second implementation of "what does the deck look like at t" is exactly
// the drift D2 forbids. So the only thing a page may add is chrome.

/** Register the KaTeX + highlight.js decoration hook.
 *
 * An append hook rather than a per-frame pass: both mutate innerHTML, so
 * re-running them on every seek would re-highlight already-marked code and
 * cost time inside the render loop.
 */
export function installDecoration(engine) {
  engine.onAppend = function (el) {
    if (typeof renderMathInElement === "function") {
      renderMathInElement(el, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
      });
    }
    if (typeof hljs !== "undefined") {
      el.querySelectorAll("pre code").forEach(function (block) {
        hljs.highlightElement(block);
      });
    }
  };
}

/** A player over one engine: position, playback, and beat navigation.
 *
 * `onFrame` fires after every seek, including every frame of playback. It is
 * how a page keeps its chrome — slide indicator, scrubber, readouts — in
 * agreement with the stage.
 */
export function createPlayer({ engine, onFrame }) {
  const player = {
    engine,
    beats: [],
    markers: [],
    duration: 0,
    fps: 30,
    playing: false,

    get t() {
      return engine.currentTime;
    },

    load(tl) {
      this.beats = (tl.beats || []).map((b) => b.t);
      this.markers = tl.markers || [];
      this.duration = (tl.meta && tl.meta.duration_ms) || 0;
      this.fps = (tl.meta && tl.meta.fps) || 30;
      engine.load(tl);
      engine.seek(0);
      if (onFrame) onFrame(this);
      window.__auditorium_duration = this.duration;
      // The renderer and the exporter drive the deck through this, never
      // through engine.seek directly: seek alone skips onFrame, which freezes
      // the slide indicator at whatever it read on load. That is how one wrong
      // page number got burned into all 63 exported stills.
      window.__auditoriumShow = (t) => this.seekTo(t);
      window.__auditorium_ready = true;
    },

    async fetchAndLoad(url = "/timeline.json") {
      this.load(await (await fetch(url)).json());
    },

    seekTo(t) {
      this.playing = false;
      engine.seek(t);
      if (onFrame) onFrame(this);
    },

    pause() {
      this.playing = false;
    },

    /** Play from the current position to `target`, then stop.
     *
     * `onArrive` lets a caller chain — the preview client uses it to wrap a
     * loop back to its in-point. The clock is performance.now(), which is
     * fine because nothing in the render path calls this: the renderer drives
     * window.__auditoriumShow frame by frame and never reads a wall clock.
     */
    playTo(target, onArrive) {
      this.playing = true;
      const base = engine.currentTime;
      const started = performance.now();
      const step = (now) => {
        if (!this.playing) return;
        const t = Math.min(base + (now - started), target);
        engine.seek(t);
        if (onFrame) onFrame(this);
        if (t < target) {
          requestAnimationFrame(step);
        } else {
          this.playing = false;
          if (onArrive) onArrive(this);
        }
      };
      requestAnimationFrame(step);
    },

    beatIndex(t) {
      let i = 0;
      for (const b of this.beats) if (b < t) i += 1;
      return i;
    },

    nextBeat(from) {
      for (const b of this.beats) if (b > from) return b;
      return this.duration;
    },

    prevBeat(from) {
      let target = 0;
      // `from - 1` and not `from`: beat() advances the clock by exactly 1ms,
      // so sitting exactly on a beat must step to the one before it, not to
      // itself.
      for (const b of this.beats) if (b < from - 1) target = b;
      return target;
    },

    /** The scene in progress at `t` — the last marker at or before it. */
    markerAt(t) {
      let found = null;
      for (const m of this.markers) if (m.t <= t) found = m;
      return found;
    },

    /** The scene after `t`, or null when this is the last one. */
    markerAfter(t) {
      for (const m of this.markers) if (m.t > t) return m;
      return null;
    },
  };
  return player;
}

/** Connect to the server, with auto-reconnect.
 *
 * Returns a wrapper exposing send(); the socket itself is replaced on every
 * reconnect, so callers must not hold a reference to it.
 */
export function connect({ role = "audience", onReload, onCommand, onHello, onStatus } = {}) {
  const wrapper = { socket: null };

  function open() {
    if (onStatus) onStatus("connecting");
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const wsMeta = document.querySelector('meta[name="auditorium-ws-path"]');
    const wsPath = wsMeta ? wsMeta.content : "/ws";
    const ws = new WebSocket(protocol + "//" + location.host + wsPath);
    wrapper.socket = ws;

    ws.onopen = function () {
      if (onStatus) onStatus("connected");
      ws.send(JSON.stringify({ type: "hello", role }));
    };
    ws.onmessage = function (event) {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        return;
      }
      if (msg.type === "reload" && onReload) onReload(msg);
      else if (msg.type === "cmd" && onCommand) onCommand(msg);
      else if (msg.type === "hello_ack" && onHello) onHello(msg);
    };
    ws.onclose = function () {
      if (onStatus) onStatus("disconnected");
      setTimeout(open, 1000);
    };
    ws.onerror = function () {
      ws.close();
    };
  }

  wrapper.send = function (msg) {
    const ws = wrapper.socket;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  };

  open();
  return wrapper;
}

/** mm:ss.mmm — the preview client's time readout. */
export function formatTime(ms) {
  const total = Math.max(0, Math.round(ms));
  const mm = String(Math.floor(total / 60000)).padStart(2, "0");
  const ss = String(Math.floor((total % 60000) / 1000)).padStart(2, "0");
  const mmm = String(total % 1000).padStart(3, "0");
  return `${mm}:${ss}.${mmm}`;
}
