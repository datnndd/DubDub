# Prepare Stage End-to-End

## Outcome

The existing Dubbing Video Prepare screen now ingests and inspects media,
loads backend-owned choices, validates configuration, submits the shared task
runner once, and reports its lifecycle and outputs without redesigning later
stages.

## Implemented

- Added `POST /api/media` for task-owned upload storage and ffprobe metadata.
- Added opaque in-memory media identifiers; job requests cannot supply paths.
- Added strict language and engine validation before runner construction.
- Added server-side duplicate-active-job rejection per uploaded media item.
- Bound Prepare state to ingest, source/target languages, ASR, translation,
  supported TTS/settings, submission, polling, cancellation, errors, and output
  links.
- Replaced fabricated Prepare metadata and speaker analysis with probed values
  or explicit unavailable/pending states.
- Disabled visible Prepare controls that do not yet have backend behavior.

## Validation

- `python -m pytest tests/test_orchestrator.py tests/test_cli.py tests/test_webui.py -q --disable-warnings`
  passed: 96 tests.
- `tests/test_webui.py` passed: 8 tests, including HTTP ingest, invalid media
  cleanup, exact parameter mapping, duplicate rejection, and terminal output.
- JavaScript syntax checks passed for state, Prepare screen, and status footer.
- A live server accepted a generated H.264/AAC MP4 and reported 1,000 ms,
  12,297 bytes, 320x180, 25 fps, H.264, AAC, video, and audio.
- Browser smoke verification confirmed backend language/ASR/translation choices,
  honest empty-state metadata, and disabled unsupported controls.

## Known unrelated validation blocker

The repository-wide pytest run stops during collection because
`tests/test_job_helpers.py` imports missing `_get_type_name` from
`videotrans.task.job`. This pre-existing issue is outside the Prepare-stage
change.
