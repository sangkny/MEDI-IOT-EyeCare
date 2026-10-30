#!/bin/bash
PC1="/mnt/e/Office_Automation/idea-collection/projects/PORT-ALLOCATION.md"
PC2="/mnt/c/Tools/downloads/phase005-inspect/projects/PORT-ALLOCATION.md"
echo "PC1_AUTHORITATIVE_ACCESSIBLE=$([ -f "$PC1" ] && echo YES || echo NO)"
if [ -f "$PC2" ]; then
  echo "PC2_SNAPSHOT_PATH=$PC2"
  sha256sum "$PC2"
  echo "PC2_NOT_AUTHORITATIVE=YES"
else
  echo "PC2_SNAPSHOT_MISSING"
fi
