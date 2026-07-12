#!/usr/bin/env python3
"""Set-based scorer shared by the router eval runner and scorer tests."""


def prf(predicted, expected):
    predicted_set, expected_set = set(predicted), set(expected)
    if not expected_set:
        return (1.0, 1.0, 1.0) if not predicted_set else (0.0, 1.0, 0.0)
    if not predicted_set:
        return (1.0, 0.0, 0.0)
    true_positive = len(predicted_set & expected_set)
    precision = true_positive / len(predicted_set)
    recall = true_positive / len(expected_set)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1
