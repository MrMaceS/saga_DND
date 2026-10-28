from app.ai.client import metrics


def get_ai_stats() -> dict:
    """Возвращает текущие метрики для /api/dev/ai-stats."""
    return metrics.to_dict()