from celery import shared_task

from src.core.logger import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def resolve_asset_symbols_task(self, target_id: int):
    """
    STUB: Resolves vendor symbols for a newly created TargetConfig.
    Will be fully implemented in AE38 & AE39.
    """
    logger.info("Stub: Resolution engine triggered", extra_data={"target_id": target_id})
    return True
