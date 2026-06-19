from __future__ import annotations

import logging
from pathlib import Path


def setup_logger():
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger('delivery_system')
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')

        file_handler = logging.FileHandler(logs_dir / 'app.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.WARNING)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
