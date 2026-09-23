"""Launch the local web application."""

from videotrans.configure import config as runtime_config

runtime_config.init_run()

from videotrans.api.app import create_app, main  # noqa: E402

__all__ = ["create_app", "main"]


if __name__ == "__main__":
    main()
