from peermodel import build_cli

# Generated by peermodel-template and cookiecutter

cli = build_cli(
    app_name = {{ cookiecutter.pkg_name }}
)

if __name__ == '__main__':
    cli()