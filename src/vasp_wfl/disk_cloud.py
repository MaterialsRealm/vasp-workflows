"""Static disk-packing visualization for label tallies."""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


DEFAULT_PALETTE = (
    "#1b9e77",
    "#d95f02",
    "#7570b3",
    "#e7298a",
    "#66a61e",
    "#e6ab02",
    "#386cb0",
)


@dataclass(frozen=True)
class DiskCloudParams:
    """Parameters controlling disk sizes, packing, and Morse relaxation."""

    width: int = 1800
    height: int = 1200
    sphere_rx: float = 840
    sphere_ry: float = 560
    padding: float = 22
    gap: float = 1.0
    min_radius: float = 7
    max_radius: float = 163
    radius_exponent: float = 1.45
    min_font_size: float = 11
    max_font_size: float = 85
    font_exponent: float = 1.25
    font_radius_fraction: float = 0.88
    inner_target_fraction: float = 0.07
    outer_target_fraction: float = 0.95
    shell_exponent: float = 0.7
    spiral_step: float = 5
    morse_alpha: float = 3.2
    morse_force_scale: float = 0.32
    morse_cutoff_multiplier: float = 3.2
    morse_force_min: float = -2.0
    morse_force_max: float = 8.0
    shell_pull: float = 0.0028
    damping: float = 0.78
    relaxation_steps: int = 720
    projection_passes_per_step: int = 2
    final_projection_steps: int = 240
    compact_steps: int = 90
    compact_bisection_steps: int = 18
    palette: tuple[str, ...] = DEFAULT_PALETTE

    @property
    def center_x(self) -> float:
        return self.width / 2

    @property
    def center_y(self) -> float:
        return self.height / 2


@dataclass
class Disk:
    """Packed disk with label metadata."""

    label: str
    value: int
    normalized_value: float
    target_fraction: float
    target_angle: float
    radius: float
    font_size: float
    color: str
    x: float = 0
    y: float = 0


@dataclass
class DiskCloudLayout:
    """Packed disk layout and metadata."""

    disks: list[Disk]
    params: DiskCloudParams
    radius_scale: float
    max_overlap: float = 0
    min_clearance: float = 0
    metadata: dict[str, float | int] = field(default_factory=dict)


def normalized_log_value(value: int, min_value: int, max_value: int) -> float:
    """Normalize a positive tally to [0, 1] on a log scale."""
    if max_value == min_value:
        return 1.0
    return (math.log(value) - math.log(min_value)) / (math.log(max_value) - math.log(min_value))


def build_disks(
    tallies: Mapping[str, int],
    params: DiskCloudParams,
    *,
    radius_scale: float = 1.0,
) -> list[Disk]:
    """Build unpacked disks from a `{label: tally}` mapping."""
    positive = {str(label): int(value) for label, value in tallies.items() if int(value) > 0}
    if not positive:
        msg = "At least one positive tally is required."
        raise ValueError(msg)

    min_value = min(positive.values())
    max_value = max(positive.values())
    radius_range = params.max_radius - params.min_radius
    font_range = params.max_font_size - params.min_font_size
    golden_angle = math.pi * (3 - math.sqrt(5))
    ranked = sorted(positive.items(), key=lambda item: item[1], reverse=True)

    disks: list[Disk] = []
    for index, (label, value) in enumerate(ranked):
        normalized = normalized_log_value(value, min_value, max_value)
        radius = (params.min_radius + normalized**params.radius_exponent * radius_range) * radius_scale
        font_size = min(
            radius * params.font_radius_fraction,
            params.min_font_size + normalized**params.font_exponent * font_range,
        )
        target_fraction = params.inner_target_fraction + (
            (1 - normalized) ** params.shell_exponent
        ) * (params.outer_target_fraction - params.inner_target_fraction)
        disks.append(
            Disk(
                label=label,
                value=value,
                normalized_value=normalized,
                target_fraction=target_fraction,
                target_angle=index * golden_angle,
                radius=radius,
                font_size=font_size,
                color=params.palette[index % len(params.palette)],
            )
        )
    return disks


def disk_in_bounds(x: float, y: float, radius: float, params: DiskCloudParams) -> bool:
    """Return whether a disk is inside the sphere-projected ellipse."""
    rx = max(1.0, params.sphere_rx - radius - params.padding)
    ry = max(1.0, params.sphere_ry - radius - params.padding)
    return ((x - params.center_x) / rx) ** 2 + ((y - params.center_y) / ry) ** 2 <= 1


def clamp_disk_to_sphere(disk: Disk, params: DiskCloudParams) -> None:
    """Project a disk center back inside the sphere-projected ellipse."""
    rx = max(1.0, params.sphere_rx - disk.radius - params.padding)
    ry = max(1.0, params.sphere_ry - disk.radius - params.padding)
    dx = disk.x - params.center_x
    dy = disk.y - params.center_y
    norm = math.hypot(dx / rx, dy / ry)
    if norm <= 1:
        return
    disk.x = params.center_x + dx / norm
    disk.y = params.center_y + dy / norm


def candidate_points(params: DiskCloudParams) -> list[tuple[float, float]]:
    """Generate deterministic candidate centers from the sphere center outward."""
    max_radius = math.hypot(params.width, params.height)
    step = max(1.0, params.spiral_step)
    points = [(params.center_x, params.center_y)]
    for radius in range(int(step), int(max_radius), int(step)):
        samples = max(24, int((2 * math.pi * radius) / step))
        for sample in range(samples):
            angle = sample * 2 * math.pi / samples + radius * 0.011
            points.append(
                (
                    params.center_x + radius * math.cos(angle),
                    params.center_y + radius * math.sin(angle),
                )
            )
    return points


def overlaps_placed(
    x: float, y: float, radius: float, placed: list[Disk], params: DiskCloudParams
) -> bool:
    """Return whether a candidate disk overlaps already placed disks."""
    for disk in placed:
        min_distance = radius + disk.radius + params.gap
        if (x - disk.x) ** 2 + (y - disk.y) ** 2 < min_distance**2:
            return True
    return False


def target_point(disk: Disk, params: DiskCloudParams) -> tuple[float, float]:
    """Return the disk's count-ranked shell target point."""
    target_x = (
        params.center_x
        + math.cos(disk.target_angle) * disk.target_fraction * (params.sphere_rx - disk.radius)
    )
    target_y = (
        params.center_y
        + math.sin(disk.target_angle) * disk.target_fraction * (params.sphere_ry - disk.radius)
    )
    return target_x, target_y


def placement_score(x: float, y: float, disk: Disk, params: DiskCloudParams) -> float:
    """Score candidate placement by target shell, target angle, and compactness."""
    normalized_radius = math.hypot(
        (x - params.center_x) / params.sphere_rx,
        (y - params.center_y) / params.sphere_ry,
    )
    target_x, target_y = target_point(disk, params)
    shell_score = (normalized_radius - disk.target_fraction) ** 2 * 1_000_000
    angle_score = (x - target_x) ** 2 + (y - target_y) ** 2
    center_score = (x - params.center_x) ** 2 + (y - params.center_y) ** 2
    return shell_score + angle_score * 0.06 + center_score * 0.001


def initial_pack(disks: list[Disk], params: DiskCloudParams) -> bool:
    """Place disks greedily without overlap."""
    placed: list[Disk] = []
    points = candidate_points(params)
    for disk in disks:
        best: tuple[float, float] | None = None
        best_score = float("inf")
        for x, y in points:
            if not disk_in_bounds(x, y, disk.radius, params):
                continue
            if overlaps_placed(x, y, disk.radius, placed, params):
                continue
            score = placement_score(x, y, disk, params)
            if score < best_score:
                best = (x, y)
                best_score = score
        if best is None:
            return False
        disk.x, disk.y = best
        placed.append(disk)
    return True


def can_move_disk(disk: Disk, x: float, y: float, disks: list[Disk], params: DiskCloudParams) -> bool:
    """Return whether moving one disk to `(x, y)` preserves constraints."""
    if not disk_in_bounds(x, y, disk.radius, params):
        return False
    for other in disks:
        if other is disk:
            continue
        min_distance = disk.radius + other.radius + params.gap
        if (x - other.x) ** 2 + (y - other.y) ** 2 < min_distance**2:
            return False
    return True


def compact_toward_targets(disks: list[Disk], params: DiskCloudParams) -> None:
    """Move disks toward count-ranked shell targets without crossing other disks."""
    for _ in range(params.compact_steps):
        moved = 0.0
        for disk in sorted(disks, key=lambda item: item.radius):
            x = disk.x
            y = disk.y
            target_x, target_y = target_point(disk, params)
            dx = target_x - x
            dy = target_y - y
            if dx * dx + dy * dy < 1:
                continue
            lo = 0.0
            hi = 1.0
            for _ in range(params.compact_bisection_steps):
                mid = (lo + hi) / 2
                nx = x + dx * mid
                ny = y + dy * mid
                if can_move_disk(disk, nx, ny, disks, params):
                    lo = mid
                else:
                    hi = mid
            if lo > 0:
                disk.x = x + dx * lo
                disk.y = y + dy * lo
                moved += math.hypot(disk.x - x, disk.y - y)
        if moved < 0.01:
            break


def morse_signed_force(distance: float, equilibrium_distance: float, alpha: float) -> float:
    """Return a signed Morse force coefficient, proportional to `-dU/dr`.

    Let `delta = distance / equilibrium_distance - 1` and
    `U(delta) = (1 - exp(-alpha * delta))^2`.
    The vector update uses this coefficient as repulsive when positive and
    attractive when negative.
    """
    delta = distance / equilibrium_distance - 1.0
    exp_term = math.exp(max(-5.5, min(5.5, -alpha * delta)))
    return exp_term * exp_term - exp_term


def project_overlaps(disks: list[Disk], params: DiskCloudParams, *, strength: float = 0.8) -> float:
    """Project overlapping disks apart and return the maximum overlap."""
    max_overlap = 0.0
    for i, first in enumerate(disks):
        for j in range(i + 1, len(disks)):
            second = disks[j]
            dx = second.x - first.x
            dy = second.y - first.y
            distance = math.hypot(dx, dy)
            if distance < 1e-6:
                angle = (i * 41 + j * 19) * math.pi / 180
                dx = math.cos(angle)
                dy = math.sin(angle)
                distance = 1.0
            equilibrium = first.radius + second.radius + params.gap
            overlap = equilibrium - distance
            if overlap <= 0:
                continue
            ux = dx / distance
            uy = dy / distance
            correction = overlap * strength
            first.x -= ux * correction * 0.5
            first.y -= uy * correction * 0.5
            second.x += ux * correction * 0.5
            second.y += uy * correction * 0.5
            max_overlap = max(max_overlap, overlap)
    for disk in disks:
        clamp_disk_to_sphere(disk, params)
    return max_overlap


def relax_with_morse_forces(disks: list[Disk], params: DiskCloudParams) -> None:
    """Relax disks with Morse pair forces and count-ranked shell targets."""
    velocities = {id(disk): [0.0, 0.0] for disk in disks}
    for iteration in range(params.relaxation_steps):
        for disk in disks:
            target_x, target_y = target_point(disk, params)
            velocity = velocities[id(disk)]
            velocity[0] += (target_x - disk.x) * params.shell_pull
            velocity[1] += (target_y - disk.y) * params.shell_pull

        for i, first in enumerate(disks):
            for j in range(i + 1, len(disks)):
                second = disks[j]
                dx = second.x - first.x
                dy = second.y - first.y
                distance = math.hypot(dx, dy)
                if distance < 1e-6:
                    angle = (i * 41 + j * 19) * math.pi / 180
                    dx = math.cos(angle)
                    dy = math.sin(angle)
                    distance = 1.0
                equilibrium = first.radius + second.radius + params.gap
                if distance > equilibrium * params.morse_cutoff_multiplier:
                    continue
                ux = dx / distance
                uy = dy / distance
                force = morse_signed_force(distance, equilibrium, params.morse_alpha)
                force *= params.morse_force_scale
                force = max(params.morse_force_min, min(params.morse_force_max, force))
                first_velocity = velocities[id(first)]
                second_velocity = velocities[id(second)]
                first_velocity[0] -= ux * force
                first_velocity[1] -= uy * force
                second_velocity[0] += ux * force
                second_velocity[1] += uy * force

        for disk in disks:
            velocity = velocities[id(disk)]
            velocity[0] *= params.damping
            velocity[1] *= params.damping
            disk.x += velocity[0]
            disk.y += velocity[1]
            clamp_disk_to_sphere(disk, params)

        for _ in range(params.projection_passes_per_step):
            project_overlaps(disks, params, strength=0.9)
        if iteration > 260 and iteration % 20 == 0:
            compact_toward_targets(disks, params)

    for _ in range(params.final_projection_steps):
        if project_overlaps(disks, params, strength=0.65) < 1e-3:
            break
    compact_toward_targets(disks, params)
    for _ in range(params.final_projection_steps):
        if project_overlaps(disks, params, strength=0.65) < 1e-3:
            break


def clearance_stats(disks: list[Disk]) -> tuple[float, float]:
    """Return `(min_clearance, max_overlap)` for packed disks."""
    min_clearance = float("inf")
    max_overlap = 0.0
    for i, first in enumerate(disks):
        for second in disks[i + 1 :]:
            clearance = math.hypot(second.x - first.x, second.y - first.y) - first.radius - second.radius
            min_clearance = min(min_clearance, clearance)
            max_overlap = max(max_overlap, -clearance)
    if min_clearance == float("inf"):
        min_clearance = 0.0
    return min_clearance, max_overlap


def pack_disk_cloud(
    tallies: Mapping[str, int],
    params: DiskCloudParams | None = None,
    *,
    initial_radius_scale: float = 1.0,
    min_radius_scale: float = 0.42,
    radius_scale_decay: float = 0.94,
) -> DiskCloudLayout:
    """Pack a label tally mapping into non-overlapping disks."""
    params = params or DiskCloudParams()
    radius_scale = initial_radius_scale
    while radius_scale >= min_radius_scale:
        disks = build_disks(tallies, params, radius_scale=radius_scale)
        if initial_pack(disks, params):
            compact_toward_targets(disks, params)
            relax_with_morse_forces(disks, params)
            min_clearance, max_overlap = clearance_stats(disks)
            return DiskCloudLayout(
                disks=disks,
                params=params,
                radius_scale=radius_scale,
                max_overlap=max_overlap,
                min_clearance=min_clearance,
                metadata={
                    "count": len(disks),
                    "max_value": max(disk.value for disk in disks),
                    "min_value": min(disk.value for disk in disks),
                },
            )
        radius_scale *= radius_scale_decay
    msg = "Could not pack disks without overlap."
    raise RuntimeError(msg)


def svg_disk_groups(layout: DiskCloudLayout) -> str:
    """Render packed disks as SVG groups with invisible circles and centered labels."""
    groups = []
    for disk in layout.disks:
        label = html.escape(disk.label)
        color = html.escape(disk.color)
        groups.append(
            f"""
      <g class="element" data-element="{label}" data-count="{disk.value}">
        <circle class="disk" cx="{disk.x:.2f}" cy="{disk.y:.2f}" r="{disk.radius:.2f}" />
        <text x="{disk.x:.2f}" y="{disk.y:.2f}" fill="{color}" font-size="{disk.font_size:.2f}">{label}</text>
      </g>""".rstrip()
        )
    return "\n".join(groups)


def render_disk_cloud_html(
    tallies: Mapping[str, int],
    params: DiskCloudParams | None = None,
    *,
    title: str = "Disk Cloud",
) -> str:
    """Render a complete standalone HTML disk cloud from a tally mapping."""
    layout = pack_disk_cloud(tallies, params)
    return render_layout_html(layout, title=title)


def write_disk_cloud_html(
    tallies: Mapping[str, int],
    output_html: str | Path,
    params: DiskCloudParams | None = None,
    *,
    title: str = "Disk Cloud",
) -> DiskCloudLayout:
    """Write standalone HTML and return the packed layout used."""
    layout = pack_disk_cloud(tallies, params)
    Path(output_html).write_text(
        render_layout_html(layout, title=title),
        encoding="utf-8",
    )
    return layout


def render_layout_html(layout: DiskCloudLayout, *, title: str = "Disk Cloud") -> str:
    """Render standalone HTML from an already packed layout."""
    params = layout.params
    svg = svg_disk_groups(layout)
    max_value = int(layout.metadata["max_value"])
    min_clearance = layout.min_clearance
    return render_disk_cloud_html_from_svg(
        svg,
        params=params,
        title=title,
        label_count=len(layout.disks),
        max_value=max_value,
        min_clearance=min_clearance,
        radius_scale=layout.radius_scale,
    )


def render_disk_cloud_html_from_svg(
    svg: str,
    *,
    params: DiskCloudParams,
    title: str,
    label_count: int,
    max_value: int,
    min_clearance: float,
    radius_scale: float,
) -> str:
    """Render standalone HTML around pre-rendered SVG disk groups."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, Helvetica, sans-serif;
      background: #f7f7f3;
      color: #202124;
    }}

    * {{
      box-sizing: border-box;
    }}

    html,
    body {{
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
    }}

    body {{
      display: grid;
      grid-template-rows: auto 1fr;
      background: #f7f7f3;
    }}

    header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 24px;
      padding: 14px 22px 10px;
      border-bottom: 1px solid #deded6;
      background: rgba(247, 247, 243, 0.94);
    }}

    h1 {{
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0;
    }}

    .summary {{
      color: #5f6368;
      font-size: 13px;
      white-space: nowrap;
    }}

    #stage {{
      position: relative;
      display: grid;
      place-items: center;
      min-height: 0;
      padding: 18px;
      overflow: hidden;
      user-select: none;
    }}

    svg {{
      width: min(96vw, calc((100vh - 94px) * 1.5));
      height: min(calc(100vh - 112px), 64vw);
      min-width: 720px;
      min-height: 480px;
      max-width: 1600px;
      max-height: 1067px;
      filter: drop-shadow(0 20px 34px rgba(40, 72, 90, 0.16));
    }}

    .sphere {{
      fill: url(#sphereFill);
      stroke: rgba(75, 137, 170, 0.44);
      stroke-width: 3;
    }}

    .disk {{
      fill: transparent;
      stroke: transparent;
      pointer-events: all;
    }}

    text {{
      dominant-baseline: central;
      text-anchor: middle;
      font-weight: 600;
      letter-spacing: 0;
      pointer-events: none;
    }}

    .element {{
      cursor: pointer;
    }}

    .element:hover text {{
      filter: brightness(0.84);
      text-shadow: 0 0 1px currentColor;
    }}

    #tooltip {{
      position: fixed;
      z-index: 20;
      min-width: 138px;
      padding: 9px 11px;
      border: 1px solid #c6c7bf;
      border-radius: 6px;
      background: rgba(255, 255, 252, 0.98);
      box-shadow: 0 8px 24px rgba(32, 33, 36, 0.18);
      pointer-events: none;
      opacity: 0;
      transform: translate(12px, 12px);
      transition: opacity 80ms ease;
    }}

    #tooltip.visible {{
      opacity: 1;
    }}

    .tooltip-symbol {{
      display: block;
      margin-bottom: 3px;
      font-size: 24px;
      font-weight: 700;
      line-height: 1;
    }}

    .tooltip-count {{
      display: block;
      color: #3c4043;
      font-size: 13px;
      line-height: 1.25;
    }}

    @media (max-width: 820px) {{
      header {{
        align-items: flex-start;
        flex-direction: column;
        gap: 4px;
      }}

      .summary {{
        white-space: normal;
      }}

      #stage {{
        padding: 10px;
      }}

      svg {{
        width: 96vw;
        height: calc(100vh - 132px);
        min-width: 0;
        min-height: 0;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="summary">{label_count} labels, {max_value:,} max tally, min clearance {min_clearance:.3f}px, radius scale {radius_scale:.3f}</div>
  </header>
  <main id="stage">
    <svg viewBox="0 0 {params.width} {params.height}" aria-label="Static non-overlapping disk packing">
      <defs>
        <radialGradient id="sphereFill" cx="35%" cy="24%" r="76%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.96" />
          <stop offset="36%" stop-color="#edf8f9" stop-opacity="0.86" />
          <stop offset="100%" stop-color="#d5edf1" stop-opacity="0.72" />
        </radialGradient>
      </defs>
      <ellipse class="sphere" cx="{params.center_x}" cy="{params.center_y}" rx="{params.sphere_rx}" ry="{params.sphere_ry}" />
{svg}
    </svg>
  </main>
  <div id="tooltip" role="status" aria-live="polite"></div>
  <script>
    const tooltip = document.getElementById("tooltip");

    function moveTooltip(event) {{
      const padding = 14;
      const tooltipRect = tooltip.getBoundingClientRect();
      let x = event.clientX + 16;
      let y = event.clientY + 16;
      if (x + tooltipRect.width + padding > window.innerWidth) {{
        x = event.clientX - tooltipRect.width - 16;
      }}
      if (y + tooltipRect.height + padding > window.innerHeight) {{
        y = event.clientY - tooltipRect.height - 16;
      }}
      tooltip.style.left = `${{Math.max(padding, x)}}px`;
      tooltip.style.top = `${{Math.max(padding, y)}}px`;
    }}

    document.querySelectorAll(".element").forEach((element) => {{
      element.addEventListener("pointerenter", (event) => {{
        const text = element.querySelector("text");
        const count = Number(element.dataset.count);
        tooltip.innerHTML = `
          <span class="tooltip-symbol" style="color: ${{text.getAttribute("fill")}}">${{element.dataset.element}}</span>
          <span class="tooltip-count">${{count.toLocaleString()}} materials</span>
        `;
        moveTooltip(event);
        tooltip.classList.add("visible");
      }});
      element.addEventListener("pointermove", moveTooltip);
      element.addEventListener("pointerleave", () => tooltip.classList.remove("visible"));
    }});
  </script>
</body>
</html>
"""
