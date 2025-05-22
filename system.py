import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def list_mounted_partitions() -> dict[str:list[str]]:
    """ Generates a list of mounted partitions with a list of their mountpoints

    Returns:
        dict[str:list[str]]: dictionary with the names of the mounted partitions as keys and a list
                             of all mount points as the values
    """

    mount_list:dict[str:list[str]] = {}
    logger.info('Listing all mounted partitions')
    try:
        output = subprocess.run(['lsblk','-J','-o','+LABEL'], capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error('Unable to get list of all mounted partitions')
        raise
    finally:
        output_dict = json.loads(output)

        # Check if block devices exist
        if 'blockdevices' in output_dict:
            # Loop through all block devices
            for device in output_dict['blockdevices']:
                # Get device name
                device_name = 'unnamed device'
                
                if 'name' in device:
                    device_name = device['name']

                # Check if the device has any children
                if 'children' in device:
                    for child in device['children']:
                        # Get child name
                        child_name = 'unnamed child' 
                        
                        if 'name' in child:
                            child_name = child['name']

                        # Check if child has mountpoints
                        if 'mountpoints' in child:
                            mount_list[child_name] = child['mountpoints']

                            logger.debug(f'{len(mount_list[child_name])} mount points found for child "{child_name}" for block device "{device_name}"')

                        else:
                            logger.debug(f'No Mount points found in child "{child_name}" for block device "{device_name}"')


                else:
                    
                    logger.debug(f'No children found in block device "{device_name}"')
        else:
            logger.error('no block devices found in lsblk output')

    return mount_list


    


