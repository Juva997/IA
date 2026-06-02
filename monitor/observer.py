class SystemObserver:
    def __init__(self, event_bus, logger, metrics):
        self.logger = logger
        self.metrics = metrics

        event_bus.on("step_executed", self.on_step)
        event_bus.on("plan_created", self.on_plan)

    def on_step(self, data):
        self.logger.info(f"STEP: {data['step']}")
        self.metrics.record_step()

        if data.get("feedback") == "fail":
            self.metrics.record_error()
        else:
            self.metrics.record_success()

    def on_plan(self, plan):
        self.logger.debug(f"PLAN: {plan}")
