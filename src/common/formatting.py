"""Shared formatting utilities for the 2parser pipeline."""


def format_calc_str(
    amount, gold_per_point, uptime_factor=None, multiplier=None, chance_factor=None
):
    """Format calculation string showing all multipliers.

    Example: "10 x 66.7 x 0.25 x 0.50" (amount x gpp x chance x uptime)
    """
    parts = [str(amount), f"{gold_per_point:.1f}"]
    if chance_factor is not None:
        parts.append(f"{chance_factor:.2f}")
    if uptime_factor is not None:
        parts.append(f"{uptime_factor:.2f}")
    if multiplier is not None:
        parts.append(f"{multiplier:.2f}")
    return " x ".join(parts)
