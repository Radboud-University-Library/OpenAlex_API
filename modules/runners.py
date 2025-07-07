from modules.api import ApiRequest, Entities, Session
from modules.batching import BatchProcessor


class Runner:
    BATCH_SIZE = 25
    MAX_PARALLEL_BATCHES = 5

    @staticmethod
    async def enrich_dataframe(
        df,
        entity_type,
        column_name,
        update_fn,
        batch_size=None,
        max_parallel_batches=None
    ):
        batch_size = batch_size or Runner.BATCH_SIZE
        max_parallel_batches = max_parallel_batches or Runner.MAX_PARALLEL_BATCHES

        async with Session() as aio_session:
            request = ApiRequest(session=aio_session)
            entities = Entities(entity_type, request=request)

            batcher = BatchProcessor(
                df=df,
                column_name=column_name,
                entities_instance=entities,
                batch_size=batch_size,
                max_parallel_batches=max_parallel_batches
            )

            await batcher.run(update_fn=update_fn)
