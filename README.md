Python module for running scheduled backups using Restic

## Features
- Schedule multiple backups with different schedules and repository targets
- Local backups check if the backup device is mounted before running backups
- Supports stopping docker-compose containers before backup and starting them after
- Configurable via JSON

## Limitations
- At least one local repository must be configured
- Only linux is supported at this time

## Prerequisites
- Python 3 (tested on Python 3.12)
- Restic installed on the system
- Docker and Docker Compose (docker-compose-plugin) installed if stopping containers is enabled
- Instructions assume you are using a linux distribution using systemd

## Installation & Setup
- Create directory for installing the project (such as /etc/restic_scheduled_backups) and navigate to it
  - `mkdir /etc/restic_scheduled_backups`
  - `cd /etc/restic_scheduled_backups`
- Create a virtual environment and activate it run the command 
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
- Install the module using pip
  - `pip install git+https://github.com/ztif3/restic_scheduled_backups.git@v0.1.0`
- Create configuration file
  - `nano config.json`
   
  https://github.com/ztif3/restic-scheduled-backups/blob/08d1ae9191ea5fcdea779c875119511ec8e0001a/example_config.json#L1-L87
- Create a systemd service
  - `sudo nano /etc/systemd/system/restic_scheduled_backups.service`
  
  https://github.com/ztif3/restic-scheduled-backups/blob/e005b8cfbe1a01a58e39bbbe203590c616d7e16a/restic_scheduled_backups.service#L1-L12
- Set permissions on the service file
  - `sudo chmod 644 /etc/systemd/system/restic_scheduled_backups.service`
- Enable the service
  - `sudo systemctl daemon-reload`
  - `sudo systemctl enable restic_scheduled_backups.service`
