class Runner:
    BATCH_SIZE = 100
    MAX_PARALLEL_BATCHES = 10

    @staticmethod
    async def run_batches(
        batcher,
        update_fn,
    ):
        await batcher.run(update_fn=update_fn)
