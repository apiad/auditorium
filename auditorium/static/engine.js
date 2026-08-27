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
  // Normalized units, because every stroked SVG node is created with
  // pathLength="1". An anchored line's real length changes whenever the node
  // it points at moves, so a measured dash pattern would be stale by the
  // next frame.
  "stroke.dashoffset": (from_, to) => [
    { strokeDashoffset: String(from_) },
    { strokeDashoffset: String(to) },
  ],
};

const SVG_NS = "http://www.w3.org/2000/svg";
const SVG_LAYER_ID = "svg-layer";

// kind -> element. An arrow is a line that additionally carries a head marker.
const SVG_TAGS = { line: "line", arrow: "line", circle: "circle", path: "path" };

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
    this._clearOverlay();
    this._applied = 0;
    this._t = 0;
  },

  /** Empty the SVG overlay and forget its anchors.
   *
   * Everything except <defs>: wiping the whole overlay would delete the
   * arrowhead marker, and every arrow drawn afterwards would render headless.
   */
  _clearOverlay() {
    const layer = document.getElementById(SVG_LAYER_ID);
    if (layer) {
      for (const child of Array.from(layer.children)) {
        if (child.tagName.toLowerCase() !== "defs") child.remove();
      }
    }
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
      // Geometry is part of the stage, so a scene boundary wipes it too.
      // It did not, once: the Geometry scene's arrow, rule and circle stayed
      // drawn over every slide that followed it to the end of the deck.
      this._clearOverlay();
    } else if (op.action === "append") {
      const node = this._tl.nodes.find((n) => n.id === op.node);
      if (!node) return;
      if (node.layer === "svg") return this._appendSvg(node);
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

  _appendSvg(node) {
    const layer = document.getElementById(SVG_LAYER_ID);
    const spec = node.svg;
    if (!layer || !spec) return;
    const tag = SVG_TAGS[spec.kind];
    if (!tag) return;

    // createElementNS, never innerHTML: setting SVG markup through an HTML
    // parser yields HTMLUnknownElements that look right in the inspector and
    // never render.
    const el = document.createElementNS(SVG_NS, tag);
    el.id = node.id;
    el.setAttribute("fill", spec.fill || "none");
    el.setAttribute("stroke", spec.stroke || "currentColor");
    el.setAttribute("stroke-width", String(spec.width == null ? 2 : spec.width));
    // pathLength normalises the shape to a length of 1 so draw-on can run
    // 1 -> 0 without measuring geometry the anchors may be about to change.
    el.setAttribute("pathLength", "1");
    el.setAttribute("stroke-dasharray", spec.dash || "1");
    if (spec.kind === "arrow") el.setAttribute("marker-end", "url(#aud-arrowhead)");
    if (spec.kind === "path") el.setAttribute("d", spec.d || "");
    if (spec.kind === "circle") {
      el.setAttribute("cx", String(spec.at[0]));
      el.setAttribute("cy", String(spec.at[1]));
      el.setAttribute("r", String(spec.r));
    }
    if (spec.from && spec.from.point) {
      el.setAttribute("x1", String(spec.from.point[0]));
      el.setAttribute("y1", String(spec.from.point[1]));
    }
    if (spec.to && spec.to.point) {
      el.setAttribute("x2", String(spec.to.point[0]));
      el.setAttribute("y2", String(spec.to.point[1]));
    }

    layer.appendChild(el);

    // Register symbolic endpoints for resolution on every seek. Resolving
    // once here instead would look correct until the anchored node moved.
    const fromAnchor = spec.from && spec.from.anchor;
    const toAnchor = spec.to && spec.to.anchor;
    if (fromAnchor || toAnchor) {
      this._anchored.push({ el, from: fromAnchor || null, to: toAnchor || null });
    }

    this._attachTracks(node.id, el);
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
      // move_by() emits transform.x AND transform.y -- two animations writing
      // the same CSS property. Under the default composite:"replace" the last
      // one wins outright, so move_by(200, 0) renders translateY(0px) and the
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

  _pointOn(rect, side) {
    switch (side) {
      case "left":   return [rect.left, rect.top + rect.height / 2];
      case "right":  return [rect.right, rect.top + rect.height / 2];
      case "top":    return [rect.left + rect.width / 2, rect.top];
      case "bottom": return [rect.left + rect.width / 2, rect.bottom];
      default:       return [rect.left + rect.width / 2, rect.top + rect.height / 2];
    }
  },

  // ALL reads, then ALL writes. Not an optimisation: interleaving thrashes
  // layout at 182ms per frame for 2000 anchors against a 33ms budget, and
  // 965ms at 5000. Batched, the same cases are 9.9ms and 21ms. The
  // pathological shape is precisely the dense node-and-edge graph this layer
  // exists to draw, so the phase split is a correctness requirement in
  // practice even though it reads as a performance one.
  _resolveAnchors() {
    if (this._anchored.length === 0) return;
    const layer = document.getElementById(SVG_LAYER_ID);
    if (!layer) return;

    // READ PHASE. getBoundingClientRect gives screen pixels, but the overlay's
    // user units are only the same thing when nothing between it and the
    // viewport is transformed -- and the preview and presenter both scale
    // their stage. The overlay's own screen CTM, inverted, is the conversion;
    // it is read once here so the write phase touches no layout.
    const ctm = layer.getScreenCTM ? layer.getScreenCTM() : null;
    const inv = ctm ? ctm.inverse() : null;

    const reads = [];
    for (const a of this._anchored) {
      reads.push({
        spec: a,
        from: a.from ? document.getElementById(a.from.node)?.getBoundingClientRect() : null,
        to: a.to ? document.getElementById(a.to.node)?.getBoundingClientRect() : null,
      });
    }

    // WRITE PHASE. Pure arithmetic on values already read.
    const toUser = (p) =>
      inv ? [inv.a * p[0] + inv.c * p[1] + inv.e, inv.b * p[0] + inv.d * p[1] + inv.f] : p;

    for (const r of reads) {
      if (r.from) {
        const [x, y] = toUser(this._pointOn(r.from, r.spec.from.side));
        r.spec.el.setAttribute("x1", String(x));
        r.spec.el.setAttribute("y1", String(y));
      }
      if (r.to) {
        const [x, y] = toUser(this._pointOn(r.to, r.spec.to.side));
        r.spec.el.setAttribute("x2", String(x));
        r.spec.el.setAttribute("y2", String(y));
      }
    }
  },
};
