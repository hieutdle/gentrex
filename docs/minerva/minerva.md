# Running on Minerva (Mount Sinai)

On Minerva, Mount Sinai's high-performance computing cluster,
`gentrex transcribe`, `gentrex select` and `gentrex extract` each run as a
batch job on a GPU node. The job runs the command's model in
[vLLM](https://docs.vllm.ai), a server that answers Gentrex's requests.
`gentrex extract` can also use
[Minerva's AI service](#use-minervas-ai-service-instead-of-a-job), which runs
the model for you. `gentrex normalize`, `gentrex load`,
`gentrex export phenopackets` and `gentrex export fhir` need no GPU and run in
an interactive session.

Minerva schedules jobs with LSF. You write a job script and submit it with
`bsub`, and LSF starts the job when a node with the GPUs you asked for is
free. The jobs run vLLM with Apptainer, which runs software from container
images.

You need a Minerva account and a project allocation. Allocation names start
with `acc_`, and `mybalance` on a login node lists yours.

## Set up once

### Log in

If you're off campus, connect to the Mount Sinai VPN. Then log in to a Minerva
login node with `ssh` and do all of the setup there, because compute nodes
have no internet access.

### Install Gentrex

Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Reports and results must stay on Minerva, in storage approved for patient
data. Don't copy them to a laptop. Gentrex keeps both in its own folder, in
`data/raw/` and `results/`, so clone it into approved storage:

```bash
git clone https://github.com/hieutdle/gentrex.git
cd gentrex
uv sync
```

### Pull vLLM

Pick a folder for vLLM and the models, for example in your work directory.
The job scripts call it the serving folder. It needs at least 40 GB free for
vLLM and the model of `gentrex transcribe`. The model of `gentrex select` adds
about 50 GB, and the model of `gentrex extract` about 62 GB.

```bash
mkdir -p /path/to/serving && cd /path/to/serving

module load apptainer
export APPTAINER_CACHEDIR=$PWD/apptainer-cache
apptainer pull vllm.sif docker://vllm/vllm-openai:latest
rm -rf apptainer-cache
```

`apptainer pull` saves vLLM and everything it needs in one file, the container
image `vllm.sif`. The pull also fills a download cache of about 16 GB, which
would otherwise go to your home folder and its 30 GB quota.
`APPTAINER_CACHEDIR` moves the cache to the serving folder, and `rm` deletes
it afterwards.

`gentrex select` needs vLLM 0.25 or newer, and `gentrex extract` needs 0.19.1
or newer. `apptainer exec vllm.sif vllm --version` shows the version you
pulled. If it's older than 0.25, pull again.

## Transcribe PDF pages

### Download the OCR model

Once, on a login node, download the model into the serving folder:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download lightonai/LightOnOCR-3-4B \
  --local-dir models/LightOnOCR-3-4B
```

### Write the job script

Save this as `transcribe.lsf` in the `gentrex` folder. Change the three marked
lines.

```bash
#!/bin/bash
#BSUB -J gentrex-transcribe
#BSUB -P acc_xxx                       # <-- your allocation
#BSUB -q gpu
#BSUB -n 4
#BSUB -W 0:30
#BSUB -gpu num=1
#BSUB -R "select[a100] rusage[mem=8000] span[hosts=1]"
#BSUB -oo transcribe.%J.log

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
GENTREX_OCR_BASE_URL=http://localhost:$port/v1 .venv/bin/gentrex transcribe
status=$?

kill "$server"
exit $status
```

The `#BSUB` lines tell LSF what the job needs:

- `-J gentrex-transcribe` is the job's name, and `-P acc_xxx` charges the job
  to your allocation.
- `-q gpu` sends the job to the GPU queue.
- `-n 4` and `rusage[mem=8000]` ask for 4 CPU cores with 8,000 MB of memory
  each, 32 GB in all. That's memory on the node, not on the GPU, and vLLM uses
  about 6 GB of it.
- `-W 0:30` limits the job to 30 minutes.
- `-gpu num=1` and `select[a100]` ask for one A100 GPU, and `span[hosts=1]`
  keeps the job on one node.
- `-oo transcribe.%J.log` writes everything the job prints to
  `transcribe.<job ID>.log`.

The rest of the script does four things:

1. It picks a port from the job ID. On the default port, 8000, Gentrex could
   reach the vLLM of another job on the same node and send it the reports.
2. It starts vLLM in the background and waits until vLLM answers. If vLLM
   stops instead, the job ends with `vLLM stopped; see the log above`.
3. It runs `gentrex transcribe` on `data/raw/`, with the server's address in
   `GENTREX_OCR_BASE_URL`. Gentrex and vLLM run in the same job, so you need
   no `.env` file, API key or network setup.
4. It stops vLLM to free the GPU, and the job ends with Gentrex's exit code.

`apptainer exec` runs `vllm serve` inside `vllm.sif`. `--nv` gives the
container the node's NVIDIA GPUs, and `-B` makes the `models` folder visible
inside it as `/models`. `--home` gives it a home folder in the serving folder,
where vLLM keeps its compile cache, outside your own home folder and its
quota. `HF_HUB_OFFLINE=1` keeps vLLM from contacting Hugging Face, which
compute nodes can't reach.

`--served-model-name` gives the model the name that Gentrex asks for, which is
set in `transcribe.ocr.model` in settings.yaml. Otherwise vLLM would name it
after its folder.
[Transcribe PDF pages](../user-guide/transcribe.md#step-3-start-the-ocr-server)
explains `--max-model-len 18000` and `--default-chat-template-kwargs`.

`--limit-mm-per-prompt '{"image": 1}'` allows one image per request, which is
all that Gentrex sends. vLLM sets memory aside for as many images as a request
may hold. `--mm-processor-cache-gb 0` turns off the cache of processed images,
which would only take memory, since every image is sent once.
`--no-enable-prefix-caching` turns off prefix caching, which lets vLLM reuse
its work on the start that requests share. Every request holds a different
page image, so there is nothing to reuse.

### Choose the GPU and time limit

The 30 minutes of `-W 0:30` include the few minutes vLLM takes to start. A
short limit gets the job out of the queue sooner. `TERM_RUNLIMIT` in the log
means that LSF stopped the job before it finished. Raise `-W`, and add
`--retry` with the stopped run's folder to the `gentrex transcribe` line of
the job script:

```bash
GENTREX_OCR_BASE_URL=http://localhost:$port/v1 .venv/bin/gentrex transcribe --retry results/transcribe/20261014-123000
```

Submit the job again, and it reuses the pages that the stopped job read
([Redo failed files](../../README.md#redo-failed-files)). To set `-W` for the
next batch, use the speed in pages per minute that the run prints at its
end.

The OCR model's weights, the numbers it learned in training, take 9 GB, so any
of these GPUs can hold them. If the job waits a long time in the queue, put
another type in `select[a100]`:

| Value | GPU | Memory |
| --- | --- | --- |
| `v100` | V100 | 16 GB |
| `a100` | A100 | 40 GB |
| `a10080g` | A100 | 80 GB |
| `l40s` | L40S | 48 GB |
| `h10080g` | H100 | 80 GB |
| `h100nvl` | H100 | 80 GB |

The current list is on
[Minerva's GPU page](https://labs.icahn.mssm.edu/minervalab/documentation/gpgpu/).

### Submit the job

Put the reports in `data/raw/` in the `gentrex` folder, then submit the
script:

```bash
cd /path/to/gentrex
bsub < transcribe.lsf
```

Follow the job with:

```bash
bjobs                     # PEND = waiting for a GPU, RUN = running
bjobs -p3 <job ID>        # why a PEND job is waiting
tail -f transcribe.*.log  # what vLLM and Gentrex print
```

`bkill <job ID>` cancels the job.

When the job is done, the result is in `results/transcribe/latest/`, and the
end of the log lists any files that failed. Below that, LSF's summary shows
Gentrex's exit code, `Successfully completed.` for 0 or
`Exited with exit code 1.` for 1. Continue on the page of
`gentrex transcribe`:

- [Check the result](../user-guide/transcribe.md#check-the-result)
- [When something goes wrong](../user-guide/transcribe.md#when-something-goes-wrong)
- [Settings](../user-guide/transcribe.md#settings)

## Select the pages to keep

Run `gentrex select` after the job of `gentrex transcribe` has finished.

### Download the model

Once, on a login node, download the model into the serving folder:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download google/gemma-4-26B-A4B-it \
  --local-dir models/gemma-4-26B-A4B-it
```

If Hugging Face refuses the download, accept Google's terms on the model's
page, log in with `uvx --from huggingface_hub hf auth login` and download
again.

### Write the job script

Save this as `select.lsf` in the `gentrex` folder. Change the three marked
lines.

```bash
#!/bin/bash
#BSUB -J gentrex-select
#BSUB -P acc_xxx                       # <-- your allocation
#BSUB -q gpu
#BSUB -n 4
#BSUB -W 0:30
#BSUB -gpu num=1
#BSUB -R "select[h100nvl] rusage[mem=8000] span[hosts=1]"
#BSUB -oo select.%J.log

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
GENTREX_LLM_BASE_URL=http://localhost:$port/v1 .venv/bin/gentrex select
status=$?

kill "$server"
exit $status
```

It works like `transcribe.lsf`, with these differences:

- `select[h100nvl]` asks for an H100 GPU.
- vLLM loads `gemma-4-26B-A4B-it` with `--max-model-len 16384`, which
  [Select the pages to keep](../user-guide/select.md#step-1-start-the-model-server)
  explains.
- Prefix caching stays on, because Gentrex asks all its questions about a page
  one after another. vLLM then reads each page once for all of them.
- The image options are gone, because this model gets text only.
- It runs `gentrex select` with the server's address in
  `GENTREX_LLM_BASE_URL`. `gentrex select` reads the newest finished run of
  `gentrex transcribe`.

### Choose the GPU and time limit

The model's weights take about 50 GB, so the job needs a GPU with 80 GB, like
the H100 in the script. If the job waits a long time in the queue, use
`a10080g` or `h10080g` from the
[table for `gentrex transcribe`](#choose-the-gpu-and-time-limit), which also
have 80 GB.

This job also gets 30 minutes. If it ends with `TERM_RUNLIMIT`, raise `-W`,
add `--retry` with the stopped run's folder to the `gentrex select` line and
submit again.

### Submit the job

```bash
cd /path/to/gentrex
bsub < select.lsf
```

Follow it with `bjobs` and `tail -f select.*.log`. The result goes to
`results/select/latest/`, and the end of the log lists any files that failed.
Continue on the page of `gentrex select`:

- [Check the result](../user-guide/select.md#check-the-result)
- [Change the questions or the threshold](../user-guide/select.md#settings)
- [When something goes wrong](../user-guide/select.md#when-something-goes-wrong)

## Extract report data

Run `gentrex extract` after the job of `gentrex select` has finished.

### Download the model

Once, on a login node, download the model into the serving folder:

```bash
cd /path/to/serving
uvx --from huggingface_hub hf download google/gemma-4-31B-it \
  --local-dir models/gemma-4-31B-it
```

If Hugging Face refuses it, accept Google's terms and log in as for the model
of `gentrex select`.

### Write the job script

Save this as `extract.lsf` in the `gentrex` folder. Change the three marked
lines.

```bash
#!/bin/bash
#BSUB -J gentrex-extract
#BSUB -P acc_xxx                       # <-- your allocation
#BSUB -q gpu
#BSUB -n 4
#BSUB -W 0:30
#BSUB -gpu num=2
#BSUB -R "select[h100nvl] rusage[mem=8000] span[hosts=1]"
#BSUB -oo extract.%J.log

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
GENTREX_LLM_BASE_URL=http://localhost:$port/v1 .venv/bin/gentrex extract
status=$?

kill "$server"
exit $status
```

It works like `select.lsf`, with these differences:

- `-gpu num=2` asks for two GPUs, and `span[hosts=1]` keeps them on one node.
- vLLM splits `gemma-4-31B-it` across the two GPUs with
  `--tensor-parallel-size 2`.
  [Extract report data](../user-guide/extract.md#step-1-start-the-model-server)
  explains `--max-model-len 32768` and `--gpu-memory-utilization 0.95`.
- Prefix caching stays on, because every request starts with the same
  instruction and schema, which vLLM then reads once.

### Choose the GPU and time limit

The model's weights take about 62 GB. On one 80 GB GPU, that leaves too little
memory for a 32,768-token request, and vLLM stops at startup. Use two H100s or
one B200:

- **Two H100s**, as in the script. `a10080g` and `h10080g` from the
  [table for `gentrex transcribe`](#choose-the-gpu-and-time-limit) also work
  in place of `h100nvl`.
- **One B200**, with 192 GB. Change `-gpu num=2` to `-gpu num=1` and
  `select[h100nvl]` to `select[b200]`, and remove `--tensor-parallel-size 2`.
  The B200 nodes run jobs only for some allocations. If the job stays in PEND
  and `bjobs -p3 <job ID>` shows `aims_limit`, yours isn't one of them.
  Cancel the job with `bkill` and use two H100s.

`gentrex extract` is the slowest command. A report that times out takes about
21 minutes before Gentrex gives up on it, after four tries of 300 seconds each
(`extract.timeout_seconds`) with waits of 5, 20 and 60 seconds in between. One
such report can push a 30-minute job into `TERM_RUNLIMIT`. If that happens,
raise `-W`, add `--retry` with the stopped run's folder to the
`gentrex extract` line and submit again.

### Submit the job

```bash
cd /path/to/gentrex
bsub < extract.lsf
```

Follow it with `bjobs` and `tail -f extract.*.log`. The result goes to
`results/extract/latest/`, and the end of the log lists any files that failed.
Continue on the page of `gentrex extract`:

- [Check the result](../user-guide/extract.md#check-the-result)
- [Change the schema](../user-guide/extract.md#settings)
- [When something goes wrong](../user-guide/extract.md#when-something-goes-wrong)

### Use Minerva's AI service instead of a job

Minerva runs a shared AI service at `https://assistant.hpc.mssm.edu` that
serves `gemma4:31b`, a build of the model in `extract.lsf`. If
`gentrex extract` sends its requests there, you need no GPU, no model
download and no job script, and it runs in an interactive session. The model
runs in [Ollama](https://ollama.com), another model server. Open WebUI sits in
front of Ollama, checks your API key and passes each request on.
[Minerva's page](https://labs.icahn.mssm.edu/minervalab/documentation/ollama/)
describes the service and lists its models.

`gentrex transcribe` and `gentrex select` still need their jobs. The service
doesn't offer LightOnOCR, the model of `gentrex transcribe`. `gentrex select`
reads logprobs, the probabilities of the most likely tokens, instead of the
model's answer. Open WebUI passes none on from Ollama, so `gentrex select`
would stop at once with `the server sent no logprobs`.

Before you send reports, ask Minerva's support whether the service is
approved for patient data. Its page says that the service stays inside Mount
Sinai, but not that it may receive patient data.

To run `gentrex extract` on the service:

1. Log in at `https://assistant.hpc.mssm.edu` with your Mount Sinai account.
   Under Settings > Account, create an API key.
2. In `src/gentrex/defaults/settings.yaml`, change `extract.model` to the
   service's name for the model:

   ```yaml
   extract:
     model: gemma4:31b
   ```

   Change it back to `google/gemma-4-31B-it` before you next submit
   `extract.lsf`, because that's the name the job's vLLM serves.
3. If the `gentrex` folder has no `.env` file yet, create it from the example
   file:

   ```bash
   cp .env.example .env
   ```

   Then set the service's address and your key in `.env`:

   ```
   GENTREX_LLM_BASE_URL=https://assistant.hpc.mssm.edu/api
   GENTREX_LLM_API_KEY=<your API key>
   ```

   The address ends in `/api` instead of `/v1`, because the service answers
   at `/api/chat/completions` and Gentrex adds `/chat/completions` to the
   address.
4. Start an interactive session on a login node:

   ```bash
   bsub -P acc_xxx -q interactive -n 1 -W 4:00 -R "rusage[mem=2000]" -Is /bin/bash
   ```

   One core and 2,000 MB of memory are enough, since Gentrex only sends the
   requests. `-W 4:00` gives the run four hours. How fast the service answers
   depends on how many others use it. If the session ends before the run
   does, start a new session and continue the stopped run with `--retry`
   ([Redo failed files](../../README.md#redo-failed-files)).
   [Normalize report data](#normalize-report-data) explains the other options.
5. In the session, go to the `gentrex` folder and run `gentrex extract`:

   ```bash
   uv run --env-file .env gentrex extract
   ```

The result is in `results/extract/latest/`, as after the job, but the records
can differ in two ways. Open WebUI doesn't pass on the temperature of 0 that
Gentrex sends, so the model may answer the same report differently from one
run to the next. The service also sets the model's context length, and Ollama
shortens any longer request, so a long report can lose pages without an
error. Check a few records against their PDFs, the longest reports among them
([Check the result](../user-guide/extract.md#check-the-result)).

## Normalize report data

Run `gentrex normalize` in an interactive session, after the job of
`gentrex extract` has finished. Start the session on a login node:

```bash
bsub -P acc_xxx -q interactive -n 4 -W 1:00 -R "rusage[mem=4000]" -Is /bin/bash
```

Unlike batch jobs, sessions in the interactive queue (`-q interactive`) can
reach the internet, which the downloads for `gentrex normalize` need. `-n 4`
and `rusage[mem=4000]` ask for 4 CPU cores with 4,000 MB of memory each,
16 GB in all, which is enough to embed the HPO names. `-W 1:00` ends the
session after one hour. Building the HPO index takes several minutes, and
`gentrex normalize` itself a minute or two. `-Is /bin/bash` opens a shell on
the node when the session starts, and `-P` charges the session to your
allocation.

In the session, go to the `gentrex` folder and follow steps 1 to 4 of
[Normalize report data](../user-guide/normalize.md#step-1-download-the-hgnc-complete-set).
The first `uv run --extra hpo` installs PyTorch and sentence-transformers for
the HPO matching. They take about 1 GB in the `.venv` folder of `gentrex`, and
about as much in uv's cache. The two embedding models take about 1.8 GB in
`~/.cache/huggingface/`. Both caches are in your home folder. Keep the session
open if you go on to load or export the records in the next three sections.

The result is in `results/normalize/latest/`. Continue on the page of
`gentrex normalize`:

- [Check the result](../user-guide/normalize.md#check-the-result)
- [When something goes wrong](../user-guide/normalize.md#when-something-goes-wrong)

## Load report data into a database

Run `gentrex load` in the same session, after `gentrex normalize` has
finished. With SQLite, the database is one file in `results/load/`, so you
need no database server and the records stay on Minerva:

```bash
GENTREX_DATABASE_URL=sqlite:///results/load/gentrex.db uv run gentrex load
```

The first run takes a few seconds to load the HPO terms. Continue on the page
of `gentrex load`:

- [Check the result](../user-guide/load.md#check-the-result)
- [When something goes wrong](../user-guide/load.md#when-something-goes-wrong)

To load into PostgreSQL or MySQL instead, you need a workstation with Docker.
Minerva's
[database service](https://labs.icahn.mssm.edu/minervalab/documentation/services/)
runs MariaDB, which `gentrex load` isn't tested with. Install Gentrex on a
workstation approved for patient data
([Transcribe PDF pages](../user-guide/transcribe.md#step-1-install)), and copy
two things from Minerva to the same places in its Gentrex folder:

- The run folder of `gentrex normalize`, for example
  `results/normalize/20261019-030000/`. Copy the folder that
  `results/normalize/latest` points to, because the link itself would point
  to nothing on the workstation.
- `data/ontology/hp-base.json`, the HPO release that built the HPO index.

Then follow [Load report data into a database](../user-guide/load.md), with
`--input` set to the copied run, as in
`--input results/normalize/20261019-030000`.

## Export report data as Phenopackets

Run `gentrex export phenopackets` in the same session, after
`gentrex normalize` has finished:

```bash
uv run gentrex export phenopackets
```

Within a second, it writes one Phenopacket per patient to
`results/export/phenopackets/latest/phenopackets/`. Continue on the page of
`gentrex export phenopackets`:

- [Check the result](../user-guide/export-phenopackets.md#check-the-result)
- [When something goes wrong](../user-guide/export-phenopackets.md#when-something-goes-wrong)

## Export report data as FHIR Bundles

Run `gentrex export fhir` in the same session, after `gentrex normalize` has
finished:

```bash
uv run gentrex export fhir
```

Within a second, it writes one FHIR Bundle per report to
`results/export/fhir/latest/bundles/`. Continue on the page of
`gentrex export fhir`:

- [Check the result](../user-guide/export-fhir.md#check-the-result)
- [When something goes wrong](../user-guide/export-fhir.md#when-something-goes-wrong)

[Search the Bundles](../user-guide/export-fhir.md#search-the-bundles) runs a
test FHIR server in Docker, which Minerva doesn't offer. For that step, copy
the run folder of `gentrex export fhir` to a workstation approved for patient
data.

When you're done, type `exit` to end the session.

## Export report data into an OMOP database

`gentrex export omop` writes into an OMOP CDM database in PostgreSQL, and
Minerva runs no PostgreSQL server. Run it instead on a machine that can reach
the CDM, for example a workstation approved for patient data. Copy the run
folder of `gentrex normalize` there as for
[`gentrex load`](#load-report-data-into-a-database). The export needs no other
file. Then follow
[Export report data into an OMOP database](../user-guide/export-omop.md), with
`--input` set to the copied run. `gentrex export omop-extended` works the same
way.
