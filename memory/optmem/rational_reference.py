"""Independent small-domain definition of the original threshold/fill policy.
No floating search or optimized count formula. Enumerates complete dyadic cuts.
"""
from fractions import Fraction
from functools import lru_cache


def threshold_cover(total, cut):
    if not total:
        return []
    stack, result = [(0, 1 << (total - 1).bit_length())], []
    while stack:
        lo, hi = stack.pop()
        if lo >= total:
            continue
        width = hi - lo
        if width > 1 and (hi > total or width * cut.denominator > cut.numerator * (total - lo)):
            mid = (lo + hi) // 2
            stack.extend(((mid, hi), (lo, mid)))
        else:
            result.append((lo, hi))
    return result


@lru_cache(maxsize=256)
def complete_cuts(total):
    ratios = {Fraction(0), Fraction(1)}
    width = 2
    while width <= total:
        ratios.update(Fraction(width, total-lo) for lo in range(0, total-width+1, width))
        width *= 2
    return tuple((cut, tuple(threshold_cover(total, cut))) for cut in sorted(ratios))


def select(total, budget):
    assert 0 <= total <= 256 and budget > 0
    if budget >= total:
        return [(i, i+1) for i in range(total)]
    target = max(total.bit_count(), budget)
    # Smallest exact threshold whose complete cut fits; no partial tie group.
    _, forest = next((cut, forest) for cut, forest in complete_cuts(total) if len(forest) <= target)
    result = list(forest)
    while len(result) < target:
        i = next(i for i in range(len(result)-1, -1, -1) if result[i][1]-result[i][0] > 1)
        lo, hi = result[i]; mid = (lo+hi)//2
        result[i:i+1] = [(lo,mid),(mid,hi)]
    return result


if __name__ == '__main__':
    from importlib.machinery import SourceFileLoader
    from pathlib import Path
    memo = SourceFileLoader('reference_test_memo', str(Path(__file__).resolve().parent/'memo')).load_module()
    cases = 0
    for total in range(257):
        for budget in range(1, min(total+2,42)):
            actual, expected = select(total,budget), memo.cover_python(total,budget)
            assert actual == expected, (total,budget,actual,expected)
            cases += 1
    print(cases, 'exact rational reference/Python cases agree')
    for b in [11,12]:
        print('24/', b, select(24,b))
