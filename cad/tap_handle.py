from dataclasses import dataclass
from pathlib import Path

import build123d as bd
import build123d_ease as bde
from build123d_ease import show
from loguru import logger


@dataclass
class TapHandleSpec:
    """Specification for tap handle."""

    shaft_od: float = 12.5
    shaft_length: float = 140

    shaft_hex_length: float = 10.0

    tap_diameter: float = 3.0  # M3

    tap_square_length: float = 10.0
    tap_round_length: float = 2.0

    handle_base_diameter: float = 30.0
    handle_t_width: float = 15.0
    handle_t_length: float = 120.0
    handle_t_length_2: float = 60.0  # Cross part.
    handle_t_height: float = 10.0

    def __post_init__(self) -> None:
        """Post initialization checks."""
        logger.info(
            f"tap_square_side_length: {self.tap_square_side_length:.2f}"
        )

    @property
    def tap_square_side_length(self) -> float:
        """Return the side length of the square interface.

        `tap_diameter` is the hypotenuse of the square.
        """
        return self.tap_diameter / (2**0.5)


def make_tap_handle(spec: TapHandleSpec) -> bd.Part | bd.Compound:
    """Create a CAD model of tap_handle."""
    # Add the T-shaped handle.
    handle_part = bd.Part(None)
    handle_part += bd.Cylinder(
        radius=spec.handle_base_diameter / 2,
        height=spec.handle_t_height,
        align=bde.align.ANCHOR_TOP,
    )
    handle_part += bd.Box(
        spec.handle_t_length,
        spec.handle_t_width,
        spec.handle_t_height,
        align=bde.align.ANCHOR_TOP,
    )
    handle_part += bd.Box(
        spec.handle_t_width,
        spec.handle_t_length_2,
        spec.handle_t_height,
        align=bde.align.ANCHOR_TOP,
    )
    handle_part = bd.Pos(Z=0.1) * bd.fillet(handle_part.edges(), 4.5)

    # Create the shaft (without adding to p yet)
    shaft_part = bd.Part(None)

    # Add the main cylindrical shaft
    shaft_part += bd.Cylinder(
        radius=spec.shaft_od / 2,
        height=spec.shaft_length - spec.shaft_hex_length,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Add the hexagonal part of the shaft (at the top).
    shaft_part += bd.Pos(
        Z=spec.shaft_length - spec.shaft_hex_length - 0.01
    ) * bd.extrude(
        bd.RegularPolygon(
            radius=spec.shaft_od / 2,
            side_count=6,
        ),
        amount=spec.shaft_hex_length,
    )

    # Combine handle and shaft
    p = bd.Part(None) + handle_part + shaft_part

    # Add fillet between shaft and handle.
    # Find edges at the intersection of the shaft and handle base.
    # Black magic. Claude made it.
    intersection_edges = [
        edge
        for edge in p.edges()
        if (
            abs(edge.center().Z) < 0.2  # noqa: PLR2004
        )
        and (
            (spec.shaft_od / 2) ** 2 - 1
            < edge.center().X ** 2 + edge.center().Y ** 2
            and (spec.handle_base_diameter / 2) ** 2 + 1
            > edge.center().X ** 2 + edge.center().Y ** 2
        )
    ]
    assert len(intersection_edges) > 0

    # Apply fillet to the intersection edges
    p = p.fillet(
        edge_list=intersection_edges,
        radius=3.5,
    )

    # At the top of the shaft, remove the square interface.
    p -= bd.Pos(Z=spec.shaft_length) * bd.Box(
        spec.tap_square_side_length,
        spec.tap_square_side_length,
        spec.tap_square_length,
        align=bde.align.ANCHOR_TOP,
    )
    p -= bd.Pos(Z=spec.shaft_length) * bd.Cylinder(
        radius=spec.tap_diameter / 2,
        height=spec.tap_round_length,
        align=bde.align.ANCHOR_TOP,
    )

    # At the handle-side, add a place to put a bolt for security.
    p -= bd.Pos(Z=-spec.handle_t_height - 0.1) * bd.Cylinder(
        radius=4.9 / 2,  # M5 bolt.
        height=50,
        align=bde.align.ANCHOR_BOTTOM,
    )

    return p


if __name__ == "__main__":
    parts = {
        "tap_handle_m3": show(
            make_tap_handle(
                TapHandleSpec(
                    tap_diameter=3.0,
                )
            )
        ),
    }

    logger.info("Showing CAD model(s)")

    (export_folder := Path(__file__).parent.with_name("build")).mkdir(
        exist_ok=True
    )
    for name, part in parts.items():
        assert isinstance(part, bd.Part | bd.Solid | bd.Compound), (
            f"{name} is not an expected type ({type(part)})"
        )
        # if not part.is_manifold:
        #     logger.warning(f"Part '{name}' is not manifold")

        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))
