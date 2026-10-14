# Running on Minerva (Mount Sinai)

On Minerva, Mount Sinai's HPC cluster, each stage runs as one GPU job that
starts the stage's model with [vLLM](https://docs.vllm.ai) and runs Gentrex
against it. See [Stage 1](stage1.md), [Stage 2](stage2.md) and
[Stage 3](stage3.md) for what each stage does, its output and its settings.

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
#BSUB -W 0:30
#BSUB -gpu num=1
#BSUB -R "select[a100] rusage[mem=8000] span[hosts=1]"
#BSUB -oo stage1.%J.log

SERVING=/path/to/serving               # <-- the folder from step 2
GENTREX=/path/to/gentrex               # <-- this repository

module load apptainer
mkdir -p "$SERVING/home"
port=$((10000 + LSB_JOBID % 20000))

apptainer exec --nv --home "$SERVING/home" --env HF_HUB_OFFLINE=1 \
  -B "$SERVING/models:/models" "$SERVING/vllm.sif" \
  vllm serve /models/LightOnOCR-3-4B \
    --served-model-name lightonai/LightOnOCR-3-4B \
    --port "$port" \
    --max-model-len 18000 \
    --default-chat-template-kwargs '{"enable_thinking": false}' \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-cache-gb 0 \
    --no-enable-prefix-caching &
server=$!

until curl -sf "http://localhost:$port/v1/models" > /dev/null; do
  kill -0 "$server" || { echo "vLLM stopped; see the log above"; exit 1; }
  sleep 5
done

cd "$GENTREX"
GENTREX_OCR_BASE_URL=http://localhost:$port/v1 .venv/bin/gentrex stage1
status=$?

kill "$server"
exit $status
```

What the script does:

1. Asks for one GPU, 4 cores, 32 GB of memory and 30 minutes.
   `rusage[mem=8000]` is in MB per core, so 4 cores get 32 GB. It is the
   node's memory, not the GPU's; vLLM uses about 6 GB of it.
2. Starts vLLM with the OCR model and waits until it answers. vLLM keeps
   its compile cache in `$SERVING/home`, outside your home folder. The port
   comes from the job ID: on the default port, 8000, Gentrex could reach the
   vLLM of another job on the same node and send it the reports.
3. Runs stage 1 on `data/raw/`, writing a new folder in `results/transcribe/`.
4. Stops vLLM, which ends the job and frees the GPU.

Because Gentrex and vLLM run in the same job, no `.env` file, token or
network setup is needed.

`-W 0:30` limits the job to 30 minutes, including the few minutes vLLM takes
to start. A short limit gets the job out of the queue sooner. If the log
shows `TERM_RUNLIMIT`, the job was stopped before it finished: raise `-W`
and submit again. Gentrex logs its speed per minute at the end of a run;
use it to set `-W` for the next batch.

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
bjobs -p3 <job ID>        # why a PEND job is waiting
tail -f stage1.*.log      # what vLLM and Gentrex print
```

To cancel, run `bkill <job ID>` with the ID that `bjobs` shows.

## Next

When the job is done, the result is in `results/transcribe/latest/`, and the
end of the log lists any files that failed. Continue in the stage 1 guide:

- [Check the result](stage1.md#check-the-result)
- [When something goes wrong](stage1.md#when-something-goes-wrong)
- [Settings](stage1.md#settings)

Keep reports and results on Minerva, in a location approved for
[patient data](stage1.md#patient-data). Do not copy them to a laptop.

## Stage 2: Which pages to keep

Stage 2 is a second job, run after a stage 1 job has finished. It uses the
`vllm.sif` from step 2 with a larger text model.

### Download the text model

Once, on a login node, download the model into the folder from step 2:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download google/gemma-4-26B-A4B-it \
  --local-dir models/gemma-4-26B-A4B-it
```

The download is about 50 GB. If Hugging Face refuses it, open the
model's page there, accept Google's terms, log in with
`uvx --from huggingface_hub hf auth login`, and download again.

The model needs vLLM 0.25 or newer. If your `vllm.sif` is older, pull it again
as in step 2.

### Write the job script

Save this as `stage2.lsf` in the `gentrex` folder. Change the three marked
lines.

```bash
#!/bin/bash
#BSUB -J gentrex-stage2
#BSUB -P acc_xxx                       # <-- your allocation
#BSUB -q gpu
#BSUB -n 4
#BSUB -W 0:30
#BSUB -gpu num=1
#BSUB -R "select[h100nvl] rusage[mem=8000] span[hosts=1]"
#BSUB -oo stage2.%J.log

SERVING=/path/to/serving               # <-- the folder from step 2
GENTREX=/path/to/gentrex               # <-- this repository

module load apptainer
mkdir -p "$SERVING/home"
port=$((10000 + LSB_JOBID % 20000))

apptainer exec --nv --home "$SERVING/home" --env HF_HUB_OFFLINE=1 \
  -B "$SERVING/models:/models" "$SERVING/vllm.sif" \
  vllm serve /models/gemma-4-26B-A4B-it \
    --served-model-name google/gemma-4-26B-A4B-it \
    --port "$port" \
    --max-model-len 16384 &
server=$!

until curl -sf "http://localhost:$port/v1/models" > /dev/null; do
  kill -0 "$server" || { echo "vLLM stopped; see the log above"; exit 1; }
  sleep 5
done

cd "$GENTREX"
GENTREX_LLM_BASE_URL=http://localhost:$port/v1 .venv/bin/gentrex stage2
status=$?

kill "$server"
exit $status
```

It works like the stage 1 script, and runs stage 2 on the newest finished
stage 1 run, writing a new folder in `results/pagedecide/`. Do not add
`--no-enable-prefix-caching` from the stage 1 script: with the cache, vLLM
reads each page once for all of its questions.

The model's weights take about 50 GB, so the job needs a GPU with 80 GB.
`select[h100nvl]` asks for an H100; `a10080g` and `h10080g` from the table in
step 3 also have 80 GB. Change it if the job waits a long time in the queue.

### Submit the job

```bash
cd /path/to/gentrex
bsub < stage2.lsf
```

Follow it with `bjobs` and `tail -f stage2.*.log`, as in step 4.

When the job is done, the result is in `results/pagedecide/latest/`, and the
end of the log lists any files that failed. Continue in the stage 2 guide:

- [Check the result](stage2.md#check-the-result)
- [Change the questions or the threshold](stage2.md#settings)
- [When something goes wrong](stage2.md#when-something-goes-wrong)

## Stage 3: One record per report

Stage 3 is a third job, run after a stage 2 job has finished. It uses the
`vllm.sif` from step 2 with a larger text model.

### Download the model

Once, on a login node, download the model into the folder from step 2:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download google/gemma-4-31B-it \
  --local-dir models/gemma-4-31B-it
```

The download is about 62 GB. If Hugging Face refuses it, accept Google's
terms on the model's page and log in, as for the stage 2 model, then
download again.

### Write the job script

Save this as `stage3.lsf` in the `gentrex` folder. Change the three marked
lines.

```bash
#!/bin/bash
#BSUB -J gentrex-stage3
#BSUB -P acc_xxx                       # <-- your allocation
#BSUB -q gpu
#BSUB -n 4
#BSUB -W 0:30
#BSUB -gpu num=2
#BSUB -R "select[h100nvl] rusage[mem=8000] span[hosts=1]"
#BSUB -oo stage3.%J.log

SERVING=/path/to/serving               # <-- the folder from step 2
GENTREX=/path/to/gentrex               # <-- this repository

module load apptainer
mkdir -p "$SERVING/home"
port=$((10000 + LSB_JOBID % 20000))

apptainer exec --nv --home "$SERVING/home" --env HF_HUB_OFFLINE=1 \
  -B "$SERVING/models:/models" "$SERVING/vllm.sif" \
  vllm serve /models/gemma-4-31B-it \
    --served-model-name google/gemma-4-31B-it \
    --port "$port" \
    --tensor-parallel-size 2 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.95 &
server=$!

until curl -sf "http://localhost:$port/v1/models" > /dev/null; do
  kill -0 "$server" || { echo "vLLM stopped; see the log above"; exit 1; }
  sleep 5
done

cd "$GENTREX"
GENTREX_LLM_BASE_URL=http://localhost:$port/v1 .venv/bin/gentrex stage3
status=$?

kill "$server"
exit $status
```

It works like the stage 2 script, and runs stage 3 on the newest finished
stage 2 run, writing a new folder in `results/extract/`. Do not add
`--no-enable-prefix-caching` from the stage 1 script: every request starts
with the same instruction and schema, which vLLM then reads once.

Stage 3 is the slowest stage, because the model writes a whole record for
every report. If the job reaches the 30-minute limit, raise `-W` as in
step 3.

The model's weights take about 62 GB. On one 80 GB GPU, that leaves too
little memory for a 32,768-token request, and vLLM stops at startup. Use
two H100s or one B200:

- **Two H100s**, as in the script. `-gpu num=2` asks for two GPUs,
  `span[hosts=1]` keeps them on one node, and `--tensor-parallel-size 2`
  splits the model across them. `a10080g` and `h10080g` from the table in
  step 3 also work in place of `h100nvl`.
- **One B200**, with 180 GB. Change `-gpu num=2` to `-gpu num=1` and
  `select[h100nvl]` to `select[b200]`, and remove
  `--tensor-parallel-size 2`. The B200 nodes run jobs only for some
  allocations. If the job stays in PEND and `bjobs -p3 <job ID>` names
  `aims_limit`, yours is not one of them: cancel it with `bkill` and use two
  H100s.

### Submit the job

```bash
cd /path/to/gentrex
bsub < stage3.lsf
```

Follow it with `bjobs` and `tail -f stage3.*.log`, as in step 4.

When the job is done, the result is in `results/extract/latest/`, and the
end of the log lists any files that failed. Continue in the stage 3 guide:

- [Check the result](stage3.md#check-the-result)
- [Change the schema](stage3.md#settings)
- [When something goes wrong](stage3.md#when-something-goes-wrong)
