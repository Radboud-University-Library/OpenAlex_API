class Runner:
    BATCH_SIZE = 25
    MAX_PARALLEL_BATCHES = 5

    @staticmethod
    async def run_batches(
        batcher,
        update_fn,
    ):
        await batcher.run(update_fn=update_fn)