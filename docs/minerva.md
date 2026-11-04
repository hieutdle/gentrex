# Running on Minerva (Mount Sinai)

On Minerva, Mount Sinai's high-performance computing cluster, stages 1 to 3
of Gentrex each run as one batch job on a GPU node. The job starts the stage's
model with [vLLM](https://docs.vllm.ai), runs Gentrex against it, and stops
vLLM when Gentrex is done. Stage 3 can instead use Minerva's AI service,
which runs the model for you, as
[Use Minerva's AI service instead of a job](#use-minervas-ai-service-instead-of-a-job)
explains. Stages 4 to 6 need no GPU, so you run them yourself in an
interactive session. The stage pages explain what each stage
does, what it writes and how to change its settings.

Minerva schedules jobs with LSF. You describe a job in a script, submit the
script with `bsub`, and LSF runs the job when a node with the GPUs you asked
for is free. The jobs run vLLM with Apptainer, which runs software packaged as
a container image, one file that holds a program and everything it needs.

You need a Minerva account and a project allocation, whose name starts with
`acc_`. Run `mybalance` on a login node to see your allocations.

## Set up once

### Log in

Connect to the Mount Sinai VPN if you are off campus, then log in to a Minerva
login node with `ssh`. Do all of the setup on a login node, because compute
nodes have no internet access.

### Install Gentrex

Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Reports and results must stay on Minerva, in storage approved for patient
data. Don't copy them to a laptop. Gentrex keeps the reports in its
`data/raw/` folder and the results in `results/`, so clone it into approved
storage. Then install it:

```bash
git clone https://github.com/hieutdle/gentrex.git
cd gentrex
uv sync
```

### Pull vLLM

Pick a folder for vLLM and the models, such as one in your work directory. The
job scripts call it the serving folder. It needs at least 40 GB free for vLLM
and the stage 1 model. The stage 2 model adds about 50 GB, and the stage 3
model about 62 GB.

```bash
mkdir -p /path/to/serving && cd /path/to/serving

module load apptainer
export APPTAINER_CACHEDIR=$PWD/apptainer-cache
apptainer pull vllm.sif docker://vllm/vllm-openai:latest
rm -rf apptainer-cache
```

`apptainer pull` saves vLLM as one file, `vllm.sif`, which every job reuses.
The pull also fills a download cache of about 16 GB. By default, the cache
goes to your home folder, which has a 30 GB quota. `APPTAINER_CACHEDIR` puts
it in the serving folder instead, and `rm` deletes it after the pull.

Stage 2 needs vLLM 0.25 or newer, and stage 3 needs 0.19.1 or newer. To see
the version in your `vllm.sif`, run `apptainer exec vllm.sif vllm --version`.
If it is older than 0.25, pull it again.

## Stage 1: Transcribe PDF pages

### Download the OCR model

Once, on a login node, download the model into the serving folder:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download lightonai/LightOnOCR-3-4B \
  --local-dir models/LightOnOCR-3-4B
```

`hf download` saves the model's weights, the numbers it learned in training.
They take about 9 GB in `models/LightOnOCR-3-4B`, and every stage 1 job
reuses them.

### Write the job script

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

SERVING=/path/to/serving               # <-- the serving folder
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

The `#BSUB` lines tell LSF what the job needs:

- `-J gentrex-stage1` names the job, and `-P acc_xxx` charges it to your
  allocation.
- `-q gpu` sends the job to the GPU queue.
- `-n 4` and `rusage[mem=8000]` ask for 4 CPU cores with 8,000 MB of memory
  each, 32 GB in all. This is the node's memory, not the GPU's, and vLLM uses
  about 6 GB of it.
- `-W 0:30` limits the job to 30 minutes.
- `-gpu num=1` and `select[a100]` ask for one A100 GPU, and `span[hosts=1]`
  keeps the job on one node.
- `-oo stage1.%J.log` writes everything the job prints to
  `stage1.<job ID>.log`.

The rest of the script does four things:

1. It picks a port from the job ID, so that Gentrex reaches only this job's
   vLLM. On the default port, 8000, Gentrex could reach the vLLM of another
   job on the same node and send it the reports.
2. It starts vLLM in the background and waits until vLLM answers. If vLLM
   stops instead, the job ends with `vLLM stopped; see the log above`.
3. It runs stage 1 on `data/raw/`, which writes a new folder in
   `results/transcribe/`. The script passes the server's address in
   `GENTREX_OCR_BASE_URL`. Gentrex and vLLM run in the same job, so no `.env`
   file, API key or network setup is needed.
4. It stops vLLM, which ends the job and frees the GPU. The job ends with
   Gentrex's exit code.

`apptainer exec` runs `vllm serve` inside `vllm.sif`, with these options:

- `--nv` gives the container access to the node's NVIDIA GPUs.
- `--home "$SERVING/home"` makes `home/` in the serving folder the home folder
  inside the container. vLLM keeps its compile cache there, outside your home
  folder and its quota.
- `--env HF_HUB_OFFLINE=1` stops vLLM from contacting Hugging Face, which
  compute nodes can't reach. vLLM loads the model from its folder instead.
- `-B "$SERVING/models:/models"` makes the `models` folder visible inside the
  container as `/models`.

`vllm serve` loads the model from `/models/LightOnOCR-3-4B`, with these
options:

- `--served-model-name lightonai/LightOnOCR-3-4B` is the name the server lists
  at `/v1/models`. Gentrex asks for the model by this name
  (`transcribe.ocr.model` in settings.yaml). Without the option, the name
  would be the folder, `/models/LightOnOCR-3-4B`.
- `--port "$port"` uses the port from the job ID.
- `--max-model-len 18000` and `--default-chat-template-kwargs` are explained
  in [stage 1, step 3](stage1.md#step-3-start-the-ocr-server).
- `--limit-mm-per-prompt '{"image": 1}'` allows one image per request. Gentrex
  sends one page image per request, and vLLM sets memory aside for as many
  images as a request may hold.
- `--mm-processor-cache-gb 0` turns off vLLM's cache of processed images.
  Every page image is sent once, so the cache would only take memory.
- `--no-enable-prefix-caching` turns off
  prefix caching. Every request holds a different page
  image, so requests share no start that vLLM could reuse.

### Choose the GPU and time limit

`-W 0:30` gives the job 30 minutes, including the few minutes vLLM takes to
start. A short limit gets the job out of the queue sooner. If the log shows
`TERM_RUNLIMIT`, LSF stopped the job before it finished. Raise `-W` and submit
again. The last line of a run gives Gentrex's speed in pages per minute, which
you can use to set `-W` for the next batch.

`select[a100]` picks the GPU type. The OCR model's weights take 9 GB, so any of
these GPUs can hold it. Pick another type if the job waits a long time in the
queue:

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

### Submit the job

Put the reports in `data/raw/` inside the `gentrex` folder, then submit the
script:

```bash
cd /path/to/gentrex
bsub < stage1.lsf
```

Follow the job with:

```bash
bjobs                     # PEND = waiting for a GPU, RUN = running
bjobs -p3 <job ID>        # why a PEND job is waiting
tail -f stage1.*.log      # what vLLM and Gentrex print
```

To cancel the job, run `bkill <job ID>` with the ID that `bjobs` shows.

When the job is done, the result is in `results/transcribe/latest/`, and the
end of the log lists any files that failed. Below that, LSF's summary gives
Gentrex's exit code, as `Successfully completed.` for 0 or
`Exited with exit code 1.` for 1. Continue on the stage 1 page:

- [Check the result](stage1.md#check-the-result)
- [When something goes wrong](stage1.md#when-something-goes-wrong)
- [Settings](stage1.md#settings)

## Stage 2: Decide which pages to keep

Run stage 2 after a stage 1 job has finished.

### Download the model

Once, on a login node, download the model into the serving folder:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download google/gemma-4-26B-A4B-it \
  --local-dir models/gemma-4-26B-A4B-it
```

The download is about 50 GB. If Hugging Face refuses it, open the model's page
there and accept Google's terms. Then log in with
`uvx --from huggingface_hub hf auth login`, and download again.

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

SERVING=/path/to/serving               # <-- the serving folder
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

The script works like the stage 1 script. It differs in these ways:

- It asks for an H100 GPU with `select[h100nvl]`. The next section explains
  the choice.
- vLLM loads `gemma-4-26B-A4B-it` with `--max-model-len 16384`, which
  [stage 2, step 1](stage2.md#step-1-start-the-model-server) explains.
- It keeps prefix caching on, because Gentrex asks all questions about a page
  one after another. vLLM then reads each page once for all of them.
- It leaves out stage 1's image options, because Gentrex sends this model text
  only.
- It runs stage 2, with the server's address in `GENTREX_LLM_BASE_URL`. Stage
  2 reads the newest finished stage 1 run and writes a new folder in
  `results/pagedecide/`.

### Choose the GPU and time limit

The model's weights take about 50 GB, so the job needs a GPU with 80 GB.
`select[h100nvl]` asks for an H100. `a10080g` and `h10080g` from the
[stage 1 table](#choose-the-gpu-and-time-limit) also have 80 GB. Use one of
them if the job waits a long time in the queue.

`-W 0:30` gives the job 30 minutes, as for stage 1. If the log shows
`TERM_RUNLIMIT`, raise `-W` and submit again.

### Submit the job

```bash
cd /path/to/gentrex
bsub < stage2.lsf
```

Follow it with `bjobs` and `tail -f stage2.*.log`, as for stage 1. When the
job is done, the result is in `results/pagedecide/latest/`, and the end of the
log lists any files that failed. Continue on the stage 2 page:

- [Check the result](stage2.md#check-the-result)
- [Change the questions or the threshold](stage2.md#settings)
- [When something goes wrong](stage2.md#when-something-goes-wrong)

## Stage 3: Extract report data

Run stage 3 after a stage 2 job has finished.

### Download the model

Once, on a login node, download the model into the serving folder:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download google/gemma-4-31B-it \
  --local-dir models/gemma-4-31B-it
```

The download is about 62 GB. If Hugging Face refuses it, accept Google's terms
on the model's page and log in, as for the stage 2 model. Then download again.

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

SERVING=/path/to/serving               # <-- the serving folder
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

The script works like the stage 2 script. It differs in these ways:

- It asks for two GPUs with `-gpu num=2`, and `span[hosts=1]` keeps them on
  one node.
- vLLM loads `gemma-4-31B-it` and splits it across the two GPUs with
  `--tensor-parallel-size 2`. `--max-model-len 32768` and
  `--gpu-memory-utilization 0.95` are explained in
  [stage 3, step 1](stage3.md#step-1-start-the-model-server).
- It keeps prefix caching on, because every request starts with the same
  instruction and schema. vLLM then reads them once.
- It runs stage 3, which reads the newest finished stage 2 run and writes a
  new folder in `results/extract/`.

### Choose the GPU and time limit

The model's weights take about 62 GB. On one 80 GB GPU, that leaves too little
memory for a 32,768-token request, and vLLM stops at startup. Use two H100s or
one B200:

- **Two H100s**, as in the script. `a10080g` and `h10080g` from the
  [stage 1 table](#choose-the-gpu-and-time-limit) also work in place of
  `h100nvl`.
- **One B200**, with 192 GB. Change `-gpu num=2` to `-gpu num=1` and
  `select[h100nvl]` to `select[b200]`, and remove `--tensor-parallel-size 2`.
  The B200 nodes run jobs only for some allocations. If the job stays in PEND
  and `bjobs -p3 <job ID>` names `aims_limit`, yours is not one of them.
  Cancel the job with `bkill` and use two H100s.

Stage 3 is the slowest stage, because the model writes a whole record for every
report. A report that times out takes about 21 minutes before Gentrex gives up
on it, because Gentrex tries it four times for 300 seconds each
(`extract.timeout_seconds`) and waits 5, 20 and 60 seconds between the tries.
One such report can push a 30-minute job into `TERM_RUNLIMIT`. If the log
shows it, raise `-W` and submit again.

### Submit the job

```bash
cd /path/to/gentrex
bsub < stage3.lsf
```

Follow it with `bjobs` and `tail -f stage3.*.log`, as for stage 1. When the
job is done, the result is in `results/extract/latest/`, and the end of the
log lists any files that failed. Continue on the stage 3 page:

- [Check the result](stage3.md#check-the-result)
- [Change the schema](stage3.md#settings)
- [When something goes wrong](stage3.md#when-something-goes-wrong)

### Use Minerva's AI service instead of a job

Minerva runs a shared AI service at `https://assistant.hpc.mssm.edu`, which
serves `gemma4:31b`, a build of the stage 3 model. Stage 3 can send its
requests there instead of to a vLLM job of your own. You then need no GPU, no
model download and no job script, and stage 3 runs in an interactive session.
The service runs the model with [Ollama](https://ollama.com), another model
server, behind Open WebUI, a program that checks your API key and passes each
request on to Ollama.
[Minerva's page](https://labs.icahn.mssm.edu/minervalab/documentation/ollama/)
describes the service and lists its models.

Stages 1 and 2 keep their jobs, because the service lacks what they need:

- Stage 1 uses LightOnOCR, which the service doesn't offer.
- Stage 2 reads logprobs, the probabilities of the most likely tokens, instead
  of the model's answer. Open WebUI passes none on from Ollama, so stage 2
  would stop at once with `the server sent no logprobs`.

Before you send reports, ask Minerva's support whether the service is
approved for patient data. Its page says that the service stays inside Mount
Sinai, but not that it may receive patient data.

To run stage 3 on the service:

1. Log in at `https://assistant.hpc.mssm.edu` with your Mount Sinai account.
   Under Settings > Account, create an API key.
2. In `src/gentrex/defaults/settings.yaml`, change `extract.model` to the
   service's name of the model:

   ```yaml
   extract:
     model: gemma4:31b
   ```

   Change it back to `google/gemma-4-31B-it` before you submit `stage3.lsf`
   again, because the job's vLLM serves the model under that name.
3. In the `gentrex` folder, create `.env` from the example file, if you have
   none yet:

   ```bash
   cp .env.example .env
   ```

   Then set the service's address and your key in `.env`:

   ```
   GENTREX_LLM_BASE_URL=https://assistant.hpc.mssm.edu/api
   GENTREX_LLM_API_KEY=<your API key>
   ```

   The address ends in `/api` instead of `/v1`, because Gentrex adds
   `/chat/completions` to it and the service answers at
   `/api/chat/completions`. Git ignores `.env`, so the key stays out of the
   repository.
4. Start an interactive session on a login node:

   ```bash
   bsub -P acc_xxx -q interactive -n 1 -W 4:00 -R "rusage[mem=2000]" -Is /bin/bash
   ```

   One core and 2,000 MB of memory are enough, because Gentrex only sends the
   requests. `-W 4:00` gives the run four hours. The service is shared, so how
   fast it answers depends on how many others use it, and a run that the
   session cuts off can't be resumed. The other options work as in
   [stage 4](#stage-4-normalize-report-data).
5. In the session, go to the `gentrex` folder and run stage 3:

   ```bash
   uv run --env-file .env gentrex stage3
   ```

The result is in `results/extract/latest/`, as after the job. The records can
differ from those of the job in two ways. Open WebUI doesn't pass on the
temperature of 0 that Gentrex sends, so the model may answer the same report
differently from one run to the next. The service also sets the model's
context length, and Ollama shortens a request that is longer, so a long
report can lose pages without an error. Check a few records against their
PDFs, the longest reports among them, as in
[Check the result](stage3.md#check-the-result).

## Stage 4: Normalize report data

Run stage 4 after a stage 3 job has finished. Stage 4 needs no GPU and no
model server, so you run it yourself in an interactive session. Unlike batch
jobs, interactive sessions can reach the internet, which the downloads of
stage 4 need.

Start the session on a login node:

```bash
bsub -P acc_xxx -q interactive -n 4 -W 1:00 -R "rusage[mem=4000]" -Is /bin/bash
```

- `-P acc_xxx` names your allocation.
- `-q interactive` puts the session in the interactive queue, whose nodes can
  reach the internet.
- `-n 4` asks for 4 CPU cores. `rusage[mem=4000]` asks for 4,000 MB of memory
  per core, so 16 GB in all, which is enough to embed the HPO names.
- `-W 1:00` ends the session after one hour. Building the HPO index takes
  several minutes, because it embeds every HPO name with two models. Stage 4
  itself takes a minute or two.
- `-Is /bin/bash` opens a shell on the node as soon as the session starts.

In the session, go to the `gentrex` folder and follow steps 1 to 4 of
[stage 4](stage4.md#step-1-download-the-hgnc-complete-set). The first
`uv run --extra hpo` installs sentence-transformers and PyTorch, the Python
packages that stage 4 uses to find HPO terms. They take about 1 GB in the
`.venv` folder of `gentrex`, and about as much in uv's cache in your home
folder. The two embedding models, about 1.8 GB, go to Hugging Face's cache in
your home folder, `~/.cache/huggingface/`. When stage 4 has finished, type
`exit` to end the session.

The result is in `results/normalize/latest/`. Continue on the stage 4 page:

- [Check the result](stage4.md#check-the-result)
- [When something goes wrong](stage4.md#when-something-goes-wrong)

## Stage 5: Load report data into a database

Run stage 5 in the interactive session of stage 4, after stage 4 has
finished. With SQLite, the database is one file in `results/load/`, so stage
5 needs no server and the records stay on Minerva:

```bash
GENTREX_DATABASE_URL=sqlite:///results/load/gentrex.db uv run gentrex stage5
```

The first run takes a few seconds, because it loads the HPO terms. Continue
on the stage 5 page:

- [Check the result](stage5.md#check-the-result)
- [When something goes wrong](stage5.md#when-something-goes-wrong)

To load into a PostgreSQL or MySQL server instead, you need a workstation
with Docker, because Minerva's
[database service](https://labs.icahn.mssm.edu/minervalab/documentation/services/)
runs MariaDB, which stage 5 is not tested with. Install Gentrex on a
workstation approved for patient data, as in
[stage 1, step 1](stage1.md#step-1-install). Copy two things from Minerva into
the same places of its Gentrex folder:

- The stage 4 run folder, such as `results/normalize/20261019-030000/`. Copy
  the folder that `results/normalize/latest` points to, because the link
  itself would point to nothing on the workstation.
- `data/ontology/hp-base.json`, the HPO release that built the HPO index.

Then follow [stage 5](stage5.md), and name the copied run with `--input`, as in
`--input results/normalize/20261019-030000`.

## Stage 6: Export report data as Phenopackets

Run stage 6 in the same interactive session, after stage 4 has finished:

```bash
uv run gentrex stage6
```

Stage 6 writes one Phenopacket per patient to `results/export/latest/` in a
second, and it needs no server. Continue on the stage 6 page:

- [Check the result](stage6.md#check-the-result)
- [When something goes wrong](stage6.md#when-something-goes-wrong)
