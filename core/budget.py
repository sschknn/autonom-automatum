"""Interne Ressourcenverwaltung und Buchhaltung für autonom-automatum."""
from core import config, database, logger

class BudgetEngine:
    def __init__(self):
        self.db = database.Database()
        self.log = logger.DualLogger()

    def can_afford(self, cost):
        budget = self.db.get_budget()
        return budget["balance"] >= cost

    def charge(self, cost):
        if self.can_afford(cost):
            self.db.update_budget(-cost, earn=0.0, spend=cost)
            self.log.info(f"Budget belastet: -{cost:.2f} (neuer Stand wird in DB aktualisiert)")
            return True
        else:
            self.log.warning(f"Budget nicht ausreichend für Kosten: {cost:.2f}")
            return False

    def earn(self, amount):
        self.db.update_budget(amount, earn=amount, spend=0.0)
        self.log.info(f"Budget erhöht: +{amount:.2f}")

    def regenerate(self):
        budget = self.db.get_budget()
        # Regeneration nur, wenn unter Maximum
        if budget["balance"] < config.MAX_BUDGET:
            delta = min(config.ENERGY_REGEN_PER_TICK, config.MAX_BUDGET - budget["balance"])
            self.db.update_budget(delta)
            self.db.reset_regen_time()
            self.log.info(f"Regeneration: +{delta:.2f} Energie (Budget: {budget['balance'] + delta:.2f})")
        else:
            self.log.debug("Budget bereits auf Maximum.")

    def is_paused(self):
        budget = self.db.get_budget()
        return budget["balance"] < config.ENERGY_COST_PER_TASK / 2  # Pausiert bei sehr niedrigem Budget
