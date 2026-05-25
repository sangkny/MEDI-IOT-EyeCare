#!/bin/bash
ssh -i ~/.ssh/id_rsa root@192.168.0.23 "grep '^epoch' /tmp/retinal_v5_train.log 2>/dev/null | tail -1"
ssh -i ~/.ssh/id_rsa root@192.168.0.23 "grep -q 'OK checkpoint' /tmp/retinal_v5_train.log 2>/dev/null" && echo TRAINING_DONE && exit 0
echo TRAINING_RUNNING
exit 1
