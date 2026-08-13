"""Метрики за евалуација на предвидувачките модели.

Сите функции работат САМО со вистински предадени вредности: ако нема
употребливи редови, се враќа 0.0 (недостапно) и ништо не се измислува.
"""

import logging

import numpy as np
from sklearn.metrics import log_loss

# Индекси на класите: 0 = домашен, 1 = реми, 2 = гостин.
CLASSES: list[int] = [0, 1, 2]


def _as_matrix(probs: list[list[float]]) -> np.ndarray:
    """Ги нормализира веројатностите во матрица (n, 3) што сумира на 1."""
    if not probs:
        return np.zeros((0, 3), dtype=float)
    matrix = np.asarray(probs, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    matrix = np.clip(matrix, 1e-6, 1.0)
    sums = matrix.sum(axis=1, keepdims=True)
    sums[sums <= 0.0] = 1.0
    return matrix / sums


def accuracy(y_true: list[int], y_pred: list[int]) -> float:
    """Дел на точни предвидувања во проценти."""
    if not y_true or len(y_true) != len(y_pred):
        return 0.0
    correct = sum(1 for a, b in zip(y_true, y_pred) if a == b)
    return round(correct / len(y_true) * 100.0, 1)


def accuracy_1x2(y_true: list[int], probs: list[list[float]]) -> float:
    """Точност на 1X2 маркетот според најверојатната класа."""
    matrix = _as_matrix(probs)
    if matrix.shape[0] == 0 or matrix.shape[0] != len(y_true):
        return 0.0
    return accuracy(y_true, [int(row) for row in matrix.argmax(axis=1)])


def binary_proxy_accuracy(
    probabilities: list[float], outcomes: list[bool]
) -> float:
    """Прокси точност за бинарен маркет (ГГ или Над 2.5).

    Предвидувањето е „да“ кога веројатноста е ≥ 50%, а точноста се мери
    наспроти вистинскиот исход од резултатот на натпреварот.
    """
    if not probabilities or len(probabilities) != len(outcomes):
        return 0.0
    correct = 0
    for probability, outcome in zip(probabilities, outcomes):
        predicted = probability >= 50.0
        if predicted == bool(outcome):
            correct += 1
    return round(correct / len(outcomes) * 100.0, 1)


def multiclass_log_loss(y_true: list[int], probs: list[list[float]]) -> float:
    """Логаритамска загуба за трите 1X2 класи."""
    matrix = _as_matrix(probs)
    if matrix.shape[0] == 0 or matrix.shape[0] != len(y_true):
        return 0.0
    try:
        value = log_loss(y_true, matrix, labels=CLASSES)
    except Exception as error:
        logging.exception(f"Error: неуспешна log-loss пресметка: {error}")
        return 0.0
    return round(float(value), 3)


def multiclass_brier(y_true: list[int], probs: list[list[float]]) -> float:
    """Брирова оценка за повеќекласни веројатности (средна квадратна грешка)."""
    matrix = _as_matrix(probs)
    if matrix.shape[0] == 0 or matrix.shape[0] != len(y_true):
        return 0.0
    targets = np.zeros_like(matrix)
    for index, label in enumerate(y_true):
        if 0 <= int(label) <= 2:
            targets[index, int(label)] = 1.0
    value = float(np.mean(np.sum((matrix - targets) ** 2, axis=1)))
    return round(value, 3)


def roi(stakes: list[tuple[float, bool]]) -> float:
    """Поврат на инвестиција во проценти од (квота, дали е точно) редови."""
    rows = [(odds, won) for odds, won in stakes if odds > 1.0]
    if not rows:
        return 0.0
    profit = sum((odds - 1.0) if won else -1.0 for odds, won in rows)
    return round(profit / len(rows) * 100.0, 2)


def summarize(
    y_true: list[int],
    probs: list[list[float]],
    odds: list[float],
    btts_probs: list[float],
    btts_outcomes: list[bool],
    over25_probs: list[float],
    over25_outcomes: list[bool],
) -> dict[str, float]:
    """Целосен сет метрики за еден модел (сите вредности во проценти)."""
    matrix = _as_matrix(probs)
    predicted = (
        [int(row) for row in matrix.argmax(axis=1)]
        if matrix.shape[0] == len(y_true)
        else []
    )
    stakes: list[tuple[float, bool]] = []
    for index, label in enumerate(y_true):
        if index < len(odds) and index < len(predicted):
            stakes.append((odds[index], predicted[index] == label))
    return {
        "accuracy": accuracy(y_true, predicted),
        "acc_1x2": accuracy_1x2(y_true, probs),
        "acc_btts": binary_proxy_accuracy(btts_probs, btts_outcomes),
        "acc_over25": binary_proxy_accuracy(over25_probs, over25_outcomes),
        "log_loss": multiclass_log_loss(y_true, probs),
        "brier": multiclass_brier(y_true, probs),
        "roi": roi(stakes),
        "sample": float(len(y_true)),
    }
