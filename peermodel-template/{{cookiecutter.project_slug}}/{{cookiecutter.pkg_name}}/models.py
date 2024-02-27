from peermodel import App
from typing import List, Dict, Union

"Model definition for {{ cookiecutter.project_name }}, using PeerModel."

peer = App("{{ cookiecutter.pkg_name }}")

@peer.model
class Thing:

    a_field: int
    another_field: str = "a default value"

