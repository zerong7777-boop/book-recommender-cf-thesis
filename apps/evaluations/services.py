import json
from pathlib import Path

import numpy as np
import pandas as pd
from django.utils import timezone
from sklearn.metrics.pairwise import cosine_similarity

from apps.catalog.models import Book
from apps.evaluations.models import EvaluationRun
from apps.ratings.services import build_interaction_frame


def k_values():
    return [5, 10, 20, 30]


def evaluation_artifact_dir(base_dir: Path):
    return base_dir / "artifacts" / "evaluations"


def _empty_summary() -> dict:
    return {
        "metadata": {},
        "overview": [],
        "algorithms": [],
        "curves": {"precision": [], "recall": []},
        "case_studies": [],
        "similarity_comparison": {},
        "random_split": {"train_interaction_count": 0, "test_interaction_count": 0, "algorithms": []},
    }


def load_experiment_summary(base_dir: Path):
    summary_path = evaluation_artifact_dir(base_dir) / "summary.json"
    if not summary_path.exists():
        return _empty_summary()
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return _empty_summary()


def _ratings_frame() -> pd.DataFrame:
    return build_interaction_frame(include_event_metadata=True)


def _split_train_holdout(frame: pd.DataFrame):
    if frame.empty:
        empty = pd.DataFrame(columns=["subject_key", "book_id", "score", "source"])
        return empty, {}, {}

    train_parts = []
    holdouts: dict[str, int] = {}
    subject_labels: dict[str, str] = {}
    for subject_key, group in frame.groupby("subject_key", sort=True):
        if len(group) < 2:
            continue
        ordered = group.sort_values(["event_at", "event_id"])
        holdout = ordered.iloc[-1]
        holdouts[str(subject_key)] = int(holdout["book_id"])
        subject_labels[str(subject_key)] = str(holdout["subject_label"])
        train_parts.append(ordered.iloc[:-1][["subject_key", "book_id", "score", "source"]])

    if not train_parts:
        empty = pd.DataFrame(columns=["subject_key", "book_id", "score", "source"])
        return empty, {}, {}
    return pd.concat(train_parts, ignore_index=True), holdouts, subject_labels


def _split_random_interactions(frame: pd.DataFrame, test_fraction: float = 0.2):
    if frame.empty or len(frame.index) < 2:
        empty = pd.DataFrame(columns=["subject_key", "book_id", "score", "source"])
        return empty, {}, {}

    eligible_groups = [
        group
        for _, group in frame.groupby("subject_key", sort=True)
        if len(group.index) >= 2
    ]
    if not eligible_groups:
        return frame[["subject_key", "book_id", "score", "source"]].copy(), {}, {}

    eligible = pd.concat(eligible_groups)
    test_count = max(1, int(round(len(eligible.index) * test_fraction)))
    test_rows = (
        eligible.sample(n=min(test_count, len(eligible.index)), random_state=42)
        .sort_values(["subject_key", "event_at", "event_id"])
        .drop_duplicates(subset=["subject_key"], keep="first")
    )
    train_frame = frame.drop(index=test_rows.index)[["subject_key", "book_id", "score", "source"]].reset_index(
        drop=True
    )
    holdouts = {
        str(row["subject_key"]): int(row["book_id"])
        for _, row in test_rows.iterrows()
    }
    subject_labels = {
        str(row["subject_key"]): str(row["subject_label"])
        for _, row in test_rows.iterrows()
    }
    return train_frame, holdouts, subject_labels


def _interaction_matrix(frame: pd.DataFrame) -> pd.DataFrame | None:
    if frame.empty:
        return None
    return frame.pivot_table(index="subject_key", columns="book_id", values="score", fill_value=0.0)


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


def _pearson_item_similarity(matrix: pd.DataFrame | None) -> pd.DataFrame | None:
    if matrix is None or matrix.empty:
        return None
    values = matrix.T.astype(float).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        similarity = np.atleast_2d(np.corrcoef(values))
    similarity = np.nan_to_num(similarity, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(similarity, 1.0)
    return pd.DataFrame(similarity, index=matrix.columns, columns=matrix.columns)


def _itemcf_scores(subject_key: str, matrix: pd.DataFrame | None, similarity: pd.DataFrame | None) -> dict[int, float]:
    if matrix is None or similarity is None or subject_key not in matrix.index:
        return {}
    user_ratings = matrix.loc[subject_key]
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


def _usercf_scores(subject_key: str, matrix: pd.DataFrame | None, similarity: pd.DataFrame | None) -> dict[int, float]:
    if matrix is None or similarity is None or subject_key not in matrix.index:
        return {}
    user_ratings = matrix.loc[subject_key]
    seen_ids = {int(book_id) for book_id, value in user_ratings.items() if value > 0}
    neighbors = similarity.loc[subject_key].drop(labels=[subject_key], errors="ignore")
    neighbors = neighbors[neighbors > 0].sort_values(ascending=False)
    if neighbors.empty:
        return {}
    scores: dict[int, float] = {}
    for neighbor_key, sim in neighbors.items():
        neighbor_ratings = matrix.loc[neighbor_key]
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


def _hot_predictions(train_frame: pd.DataFrame, holdouts: dict[str, int], limit: int) -> dict[str, list[int]]:
    popularity = _sorted_popularity(train_frame)
    predictions = {}
    for subject_key in holdouts:
        seen_ids = set(train_frame.loc[train_frame["subject_key"] == subject_key, "book_id"].tolist())
        predictions[subject_key] = _exclude_seen(popularity, seen_ids, limit)
    return predictions


def _itemcf_predictions(train_frame: pd.DataFrame, holdouts: dict[str, int], limit: int) -> dict[str, list[int]]:
    matrix = _interaction_matrix(train_frame)
    similarity = _item_similarity(matrix)
    return _itemcf_predictions_with_similarity(train_frame, holdouts, limit, matrix, similarity)


def _itemcf_predictions_with_similarity(
    train_frame: pd.DataFrame,
    holdouts: dict[str, int],
    limit: int,
    matrix: pd.DataFrame | None,
    similarity: pd.DataFrame | None,
) -> dict[str, list[int]]:
    popularity = _sorted_popularity(train_frame)
    predictions = {}
    for subject_key in holdouts:
        seen_ids = set(train_frame.loc[train_frame["subject_key"] == subject_key, "book_id"].tolist())
        raw_scores = _itemcf_scores(subject_key, matrix, similarity)
        ranked = [book_id for book_id, _ in sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)]
        ranked.extend(book_id for book_id in popularity if book_id not in ranked)
        predictions[subject_key] = _exclude_seen(ranked, seen_ids, limit)
    return predictions


def _usercf_predictions(train_frame: pd.DataFrame, holdouts: dict[str, int], limit: int) -> dict[str, list[int]]:
    matrix = _interaction_matrix(train_frame)
    similarity = _user_similarity(matrix)
    popularity = _sorted_popularity(train_frame)
    predictions = {}
    for subject_key in holdouts:
        seen_ids = set(train_frame.loc[train_frame["subject_key"] == subject_key, "book_id"].tolist())
        raw_scores = _usercf_scores(subject_key, matrix, similarity)
        ranked = [book_id for book_id, _ in sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)]
        ranked.extend(book_id for book_id in popularity if book_id not in ranked)
        predictions[subject_key] = _exclude_seen(ranked, seen_ids, limit)
    return predictions


def _hybrid_predictions(train_frame: pd.DataFrame, holdouts: dict[str, int], limit: int) -> dict[str, list[int]]:
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
    for subject_key in holdouts:
        seen_ids = set(train_frame.loc[train_frame["subject_key"] == subject_key, "book_id"].tolist())
        item_scores = _normalize_scores(_itemcf_scores(subject_key, matrix, similarity))
        candidate_ids = list(dict.fromkeys(itemcf_predictions[subject_key] + hot_predictions[subject_key] + popularity_order))
        combined = {}
        for book_id in candidate_ids:
            combined[book_id] = item_scores.get(book_id, 0.0) * 0.7 + normalized_popularity.get(book_id, 0.0) * 0.3
        ranked = [book_id for book_id, _ in sorted(combined.items(), key=lambda item: item[1], reverse=True)]
        predictions[subject_key] = _exclude_seen(ranked, seen_ids, limit)
    return predictions


def _metric_rows(predictions: dict[str, list[int]], holdouts: dict[str, int]) -> list[dict[str, float]]:
    user_count = len(holdouts)
    if user_count == 0:
        return [{"k": k, "precision": 0.0, "recall": 0.0} for k in k_values()]

    rows = []
    for k in k_values():
        precision_total = 0.0
        recall_total = 0.0
        for subject_key, holdout_book_id in holdouts.items():
            recommended = predictions.get(subject_key, [])[:k]
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


def _svg_points(metric_rows: list[dict[str, float]], metric_name: str) -> str:
    if not metric_rows:
        return ""
    width = 240.0
    height = 120.0
    inset = 12.0
    if len(metric_rows) == 1:
        row = metric_rows[0]
        return f"{width / 2:.1f},{height - inset - (height - inset * 2) * float(row[metric_name]):.1f}"
    x_step = (width - inset * 2) / float(len(metric_rows) - 1)
    y_scale = height - inset * 2
    points = []
    for idx, row in enumerate(metric_rows):
        x = inset + (idx * x_step)
        y = height - inset - (y_scale * float(row[metric_name]))
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def _build_curves(per_algorithm_rows: dict[str, list[dict[str, float]]]) -> dict[str, list[dict[str, object]]]:
    curves = {"precision": [], "recall": []}
    for name, rows in per_algorithm_rows.items():
        curves["precision"].append(
            {
                "name": name,
                "points": [{"k": row["k"], "value": row["precision"]} for row in rows],
                "svg_points": _svg_points(rows, "precision"),
            }
        )
        curves["recall"].append(
            {
                "name": name,
                "points": [{"k": row["k"], "value": row["recall"]} for row in rows],
                "svg_points": _svg_points(rows, "recall"),
            }
        )
    return curves


def _build_case_studies(
    algorithms: dict[str, dict[str, list[int]]],
    holdouts: dict[str, int],
    subject_labels: dict[str, str],
    limit: int = 3,
) -> list[dict[str, object]]:
    if not holdouts:
        return []
    candidate_book_ids = set(holdouts.values())
    for predictions in algorithms.values():
        for recommendation_ids in predictions.values():
            candidate_book_ids.update(recommendation_ids[:3])
    book_lookup = Book.objects.in_bulk(candidate_book_ids)
    case_studies = []
    for subject_key in sorted(holdouts.keys())[:limit]:
        holdout_book_id = holdouts[subject_key]
        best_strategy = None
        best_rank = None
        for name, predictions in algorithms.items():
            ranked = predictions.get(subject_key, [])
            if holdout_book_id in ranked:
                rank = ranked.index(holdout_book_id) + 1
                if best_rank is None or rank < best_rank:
                    best_strategy = name
                    best_rank = rank
        if best_strategy is None:
            best_strategy = "itemcf"
        ranked = algorithms.get(best_strategy, {}).get(subject_key, [])
        top_recommendations = [
            book_lookup[book_id].title
            for book_id in ranked[:3]
            if book_id in book_lookup
        ]
        case_studies.append(
            {
                "subject": subject_labels.get(subject_key, subject_key),
                "holdout_book": book_lookup.get(holdout_book_id).title if holdout_book_id in book_lookup else str(holdout_book_id),
                "best_strategy": best_strategy,
                "top_recommendations": top_recommendations,
                "hit_rank": best_rank,
            }
        )
    return case_studies


def _build_similarity_comparison(
    train_frame: pd.DataFrame,
    holdouts: dict[str, int],
) -> dict[str, dict[str, object]]:
    if not holdouts:
        return {}
    matrix = _interaction_matrix(train_frame)
    comparison = {}
    similarities = {
        "cosine": _item_similarity(matrix),
        "pearson": _pearson_item_similarity(matrix),
    }
    for name, similarity in similarities.items():
        predictions = _itemcf_predictions_with_similarity(
            train_frame,
            holdouts,
            max(k_values()),
            matrix,
            similarity,
        )
        metric_rows = _metric_rows(predictions, holdouts)
        best_row = _best_metric_row(metric_rows)
        comparison[name] = {
            "name": name,
            "best_precision": best_row["precision"],
            "best_recall": best_row["recall"],
            "best_k": best_row["k"],
            "user_count": len(holdouts),
            "metrics": metric_rows,
        }
    return comparison


def _build_random_split_summary(frame: pd.DataFrame) -> dict[str, object]:
    train_frame, holdouts, _subject_labels = _split_random_interactions(frame)
    if not holdouts:
        return {
            "train_interaction_count": int(len(train_frame.index)),
            "test_interaction_count": 0,
            "algorithms": [],
        }

    algorithms = {
        "hot": _hot_predictions(train_frame, holdouts, max(k_values())),
        "itemcf": _itemcf_predictions(train_frame, holdouts, max(k_values())),
        "usercf": _usercf_predictions(train_frame, holdouts, max(k_values())),
        "hybrid": _hybrid_predictions(train_frame, holdouts, max(k_values())),
    }
    algorithm_rows = []
    for name, predictions in algorithms.items():
        metric_rows = _metric_rows(predictions, holdouts)
        best_row = _best_metric_row(metric_rows)
        algorithm_rows.append(
            {
                "name": name,
                "precision": best_row["precision"],
                "recall": best_row["recall"],
                "best_k": best_row["k"],
                "test_subject_count": len(holdouts),
            }
        )
    return {
        "train_interaction_count": int(len(train_frame.index)),
        "test_interaction_count": int(len(holdouts)),
        "algorithms": algorithm_rows,
    }


def record_evaluation_runs(summary: dict, experiment_name: str = "leave-one-out-offline") -> list[EvaluationRun]:
    started_at = timezone.now()
    finished_at = timezone.now()
    dataset_name = summary.get("metadata", {}).get("dataset_name", "")
    runs = [
        EvaluationRun.objects.create(
            experiment_name=experiment_name,
            strategy=algorithm["name"],
            dataset_name=dataset_name,
            started_at=started_at,
            finished_at=finished_at,
            metric_summary=json.dumps(
                {
                    "best_precision": algorithm["best_precision"],
                    "best_recall": algorithm["best_recall"],
                    "best_k": algorithm["best_k"],
                    "user_count": algorithm["user_count"],
                },
                ensure_ascii=False,
            ),
        )
        for algorithm in summary.get("algorithms", [])
    ]
    return runs


def generate_evaluation_summary() -> dict:
    frame = _ratings_frame()
    train_frame, holdouts, subject_labels = _split_train_holdout(frame)
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
                    f"Evaluated on {user_count} leave-one-out subjects. "
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

    site_rows = frame.loc[frame["source"] == "site"] if not frame.empty else frame
    imported_rows = frame.loc[frame["source"] != "site"] if not frame.empty else frame
    curves = _build_curves(per_algorithm_rows)
    case_studies = _build_case_studies(algorithms, holdouts, subject_labels)
    similarity_comparison = _build_similarity_comparison(train_frame, holdouts)
    random_split = _build_random_split_summary(frame)
    return {
        "metadata": {
            "dataset_name": "site-ratings+goodbooks-10k",
            "site_user_count": int(site_rows["subject_key"].nunique()) if not site_rows.empty else 0,
            "dataset_user_count": int(imported_rows["subject_key"].nunique()) if not imported_rows.empty else 0,
            "interaction_count": int(len(frame.index)),
            "holdout_subject_count": user_count,
            "run_count": len(algorithm_payload),
        },
        "overview": overview,
        "algorithms": algorithm_payload,
        "curves": curves,
        "case_studies": case_studies,
        "similarity_comparison": similarity_comparison,
        "random_split": random_split,
    }
