#!/bin/bash
#SBATCH -t 48:00:00
#SBATCH -N 1
#SBATCH -n 4
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --constraint=12GB
#SBATCH -p normal

# Setting up singularity variable
SINGULARITY_CONTAINER="/om2/user/tzhao/singularity/ortools-pytorch-gpu.simg"
STARTING_DIRECTORY="/om2/user/tzhao/6883/curriculum-tsp"

cd ${STARTING_DIRECTORY}
module load openmind/singularity
hostname
nvidia-smi

singularity exec --nv ${SINGULARITY_CONTAINER} python3 src/main.py --mode all --run-name static-exp-1 --curriculum 1 &
singularity exec --nv ${SINGULARITY_CONTAINER} python3 src/main.py --mode all --run-name static-exp-2 --curriculum 2 &
singularity exec --nv ${SINGULARITY_CONTAINER} python3 src/main.py --mode all --run-name static-exp-3 --curriculum 3 &

sleep 3h
nvidia-smi
sleep 48h

