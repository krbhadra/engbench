"""Shared optimality check for generated families that carry task["objective"]."""


def check_objective(task, metrics, violations):
    """Append a violation if the design is feasible but not within tolerance of the brute-force optimum."""
    obj = task.get("objective")  # {"minimize": <metric key>, "optimum": <brute-force best>, "tolerance": 0.05}
    if obj and not violations and metrics[obj["minimize"]] > obj["optimum"] * (1 + obj["tolerance"]) + 1e-9:
        # ponytail: the optimum is not echoed back, so agentic feedback says "search harder", not "the answer is X"
        violations.append(f"{obj['minimize']} {metrics[obj['minimize']]:.2f} is not within {obj['tolerance']*100:.0f}% "
                          f"of the best design that meets every constraint")
