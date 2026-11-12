# Running on Minerva (Mount Sinai)

On Minerva, Mount Sinai's high-performance computing cluster,
`gentrex transcribe`, `gentrex select` and `gentrex extract` each run as a
batch job on a GPU node. The job runs the command's model in
[vLLM](https://docs.vllm.ai), a server that answers Gentrex's requests.
`gentrex extract` can also use
[Minerva's AI service](#use-minervas-ai-service-instead-of-a-job), which runs
the model for you. `gentrex normalize`, `gentrex load`,
`gentrex export phenopackets` and `gentrex export fhir` need no GPU and run in
an interactive session. The generator of the benchmark,
[gentrex-bench](#generate-benchmark-reports), also runs as a batch job, and
so does a [run of the benchmark](#run-the-benchmark).

Minerva schedules jobs with LSF. You write a job script and submit it with
`bsub`, and LSF starts the job when a node with the GPUs you asked for is
free. The jobs run vLLM with Apptainer, which runs software from container
images.

You need a Minerva account and a project allocation. Allocation names start
with `acc_`, and `mybalance` on a login node lists yours.

## Set up once

### Log in

If you're off campus, connect to the Mount Sinai VPN. Then log in to a Minerva
login node with `ssh` and do all of the setup there.

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
quota. `HF_HUB_OFFLINE=1` keeps vLLM from contacting Hugging Face, because
the model is already in the `models` folder.

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
([Redo failed files](../user-guide/runs-and-results.md#redo-failed-files)). To set `-W` for the
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
   ([Redo failed files](../user-guide/runs-and-results.md#redo-failed-files)).
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

`-q interactive` asks for a session in the interactive queue. `-n 4` and
`rusage[mem=4000]` ask for 4 CPU cores with 4,000 MB of memory each, 16 GB in
all, which is enough to embed the HPO names. `-W 1:00` ends the session after
one hour. Building the HPO index takes several minutes, and
`gentrex normalize` itself a minute or two. `-Is /bin/bash` opens a shell on
the node when the session starts, and `-P` charges the session to your
allocation.

In the session, go to the `gentrex` folder and follow steps 1 to 5 of
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

Within a second, it writes one FHIR® Bundle per report to
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

## Generate benchmark reports

The [benchmark generator](../development/benchmark-generator.md) makes
synthetic reports whose true content is known. Its writing model runs in
vLLM in a batch job, like the models of Gentrex. The reports hold no patient
data, so they can be stored anywhere.

The scripts for it are in `evaluation/minerva/`.
[Evaluate Gentrex](../../evaluation/README.md#run-on-minerva) lists the
commands in order, and this section explains what the scripts do.

### Prepare in an interactive session

The downloads take a while, so do them in a session before the jobs, which
then spend none of their GPU time on them. Start the session on a login node:

```bash
bsub -P acc_xxx -q interactive -n 4 -W 6:00 -R "rusage[mem=4000]" -Is /bin/bash
```

In the session, go to the `gentrex` folder and run the script with the path
of your serving folder:

```bash
SERVING=/path/to/serving evaluation/minerva/prepare.sh
```

The script gets everything that the jobs of this section and the next need,
and keeps what is already there:

- The packages of `gentrex normalize`, the reference files and the HPO
  index, as in steps 1 to 3 of
  [Normalize report data](../user-guide/normalize.md#step-1-download-the-hgnc-complete-set).
  It also downloads ClinVar's file and HPO's disease annotations, which the
  generator samples the cases from.
- The cases, which it samples into `data/gentrex-bench/v1/cases/`.
- vLLM and Gentrex's three models in the serving folder, as in
  [Pull vLLM](#pull-vllm) and the three sections on downloading a model.
- The writing model, Muse Glimmer 30B. Its weights take about 60 GB, which
  fits on one GPU with 80 GB. It needs vLLM 0.28 or newer. If your
  `vllm.sif` is older, delete it before you run the script, which then
  pulls the newest one.
- Chrome, which prints the reports to PDF. Compute nodes have no Chrome, so
  this is Google's Chrome for Testing, which runs from its folder without an
  installation or a display. The version is fixed, so every report is printed
  by the same Chrome.

Near its end the script prints Chrome's version,
`Google Chrome for Testing 157.0.8103.38`. If it names a missing library
instead, or the job's log later shows a sandbox error, see
[When the job fails](#when-the-job-fails).

### Submit the job

Build two cases first, and look at their PDFs before you build the rest:

```bash
cd /path/to/gentrex
SERVING=/path/to/serving CASES="SYN-0001 SYN-0002" \
  bsub -P acc_xxx < evaluation/minerva/generate_reports.lsf
```

LSF passes your environment to the job, so `SERVING` and `CASES` reach the
script. `-P` charges the job to your allocation. The script has no `-P`
line of its own, so you don't have to change it.

`generate_reports.lsf` works like the job script of
[`gentrex transcribe`](#write-the-job-script), with these differences:

- It starts vLLM through `evaluation/minerva/serve.sh`, which holds the
  options of every model. For Muse Glimmer, `--max-model-len 20480` gives
  room for the prompt and an answer of up to 16,384 tokens
  (`build.max_tokens`). `--reasoning-parser muse_glimmer` keeps the
  reasoning that the model writes first out of its answer.
- `-n 8` asks for 8 CPU cores. Chrome and the scans run on the CPU while
  vLLM writes the next reports, up to `build.concurrency` (8) at a time.
- It runs `generate.py build` with the Chrome from the serving folder.
  Without `CASES`, the job builds every case that has no truth file yet.

Follow the job with `bjobs` and `tail -f generate-reports.*.log`. Each case
logs `passed on attempt 1`, or why the attempt failed. The PDFs go to
`data/gentrex-bench/v1/pdf/`, and
[Check the result](../development/generate-benchmark-reports.md#check-the-result)
lists what else the folder holds.

Then submit without `CASES` and with more time. `-W` on the command line
replaces the hour that the script asks for:

```bash
SERVING=/path/to/serving bsub -P acc_xxx -W 8:00 < evaluation/minerva/generate_reports.lsf
```

A case that already has a truth file is skipped. If the job ends in
`TERM_RUNLIMIT`, submit it again and it goes on where it stopped. The log of
the two test cases shows how long a case takes. The full build writes several
cases at once, so it needs less time per case than the test did.

### When the job fails

| Problem | What to do |
| --- | --- |
| `chrome-headless-shell --version` names a missing library, such as `libnss3.so` | The node lacks a library that Chrome needs. Ask Minerva's support to install it. |
| The log shows `No usable sandbox!` or another sandbox error | Start Chrome without its sandbox. Save `exec /path/to/serving/chrome-headless-shell-linux64/chrome-headless-shell --no-sandbox "$@"` after a `#!/bin/bash` line in `chrome.sh`, run `chmod +x chrome.sh`, and give the path of `chrome.sh` to `--chrome` in `generate_reports.lsf`. The sandbox guards against harmful web pages, which these reports aren't. |
| `vLLM stopped; see above` | vLLM couldn't start, often because the model doesn't fit. Check that `models/Muse-Glimmer-30B` is complete and that the job got an 80 GB GPU. If vLLM doesn't know `muse_glimmer`, `vllm.sif` is older than 0.28. |
| A case fails all attempts | The log names the values that the model didn't print. Submit the job again with that case in `CASES`, or leave the case out. |

## Run the benchmark

[Run the benchmark](../development/run-benchmark.md) runs Gentrex on
benchmark reports and scores its records against their truth files. On
Minerva, one batch job does all of it. The job serves the three models one
after another, so it needs the two GPUs of `gentrex extract` for its whole
time.

The job needs what
[`prepare.sh`](#prepare-in-an-interactive-session) downloads, and a
benchmark version in `data/gentrex-bench/`, from
[Generate benchmark reports](#generate-benchmark-reports).

### Submit the job

```bash
cd /path/to/gentrex
SERVING=/path/to/serving bsub -P acc_xxx < evaluation/minerva/run_pipeline.lsf
```

The `#BSUB` lines of `run_pipeline.lsf` ask for what
[`extract.lsf`](#write-the-job-script-2) asks for, with two hours instead of
30 minutes. The script then runs `gentrex-bench/run.py`, which does the work
of the three job scripts. It picks a free port, starts
`evaluation/minerva/serve.sh` for the model of `gentrex transcribe`, waits
until vLLM answers, runs the command and stops vLLM. It does the same for
`gentrex select` and `gentrex extract`, and then runs `gentrex normalize`
and the scorer on the CPU.

`serve.sh` starts vLLM as the three job scripts above do, with the options
of each model. The script sets three more things:

- `HF_HUB_OFFLINE=1` makes `gentrex normalize` load its embedding models
  from the cache without contacting Hugging Face.
- `--gpus 1 1 2` records that the first two servers use one GPU and the
  third uses two, for the GPU-hours in the scores.
- `--settings evaluation/settings.yaml` turns on the lookup of ClinVar IDs,
  so that the scorer scores them.

By default the job reads the native PDFs of the dev set. `COPIES` names the
copies to read, one after another, and `SPLIT` the split. Give a job with
several copies more time:

```bash
SERVING=/path/to/serving COPIES="native scan fax mixed image" SPLIT=test \
  bsub -P acc_xxx -W 10:00 < evaluation/minerva/run_pipeline.lsf
```

`OPTIONS` passes more options to `run.py`, as in `OPTIONS=--no-select`
([Run another setup](../development/run-benchmark.md#run-another-setup)).
Run one such job at a time in a `gentrex` folder, because `run.py` finds the
run that a command just made through the command's `latest` link.

Follow the job with `bjobs` and `tail -f run-pipeline.*.log`. Its last line
gives the report accuracy and the folder with the scores, such as
`results/gentrex-bench/20261110-103752/`. If the job ends in `TERM_RUNLIMIT`,
raise `-W` and submit it again. A benchmark run starts from the beginning
each time, so that its times cover the whole run.

Continue on the page of the benchmark:

- [Check the result](../development/run-benchmark.md#check-the-result)
- [Compare runs in the notebook](../development/run-benchmark.md#compare-runs-in-the-notebook)
- [When something goes wrong](../development/run-benchmark.md#when-something-goes-wrong)

HL7®, FHIR® and the FHIR [FLAME DESIGN] are the registered trademarks of
Health Level Seven International and their use does not constitute
endorsement by HL7.
