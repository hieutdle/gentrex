# Running on Minerva (Mount Sinai)

On Minerva, Mount Sinai's HPC cluster, one GPU job starts the OCR model with
[vLLM](https://docs.vllm.ai) and runs Gentrex against it. See
[Stage 1: PDF pages to text](stage1.md) for what the stage does, its output
and its settings.

You need a Minerva account and a project allocation (`acc_...`). Run
`mybalance` on a login node to see your allocations.

Steps 1 and 2 are done once. After that, each run is steps 3 and 4.

## Step 1: Log in and get Gentrex

Connect to the Mount Sinai VPN if you are off campus, then log in to a
Minerva login node with `ssh`.

Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Get the code and install it:

```bash
git clone https://github.com/hieutdle/gentrex.git
cd gentrex
uv sync
```

Do this on a login node: compute nodes have no internet access.

## Step 2: Download vLLM and the OCR model

Still on a login node, pick a folder with at least 40 GB free, for example
in your work directory, and download both into it:

```bash
mkdir -p /path/to/serving && cd /path/to/serving

module load apptainer
export APPTAINER_CACHEDIR=$PWD/apptainer-cache
apptainer pull vllm.sif docker://vllm/vllm-openai:latest
rm -rf apptainer-cache

uvx --from huggingface_hub hf download lightonai/LightOnOCR-3-4B \
  --local-dir models/LightOnOCR-3-4B
```

`apptainer pull` saves vLLM as one file, `vllm.sif`. Its download cache
takes about 16 GB and by default goes to your home folder, which has a
30 GB quota; `APPTAINER_CACHEDIR` keeps it here until `rm` deletes it.
`hf download` saves the model weights. Both are reused by every later
run.

## Step 3: Write the job script

Save this as `stage1.lsf` in the `gentrex` folder. Change the three marked
lines.

```bash
#!/bin/bash
#BSUB -J gentrex-stage1
#BSUB -P acc_xxx                       # <-- your allocation
#BSUB -q gpu
#BSUB -n 4
#BSUB -W 2:00
#BSUB -gpu num=1
#BSUB -R "select[a100] rusage[mem=8000] span[hosts=1]"
#BSUB -oo stage1.%J.log

SERVING=/path/to/serving               # <-- the folder from step 2
GENTREX=/path/to/gentrex               # <-- this repository

module load apptainer
mkdir -p "$SERVING/home"

apptainer exec --nv --home "$SERVING/home" --env HF_HUB_OFFLINE=1 \
  -B "$SERVING/models:/models" "$SERVING/vllm.sif" \
  vllm serve /models/LightOnOCR-3-4B \
    --served-model-name lightonai/LightOnOCR-3-4B \
    --port 8000 \
    --max-model-len 18000 \
    --default-chat-template-kwargs '{"enable_thinking": false}' \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-cache-gb 0 \
    --no-enable-prefix-caching &
server=$!

until curl -sf http://localhost:8000/v1/models > /dev/null; do
  kill -0 "$server" || { echo "vLLM stopped; see the log above"; exit 1; }
  sleep 5
done

cd "$GENTREX"
GENTREX_OCR_BASE_URL=http://localhost:8000/v1 .venv/bin/gentrex stage1
status=$?

kill "$server"
exit $status
```

What the script does:

1. Asks for one GPU, 4 cores and 2 hours.
2. Starts vLLM with the OCR model and waits until it answers. vLLM keeps
   its compile cache in `$SERVING/home`, outside your home folder.
3. Runs stage 1 on `data/raw/`, writing `results/pages.jsonl`.
4. Stops vLLM, which ends the job and frees the GPU.

Because Gentrex and vLLM run in the same job, no `.env` file, token or
network setup is needed.

`select[a100]` picks the GPU type. The OCR model's weights take 9 GB, so any
of them can hold it. Change it if the job waits a long time in the queue:

| Value | GPU | Memory |
| --- | --- | --- |
| `v100` | V100 | 16 GB |
| `a100` | A100 | 40 GB |
| `a10080g` | A100 | 80 GB |
| `l40s` | L40S | 48 GB |
| `h10080g` | H100 | 80 GB |
| `h100nvl` | H100 | 80 GB |

The current list is on the
[Minerva GPU page](https://labs.icahn.mssm.edu/minervalab/documentation/gpgpu/).

## Step 4: Submit the job

Put the reports in `data/raw/` inside the `gentrex` folder, then:

```bash
cd /path/to/gentrex
bsub < stage1.lsf
```

Follow it with:

```bash
bjobs                     # PEND = waiting for a GPU, RUN = running
tail -f stage1.*.log      # what vLLM and Gentrex print
```

To cancel, run `bkill <job ID>` with the ID that `bjobs` shows.

## Next

When the job is done, the result is in `results/pages.jsonl`, and the end of
the log lists any files that failed. Continue in the stage 1 guide:

- [Check the result](stage1.md#check-the-result)
- [When something goes wrong](stage1.md#when-something-goes-wrong)
- [Settings](stage1.md#settings)

Keep reports and results on Minerva, in a location approved for
[patient data](stage1.md#patient-data). Do not copy them to a laptop.
