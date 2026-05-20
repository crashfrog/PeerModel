# {{ cookiecutter.project_name }}

{{ cookiecutter.project_short_description }}

## Installation

```bash
pip install {{ cookiecutter.project_slug }}
```

## Usage

```python
from {{ cookiecutter.pkg_name }} import models
```

## Development

### Setup

Install development dependencies:

```bash
pip install -e ".[dev,test]"
```

### Testing

Run tests:

```bash
make test
```

### Code Quality

Lint code:

```bash
make lint
```

## Data Migrations

This project includes a migration system for handling schema changes. Migrations allow you to transform data from one version to another while preserving existing records.

### Creating a Migration

Generate a new migration stub:

```bash
make migration FROM=1.0.0 TO=1.1.0
```

This creates a migration file in `{{ cookiecutter.pkg_name }}/migrations/`.

### Implementing Migrations

Edit the generated migration file to implement your transformation logic. See `{{ cookiecutter.pkg_name }}/migrations/README.md` for detailed instructions.

### Registering Migrations

After implementing a migration, register it in `{{ cookiecutter.pkg_name }}/migrations/registry.py`:

```python
from .v1_0_to_v1_1 import migrate
MIGRATIONS[("1.0.0", "1.1.0")] = migrate
```

For more details on migrations, see:
- `{{ cookiecutter.pkg_name }}/migrations/README.md` - Migration guide
- `{{ cookiecutter.pkg_name }}/migrations/registry.py` - Migration registry and examples

## License

{{ cookiecutter.open_source_license }}

## Credits

Created by {{ cookiecutter.full_name }} ({{ cookiecutter.email }})
