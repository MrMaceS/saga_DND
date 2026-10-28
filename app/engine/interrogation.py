from engine import rules


class InterrogationManager:
    """Управляет допросом пленных."""

    @staticmethod
    def is_allowed(enemy_state: str, enemy_zone: str, hero_zone: str) -> bool:
        """Можно ли допросить этого врага."""
        return rules.interrogation_allowed(enemy_state, enemy_zone, hero_zone)

    @staticmethod
    def calculate_dc(hero_interrogation_style: str, has_leverage: bool) -> int:
        """
        Вычисляет сложность допроса.
        В MVP базовая сложность 11, наличие улики/рычага даёт +2 (упрощённо).
        """
        base = "normal"
        tags = ["prepared"] if has_leverage else []
        return rules.compute_difficulty(base, tags)