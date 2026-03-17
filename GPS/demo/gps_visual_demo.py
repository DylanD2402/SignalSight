#!/usr/bin/env python3
"""
SignalSight GPS Visual Demo
===========================
Graphical demo of the GPS traffic-light scanning system.

Controls
--------
  W / Up     – accelerate forward
  S / Down   – brake / reverse
  A / Left   – steer left
  D / Right  – steer right
  SPACE      – pause / resume
  R          – reset to start
  T          – toggle OSM map overlay
  + / -      – zoom in / out
  ESC / Q    – quit

After 10 s of no input the watcher returns to autonomous wandering mode.

Requirements: pygame-ce  (pip install pygame-ce)
"""

import pygame
import math
import random
import time
import threading
import urllib.request
import io
import sys
from typing import List, Optional, Tuple
from pathlib import Path

# Allow importing from the GPS package one level up
sys.path.insert(0, str(Path(__file__).parent.parent))
from traffic_light_db import TrafficLightDB, TrafficLight

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "data" / "traffic_lights.db"

# ── Simulation start (downtown Toronto) ──────────────────────────────────────
START_LAT =  45.386979
START_LON = -75.691527

# ── Physics ───────────────────────────────────────────────────────────────────
WATCHER_SPEED_MS   = 80.0 / 3.6   # m/s autonomous speed (80 km/h)
MAX_SPEED_MS       = 80.0 / 3.6   # m/s max manual (80 km/h)
ACCEL_MS2          = 4.0    # acceleration
BRAKE_MS2          = 8.0    # braking
MAX_TURN_DEG_S     = 55.0   # max yaw rate
WANDER_RADIUS_M    = 700.0  # soft pull-back from home

# ── Default scanner params ────────────────────────────────────────────────────
DEFAULT_SCAN_RADIUS  = 500.0   # metres
DEFAULT_HEADING_CONE = 90.0    # ± degrees
SCAN_HZ              = 8.0

# ── Zone thresholds (metres) ──────────────────────────────────────────────────
ZONE_IMMINENT    =  50
ZONE_NEAR        = 100
ZONE_APPROACHING = 250

# ── Render ────────────────────────────────────────────────────────────────────
DEFAULT_SCALE = 0.65     # px / m  →  500 m scan radius ≈ 325 px at 1080p
AUTO_RESUME_S = 10.0     # seconds before returning to auto-pilot
FPS = 60

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG               = (13, 15, 23)
C_GRID             = (25, 30, 48)
C_GRID_LABEL       = (44, 55, 85)

C_LIGHT_IDLE       = (50, 50, 72)
C_LIGHT_NEARBY     = (140, 60, 60)
C_LIGHT_LOCKED     = (255, 55, 55)

C_NEARBY_LINE      = (70, 75, 110)    # grey lines to nearby (non-locked) lights
C_NEARBY_LABEL     = (85, 90, 130)

C_WATCHER          = (80, 185, 255)
C_WATCHER_GLOW     = (30, 90, 190)
C_WATCHER_MANUAL   = (255, 200, 60)   # amber in manual mode

C_SCAN_FILL        = (25,  90, 200,  16)
C_SCAN_RING        = (55, 130, 255,  90)
C_CONE_FILL        = (55, 130, 255,  11)
C_CONE_EDGE        = (90, 160, 255,  65)
C_SWEEP            = (80, 180, 255,  55)

C_ZONE_FAR         = (190, 190,  50)
C_ZONE_APPROACHING = (220, 130,  25)
C_ZONE_NEAR        = (255,  70,  25)
C_ZONE_IMMINENT    = (255,  25,  25)

C_HUD_BG     = (10, 14, 28, 210)
C_HUD_BORDER = (60, 110, 200, 90)
C_HUD_LABEL  = (85, 120, 175)
C_HUD_VALUE  = (215, 235, 255)
C_HUD_TITLE  = (80, 185, 255)
C_HUD_SEP    = (40, 70, 140, 80)

C_SLIDER_TRACK = (30, 38, 65)
C_SLIDER_FILL  = (55, 120, 220)
C_SLIDER_THUMB = (100, 180, 255)

EARTH_R = 6_371_008.8

# ── Tile map ──────────────────────────────────────────────────────────────────
TILE_URL       = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_CACHE_DIR = Path(__file__).parent / "tile_cache"
TILE_DIM       = 256   # px per OSM tile


# ── Math helpers ──────────────────────────────────────────────────────────────

# haversine  →  TrafficLightDB._haversine_distance()   (called via watcher.db)
# bearing    →  TrafficLightDB._calculate_bearing()    (called via watcher.db)
# cone check →  TrafficLightDB._is_in_direction()      (called via watcher.db)

def angle_diff(a, b) -> float:
    """Signed shortest-arc difference – needed for steering interpolation (no GPS equivalent)."""
    return (a - b + 180) % 360 - 180


def offset_latlon(lat, lon, dx_m, dy_m):
    dlat = dy_m / 111_320.0
    dlon = dx_m / (111_320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def compass_label(h) -> str:
    return ["N","NE","E","SE","S","SW","W","NW","N"][round(h/45) % 8]


def zone_of(dist) -> Tuple[str, tuple]:
    if dist <= ZONE_IMMINENT:    return "IMMINENT",    C_ZONE_IMMINENT
    if dist <= ZONE_NEAR:        return "NEAR",        C_ZONE_NEAR
    if dist <= ZONE_APPROACHING: return "APPROACHING", C_ZONE_APPROACHING
    return "FAR", C_ZONE_FAR


# TrafficLightDB and TrafficLight are imported from GPS/traffic_light_db.py


# ── Tile manager ──────────────────────────────────────────────────────────────

class TileManager:
    """Fetches, caches and serves OSM raster tiles."""

    def __init__(self):
        TILE_CACHE_DIR.mkdir(exist_ok=True)
        self._mem: dict = {}      # (z,x,y) → pygame.Surface
        self._pending: set = set()
        self._lock = threading.Lock()

    # ── Coordinate helpers ────────────────────────────────────────────────────

    @staticmethod
    def lat_lon_to_tile(lat, lon, z):
        n = 2 ** z
        x = int((lon + 180) / 360 * n)
        lr = math.radians(lat)
        y = int((1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n)
        return max(0, min(n-1, x)), max(0, min(n-1, y))

    @staticmethod
    def tile_nw_lat_lon(tx, ty, z):
        """Return the lat/lon of the North-West corner of tile (tx, ty, z)."""
        n = 2 ** z
        lon = tx / n * 360 - 180
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
        return lat, lon

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, z, x, y) -> Optional[pygame.Surface]:
        key = (z, x, y)
        with self._lock:
            if key in self._mem:
                return self._mem[key]

        path = TILE_CACHE_DIR / f"{z}_{x}_{y}.png"
        if path.exists():
            try:
                surf = pygame.image.load(str(path)).convert()
                with self._lock:
                    self._mem[key] = surf
                return surf
            except Exception:
                pass

        with self._lock:
            if key not in self._pending:
                self._pending.add(key)
                threading.Thread(target=self._fetch, args=(z, x, y, path),
                                 daemon=True).start()
        return None

    def _fetch(self, z, x, y, path):
        try:
            url = TILE_URL.format(z=z, x=x, y=y)
            req = urllib.request.Request(
                url, headers={"User-Agent": "SignalSightGPSDemo/1.0 (educational)"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            path.write_bytes(data)
            surf = pygame.image.load(io.BytesIO(data)).convert()
            with self._lock:
                self._mem[(z, x, y)] = surf
                self._pending.discard((z, x, y))
        except Exception:
            with self._lock:
                self._pending.discard((z, x, y))


def _pick_zoom(scale, lat) -> int:
    """Choose OSM zoom level so tiles are roughly 300–700 px wide on screen."""
    circ_m = 40_075_000 * math.cos(math.radians(lat))
    ideal  = math.log2(circ_m * scale / TILE_DIM)
    return max(10, min(19, round(ideal)))


def draw_tiles(surf, tile_mgr, c_lat, c_lon, scale, cx, cy, win_w, win_h):
    """Blit OSM tiles that cover the current viewport, then darken for UI contrast."""
    z = _pick_zoom(scale, c_lat)
    n = 2 ** z

    # Find tile range covering the screen
    # screen corners → world offset → lat/lon
    half_w_m = (win_w / 2) / scale
    half_h_m = (win_h / 2) / scale
    tl_lat, tl_lon = offset_latlon(c_lat, c_lon, -half_w_m,  half_h_m)
    br_lat, br_lon = offset_latlon(c_lat, c_lon,  half_w_m, -half_h_m)

    tx_min, ty_min = tile_mgr.lat_lon_to_tile(tl_lat, tl_lon, z)
    tx_max, ty_max = tile_mgr.lat_lon_to_tile(br_lat, br_lon, z)
    # y increases southward in tile coords
    tx_min, tx_max = min(tx_min, tx_max), max(tx_min, tx_max)
    ty_min, ty_max = min(ty_min, ty_max), max(ty_min, ty_max)

    for tx in range(tx_min, tx_max + 1):
        for ty in range(ty_min, ty_max + 1):
            if not (0 <= tx < n and 0 <= ty < n):
                continue

            nw_lat, nw_lon = tile_mgr.tile_nw_lat_lon(tx,   ty,   z)
            se_lat, se_lon = tile_mgr.tile_nw_lat_lon(tx+1, ty+1, z)

            sx0, sy0 = w2s(nw_lat, nw_lon, c_lat, c_lon, scale, cx, cy, win_w, win_h)
            sx1, sy1 = w2s(se_lat, se_lon, c_lat, c_lon, scale, cx, cy, win_w, win_h)
            tw, th = max(1, sx1 - sx0), max(1, sy1 - sy0)

            tile = tile_mgr.get(z, tx, ty)
            if tile:
                scaled = pygame.transform.scale(tile, (tw, th))
                surf.blit(scaled, (sx0, sy0))
            else:
                pygame.draw.rect(surf, (22, 26, 38), (sx0, sy0, tw, th))

    # Dark tint so the UI / lights remain legible over the map
    tint = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    tint.fill((0, 5, 18, 155))
    surf.blit(tint, (0, 0))


# ── Watcher ───────────────────────────────────────────────────────────────────

class Watcher:
    def __init__(self, lat, lon, db: TrafficLightDB):
        self.lat = lat; self.lon = lon
        self.home_lat = lat; self.home_lon = lon
        self.heading = random.uniform(0, 360)
        self._target_heading = self.heading
        self.speed = WATCHER_SPEED_MS

        # Real TrafficLightDB instance (from GPS/traffic_light_db.py)
        self.db = db

        # Scanner params (driven by sliders)
        self.scan_radius  = DEFAULT_SCAN_RADIUS
        self.heading_cone = DEFAULT_HEADING_CONE

        # Results from TrafficLightDB queries
        self.nearby: List[TrafficLight] = []           # in-cone results
        self.locked: Optional[TrafficLight] = None     # nearest in cone
        self.viewport_lights: List[tuple] = []         # (id, lat, lon) for rendering

        self._dir_timer  = 0.0
        self._scan_timer = 0.0
        self._sweep_angle = 0.0
        self._pulse = 0.0

        # Manual control
        self.manual = False
        self._last_input = 0.0

    # ── update ────────────────────────────────────────────────────────────────

    def update(self, dt, now, keys):
        # ── Input detection ───────────────────────────────────────────────────
        left  = keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]
        fwd   = keys[pygame.K_w] or keys[pygame.K_UP]
        back  = keys[pygame.K_s] or keys[pygame.K_DOWN]

        any_input = left or right or fwd or back
        if any_input:
            self.manual = True
            self._last_input = now

        if self.manual and (now - self._last_input) > AUTO_RESUME_S:
            self.manual = False
            self._target_heading = self.heading
            self._dir_timer = 0.0

        # ── Steering / motion ─────────────────────────────────────────────────
        if self.manual:
            turn_rate = MAX_TURN_DEG_S * ((-1 if left else 0) + (1 if right else 0))
            self.heading = (self.heading + turn_rate * dt) % 360

            boost = keys[pygame.K_LSHIFT]
            ctrl  = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
            if ctrl:
                # Hard brake at 20× rate, stop at zero
                decel = BRAKE_MS2 * 20 * dt
                if abs(self.speed) <= decel:
                    self.speed = 0.0
                else:
                    self.speed -= math.copysign(decel, self.speed)
            elif fwd:
                if boost:
                    self.speed += ACCEL_MS2 * 4 * dt          # uncapped
                elif self.speed > MAX_SPEED_MS:
                    self.speed = max(MAX_SPEED_MS,             # bleed off boost speed
                                     self.speed - ACCEL_MS2 * 2 * dt)
                else:
                    self.speed = min(MAX_SPEED_MS, self.speed + ACCEL_MS2 * dt)
            elif back:
                self.speed = max(-MAX_SPEED_MS * 0.5, self.speed - BRAKE_MS2 * 3 * dt)
            else:
                # coast to zero
                decel = BRAKE_MS2 * 0.4 * dt
                if abs(self.speed) <= decel:
                    self.speed = 0.0
                else:
                    self.speed -= math.copysign(decel, self.speed)
        else:
            # Autonomous wander
            self._dir_timer -= dt
            if self._dir_timer <= 0:
                dist_home = self.db._haversine_distance(self.lat, self.lon, self.home_lat, self.home_lon)
                if dist_home > WANDER_RADIUS_M * 0.82:
                    home_brng = self.db._calculate_bearing(self.lat, self.lon, self.home_lat, self.home_lon)
                    self._target_heading = (home_brng + random.gauss(0, 18)) % 360
                else:
                    self._target_heading = (self.heading + random.gauss(0, 35)) % 360
                self._dir_timer = random.uniform(3.5, 8.0)

            diff = angle_diff(self._target_heading, self.heading)
            step = max(-MAX_TURN_DEG_S*dt, min(MAX_TURN_DEG_S*dt, diff))
            self.heading = (self.heading + step) % 360
            self.speed = WATCHER_SPEED_MS

        # ── Move ──────────────────────────────────────────────────────────────
        if self.speed != 0:
            h = math.radians(self.heading)
            dx = self.speed * math.sin(h) * dt
            dy = self.speed * math.cos(h) * dt
            self.lat, self.lon = offset_latlon(self.lat, self.lon, dx, dy)

        # ── Scan ──────────────────────────────────────────────────────────────
        self._scan_timer += dt
        if self._scan_timer >= 1.0 / SCAN_HZ:
            self._do_scan(); self._scan_timer = 0.0

        # ── Animations ────────────────────────────────────────────────────────
        self._sweep_angle = (self._sweep_angle + 90*dt) % 360
        self._pulse = (self._pulse + dt*2.5) % (2*math.pi)

    def _do_scan(self):
        # ── Cone scan via TrafficLightDB.get_nearby_lights_fast() ─────────────
        # Uses the real bounding-box + Haversine + heading-cone implementation
        self.nearby = self.db.get_nearby_lights_fast(
            self.lat, self.lon,
            radius_m=self.scan_radius,
            heading=self.heading,
            heading_cone=self.heading_cone,
        )
        self.locked = self.nearby[0] if self.nearby else None

        # ── Viewport lights for rendering idle grey dots ───────────────────────
        # Wider bbox so dots appear beyond the scan circle too
        view_r = max(self.scan_radius * 3, 1500)
        cos_lat = math.cos(math.radians(self.lat))
        dlat = view_r / 111_320.0
        dlon = view_r / (111_320.0 * cos_lat)
        self.viewport_lights = self.db.get_lights_in_bbox(
            self.lat - dlat, self.lat + dlat,
            self.lon - dlon, self.lon + dlon,
        )


# ── Slider ────────────────────────────────────────────────────────────────────

class Slider:
    def __init__(self, x, y, w, h, lo, hi, val, label, fmt="{:.0f}"):
        self.rect  = pygame.Rect(x, y, w, h)
        self.lo    = lo; self.hi = hi; self.value = val
        self.label = label; self.fmt = fmt
        self.dragging = False

    def reposition(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.rect.h)

    def _t(self): return (self.value - self.lo) / (self.hi - self.lo)

    def handle_event(self, event) -> bool:
        """Returns True if the slider consumed the event."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Expand hit area slightly
            hit = self.rect.inflate(0, 16)
            if hit.collidepoint(event.pos):
                self.dragging = True
                self._set_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(event.pos[0])
            return True
        return False

    def _set_from_x(self, mx):
        t = (mx - self.rect.left) / max(1, self.rect.width)
        t = max(0.0, min(1.0, t))
        self.value = self.lo + t * (self.hi - self.lo)

    def draw(self, surf, font):
        r = self.rect
        # Track
        pygame.draw.rect(surf, C_SLIDER_TRACK, r, border_radius=4)
        # Fill
        fw = int(r.width * self._t())
        if fw > 0:
            pygame.draw.rect(surf, C_SLIDER_FILL,
                             pygame.Rect(r.left, r.top, fw, r.height), border_radius=4)
        # Border
        pygame.draw.rect(surf, C_HUD_BORDER, r, 1, border_radius=4)
        # Thumb
        tx = r.left + int(r.width * self._t())
        pygame.draw.circle(surf, C_SLIDER_THUMB, (tx, r.centery), 8)
        pygame.draw.circle(surf, C_HUD_VALUE,    (tx, r.centery), 8, 1)
        # Label
        lbl = f"{self.label}: {self.fmt.format(self.value)}"
        t = font.render(lbl, True, C_HUD_VALUE)
        surf.blit(t, (r.left, r.top - 17))


# ── Coordinate transform ──────────────────────────────────────────────────────

def w2s(lat, lon, c_lat, c_lon, scale, cx, cy, win_w, win_h):
    dx = (lon - c_lon) * 111_320.0 * math.cos(math.radians(c_lat))
    dy = (lat - c_lat) * 111_320.0
    return int(cx + dx*scale), int(cy - dy*scale)


def on_screen(sx, sy, win_w, win_h, margin=80):
    return -margin <= sx <= win_w+margin and -margin <= sy <= win_h+margin


# ── Drawing ───────────────────────────────────────────────────────────────────

def draw_grid(surf, c_lat, c_lon, scale, cx, cy, win_w, win_h, font):
    span_m = win_w / scale
    raw = span_m / 8
    mag = 10 ** math.floor(math.log10(max(raw, 1)))
    step_m = next((mag*m for m in [1,2,5,10] if mag*m >= raw*0.8), mag*10)
    n = 16
    for i in range(-n, n+1):
        lat_l = c_lat + (i*step_m) / 111_320.0
        _, y0  = w2s(lat_l, c_lon, c_lat, c_lon, scale, cx, cy, win_w, win_h)
        if 0 <= y0 <= win_h:
            pygame.draw.line(surf, C_GRID, (0, y0), (win_w, y0), 1)
            surf.blit(font.render(f"{lat_l:.4f}°", True, C_GRID_LABEL), (4, y0+2))

        lon_l = c_lon + (i*step_m) / (111_320.0*math.cos(math.radians(c_lat)))
        x1, _  = w2s(c_lat, lon_l, c_lat, c_lon, scale, cx, cy, win_w, win_h)
        if 0 <= x1 <= win_w:
            pygame.draw.line(surf, C_GRID, (x1, 0), (x1, win_h), 1)
            surf.blit(font.render(f"{lon_l:.4f}°", True, C_GRID_LABEL), (x1+2, win_h-14))


def _heading_to_screen_vec(heading_deg):
    """Return (fx, fy) unit vector in SCREEN space (y-down) for geographic heading."""
    h = math.radians(heading_deg)
    # geographic heading 0=N=up on screen, 90=E=right
    return math.sin(h), -math.cos(h)   # (sin, -cos) because screen-y is inverted


def draw_scan_area(surf, watcher, scale, cx, cy, win_w, win_h):
    r = int(watcher.scan_radius * scale)
    ov = pygame.Surface((win_w, win_h), pygame.SRCALPHA)

    # Full scan circle
    pygame.draw.circle(ov, C_SCAN_FILL, (cx, cy), r)
    pygame.draw.circle(ov, C_SCAN_RING, (cx, cy), r, 2)

    # Heading cone ─────────────────────────────────────────────────────────────
    # Forward direction in screen space (y-down): (sin(h), -cos(h))
    # We spread the cone ± heading_cone degrees around the forward direction.
    # To do this cleanly we use rotation of the forward vector.
    h = math.radians(watcher.heading)
    fwd_x = math.sin(h)
    fwd_y = -math.cos(h)   # screen y is down, so north = -y

    cone_half = math.radians(watcher.heading_cone)
    steps = 44
    pts = [(cx, cy)]
    for k in range(steps + 1):
        a = -cone_half + (2*cone_half) * k / steps
        # Rotate forward vector by 'a' (counter-clockwise in standard math,
        # which is CLOCKWISE in screen space because y is down – matching
        # the geographic "right is positive angle" convention).
        ca, sa = math.cos(a), math.sin(a)
        dx_ = fwd_x*ca - fwd_y*sa
        dy_ = fwd_x*sa + fwd_y*ca
        pts.append((int(cx + r*dx_), int(cy + r*dy_)))

    pygame.draw.polygon(ov, C_CONE_FILL, pts)
    pygame.draw.line(ov, C_CONE_EDGE, (cx, cy), pts[1],  2)
    pygame.draw.line(ov, C_CONE_EDGE, (cx, cy), pts[-1], 2)
    pygame.draw.lines(ov, C_CONE_EDGE, False, pts[1:], 1)

    # Radar sweep (stays within cone) ─────────────────────────────────────────
    sweep_hdg = watcher._sweep_angle % 360
    if watcher.db._is_in_direction(sweep_hdg, watcher.heading, watcher.heading_cone):
        sh = math.radians(watcher._sweep_angle)
        sx_e = int(cx + r * math.sin(sh))
        sy_e = int(cy - r * math.cos(sh))
        pygame.draw.line(ov, C_SWEEP, (cx, cy), (sx_e, sy_e), 2)
        for trail in range(1, 5):
            t_hdg = (watcher._sweep_angle - trail*5) % 360
            if not watcher.db._is_in_direction(t_hdg, watcher.heading, watcher.heading_cone):
                break
            th = math.radians(watcher._sweep_angle - trail*5)
            alpha = max(0, C_SWEEP[3] - trail*13)
            pygame.draw.line(ov, (*C_SWEEP[:3], alpha),
                             (cx, cy),
                             (int(cx + r*math.sin(th)), int(cy - r*math.cos(th))), 1)

    surf.blit(ov, (0, 0))


def draw_lights_and_lines(surf, watcher, scale, cx, cy, win_w, win_h, font_small):
    """Draw all lights; draw grey lines to nearby (non-locked), coloured line to locked."""
    # Build id sets from TrafficLight objects returned by TrafficLightDB
    nearby_ids = {lt.id for lt in watcher.nearby}
    locked_id  = watcher.locked.id if watcher.locked else None

    # ── Grey lines to nearby in-cone lights (non-locked) ─────────────────────
    line_ov = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    for lt in watcher.nearby:
        if lt.id == locked_id:
            continue
        sx, sy = w2s(lt.lat, lt.lon, watcher.lat, watcher.lon,
                     scale, cx, cy, win_w, win_h)
        if not on_screen(sx, sy, win_w, win_h):
            continue
        pygame.draw.line(line_ov, (*C_NEARBY_LINE, 120), (cx, cy), (sx, sy), 1)
        mx, my = int((cx+sx)/2), int((cy+sy)/2)
        lbl = font_small.render(f"{lt.distance:.0f}m", True, C_NEARBY_LABEL)
        line_ov.blit(lbl, lbl.get_rect(center=(mx, my)))
    surf.blit(line_ov, (0, 0))

    # ── Coloured dashed line to locked target ─────────────────────────────────
    if watcher.locked:
        lt = watcher.locked
        tx, ty = w2s(lt.lat, lt.lon, watcher.lat, watcher.lon,
                     scale, cx, cy, win_w, win_h)
        zname, zcol = zone_of(lt.distance)
        if zname == "IMMINENT":
            flash = (math.sin(watcher._pulse) + 1) / 2
            zcol  = (int(zcol[0]*(0.55+0.45*flash)), zcol[1], zcol[2])

        dl = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
        ddx, ddy = tx-cx, ty-cy
        dist_px = math.hypot(ddx, ddy)
        if dist_px > 1:
            n_seg = max(1, int(dist_px/14))
            for k in range(n_seg):
                if k % 2: continue
                t0 = k/n_seg; t1 = min(1.0,(k+0.65)/n_seg)
                pygame.draw.line(dl, (*zcol, 160),
                                 (int(cx+ddx*t0), int(cy+ddy*t0)),
                                 (int(cx+ddx*t1), int(cy+ddy*t1)), 2)
        surf.blit(dl, (0, 0))

    # ── Light nodes ───────────────────────────────────────────────────────────
    # viewport_lights is List[Tuple[id, lat, lon]] from TrafficLightDB.get_lights_in_bbox()
    for (lid, llat, llon) in watcher.viewport_lights:
        sx, sy = w2s(llat, llon, watcher.lat, watcher.lon,
                     scale, cx, cy, win_w, win_h)
        if not on_screen(sx, sy, win_w, win_h):
            continue
        if lid == locked_id:
            pygame.draw.circle(surf, C_LIGHT_LOCKED, (sx, sy), 7)
            pygame.draw.circle(surf, C_LIGHT_LOCKED, (sx, sy), 9, 1)
        elif lid in nearby_ids:
            pygame.draw.circle(surf, C_LIGHT_NEARBY, (sx, sy), 5)
        else:
            pygame.draw.circle(surf, C_LIGHT_IDLE, (sx, sy), 2)


def draw_lockon_reticle(surf, watcher, target, scale, cx, cy, win_w, win_h, font_small):
    """Animated corner-bracket reticle + zone badge on the locked target."""
    tx, ty = w2s(target.lat, target.lon, watcher.lat, watcher.lon,
                 scale, cx, cy, win_w, win_h)
    zname, zcol = zone_of(target.distance)
    if zname == "IMMINENT":
        flash = (math.sin(watcher._pulse) + 1) / 2
        zcol  = (int(zcol[0]*(0.55+0.45*flash)), zcol[1], zcol[2])

    ps = 18 + int(3*math.sin(watcher._pulse))
    arm, thick = 9, 2
    for sx_, sy_ in [(-1,-1),(1,-1),(1,1),(-1,1)]:
        ox, oy = tx+sx_*ps, ty+sy_*ps
        pygame.draw.line(surf, zcol, (ox,oy), (ox-sx_*arm, oy),   thick)
        pygame.draw.line(surf, zcol, (ox,oy), (ox, oy-sy_*arm),   thick)
    pygame.draw.circle(surf, zcol, (tx, ty), 4)

    # Badge
    label = f"  {target.distance:.0f} m  ·  {zname}  "
    badge = font_small.render(label, True, zcol)
    br = badge.get_rect(center=(tx, ty - ps - 14))
    bg = pygame.Surface((br.width+8, br.height+4), pygame.SRCALPHA)
    bg.fill((8, 12, 25, 175))
    pygame.draw.rect(bg, (*zcol, 70), (0,0,bg.get_width(),bg.get_height()), 1)
    surf.blit(bg, (br.left-4, br.top-2))
    surf.blit(badge, br)


def draw_watcher(surf, watcher, cx, cy, win_w, win_h):
    h     = math.radians(watcher.heading)
    color = C_WATCHER_MANUAL if watcher.manual else C_WATCHER
    size  = 15

    tip_x = int(cx + size*math.sin(h))
    tip_y = int(cy - size*math.cos(h))
    la = h + math.radians(145); ra = h - math.radians(145)
    lx = int(cx + size*0.55*math.sin(la)); ly = int(cy - size*0.55*math.cos(la))
    rx = int(cx + size*0.55*math.sin(ra)); ry = int(cy - size*0.55*math.cos(ra))

    glow = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    for alpha in [20, 45, 75]:
        pygame.draw.polygon(glow, (*C_WATCHER_GLOW, alpha),
                            [(tip_x,tip_y),(lx,ly),(rx,ry)])
    surf.blit(glow, (0, 0))
    pygame.draw.polygon(surf, color, [(tip_x,tip_y),(lx,ly),(rx,ry)])
    pygame.draw.circle(surf, (230, 245, 255), (cx, cy), 3)


def draw_hud(surf, watcher, scale, font_title, font, win_w, win_h):
    W, H = 275, 265
    x, y = 18, 18

    panel = pygame.Surface((W, H), pygame.SRCALPHA)
    panel.fill(C_HUD_BG)
    pygame.draw.rect(panel, C_HUD_BORDER, (0,0,W,H), 1)
    surf.blit(panel, (x, y))

    surf.blit(font_title.render("GPS  TRAFFIC  SCANNER", True, C_HUD_TITLE), (x+10, y+10))
    pygame.draw.line(surf, C_HUD_SEP, (x+8, y+30), (x+W-8, y+30), 1)

    mode_col = C_WATCHER_MANUAL if watcher.manual else (80, 180, 80)
    mode_txt = "MANUAL" if watcher.manual else "AUTO"
    surf.blit(font.render(f"MODE: {mode_txt}", True, mode_col), (x+10, y+36))

    if watcher.manual:
        left_s = time.time() - watcher._last_input
        rem    = max(0.0, AUTO_RESUME_S - left_s)
        surf.blit(font.render(f"auto in {rem:.1f}s", True, C_HUD_LABEL), (x+140, y+36))

    pygame.draw.line(surf, C_HUD_SEP, (x+8, y+54), (x+W-8, y+54), 1)

    fields = [
        ("LAT",         f"{watcher.lat:+.6f}°"),
        ("LON",         f"{watcher.lon:+.6f}°"),
        ("HEADING",     f"{watcher.heading:05.1f}°  {compass_label(watcher.heading)}"),
        ("SPEED",       f"{watcher.speed*3.6:.1f} km/h"),
        ("SCAN RADIUS", f"{watcher.scan_radius:.0f} m"),
        ("CONE",        f"±{watcher.heading_cone:.0f}°"),
        ("IN CONE",     str(len(watcher.nearby))),
    ]
    yy = y + 62
    for lbl, val in fields:
        surf.blit(font.render(lbl+":", True, C_HUD_LABEL),  (x+10,  yy))
        surf.blit(font.render(val,     True, C_HUD_VALUE), (x+145, yy))
        yy += 22

    pygame.draw.line(surf, C_HUD_SEP, (x+8, yy+1), (x+W-8, yy+1), 1)
    yy += 8
    if watcher.locked:
        lt = watcher.locked; zn, zc = zone_of(lt.distance)
        surf.blit(font.render("LOCKED ON:", True, C_HUD_LABEL), (x+10, yy)); yy += 22
        surf.blit(font.render(f"  {lt.distance:.0f} m  [{zn}]", True, zc), (x+10, yy))
    else:
        surf.blit(font.render("NO TARGET IN CONE", True, C_HUD_LABEL), (x+10, yy))


def draw_compass(surf, heading, cx, cy, r, font):
    bg = pygame.Surface((r*2+12, r*2+12), pygame.SRCALPHA)
    cc = (r+6, r+6)
    pygame.draw.circle(bg, C_HUD_BG,     cc, r)
    pygame.draw.circle(bg, C_HUD_BORDER, cc, r, 1)
    for ang, lbl, col in [(0,"N",(200,70,70)),(90,"E",C_HUD_LABEL),(180,"S",C_HUD_LABEL),(270,"W",C_HUD_LABEL)]:
        a = math.radians(ang - 90)
        t = font.render(lbl, True, col)
        bg.blit(t, t.get_rect(center=(int(cc[0]+(r-13)*math.cos(a)), int(cc[1]+(r-13)*math.sin(a)))))
    h_rad = math.radians(heading - 90)
    nx = int(cc[0]+(r-7)*math.cos(h_rad)); ny = int(cc[1]+(r-7)*math.sin(h_rad))
    pygame.draw.line(bg, C_WATCHER, cc, (nx, ny), 2)
    pygame.draw.circle(bg, C_WATCHER, cc, 3)
    surf.blit(bg, (cx-r-6, cy-r-6))


# ── Main ──────────────────────────────────────────────────────────────────────

def make_sliders(win_w, win_h):
    """Create the two sliders, positioned at the bottom of the screen."""
    pad  = 20
    sw   = min(300, (win_w - pad*4) // 2)
    sy   = win_h - 55
    s1 = Slider(pad,      sy, sw, 10, 100,  1000, DEFAULT_SCAN_RADIUS,  "Scan radius", "{:.0f} m")
    s2 = Slider(pad*2+sw, sy, sw, 10,  10,   180, DEFAULT_HEADING_CONE, "Cone ±°",     "{:.0f}°")
    return s1, s2


def main():
    pygame.init()
    win_w, win_h = 1920, 1080
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption("SignalSight  ·  GPS Visual Demo")
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("monospace", 16, bold=True)
    font       = pygame.font.SysFont("monospace", 14)
    font_small = pygame.font.SysFont("monospace", 12)

    print("Loading traffic lights …")
    db      = TrafficLightDB(str(DB_PATH))
    watcher = Watcher(START_LAT, START_LON, db)
    watcher._do_scan()
    stats = db.get_stats()
    print(f"[INFO] DB: {stats['total_lights']} lights total")

    scale    = DEFAULT_SCALE
    paused   = False
    show_map = True
    cx, cy   = win_w // 2, win_h // 2
    tile_mgr = TileManager()

    s_radius, s_cone = make_sliders(win_w, win_h)

    print("Ready.  WASD/Arrows=drive  SPACE=pause  R=reset  +/-=zoom  ESC=quit")

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        now = time.time()
        keys = pygame.key.get_pressed()

        # ── Events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return

            if event.type == pygame.VIDEORESIZE:
                win_w, win_h = event.w, event.h
                cx, cy = win_w // 2, win_h // 2
                screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                s_radius, s_cone = make_sliders(win_w, win_h)

            # Let sliders consume mouse events first
            if s_radius.handle_event(event) or s_cone.handle_event(event):
                continue

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    pygame.quit(); return
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    scale = min(scale * 1.2, 5.0)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    scale = max(scale / 1.2, 0.05)
                elif event.key == pygame.K_t:
                    show_map = not show_map
                elif event.key == pygame.K_r:
                    watcher.lat = START_LAT; watcher.lon = START_LON
                    watcher.heading = random.uniform(0, 360)
                    watcher.speed = WATCHER_SPEED_MS; watcher.manual = False
                    watcher._do_scan()

        # ── Push slider values into watcher ───────────────────────────────────
        watcher.scan_radius  = s_radius.value
        watcher.heading_cone = s_cone.value

        # ── Simulate ──────────────────────────────────────────────────────────
        if not paused:
            watcher.update(dt, now, keys)

        # ── Render ────────────────────────────────────────────────────────────
        screen.fill(C_BG)

        if show_map:
            draw_tiles(screen, tile_mgr, watcher.lat, watcher.lon,
                       scale, cx, cy, win_w, win_h)

        draw_grid(screen, watcher.lat, watcher.lon, scale, cx, cy, win_w, win_h, font_small)
        draw_scan_area(screen, watcher, scale, cx, cy, win_w, win_h)
        draw_lights_and_lines(screen, watcher, scale, cx, cy, win_w, win_h, font_small)

        if watcher.locked:
            draw_lockon_reticle(screen, watcher, watcher.locked,
                                scale, cx, cy, win_w, win_h, font_small)

        draw_watcher(screen, watcher, cx, cy, win_w, win_h)
        draw_hud(screen, watcher, scale, font_title, font_small, win_w, win_h)
        draw_compass(screen, watcher.heading, win_w-68, 68, 50, font_small)

        # ── Sliders panel ─────────────────────────────────────────────────────
        sp_w = (s_cone.rect.right - s_radius.rect.left) + 40
        sp_h = 70
        sp_x = s_radius.rect.left - 20
        sp_y = win_h - 75
        sp = pygame.Surface((sp_w, sp_h), pygame.SRCALPHA)
        sp.fill(C_HUD_BG)
        pygame.draw.rect(sp, C_HUD_BORDER, (0,0,sp_w,sp_h), 1)
        screen.blit(sp, (sp_x, sp_y))
        s_radius.draw(screen, font_small)
        s_cone.draw(screen, font_small)

        # ── Pause overlay ─────────────────────────────────────────────────────
        if paused:
            ov = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
            ov.fill((0,0,0,70)); screen.blit(ov, (0,0))
            pt = font_title.render("  PAUSED  –  SPACE to resume  ", True, (200,210,255))
            pr = pt.get_rect(center=(win_w//2, win_h//2))
            bg2 = pygame.Surface((pr.width+20, pr.height+10), pygame.SRCALPHA)
            bg2.fill((10,15,40,200)); screen.blit(bg2, (pr.left-10, pr.top-5))
            screen.blit(pt, pr)

        # FPS
        screen.blit(font_small.render(f"{clock.get_fps():.0f} fps", True, C_GRID_LABEL),
                    (win_w-52, win_h-16))

        pygame.display.flip()


if __name__ == "__main__":
    main()
