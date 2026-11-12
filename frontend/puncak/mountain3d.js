// The 3D mountain (off unless MODEL_3D is set in app.js): loads a .glb model, traces the summit trail onto its surface,
// and moves the camera up the mountain as the player's score rises.

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const TRAIL_SAMPLES = 150;
const BASE_SKIP = 0.17; // the bottom of the model is its display base, not mountain
const CAMERA_DISTANCE = 3.7;
const CAMERA_FOV = 32;
const WIDEST = 2.2; // widest footprint allowed, in model heights, before the model is scaled down
const FOREST_TOP = 0.34; // fraction of the trail that runs through the trees

const lerp = (a, b, t) => a + (b - a) * t;

/** Finds the highest vertex of the model: the summit. */
function findPeak(model) {
  const peak = new THREE.Vector3(0, -Infinity, 0);
  const v = new THREE.Vector3();
  model.traverse((node) => {
    if (!node.isMesh) return;
    const positions = node.geometry.attributes.position;
    for (let i = 0; i < positions.count; i++) {
      v.fromBufferAttribute(positions, i).applyMatrix4(node.matrixWorld);
      if (v.y > peak.y) peak.copy(v);
    }
  });
  return peak;
}

/** Walks a zigzag up the camera-facing side of the model, snapping each step onto the surface. */
function traceTrail(model, box, peak) {
  const raycaster = new THREE.Raycaster();
  const yStart = lerp(box.min.y, box.max.y, BASE_SKIP);
  const reach = Math.max(box.max.x - box.min.x, box.max.z - box.min.z);
  const points = [];
  const normals = [];

  for (let i = 0; i < TRAIL_SAMPLES; i++) {
    const f = i / TRAIL_SAMPLES;
    const y = lerp(yStart, peak.y, f);
    // Wide switchbacks low down, tightening toward the summit.
    const angle = Math.sin(f * Math.PI * 4.5) * 0.75 * (1 - 0.7 * f);
    // Aim at the summit's axis so rays still land on the spires near the top.
    const axis = new THREE.Vector3(lerp(0, peak.x, f), y, lerp(0, peak.z, f));
    const origin = new THREE.Vector3(axis.x + Math.sin(angle) * reach, y, axis.z + Math.cos(angle) * reach);
    raycaster.set(origin, axis.clone().sub(origin).normalize());
    const hit = raycaster.intersectObject(model, true)[0];
    if (!hit) continue;
    const normal = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
    points.push(hit.point.clone().addScaledVector(normal, 0.012));
    normals.push(normal);
  }
  points.push(peak.clone().add(new THREE.Vector3(0, 0.012, 0)));
  normals.push(new THREE.Vector3(0, 0.3, 1).normalize());

  // The lower slopes are bumpy treetops, which makes the raw path jagged. Average each point there
  // with its neighbours, fading the smoothing out as the trail reaches bare rock.
  const smoothed = points.map((point, i) => {
    const f = i / (points.length - 1);
    const strength = Math.max(0, 1 - f / FOREST_TOP);
    if (strength === 0) return point;
    const average = new THREE.Vector3();
    let count = 0;
    for (let j = Math.max(0, i - 5); j <= Math.min(points.length - 1, i + 5); j++, count++) average.add(points[j]);
    return point.clone().lerp(average.divideScalar(count), strength);
  });
  return { points: smoothed, normals };
}

/**
 * For wide landscapes: lays the trail over the ground from the near edge to the summit,
 * in switchbacks that tighten on the way up, by dropping a ray onto the terrain at each step.
 */
function traceTerrainTrail(model, box, peak) {
  const raycaster = new THREE.Raycaster();
  const down = new THREE.Vector3(0, -1, 0);
  const start = new THREE.Vector2(peak.x * 0.3, lerp(peak.z, box.max.z, 0.82));
  const end = new THREE.Vector2(peak.x, peak.z);
  const along = end.clone().sub(start);
  const across = new THREE.Vector2(-along.y, along.x).normalize();
  const swing = along.length() * 0.14;
  const points = [];
  const normals = [];

  for (let i = 0; i < TRAIL_SAMPLES; i++) {
    const f = i / TRAIL_SAMPLES;
    const spot = start.clone().lerp(end, f).addScaledVector(across, Math.sin(f * Math.PI * 5) * swing * (1 - f));
    raycaster.set(new THREE.Vector3(spot.x, box.max.y + 1, spot.y), down);
    const hit = raycaster.intersectObject(model, true)[0];
    if (!hit) continue;
    points.push(hit.point.clone().add(new THREE.Vector3(0, 0.014, 0)));
    normals.push(new THREE.Vector3(0, 1, 0));
  }
  points.push(peak.clone().add(new THREE.Vector3(0, 0.014, 0)));
  normals.push(new THREE.Vector3(0, 1, 0));
  return { points, normals, behind: new THREE.Vector3(-along.x, 0, -along.y).normalize() };
}

function makeLabel(layer, className, text, sub) {
  const el = document.createElement("div");
  el.className = `label3d ${className}`;
  const dot = document.createElement("i");
  const name = document.createElement("span");
  name.textContent = text;
  el.append(dot, name);
  if (sub) {
    const small = document.createElement("small");
    small.textContent = sub;
    name.append(small);
  }
  layer.append(el);
  return el;
}

/**
 * @param container  the element the mountain fills
 * @param checkpoints  [{name, label, fraction}] along the trail, 0 = gate, 1 = summit
 * @returns a controller, or throws if WebGL or the model is unavailable
 */
export async function initMountain3D({ modelUrl, container, checkpoints, kopi }) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.domElement.className = "world-canvas";

  const scene = new THREE.Scene();
  // Distant ground fades into the night sky, which hides the square edges of a landscape model.
  scene.fog = new THREE.Fog(0x0b1026, 1.9, 4.6);
  const camera = new THREE.PerspectiveCamera(CAMERA_FOV, 1, 0.1, 50);

  const sky = new THREE.HemisphereLight(0xaebcff, 0x16241a, 1.1);
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(2.5, 3, 2.5);
  scene.add(sky, sun);

  const startedAt = performance.now();
  const gltf = await new GLTFLoader().loadAsync(modelUrl);
  const loadedAt = performance.now();
  const model = gltf.scene;
  scene.add(model);

  // Models come in any size. Fit this one into a standard space: about 2 units tall (less for very
  // wide terrain), centred, with its lowest point at y = -1. Everything else assumes that scale.
  model.updateMatrixWorld(true);
  const raw = new THREE.Box3().setFromObject(model);
  const size = raw.getSize(new THREE.Vector3());
  const centre = raw.getCenter(new THREE.Vector3());
  const fit = 2 / Math.max(size.y, Math.max(size.x, size.z) / WIDEST);
  model.scale.setScalar(fit);
  model.position.set(-centre.x * fit, -raw.min.y * fit - 1, -centre.z * fit);
  model.updateMatrixWorld(true);

  const box = new THREE.Box3().setFromObject(model);
  const peak = findPeak(model);
  const terrain = Math.max(size.x, size.z) / size.y > 1.6; // a landscape, as opposed to a single spire
  // Tracing the trail means testing rays against every triangle, which is slow on a detailed model,
  // so the result is remembered in the browser and reused on the next visit.
  const cacheKey = `puncak.trail.v1:${modelUrl}:${terrain ? "terrain" : "spire"}:${box.max.y.toFixed(4)}`;
  let traced = null;
  try {
    const saved = JSON.parse(localStorage.getItem(cacheKey) ?? "null");
    if (saved) {
      traced = {
        points: saved.points.map((p) => new THREE.Vector3(...p)),
        normals: saved.normals.map((n) => new THREE.Vector3(...n)),
        behind: saved.behind ? new THREE.Vector3(...saved.behind) : undefined,
      };
    }
  } catch {
    /* no usable cache: trace it again */
  }
  if (!traced) {
    traced = terrain ? traceTerrainTrail(model, box, peak) : traceTrail(model, box, peak);
    try {
      localStorage.setItem(
        cacheKey,
        JSON.stringify({
          points: traced.points.map((p) => p.toArray()),
          normals: traced.normals.map((n) => n.toArray()),
          behind: traced.behind?.toArray(),
        }),
      );
    } catch {
      /* storage unavailable: it will just be traced again next time */
    }
  }
  const { points, normals, behind } = traced;
  console.info(`3D mountain: model ${Math.round(loadedAt - startedAt)} ms, trail ${Math.round(performance.now() - loadedAt)} ms`);
  if (points.length < 10) throw new Error("Could not trace a trail on the model");
  const curve = new THREE.CatmullRomCurve3(points, false, "centripetal");
  const normalAt = (fraction) => normals[Math.min(normals.length - 1, Math.round(fraction * (normals.length - 1)))];

  // The whole trail, faint, and the climbed part on top of it in sunrise orange.
  const segments = 500;
  const sides = 6;
  const trail = new THREE.Mesh(
    new THREE.TubeGeometry(curve, segments, 0.005, sides),
    new THREE.MeshBasicMaterial({ color: 0xeef2ff, transparent: true, opacity: 0.5 }),
  );
  const climbed = new THREE.Mesh(
    new THREE.TubeGeometry(curve, segments, 0.009, sides),
    new THREE.MeshBasicMaterial({ color: 0xffb454 }),
  );
  climbed.geometry.setDrawRange(0, 0);
  scene.add(trail, climbed);

  const marker = new THREE.Mesh(new THREE.SphereGeometry(0.022, 20, 20), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  scene.add(marker);
  for (const cp of checkpoints) {
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.013, 12, 12), new THREE.MeshBasicMaterial({ color: 0x070b1c }));
    dot.position.copy(curve.getPointAt(cp.fraction));
    scene.add(dot);
  }

  // Text and player dots are ordinary HTML, positioned over the canvas every frame.
  const layer = document.createElement("div");
  layer.className = "labels3d";
  container.append(renderer.domElement, layer);
  const checkpointLabels = checkpoints.map((cp) => ({ ...cp, el: makeLabel(layer, "checkpoint3d", cp.name, cp.label) }));
  const youLabel = makeLabel(layer, "you3d", "YOU");
  const others = new Map(); // key -> {el, fraction, shown}

  // The easter egg: a tiny coffee stall beside the trail. Clicking it flies the camera in for a look around.
  let stall = null; // the stall model, once loaded
  let visit = null; // an in-progress visit: {startedAt, duration}
  const stallHit = document.createElement("button");
  stallHit.type = "button";
  stallHit.className = "kopi-hit";
  stallHit.setAttribute("aria-label", "A tiny coffee stall");
  stallHit.hidden = true;
  layer.append(stallHit);
  stallHit.addEventListener("click", () => {
    visit = { startedAt: performance.now(), duration: 10000 };
    kopi?.onFound?.();
  });
  if (kopi?.modelUrl) {
    new GLTFLoader()
      .loadAsync(kopi.modelUrl)
      .then((loaded) => {
        const shop = loaded.scene;
        shop.updateMatrixWorld(true);
        const bounds = new THREE.Box3().setFromObject(shop);
        const extent = bounds.getSize(new THREE.Vector3());
        const middle = bounds.getCenter(new THREE.Vector3());
        const shrink = 0.07 / Math.max(extent.x, extent.y, extent.z);
        // Stand it on the ground beside the trail, somewhere the camera can actually see: a spot behind
        // a ridge would be clickable but invisible. Candidates around the trail are tested against where
        // the camera sits at the start and at the middle of the climb; the result is remembered.
        const spotKey = `puncak.kopi.v4:${modelUrl}:${kopi.fraction ?? 0.63}`;
        let spot = null;
        try {
          const saved = JSON.parse(localStorage.getItem(spotKey) ?? "null");
          if (saved) spot = new THREE.Vector3(...saved);
        } catch {
          /* no usable cache: search again */
        }
        if (!spot) {
          const ray = new THREE.Raycaster();
          const downward = new THREE.Vector3(0, -1, 0);
          const groundAt = (x, z) => {
            ray.set(new THREE.Vector3(x, box.max.y + 1, z), downward);
            return ray.intersectObject(model, true)[0]?.point;
          };
          const eyeAt = (s) => {
            const at = curve.getPointAt(s);
            return terrain
              ? at.clone().addScaledVector(behind, lerp(1.7, 1.35, s)).setY(at.y + lerp(0.95, 1.0, s))
              : new THREE.Vector3(0, at.y + 0.4, CAMERA_DISTANCE);
          };
          // What matters is the opening view, where the judges are shown it.
          const eyes = [eyeAt(0)];
          const seenFrom = (eye, point) => {
            const direction = point.clone().sub(eye);
            const distance = direction.length();
            ray.set(eye, direction.normalize());
            const hit = ray.intersectObject(model, true)[0];
            return !hit || hit.distance > distance - 0.03;
          };
          const base = kopi.fraction ?? 0.63;
          let best = null;
          // Work outward along the trail from the wanted place until a spot is in view from both.
          const steps = [0, -0.04, 0.04, -0.08, 0.08, -0.12, 0.12, -0.16, 0.16, -0.2, 0.2];
          search: for (const step of steps) {
            const onTrail = curve.getPointAt(Math.max(0.05, Math.min(0.95, base + step)));
            for (const reach of [0.05, 0.09]) {
              for (let k = 0; k < 6; k++) {
                const angle = (k / 6) * Math.PI * 2;
                const ground = groundAt(onTrail.x + Math.sin(angle) * reach, onTrail.z + Math.cos(angle) * reach);
                if (!ground) continue;
                const roof = ground.clone().setY(ground.y + 0.05);
                let score = 0;
                for (const eye of eyes) {
                  if (!seenFrom(eye, roof)) break;
                  score += 1;
                }
                if (!best || score > best.score) best = { spot: ground, score, step };
                if (score === eyes.length) break search;
              }
            }
          }
          console.info(`Coffee stall: in view from ${best?.score ?? 0} of ${eyes.length} camera positions, ${best?.step ?? 0} along the trail from Laban Rata`);
          spot = best?.spot ?? curve.getPointAt(base);
          try {
            localStorage.setItem(spotKey, JSON.stringify(spot.toArray()));
          } catch {
            /* storage unavailable: it will just be searched again next time */
          }
        }
        // Keep its colours through the night haze, so it can be spotted from the bottom of the mountain.
        shop.traverse((node) => {
          if (node.isMesh) node.material.fog = false;
        });
        const holder = new THREE.Group();
        shop.scale.setScalar(shrink);
        shop.position.set(-middle.x * shrink, -bounds.min.y * shrink, -middle.z * shrink);
        holder.add(shop);
        holder.position.copy(spot);
        scene.add(holder);
        stall = holder;
        stallHit.hidden = false;
      })
      .catch((err) => console.info("Coffee stall not loaded:", err.message));
  }

  let target = 0;
  let shown = 0;
  let azimuth = 0;
  let sweep = null; // an in-progress finale: {startedAt, duration, summit}
  const stallView = new THREE.Vector3();
  const stallLook = new THREE.Vector3();
  const pos = new THREE.Vector3();
  const look = new THREE.Vector3();
  const up = new THREE.Vector3(0, 1, 0);
  const projected = new THREE.Vector3();
  const toCamera = new THREE.Vector3();

  function resize() {
    const { clientWidth: w, clientHeight: h } = container;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // On wide screens the text sits on the left, so push the scene's centre to the right.
    if (w > 900) camera.setViewOffset(w, h, -w * 0.2, 0, w, h);
    else camera.clearViewOffset();
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(container);
  resize();

  /** Places an HTML element over a point on the trail; hides it when that point faces away. */
  function place(el, fraction, offset = 0) {
    const point = curve.getPointAt(Math.max(0, Math.min(1, fraction)));
    const facing = normalAt(fraction).dot(toCamera.copy(camera.position).sub(point).normalize());
    projected.copy(point).project(camera);
    const x = ((projected.x + 1) / 2) * container.clientWidth;
    const y = ((1 - projected.y) / 2) * container.clientHeight;
    const visible = facing > -0.15 && projected.z < 1 && y > -40 && y < container.clientHeight + 40;
    el.style.opacity = visible ? "1" : "0";
    el.style.transform = `translate(${x + offset}px, ${y}px)`;
    el.classList.toggle("flip", x > container.clientWidth * 0.62);
  }

  function frame(time) {
    shown += (target - shown) * 0.045;
    const here = curve.getPointAt(Math.max(0, Math.min(1, shown)));
    marker.position.copy(here);
    marker.scale.setScalar(1 + 0.18 * Math.sin(time / 260));
    climbed.geometry.setDrawRange(0, Math.floor(segments * shown) * sides * 6);

    if (terrain) {
      // Follow from behind and above, looking ahead up the trail toward the summit.
      const sway = Math.sin(time / 5200) * 0.12;
      const offset = behind.clone().applyAxisAngle(up, sway).multiplyScalar(lerp(1.7, 1.35, shown));
      pos.copy(here).add(offset).setY(here.y + lerp(0.95, 1.0, shown));
      look.copy(here).lerp(peak, lerp(0.3, 0, shown)).setY(here.y + lerp(0.12, -0.2, shown));
    } else {
    // The camera circles to keep the climber in view and rises with them, with a slow idle sway.
    const wanted = Math.atan2(here.x, here.z) * 0.75 + Math.sin(time / 5200) * 0.06;
    azimuth += (wanted - azimuth) * 0.04;
    // Low down the camera looks up the mountain; near the top it looks back down so the summit fills the view.
    pos.set(Math.sin(azimuth) * CAMERA_DISTANCE, here.y + lerp(0.55, 0.2, shown), Math.cos(azimuth) * CAMERA_DISTANCE);
    look.set(here.x * 0.3, here.y + lerp(0.12, -0.42, shown), here.z * 0.3);
    }

    // The finale: one slow full circle around the climber, pulling out and rising at the midpoint,
    // starting and ending exactly where the normal camera sits so there is no jump.
    let glow = 0;
    if (sweep) {
      const t = (time - sweep.startedAt) / sweep.duration;
      if (t >= 1) {
        sweep = null;
      } else if (t > 0) {
        const eased = t * t * (3 - 2 * t);
        const swell = Math.sin(Math.PI * t);
        const pivot = terrain ? here : new THREE.Vector3(0, here.y, 0);
        const arm = pos.clone().sub(pivot).applyAxisAngle(up, eased * Math.PI * 2).multiplyScalar(1 + 0.3 * swell);
        arm.y += 0.3 * swell;
        pos.copy(pivot).add(arm);
        // On a landscape, circling at the climber's own height would fly through neighbouring ridges,
        // so rise above the highest ground for the middle of the sweep.
        if (terrain) pos.y = lerp(pos.y, Math.max(pos.y, box.max.y + 0.3), Math.min(1, swell * 4));
        look.lerp(here, swell);
        glow = sweep.summit ? swell : swell * 0.35;
      }
    }
    // Visiting the coffee stall: glide in close, swing from one side of it to the other, then glide back.
    if (visit && stall) {
      const t = (time - visit.startedAt) / visit.duration;
      if (t >= 1) {
        visit = null;
      } else if (t > 0) {
        const ramp = Math.min(1, t * 5, (1 - t) * 5);
        const blend = ramp * ramp * (3 - 2 * ramp);
        // Stay on the side the camera normally sits, so the view never ends up inside the slope.
        const front = terrain ? behind.clone() : new THREE.Vector3(stall.position.x, 0, stall.position.z).normalize();
        const arm = front.applyAxisAngle(up, Math.sin(t * Math.PI * 2) * 1.25).multiplyScalar(0.3);
        stallView.copy(stall.position).add(arm);
        stallView.y += 0.14;
        // Look a little above the stall, so it sits in the lower half of the view, clear of the message.
        stallLook.copy(stall.position).setY(stall.position.y + 0.085);
        pos.lerp(stallView, blend);
        look.lerp(stallLook, blend);
        glow = Math.max(glow, blend * 0.45);
        stall.rotation.y = Math.sin(t * Math.PI * 2) * 0.5 * blend;
      }
    }
    camera.position.copy(pos);
    camera.lookAt(look);

    // Night-blue light low down, warm sunrise light near the summit, and a flare of gold during the finale.
    sun.color.setRGB(lerp(0.72, 1, shown), lerp(lerp(0.8, 0.82, shown), 0.74, glow), lerp(lerp(1, 0.62, shown), 0.42, glow));
    sun.intensity = lerp(1.3, 2.3, shown) + glow * 1.6;
    sky.intensity = lerp(0.9, 1.25, shown) + glow * 0.35;
    scene.fog.color.setRGB(lerp(0.043, 0.36, glow), lerp(0.063, 0.2, glow), lerp(0.15, 0.24, glow));

    renderer.render(scene, camera);

    for (const cp of checkpointLabels) {
      place(cp.el, cp.fraction);
      cp.el.classList.toggle("reached", shown >= cp.fraction - 0.004);
    }
    place(youLabel, shown);
    if (stall) {
      // An invisible click target that follows the stall on screen.
      projected.copy(stall.position).project(camera);
      const sx = ((projected.x + 1) / 2) * container.clientWidth;
      const sy = ((1 - projected.y) / 2) * container.clientHeight;
      stallHit.style.transform = `translate(${sx}px, ${sy}px)`;
      stallHit.style.visibility = projected.z < 1 ? "visible" : "hidden";
    }
    for (const other of others.values()) {
      other.shown += (other.fraction - other.shown) * 0.05;
      place(other.el, other.shown, other.nudge);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  return {
    /** fraction: 0 at the gate, 1 on the summit. */
    setProgress(fraction, { instant = false } = {}) {
      target = Math.max(0, Math.min(1, fraction));
      if (instant) shown = target;
    },
    /** Plays the finale camera sweep. summit: true for the longer, brighter version at the very top. */
    celebrate({ summit = false } = {}) {
      sweep = { startedAt: performance.now(), duration: summit ? 12000 : 7500, summit };
    },
    /** climbers: [{key, initials, color, title, fraction}] */
    setOthers(climbers) {
      const seen = new Set();
      for (const c of climbers) {
        seen.add(c.key);
        let other = others.get(c.key);
        if (!other) {
          const el = makeLabel(layer, "other3d", c.initials);
          el.querySelector("i").style.background = c.color;
          other = { el, shown: c.fraction, nudge: c.nudge ?? 0 };
          others.set(c.key, other);
        }
        other.fraction = Math.max(0, Math.min(1, c.fraction));
        other.el.title = c.title;
      }
      for (const [key, other] of others) {
        if (!seen.has(key)) {
          other.el.remove();
          others.delete(key);
        }
      }
    },
  };
}
