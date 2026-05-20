"""Model definition for {{ cookiecutter.project_name }}, using PeerModel."""

from peermodel import App

peer = App("{{ cookiecutter.pkg_name }}")


@peer.model
class Thing:

    a_field: int
    another_field: str = "a default value"
