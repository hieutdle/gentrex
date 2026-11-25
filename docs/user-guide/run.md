# Run all four commands

`gentrex run` runs `gentrex transcribe`, `gentrex select`, `gentrex extract`
and `gentrex normalize` one after another on a folder of PDFs. It starts the
model server of each command before the command and stops it afterwards, so
you don't start and stop three servers by hand. The run folders are the same
as when you run the four commands yourself.

Go through the pages of the four commands once first. They explain the model
servers and what to check in each output.

## Before you start

You need:

- Gentrex installed ([Transcribe PDF pages](transcribe.md#step-1-install)).
- A GPU that can serve each of the models, one at a time
  ([transcribe](transcribe.md#step-3-start-the-ocr-server),
  [select](select.md#step-1-start-the-model-server),
  [extract](extract.md#step-1-start-the-model-server)).
- The reference files of `gentrex normalize`, from steps 1 to 4 of
  [Normalize report data](normalize.md#step-1-download-the-hgnc-complete-set).
- The PDFs in `data/raw/`, or in a folder that you name with `--input-dir`.

## Step 1: Check the script that starts a model server

Gentrex starts each server with a script, which it calls with the model's
name and a free port. `evaluation/local/serve.sh` is that script for vLLM:

```bash
case "$1" in
  lightonai/LightOnOCR-3-4B)
    options=(--max-model-len 18000
      --default-chat-template-kwargs '{"enable_thinking": false}') ;;
  google/gemma-4-26B-A4B-it)
    options=(--max-model-len 32768) ;;
  ...
esac

exec vllm serve "$1" --port "$2" "${options[@]}"
```

The options are those of each command's own page. `gentrex select` and
`gentrex extract` use the same model. If you changed a model in a settings
file, add a line with its name.

A script of your own for another model server works too. It must serve the
model at the port it is given, and keep running for as long as the server
does, which `exec` takes care of.

## Step 2: Run

```bash
uv run --extra hpo gentrex run --serve evaluation/local/serve.sh
```

The addresses of the servers come from the script, so this command needs no
`.env`. It takes these options:

| Option | What it does |
| --- | --- |
| `--input-dir` | The folder of PDFs, `data/raw` by default. |
| `--settings` | A [settings file of your own](runs-and-results.md#change-the-settings), for every command. |
| `--schema` | An [extraction schema of your own](extract.md#settings), for `gentrex extract`. |
| `--no-hpo` | Leaves the clinical features without HPO terms, as in `gentrex normalize --no-hpo`. Then `--extra hpo` isn't needed. |

The output is that of the four commands, with two lines around each model
server:

```
waiting for google/gemma-4-26B-A4B-it at http://localhost:52311/v1
google/gemma-4-26B-A4B-it is ready after 212 s
```

## Check the result

Each command writes its own run folder, as
[Runs and results](runs-and-results.md) describes, and
`results/normalize/latest` has the records. Check each output as the
command's page shows.

The exit code is 0 if every command finished without a failed file, and 1
otherwise.

## How it works

Gentrex waits until a server lists its models at
`http://localhost:<port>/v1/models`, runs the command and stops the script.
Each command reads the run folder that the command before it wrote.

A command with failed files doesn't stop the run, because the next commands
pass the errors on, as they do when you run them yourself. A command that
didn't finish stops it.

## When something goes wrong

| Message | What to do |
| --- | --- |
| `serve.sh ended before google/gemma-4-26B-A4B-it was ready` | The server didn't start. Run the script by hand to see why, as in `evaluation/local/serve.sh google/gemma-4-26B-A4B-it 8000`. |
| `gentrex extract did not finish, so the run stops here` | The lines above it say why. The commands before it are done. Fix the cause and go on with the command's own page, which reads `results/select/latest`. |
| Failed files at the end of a command | Redo them with the command's `--retry` ([Redo failed files](runs-and-results.md#redo-failed-files)), and then run the commands after it. |
