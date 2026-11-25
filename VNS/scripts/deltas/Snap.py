from Cost import Cost

SNAP = 1e-6


def snapped(cost: Cost, hard_flags: tuple, epsilon: float = SNAP) -> Cost:
    if not cost.all_components or len(cost.all_components) != len(hard_flags):
        return cost
    values = tuple(0.0 if -epsilon < value < epsilon else value
                   for value in cost.all_components)
    if values == cost.all_components:
        return cost
    return Cost(violations=sum(value for value, hard in zip(values, hard_flags) if hard),
                objective=sum(value for value, hard in zip(values, hard_flags) if not hard),
                all_components=values)
