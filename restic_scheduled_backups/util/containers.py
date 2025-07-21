
import logging
import subprocess
from os import PathLike

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)
    

def stop_container(container:PathLike):
    """ Function to stop a container.

    Args:
        container (str): path to the container to stop
    """

    logger.info(f'Stopping container {container}...')
    try:
        output=subprocess.run(['docker compose', 'down'], capture_output=True, cwd=container)
        logger.info(f'Container {container} stopped. {output.stdout.decode()}')
    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to stop container {container}: {e}')
        raise
    else:
        if output.returncode == 0:
            logger.info(f'Container {container} stopped successfully.')
            logger.debug(f'Results from stopping container {container}. \n{output.stdout.decode()}')
        else:
            logger.error(f'Failed to stop container {container}. \n{output.stderr.decode()}')
            raise subprocess.CalledProcessError(output.returncode, output.args, output.stdout, output.stderr) 

def start_container(container:PathLike):
    """ Function to start a container.

    Args:
        container (str): path to the container to start
    """

    logger.info(f'Starting container {container}...')
    try:
        output = subprocess.run(['docker compose', 'up', '-d'], check=True, capture_output=True, cwd=container)
        logger.info(f'Container {container} started. {output.stdout.decode()}')
    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to start container {container}: {e}')
        raise
    else:
        if output.returncode == 0:
            logger.info(f'Container {container} started successfully. \n{output.stdout.decode()}')
            logger.debug(f'Results from starting container {container}. \n{output.stdout.decode()}')
        else:
            logger.error(f'Failed to start container {container}. \n{output.stderr.decode()}')
            raise subprocess.CalledProcessError(output.returncode, output.args, output.stdout, output.stderr) 