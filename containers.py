
import logging
import subprocess
from os import PathLike


        

    

def stop_container(container:PathLike):
    """ Function to stop a container.

    Args:
        container (str): path to the container to stop
    """

    logging.info(f'Stopping container {container}...')
    try:
        output=subprocess.run(['docker-compose', 'down'], capture_output=True, cwd=container)
        logging.info(f'Container {container} stopped. {output.stdout.decode()}')
    except subprocess.CalledProcessError as e:
        logging.error(f'Failed to stop container {container}: {e}')
        raise
    else:
        if output.returncode == 0:
            logging.info(f'Container {container} stopped successfully.')
            logging.debug(f'Results from stopping container {container}. \n{output.stdout.decode()}')
        else:
            logging.error(f'Failed to stop container {container}. \n{output.stderr.decode()}')
            raise subprocess.CalledProcessError(output.returncode, output.args, output.stdout, output.stderr) 

def start_container(container:PathLike):
    """ Function to start a container.

    Args:
        container (str): path to the container to start
    """

    logging.info(f'Starting container {container}...')
    try:
        output = subprocess.run(['docker-compose', 'up', '-d'], check=True, capture_output=True, cwd=container)
        logging.info(f'Container {container} started. {output.stdout.decode()}')
    except subprocess.CalledProcessError as e:
        logging.error(f'Failed to start container {container}: {e}')
        raise
    else:
        if output.returncode == 0:
            logging.info(f'Container {container} started successfully. \n{output.stdout.decode()}')
            logging.debug(f'Results from starting container {container}. \n{output.stdout.decode()}')
        else:
            logging.error(f'Failed to start container {container}. \n{output.stderr.decode()}')
            raise subprocess.CalledProcessError(output.returncode, output.args, output.stdout, output.stderr) 