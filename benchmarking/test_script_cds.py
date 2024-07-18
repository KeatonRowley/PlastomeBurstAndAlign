#!/usr/bin/env python3 

import subprocess
import os
import shutil
import sys
import time

# Get the current directory of the test script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the relative path to your Python script
MYSCRIPT = "../PlastomeRegionBurstAndAlign.py"

# Define the benchmarking dataset
dataset = sys.argv[1]

# Combine the directory of the test script with the relative path to the Python script
full_script_path = os.path.join(script_dir, MYSCRIPT)

# Define the path to the output directory
folder_CDS = dataset+"/output_CDS"

# Step 1: Extract the tar.gz file
subprocess.run(["tar", "-xf", dataset+".tar.gz"])

# Step 2: Change the current directory to the selected dataset
os.chdir(dataset)
subprocess.call('echo "Size of input dataset: $(ls *.gb 2>\\dev\\null | wc -l) GenBank files"', shell=True)
subprocess.call('echo ""', shell=True)

# Step 3: Create necessary directories
subprocess.run(["mkdir", "-p", folder_CDS])
subprocess.run(["mkdir", "-p", f"{folder_CDS}/01_unalign"])
subprocess.run(["mkdir", "-p", f"{folder_CDS}/02_aligned"])
subprocess.run(["mkdir", "-p", f"{folder_CDS}/02_aligned/fasta"])
subprocess.run(["mkdir", "-p", f"{folder_CDS}/02_aligned/nexus"])

# Step 4: Run your Python script using the full_script_path
run_start = time.time()
subprocess.run(["python3", full_script_path, "-i", ".", "-o", folder_CDS, "-s", "cds", "-t", "5", "-l", "6", "-n", "10"])
run_end = time.time()

# run this to remove the folder, if not can comment out
# Step 5: Delete the dataset directory and its contents
os.chdir(script_dir)  # Move back to the directory containing the test script
shutil.rmtree(dataset)
print("Directory '" + dataset + "' and its contents have been deleted")
print("Time required for analysis: %.2f seconds" % (run_end - run_start))

