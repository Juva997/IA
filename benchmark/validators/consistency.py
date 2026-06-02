from collections import Counter

from benchmark.validators.common import normalized_text


def consistency_check(outputs):
    if not outputs:
        return 0.0

    signatures = [normalized_text(output) for output in outputs]
    if not signatures:
        return 0.0

    counts = Counter(signatures)
    return counts.most_common(1)[0][1] / len(signatures)
