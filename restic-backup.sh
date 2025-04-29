#!/bin/bash

# Variables
BACKUP_PATH=/documents
RET_DAYS=14
RET_WEEKS=16
RET_MONTHS=18
RET_YEARS=3

MAIN_REPO=/mnt/backup1$BACKUP_PATH
SECOND_REPO=/mnt/backup2$BACKUP_PATH
CLOUD_REPO=s3:https://s3.us-east-005.backblazeb2.com/fitznet-backup$BACKUP_PATH

export AWS_ACCESS_KEY_ID=005fcdc17a144e00000000002
export AWS_SECRET_ACCESS_KEY=K005ZbyqO0BONZN9BHaZF4K39M1tsd8

# Create repos if they do not exist
if [ ! -d "$MAIN_REPO/snapshots" ]; then
	echo Creating $MAIN_REPO
	restic init \
		-r $MAIN_REPO \
		--password-file restic-pw  &
	wait $!
else
	echo $MAIN_REPO exists. Skipping Creation.
fi

if [ ! -d "$SECOND_REPO/snapshots" ]; then
	echo Creating $SECOND_REPO
	restic init \
		-r $SECOND_REPO \
		--password-file restic-pw &
	wait $!
else
        echo $SECOND_REPO exists. Skipping Creation.
fi

if restic -r $CLOUD_REPO --password-file restic-pw cat config; then
        echo Creating $CLOUD_REPO
        restic init \
                -r $CLOUD_REPO \
                --password-file restic-pw &
        wait $!
else
        echo $CLOUD_REPO exists. Skipping Creation.
fi

# Remove locks in case other stale processes kept them in
echo unlockin
restic unlock \
	-r $MAIN_REPO \
	--password-file restic-pw &
wait $!

restic unlock \
	-r $SECOND_REPO \
	--password-file restic-pw &
wait $!

restic unlock \
        -r $CLOUD_REPO \
        --password-file restic-pw &
wait $!

# Backup to primary backup drive
echo Backing up to $MAIN_REPO
restic backup \
	--verbose \
	-r $MAIN_REPO \
	--password-file restic-pw \
	. &
wait $!

# Cleanup primary backup
echo Cleaing up $MAIN_REPO
restic forget \
        --verbose \
        -r $MAIN_REPO \
        --password-file restic-pw \
        --prune \
        --keep-daily $RET_DAYS \
        --keep-weekly $RET_WEEKS \
        --keep-monthly $RET_MONTHS \
        --keep-yearly $RET_YEARS &
wait $!

# Copy backup to secondary drive
echo Copying from $MAIN_REPO to $SECOND_REPO
restic copy \
	--verbose \
	-r $SECOND_REPO \
	--password-file restic-pw \
	--from-repo $MAIN_REPO \
	--from-password-file restic-pw &
wait $!

echo Cleaing up $SECOND_REPO
restic forget \
        --verbose \
        -r $SECOND_REPO \
        --password-file restic-pw \
        --prune \
        --keep-daily $RET_DAYS \
        --keep-weekly $RET_WEEKS \
        --keep-monthly $RET_MONTHS \
        --keep-yearly $RET_YEARS &
wait $!

# Copy backup to Backblaze
echo Copying from $MAIN_REPO to $CLOUD_REPO
restic copy \
	--verbose \
	-r $CLOUD_REPO \
        --password-file restic-pw \
	--from-repo $MAIN_REPO \
	--from-password-file restic-pw &
wait $!


echo Cleaing up $CLOUD_REPO
restic forget \
        --verbose \
        -r $CLOUD_REPO \
        --password-file restic-pw \
        --prune \
        --keep-daily $RET_DAYS \
        --keep-weekly $RET_WEEKS \
        --keep-monthly $RET_MONTHS \
        --keep-yearly $RET_YEARS &
wait $!
