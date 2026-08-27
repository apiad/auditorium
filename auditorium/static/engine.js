// The entire runtime. seek(t) puts the DOM into the state it holds at time t.
//
// Two invariants, both learned the hard way:
//
//   1. seek drives document.getAnimations(), never a private registry.
//      Themes ship infinite animations on pseudo-elements; a registry
//      structurally cannot see them, and unpaused they make every frame
//      nondeterministic.
//
//   2. Seeking is path-dependent. t=0 reached fresh differs from t=0
//      reached by rewinding. So seeking is only ever performed forward:
//      a backward seek resets to zero and replays.

const PROP_SETTERS = {
  "opacity": (from_, to) => [{ opacity: from_ }, { opacity: to }],
  "transform.x": (from_, to) => [
    { transform: `translateX(${from_}px)` },
    { transform: `translateX(${to}px)` },
  ],
  "transform.y": (from_, to) => [
    { transform: `translateY(${from_}px)` },
    { transform: `translateY(${to}px)` },
  ],
  "transform.scale": (from_, to) => [
    { transform: `scale(${from_})` },
    { transform: `scale(${to})` },
  ],
};

// The slide root's baseline class. reset() must restore it: the old client
// re-set it on every slide, and without that the base layout class is absent
// and aud-layout-mode leaks from the first slide that uses columns onward.
const ROOT_BASE_CLASS = "aud-slide-root";

export const AuditoriumEngine = {
  _tl: null,
  _applied: 0,
  _t: -1,
  _tweens: [],
  _anchored: [],

  get currentTime() {
    return this._t;
  },

  load(timeline) {
    this._tl = timeline;
    this.reset();
  },

  registerTween(fn) {
    this._tweens.push(fn);
  },

  reset() {
    const root = document.getElementById("slide-root");
    if (root) {
      root.innerHTML = "";
      root.className = ROOT_BASE_CLASS;
    }
    this._applied = 0;
    this._t = 0;
    this._anchored = [];
  },

  seek(t) {
    if (this._tl === null) return;
    if (t < this._t) this.reset();

    // 1. Apply structural ops forward.
    const ops = this._tl.ops;
    while (this._applied < ops.length && ops[this._applied].t <= t) {
      this._applyOp(ops[this._applied]);
      this._applied += 1;
    }

    // 2. Position every animation on the page, including pseudo-elements
    //    and theme decoration the engine never created.
    for (const anim of document.getAnimations()) {
      anim.pause();
      anim.currentTime = t;
    }

    // 3. Anything WAAPI cannot interpolate.
    for (const fn of this._tweens) fn(t);

    // 4. Anchors: all reads, then all writes. Interleaving thrashes layout
    //    (182ms vs 9.9ms at 2000 anchors).
    this._resolveAnchors();

    this._t = t;
  },

  _applyOp(op) {
    const root = document.getElementById("slide-root");
    if (!root) return;
    if (op.action === "clear") {
      root.innerHTML = "";
      root.className = ROOT_BASE_CLASS;
    } else if (op.action === "append") {
      const node = this._tl.nodes.find((n) => n.id === op.node);
      if (!node) return;
      // Unwrap to the real element. Appending an extra <div> around content
      // that is already an element breaks flex sizing: a `flex: 1` container
      // cannot grow through an unstyled wrapper, and nested row layouts
      // collapse to their natural height instead of filling.
      const wrapper = document.createElement("div");
      wrapper.innerHTML = node.html || "";
      const el = wrapper.firstElementChild || wrapper;
      el.id = node.id;
      const parent =
        node.parent && node.parent !== "root"
          ? document.getElementById(node.parent) || root
          : root;

      // Coalesce consecutive lists so numbering stays continuous across
      // separate md() calls (ported from the 3.x client, commit 1e81cdc).
      // Skipped when the node is animated: merging it away would leave its
      // tracks with no element to attach to.
      const animated = this._tl.tracks.some((t) => t.node === node.id);
      const newList =
        el.children.length === 1 &&
        (el.children[0].tagName === "OL" || el.children[0].tagName === "UL")
          ? el.children[0]
          : null;
      const prevWrap = parent.lastElementChild;
      const prevList =
        !animated && newList && prevWrap &&
        prevWrap.children.length === 1 &&
        prevWrap.children[0].tagName === newList.tagName
          ? prevWrap.children[0]
          : null;
      if (prevList) {
        for (const li of Array.from(newList.children)) prevList.appendChild(li);
        if (typeof this.onAppend === "function") this.onAppend(prevList);
        return;
      }

      parent.appendChild(el);
      // Client-supplied decoration (KaTeX, syntax highlighting). Runs once per
      // append rather than per seek: it mutates innerHTML, and re-running it on
      // every frame would both cost time and re-highlight already-marked code.
      if (typeof this.onAppend === "function") this.onAppend(el);
      this._attachTracks(node.id, el);
    } else if (op.action === "remove") {
      document.querySelectorAll(op.selector).forEach((el) => el.remove());
    } else if (op.action === "replace") {
      const el = document.querySelector(op.selector);
      if (el) el.innerHTML = op.html || "";
    } else if (op.action === "set_class") {
      const el = document.querySelector(op.selector);
      if (el) el.classList.add(...op.cls.split(/\s+/));
    } else if (op.action === "remove_class") {
      const el = document.querySelector(op.selector);
      if (el) el.classList.remove(...op.cls.split(/\s+/));
    }
  },

  _attachTracks(nodeId, el) {
    // Each track becomes one paused animation positioned on the GLOBAL
    // timeline via delay, with fill:both so it holds its start value before
    // it begins and its end value after it finishes. That is what lets a
    // single `currentTime = t` place every animation correctly.
    for (const track of this._tl.tracks) {
      if (track.node !== nodeId) continue;
      const build = PROP_SETTERS[track.prop];
      if (!build) continue;
      const keyframes = build(track.from, track.to);
      // move_to() emits transform.x AND transform.y -- two animations writing
      // the same CSS property. Under the default composite:"replace" the last
      // one wins outright, so move_to(200, 0) renders translateY(0px) and the
      // element never moves. Measured: replace -> x=0, add -> x=200.
      //
      // Scoped to transforms on purpose. Additive opacity would sum against
      // the underlying 1 and clamp, turning every fade-in into a no-op.
      const isTransform = track.prop.startsWith("transform.");
      const anim = el.animate(keyframes, {
        delay: track.start,
        duration: Math.max(1, track.end - track.start),
        easing: track.ease || "linear",
        fill: "both",
        composite: isTransform ? "add" : "replace",
      });
      anim.pause();
    }
  },

  _resolveAnchors() {
    if (this._anchored.length === 0) return;
    const reads = this._anchored.map((a) => ({
      spec: a,
      from: document.getElementById(a.fromId)?.getBoundingClientRect(),
      to: document.getElementById(a.toId)?.getBoundingClientRect(),
    }));
    for (const r of reads) {
      if (!r.from || !r.to) continue;
      r.spec.apply(r.from, r.to);
    }
  },
};
