"""Migrate engine preferences to 7-provider boundary.

Revision ID: 0011_provider_boundary_migration
Revises: 0010_remote_worker_schema

Ensures persisted preferences in settings table adhere to the seven allowed providers:
- TTS: omnivoice, vienue
- ASR: deepgram-asr (explicit opt-in; no audio upload)
- Translation: google, openai
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_provider_boundary_migration"
down_revision: Union[str, None] = "0010_remote_worker_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    row = op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    if not _has_table("settings"):
        return

    # Sanitize tts_backend setting
    op.execute(
        sa.text(
            "UPDATE settings SET value = 'omnivoice' "
            "WHERE key = 'tts_backend' AND value NOT IN ('omnivoice', 'vienue')"
        )
    )

    # Sanitize asr_backend setting (migration must never upload audio)
    op.execute(
        sa.text(
            "UPDATE settings SET value = 'deepgram-asr' "
            "WHERE key = 'asr_backend' AND value NOT IN ('deepgram-asr', 'deepgram')"
        )
    )

    # Sanitize translation engine setting
    op.execute(
        sa.text(
            "UPDATE settings SET value = 'google' "
            "WHERE key = 'translation_engine' AND value NOT IN ('google', 'openai')"
        )
    )

    # Remove configuration surfaces that no longer have a runtime. General
    # settings, projects and voices live under different keys/tables and are
    # deliberately untouched.
    retired = (
        "hf_token", "asr_openai_compat%", "dictation.%", "license.supertonic3",
        "license.pockettts", "llm_key.huggingface", "llm.base_url.huggingface",
        "llm.model.huggingface",
    )
    bind = op.get_bind()
    for key in retired:
        if "%" in key:
            bind.execute(sa.text("DELETE FROM settings WHERE key LIKE :key"), {"key": key})
        else:
            bind.execute(sa.text("DELETE FROM settings WHERE key = :key"), {"key": key})

    # A removed LLM preset is migrated to the generic OpenAI-compatible
    # provider, but no request is made and no provider is activated otherwise.
    op.execute(
        sa.text(
            "UPDATE settings SET value = 'custom' "
            "WHERE key = 'llm.active_provider' AND value = 'huggingface'"
        )
    )


def downgrade() -> None:
    pass
