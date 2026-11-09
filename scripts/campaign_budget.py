"""Durable pre-request reservations for a bounded classification campaign."""

from directory import read_json, write_json


class CampaignBudget:
    def __init__(self, path, limit):
        self.path = path
        self.state = read_json(path) if path.exists() else {"limit": limit, "requests": {}}
        if self.state["limit"] != limit:
            raise ValueError("DeepSeek campaign budget differs from its saved limit")

    @property
    def spent(self):
        return sum(row["charged"] for row in self.state["requests"].values())

    def reserve(self, request_id, amount):
        previous = self.state["requests"].get(request_id)
        if previous and previous["status"] == "pending":
            raise ValueError("DeepSeek prior request has unknown billing")
        if self.spent + amount > self.state["limit"]:
            raise ValueError("DeepSeek campaign budget exhausted")
        if previous:
            request_id = request_id + ":" + str(len(self.state["requests"]))
        self.state["requests"][request_id] = {"status": "pending", "charged": amount}
        write_json(self.path, self.state)
        return request_id

    def settle(self, request_id, amount):
        row = self.state["requests"][request_id]
        if amount < 0 or amount > row["charged"]:
            raise ValueError("DeepSeek billing exceeds reservation")
        row.update(status="settled", charged=amount)
        write_json(self.path, self.state)
