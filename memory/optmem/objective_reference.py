"""Independent exhaustive minimax/newest-detail specification, tiny domains only."""
from fractions import Fraction
from rational_reference import select


def partitions(left, depth):
    if left == 0:
        yield ()
        return
    for d in range(min(depth, left.bit_length()-1), -1, -1):
        width = 1 << d
        for tail in partitions(left-width, d):
            yield (width,) + tail


def score(total, widths):
    lo, ratios = 0, []
    for width in widths:
        if width > 1:
            ratios.append(Fraction(width, total-lo))
        lo += width
    return max(ratios, default=Fraction(0)), widths[::-1]


if __name__ == '__main__':
    cases = 0
    for total in range(1, 49):
        best = {}
        for widths in partitions(total, total.bit_length()-1):
            count, value = len(widths), score(total, widths)
            if count not in best or value < best[count][0]:
                best[count] = (value, widths)
        for budget, (_, expected) in best.items():
            actual = tuple(hi-lo for lo,hi in select(total,budget))
            assert actual == expected, (total,budget,actual,expected)
            cases += 1
    print(cases, 'all-partition optimum cases agree')
