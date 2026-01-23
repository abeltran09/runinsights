class StravaRateLimiter:

    def __init__(self, read_15_limit: int = 100, read_daily_limit: int = 1000):

        self.read_rate_15_limit = read_15_limit
        self.read_rate_15_usage = 0
        self.read_daily_limit = read_daily_limit
        self.read_daily_usage = 0

    def update_from_headers(self, headers: dict) -> None:
        usage_15, usage_daily = map(
            int, headers['x-readratelimit-usage'].split(",")
        )

        limit_15, limit_daily = map(
            int, headers['x-readratelimit-limit'].split(",")
        )

        self.read_rate_15_usage = usage_15
        self.read_daily_usage = usage_daily
        self.read_rate_15_limit = limit_15
        self.read_daily_limit = limit_daily

    def should_throttle(self, buffer: int = 10) -> bool:
        return (
            self.read_rate_15_usage >= self.read_rate_15_limit - buffer or
            self.read_daily_usage >= self.read_daily_limit - buffer
        )





