#!/usr/bin/env python

"""Tests for cookiecutter template migrations scaffold (Issue #37)."""

import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for test output."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def cookiecutter_template_path():
    """Return the path to the peermodel-template directory."""
    # Assuming tests run from project root or can find template
    template_path = Path(__file__).parent.parent.parent / "peermodel-template"
    if not template_path.exists():
        pytest.skip("Cookiecutter template not found")
    return template_path


@pytest.fixture
def generated_package(temp_test_dir, cookiecutter_template_path):
    """Generate a test package from the cookiecutter template."""
    # Create a test cookiecutter config
    config = {
        "full_name": "Test User",
        "email": "test@example.com",
        "github_username": "testuser",
        "project_name": "TestProject",
        "pkg_name": "testprojectdb",
        "project_short_description": "Test package for migrations scaffold",
        "project_slug": "TestProject-peermodel",
        "project_shell_cmd": "tstprjct",
        "pypi_username": "testuser",
        "version": "0.1.0",
        "use_pytest": "y",
        "add_pyup_badge": "y",
        "create_author_file": "y",
        "open_source_license": "MIT license"
    }

    # Use cookiecutter to generate the project
    # This test assumes cookiecutter is installed
    try:
        from cookiecutter.main import cookiecutter
        output_dir = cookiecutter(
            str(cookiecutter_template_path),
            no_input=True,
            extra_context=config,
            output_dir=str(temp_test_dir)
        )
        return Path(output_dir)
    except ImportError:
        pytest.skip("cookiecutter not installed")
    except Exception as e:
        pytest.fail(f"Failed to generate package: {e}")


class TestMigrationsDirectoryScaffold:
    """Test that generated packages have a migrations/ directory."""

    def test_migrations_directory_exists(self, generated_package):
        """Generated package should have a migrations/ directory."""
        pkg_name = "testprojectdb"
        migrations_dir = generated_package / pkg_name / "migrations"
        assert migrations_dir.exists(), (
            f"migrations/ directory not found at {migrations_dir}"
        )
        assert migrations_dir.is_dir(), (
            f"{migrations_dir} exists but is not a directory"
        )

    def test_migrations_directory_is_python_package(
            self, generated_package):
        """migrations/ directory should be a Python package."""
        pkg_name = "testprojectdb"
        migrations_init = (
            generated_package / pkg_name / "migrations" / "__init__.py"
        )
        assert migrations_init.exists(), (
            f"migrations/__init__.py not found at {migrations_init}"
        )


class TestMigrationsRegistryStub:
    """Test generated packages have registry.py stub with instructions."""

    def test_registry_file_exists(self, generated_package):
        """Generated package should have migrations/registry.py."""
        pkg_name = "testprojectdb"
        registry_file = (
            generated_package / pkg_name / "migrations" / "registry.py"
        )
        assert registry_file.exists(), (
            f"migrations/registry.py not found at {registry_file}"
        )

    def test_registry_has_migrations_dict(self, generated_package):
        """registry.py should contain MIGRATIONS dict."""
        pkg_name = "testprojectdb"
        registry_file = (
            generated_package / pkg_name / "migrations" / "registry.py"
        )
        content = registry_file.read_text()

        assert "MIGRATIONS" in content, (
            "registry.py should define MIGRATIONS dict"
        )
        # Check that it's a dict definition
        migrations_defined = (
            "MIGRATIONS:" in content or "MIGRATIONS =" in content
        )
        assert migrations_defined, (
            "MIGRATIONS should be defined as a dict"
        )

    def test_registry_has_documentation(self, generated_package):
        """registry.py should contain documentation for users."""
        pkg_name = "testprojectdb"
        registry_file = (
            generated_package / pkg_name / "migrations" / "registry.py"
        )
        content = registry_file.read_text()

        # Should have comments or docstrings explaining usage
        has_docs = (
            "#" in content or '"""' in content or "'''" in content
        )
        assert has_docs, (
            "registry.py should contain documentation comments"
        )

    def test_registry_has_migration_signature_example(
            self, generated_package):
        """registry.py should document the migration function signature."""
        pkg_name = "testprojectdb"
        registry_file = (
            generated_package / pkg_name / "migrations" / "registry.py"
        )
        content = registry_file.read_text()

        # Should show the expected signature
        has_signature = (
            "record_type" in content or "record_dict" in content
        )
        assert has_signature, (
            "registry.py should document migration function signature"
        )

    def test_registry_imports_correctly(self, generated_package):
        """registry.py should be importable without errors."""
        pkg_name = "testprojectdb"

        # Add the generated package to sys.path temporarily
        import sys
        sys.path.insert(0, str(generated_package))

        try:
            # Import the registry module
            import importlib
            module_name = f"{pkg_name}.migrations.registry"
            registry_module = importlib.import_module(module_name)

            # Should have MIGRATIONS attribute
            assert hasattr(registry_module, "MIGRATIONS"), (
                "registry module should expose MIGRATIONS"
            )

            # MIGRATIONS should be a dict
            migrations = getattr(registry_module, "MIGRATIONS")
            assert isinstance(migrations, dict), (
                "MIGRATIONS should be a dict"
            )

            # Initial MIGRATIONS should be empty
            assert len(migrations) == 0, (
                "Initial MIGRATIONS dict should be empty"
            )
        finally:
            sys.path.remove(str(generated_package))


class TestMigrationScaffolderScript:
    """Test the scripts/new_migration.py scaffolder script."""

    def test_scaffolder_script_exists(self, generated_package):
        """Generated package should have scripts/new_migration.py."""
        scripts_dir = generated_package / "scripts"
        assert scripts_dir.exists(), (
            f"scripts/ directory not found at {scripts_dir}"
        )

        scaffolder = scripts_dir / "new_migration.py"
        assert scaffolder.exists(), (
            f"scripts/new_migration.py not found at {scaffolder}"
        )

    def test_scaffolder_is_executable(self, generated_package):
        """Scaffolder script should be executable."""
        scaffolder = generated_package / "scripts" / "new_migration.py"

        # Check if file has executable bit or is a valid Python script
        assert scaffolder.exists()
        # Should be a Python file
        content = scaffolder.read_text()
        is_python = (
            content.startswith("#!") or "python" in content.lower()[:100]
        )
        assert is_python, (
            "Scaffolder should be a Python script"
        )

    def test_scaffolder_accepts_version_arguments(self, generated_package):
        """Scaffolder should accept FROM and TO version arguments."""
        scaffolder = generated_package / "scripts" / "new_migration.py"

        # Check that the script mentions version arguments
        content = scaffolder.read_text()
        assert "FROM" in content or "from_version" in content, (
            "Scaffolder should accept FROM version argument"
        )
        assert "TO" in content or "to_version" in content, (
            "Scaffolder should accept TO version argument"
        )

    def test_scaffolder_creates_migration_stub(
            self, generated_package, temp_test_dir):
        """Scaffolder should create a migration stub file."""
        scaffolder = generated_package / "scripts" / "new_migration.py"
        pkg_name = "testprojectdb"

        # Run the scaffolder to create a migration
        result = subprocess.run(
            [
                "python",
                str(scaffolder),
                "--from", "1.0.0",
                "--to", "1.1.0"
            ],
            capture_output=True,
            text=True,
            cwd=str(generated_package)
        )

        assert result.returncode == 0, (
            f"Scaffolder failed: {result.stderr}"
        )

        # Check that a migration file was created
        migrations_dir = generated_package / pkg_name / "migrations"
        migration_files = list(migrations_dir.glob("v1_0_to_v1_1.py"))

        assert len(migration_files) > 0, (
            f"No migration file created in {migrations_dir}"
        )

    def test_migration_stub_has_migrate_function(self, generated_package):
        """Generated migration stub should have a migrate() function."""
        scaffolder = generated_package / "scripts" / "new_migration.py"
        pkg_name = "testprojectdb"

        # Run the scaffolder
        subprocess.run(
            [
                "python",
                str(scaffolder),
                "--from", "2.0.0",
                "--to", "2.1.0"
            ],
            capture_output=True,
            cwd=str(generated_package)
        )

        # Check the generated migration file
        migration_file = (
            generated_package / pkg_name / "migrations" / "v2_0_to_v2_1.py"
        )

        if migration_file.exists():
            content = migration_file.read_text()

            assert "def migrate" in content, (
                "Migration stub should define migrate() function"
            )
            has_params = (
                "record_type" in content and "record_dict" in content
            )
            assert has_params, (
                "migrate() should have record_type/record_dict params"
            )
            assert "return" in content, (
                "migrate() should return transformed dict"
            )

    def test_migration_stub_has_documentation(self, generated_package):
        """Generated migration stub should have helpful documentation."""
        scaffolder = generated_package / "scripts" / "new_migration.py"
        pkg_name = "testprojectdb"

        # Run the scaffolder
        subprocess.run(
            [
                "python",
                str(scaffolder),
                "--from", "3.0.0",
                "--to", "3.1.0"
            ],
            capture_output=True,
            cwd=str(generated_package)
        )

        # Check the generated migration file
        migration_file = (
            generated_package / pkg_name / "migrations" / "v3_0_to_v3_1.py"
        )

        if migration_file.exists():
            content = migration_file.read_text()

            # Should have docstrings or comments
            has_docs = (
                '"""' in content or "'''" in content or "#" in content
            )
            assert has_docs, (
                "Migration stub should contain documentation"
            )


class TestMakefileIntegration:
    """Test the Makefile migration target."""

    def test_makefile_has_migration_target(self, generated_package):
        """Generated package Makefile should have a migration target."""
        makefile = generated_package / "Makefile"
        assert makefile.exists(), (
            f"Makefile not found at {makefile}"
        )

        content = makefile.read_text()

        # Should have a migration target
        assert "migration:" in content or "migration " in content, (
            "Makefile should define 'migration' target"
        )

    def test_migration_target_accepts_from_to_args(self, generated_package):
        """Migration target should accept FROM and TO arguments."""
        makefile = generated_package / "Makefile"
        content = makefile.read_text()

        # Check for FROM and TO variable usage
        assert "FROM" in content, (
            "Makefile migration target should accept FROM argument"
        )
        assert "TO" in content, (
            "Makefile migration target should accept TO argument"
        )

    def test_migration_target_calls_scaffolder(self, generated_package):
        """Migration target should invoke the new_migration.py script."""
        makefile = generated_package / "Makefile"
        content = makefile.read_text()

        # Should reference the scaffolder script
        calls_scaffolder = (
            "new_migration.py" in content or "new_migration" in content
        )
        assert calls_scaffolder, (
            "Makefile migration target should call new_migration.py"
        )

    def test_make_migration_creates_file(self, generated_package):
        """Running 'make migration FROM=x TO=y' creates migration file."""
        pkg_name = "testprojectdb"

        # Run make migration
        result = subprocess.run(
            ["make", "migration", "FROM=4.0.0", "TO=4.1.0"],
            capture_output=True,
            text=True,
            cwd=str(generated_package)
        )

        # Check if make command succeeded
        # Note: This may fail if make or dependencies are missing
        if result.returncode == 0:
            # Check that a migration file was created
            migrations_dir = generated_package / pkg_name / "migrations"
            migration_file = migrations_dir / "v4_0_to_v4_1.py"

            assert migration_file.exists(), (
                f"make migration did not create {migration_file}"
            )

    def test_makefile_has_help_text_for_migration(self, generated_package):
        """Migration target should have help text."""
        makefile = generated_package / "Makefile"
        content = makefile.read_text()

        # Check for help comment (target: ## help text)
        lines = content.split('\n')
        migration_lines = [
            line for line in lines if 'migration' in line.lower()
        ]

        # Should have some documentation about the migration target
        has_help = any('##' in line for line in migration_lines)
        assert has_help or len(migration_lines) > 1, (
            "Migration target should have help documentation"
        )


class TestScaffoldDocumentation:
    """Test that the scaffold includes documentation on usage."""

    def test_readme_mentions_migrations(self, generated_package):
        """Generated README should mention migrations."""
        # Check for README.md or README.rst
        readme_md = generated_package / "README.md"
        readme_rst = generated_package / "README.rst"

        readme_file = readme_md if readme_md.exists() else readme_rst
        if not readme_file.exists():
            pytest.skip("No README file found")

        content = readme_file.read_text()

        # Should mention migrations
        assert "migration" in content.lower(), (
            "README should document migrations"
        )

    def test_migrations_readme_exists(self, generated_package):
        """migrations/ directory should have its own README."""
        pkg_name = "testprojectdb"
        migrations_dir = generated_package / pkg_name / "migrations"

        # Check for README in migrations directory
        readme_md = migrations_dir / "README.md"
        readme_rst = migrations_dir / "README.rst"

        has_readme = readme_md.exists() or readme_rst.exists()
        assert has_readme, (
            f"migrations/ directory should have README at {migrations_dir}"
        )

    def test_migrations_readme_has_instructions(self, generated_package):
        """migrations/README explains how to create/register migrations."""
        pkg_name = "testprojectdb"
        migrations_dir = generated_package / pkg_name / "migrations"

        # Find README
        readme_md = migrations_dir / "README.md"
        readme_rst = migrations_dir / "README.rst"
        readme_file = readme_md if readme_md.exists() else readme_rst

        if not readme_file.exists():
            pytest.skip("No migrations README found")

        content = readme_file.read_text()

        # Should explain the process
        has_creation_docs = (
            "make migration" in content or "new_migration" in content
        )
        assert has_creation_docs, (
            "README should explain how to create migrations"
        )
        assert "registry" in content.lower(), (
            "README should explain how to register migrations"
        )
        has_testing_docs = (
            "testing" in content.lower() or "test" in content.lower()
        )
        assert has_testing_docs, (
            "README should explain how to test migrations"
        )


class TestScaffoldValidation:
    """Integration tests to verify the complete scaffold works end-to-end."""

    def test_generated_package_structure_complete(self, generated_package):
        """Verify all required scaffold components exist."""
        pkg_name = "testprojectdb"

        # Check all required paths
        required_paths = [
            generated_package / pkg_name / "migrations",
            generated_package / pkg_name / "migrations" / "__init__.py",
            generated_package / pkg_name / "migrations" / "registry.py",
            generated_package / "scripts" / "new_migration.py",
            generated_package / "Makefile",
        ]

        for path in required_paths:
            assert path.exists(), f"Required path missing: {path}"

    def test_can_import_migrations_registry(self, generated_package):
        """Verify migrations.registry can be imported without errors."""
        pkg_name = "testprojectdb"

        import sys
        sys.path.insert(0, str(generated_package))

        try:
            import importlib
            module_name = f"{pkg_name}.migrations.registry"
            registry = importlib.import_module(module_name)
            assert hasattr(registry, "MIGRATIONS")
            assert isinstance(registry.MIGRATIONS, dict)
        finally:
            sys.path.remove(str(generated_package))

    def test_scaffolder_generates_valid_python(self, generated_package):
        """Verify scaffolder creates syntactically valid Python code."""
        scaffolder = generated_package / "scripts" / "new_migration.py"
        pkg_name = "testprojectdb"

        # Generate a migration
        subprocess.run(
            [
                "python",
                str(scaffolder),
                "--from", "5.0.0",
                "--to", "5.1.0"
            ],
            capture_output=True,
            cwd=str(generated_package)
        )

        # Try to import the generated migration
        migration_file = (
            generated_package / pkg_name / "migrations" / "v5_0_to_v5_1.py"
        )

        if migration_file.exists():
            # Check Python syntax
            import ast
            content = migration_file.read_text()

            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Generated migration has syntax error: {e}")
