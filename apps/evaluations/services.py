import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from apps.ratings.models import UserRating


def k_values():
    return [5, 10, 20, 30]


def evaluation_artifact_dir(base_dir: Path):
    return base_dir / "artifacts" / "evaluations"


def load_experiment_summary(base_dir: Path):
    summary_path = evaluation_artifact_dir(base_dir) / "summary.json"
    if not summary_path.exists():
        return {"overview": [], "algorithms": []}
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {"overview": [], "algorithms": []}


def _ratings_frame() -> pd.DataFrame:
    ratings = list(UserRating.objects.values("id", "user_id", "book_id", "score", "rated_at"))
    if not ratings:
        return pd.DataFrame(columns=["id", "user_id", "book_id", "score", "rated_at"])
    frame = pd.DataFrame.from_records(ratings)
    return frame.sort_values(["user_id", "rated_at", "id"]).reset_index(drop=True)


def _split_train_holdout(frame: pd.DataFrame):
    if frame.empty:
        empty = pd.DataFrame(columns=["user_id", "book_id", "score"])
        return empty, {}

    train_parts = []
    holdouts = {}
    for user_id, group in frame.groupby("user_id", sort=True):
        if len(group) < 2:
            continue
        ordered = group.sort_values(["rated_at", "id"])
        holdout = ordered.iloc[-1]
        holdouts[int(user_id)] = int(holdout["book_id"])
        train_parts.append(ordered.iloc[:-1][["user_id", "book_id", "score"]])

    if not train_parts:
        empty = pd.DataFrame(columns=["user_id", "book_id", "score"])
        return empty, {}
    return pd.concat(train_parts, ignore_index=True), holdouts


def _interaction_matrix(frame: pd.DataFrame) -> pd.DataFrame | None:
    if frame.empty:
        return None
    return frame.pivot_table(index="user_id", columns="book_id", values="score", fill_value=0.0)


def _sorted_popularity(frame: pd.DataFrame) -> list[int]:
    if frame.empty:
        return []
    ranking = (
        frame.groupby("book_id")
        .agg(rating_count=("score", "count"), average_score=("score", "mean"))
        .sort_values(["rating_count", "average_score", "book_id"], ascending=[False, False, True])
        .reset_index()
    )
    return [int(book_id) for book_id in ranking["book_id"].tolist()]


def _exclude_seen(book_ids: list[int], seen_ids: set[int], limit: int) -> list[int]:
    filtered = [book_id for book_id in book_ids if book_id not in seen_ids]
    return filtered[:limit]


def _item_similarity(matrix: pd.DataFrame | None) -> pd.DataFrame | None:
    if matrix is None or matrix.empty:
        return None
    similarity = cosine_similarity(matrix.T)
    return pd.DataFrame(similarity, index=matrix.columns, columns=matrix.columns)


def _itemcf_scores(user_id: int, matrix: pd.DataFrame | None, similarity: pd.DataFrame | None) -> dict[int, float]:
    if matrix is None or similarity is None or user_id not in matrix.index:
        return {}
    user_ratings = matrix.loc[user_id]
    rated_mask = user_ratings.values > 0
    if rated_mask.sum() == 0:
        return {}
    rated_indices = np.where(rated_mask)[0]
    scores = similarity.values[:, rated_indices].dot(user_ratings.values[rated_indices])
    scores[rated_indices] = -np.inf
    scored_books = {}
    for idx, raw_score in enumerate(scores):
        if np.isfinite(raw_score) and raw_score > 0:
            scored_books[int(similarity.index[idx])] = float(raw_score)
    return scored_books


def _user_similarity(matrix: pd.DataFrame | None) -> pd.DataFrame | None:
    if matrix is None or matrix.empty:
        return None
    similarity = cosine_similarity(matrix)
    return pd.DataFrame(similarity, index=matrix.index, columns=matrix.index)


def _usercf_scores(user_id: int, matrix: pd.DataFrame | None, similarity: pd.DataFrame | None) -> dict[int, float]:
    if matrix is None or similarity is None or user_id not in matrix.index:
        return {}
    user_ratings = matrix.loc[user_id]
    seen_ids = {int(book_id) for book_id, value in user_ratings.items() if value > 0}
    neighbors = similarity.loc[user_id].drop(labels=[user_id], errors="ignore")
    neighbors = neighbors[neighbors > 0].sort_values(ascending=False)
    if neighbors.empty:
        return {}
    scores: dict[int, float] = {}
    for neighbor_id, sim in neighbors.items():
        neighbor_ratings = matrix.loc[neighbor_id]
        for book_id, value in neighbor_ratings.items():
            if value <= 0 or int(book_id) in seen_ids:
                continue
            scores[int(book_id)] = scores.get(int(book_id), 0.0) + float(sim) * float(value)
    return scores


def _normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    min_score = min(scores.values())
    if max_score == min_score:
        return {book_id: 1.0 for book_id in scores}
    return {book_id: (score - min_score) / (max_score - min_score) for book_id, score in scores.items()}


def _hot_predictions(train_frame: pd.DataFrame, holdouts: dict[int, int], limit: int) -> dict[int, list[int]]:
    popularity = _sorted_popularity(train_frame)
    predictions = {}
    for user_id in holdouts:
        seen_ids = set(train_frame.loc[train_frame["user_id"] == user_id, "book_id"].tolist())
        predictions[user_id] = _exclude_seen(popularity, seen_ids, limit)
    return predictions


def _itemcf_predictions(train_frame: pd.DataFrame, holdouts: dict[int, int], limit: int) -> dict[int, list[int]]:
    matrix = _interaction_matrix(train_frame)
    similarity = _item_similarity(matrix)
    popularity = _sorted_popularity(train_frame)
    predictions = {}
    for user_id in holdouts:
        seen_ids = set(train_frame.loc[train_frame["user_id"] == user_id, "book_id"].tolist())
        raw_scores = _itemcf_scores(user_id, matrix, similarity)
        ranked = [book_id for book_id, _ in sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)]
        ranked.extend(book_id for book_id in popularity if book_id not in ranked)
        predictions[user_id] = _exclude_seen(ranked, seen_ids, limit)
    return predictions


def _usercf_predictions(train_frame: pd.DataFrame, holdouts: dict[int, int], limit: int) -> dict[int, list[int]]:
    matrix = _interaction_matrix(train_frame)
    similarity = _user_similarity(matrix)
    popularity = _sorted_popularity(train_frame)
    predictions = {}
    for user_id in holdouts:
        seen_ids = set(train_frame.loc[train_frame["user_id"] == user_id, "book_id"].tolist())
        raw_scores = _usercf_scores(user_id, matrix, similarity)
        ranked = [book_id for book_id, _ in sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)]
        ranked.extend(book_id for book_id in popularity if book_id not in ranked)
        predictions[user_id] = _exclude_seen(ranked, seen_ids, limit)
    return predictions


def _hybrid_predictions(train_frame: pd.DataFrame, holdouts: dict[int, int], limit: int) -> dict[int, list[int]]:
    itemcf_predictions = _itemcf_predictions(train_frame, holdouts, limit * 3)
    hot_predictions = _hot_predictions(train_frame, holdouts, limit * 3)
    matrix = _interaction_matrix(train_frame)
    similarity = _item_similarity(matrix)
    popularity_order = _sorted_popularity(train_frame)
    popularity_scores = {
        book_id: float(len(popularity_order) - idx)
        for idx, book_id in enumerate(popularity_order)
    }
    normalized_popularity = _normalize_scores(popularity_scores)
    predictions = {}
    for user_id in holdouts:
        seen_ids = set(train_frame.loc[train_frame["user_id"] == user_id, "book_id"].tolist())
        item_scores = _normalize_scores(_itemcf_scores(user_id, matrix, similarity))
        candidate_ids = list(dict.fromkeys(itemcf_predictions[user_id] + hot_predictions[user_id] + popularity_order))
        combined = {}
        for book_id in candidate_ids:
            combined[book_id] = item_scores.get(book_id, 0.0) * 0.7 + normalized_popularity.get(book_id, 0.0) * 0.3
        ranked = [book_id for book_id, _ in sorted(combined.items(), key=lambda item: item[1], reverse=True)]
        predictions[user_id] = _exclude_seen(ranked, seen_ids, limit)
    return predictions


def _metric_rows(predictions: dict[int, list[int]], holdouts: dict[int, int]) -> list[dict[str, float]]:
    user_count = len(holdouts)
    if user_count == 0:
        return [{"k": k, "precision": 0.0, "recall": 0.0} for k in k_values()]

    rows = []
    for k in k_values():
        precision_total = 0.0
        recall_total = 0.0
        for user_id, holdout_book_id in holdouts.items():
            recommended = predictions.get(user_id, [])[:k]
            hit = 1.0 if holdout_book_id in recommended else 0.0
            precision_total += hit / float(k)
            recall_total += hit
        rows.append(
            {
                "k": k,
                "precision": round(precision_total / user_count, 4),
                "recall": round(recall_total / user_count, 4),
            }
        )
    return rows


def _best_metric_row(metric_rows: list[dict[str, float]]) -> dict[str, float]:
    if not metric_rows:
        return {"k": 0, "precision": 0.0, "recall": 0.0}
    return max(metric_rows, key=lambda row: (row["precision"], row["recall"], -row["k"]))


def generate_evaluation_summary() -> dict:
    frame = _ratings_frame()
    train_frame, holdouts = _split_train_holdout(frame)
    algorithms = {
        "hot": _hot_predictions(train_frame, holdouts, max(k_values())),
        "itemcf": _itemcf_predictions(train_frame, holdouts, max(k_values())),
        "usercf": _usercf_predictions(train_frame, holdouts, max(k_values())),
        "hybrid": _hybrid_predictions(train_frame, holdouts, max(k_values())),
    }

    algorithm_payload = []
    per_algorithm_rows = {}
    user_count = len(holdouts)
    for name, predictions in algorithms.items():
        metric_rows = _metric_rows(predictions, holdouts)
        per_algorithm_rows[name] = metric_rows
        best_row = _best_metric_row(metric_rows)
        algorithm_payload.append(
            {
                "name": name,
                "summary": (
                    f"Evaluated on {user_count} leave-one-out users. "
                    f"Best precision {best_row['precision']:.4f} at K={best_row['k']}, "
                    f"recall {best_row['recall']:.4f}."
                ),
                "best_precision": best_row["precision"],
                "best_recall": best_row["recall"],
                "best_k": best_row["k"],
                "user_count": user_count,
                "metrics": metric_rows,
            }
        )

    overview = []
    for idx, k in enumerate(k_values()):
        row_candidates = [
            {
                "name": name,
                "precision": per_algorithm_rows[name][idx]["precision"],
                "recall": per_algorithm_rows[name][idx]["recall"],
            }
            for name in algorithms
        ]
        best = max(row_candidates, key=lambda row: (row["precision"], row["recall"]))
        overview.append(
            {
                "k": k,
                "precision": best["precision"],
                "recall": best["recall"],
                "best_algorithm": best["name"],
            }
        )

    return {"overview": overview, "algorithms": algorithm_payload}
