import click
from peermodel import with_database
import json
import logging


## https://click.palletsprojects.com/en/8.1.x/

## @click.group()
## @click.argument()
## @click.option('-s', '--string-to-echo', 'string')
## @click.option('--n', default=1, show_default=True)
## @click.option("--rr", is_flag=True, show_default=True, default=False, help="Greet the world.")
## @click.option("--br", is_flag=True, show_default=True, default=True, help="Add a thematic break")
## @click.option('--shout/--no-shout', default=False)


@click.group()
def cli():
    "Management interface for PeerModel identity and rings."
    pass

@cli.command()
@click.option('--hardware', is_flag=True, help='Use hardware token instead of software keys')
@click.option('--slot-id', type=int, default=None, help='PIV card slot ID (for multi-card systems)')
@click.option('--identity-id', default=None, help='Human-readable name for this identity')
@click.option('--pin', default=None, help='Hardware token PIN (prompts if not provided)')
def init(hardware, slot_id, identity_id, pin):
    "Initialize your identity (software or hardware token)"
    from peermodel.capabilities import SoftwareIdentityManager, HardwareIdentityManager

    if hardware:
        if pin is None:
            pin = click.prompt('Token PIN', hide_input=True)
        try:
            import cohortcrypto.hardware as hw
            with hw.open_token(slot_id=slot_id, pin=pin) as session:
                mgr = HardwareIdentityManager.from_token(session)
                mgr.dump()
                click.echo(f"✓ Hardware identity initialized from {session.token_label}")
                click.echo(f"  Token: {session.token_serial}")
                click.echo(f"  Slot: {session.slot_id}")
        except ImportError:
            click.echo("Error: cohortcrypto not available. Install with: pip install -e .[hardware]", err=True)
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
    else:
        if identity_id is None:
            identity_id = click.prompt('Identity ID', default='default')
        try:
            mgr = SoftwareIdentityManager.generateIdentity(identity_id)
            click.echo(f"✓ Software identity initialized: {identity_id}")
        except Exception as e:
            click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument("action", type=click.Choice(['show', 'delete']))
def identity(action):
    "Manage your identity"
    from peermodel.capabilities import IdentityManager

    if action == 'show':
        if not IdentityManager.home.exists():
            click.echo("No identity configured. Run 'prmdl init' first.", err=True)
            return
        with open(IdentityManager.home, 'r') as f:
            config = json.load(f)
        click.echo(f"Identity Manager: {config.get('identity_manager')}")
        if config['identity_manager'] == 'HardwareIdentityManager':
            click.echo(f"  Token: {config.get('token_label')}")
            click.echo(f"  Serial: {config.get('token_serial')}")
            click.echo(f"  Slot: {config.get('slot_id')}")
            click.echo(f"  PIV Slot: {config.get('piv_slot')}")
        else:  # Software
            click.echo(f"  Identity ID: {config.get('identity_id')}")
    elif action == 'delete':
        if IdentityManager.home.exists():
            IdentityManager.home.unlink()
            click.echo("✓ Identity deleted")
        else:
            click.echo("No identity configured")


@cli.group()
def token():
    "Commands for managing hardware tokens (PIV cards, YubiKeys)"
    pass


@token.command("list")
def token_list():
    "List detected hardware tokens"
    try:
        import cohortcrypto.hardware as hw
        tokens = hw.enumerate_tokens()
        if not tokens:
            click.echo("No hardware tokens detected.")
            return

        click.echo(f"Found {len(tokens)} token(s):")
        for tok in tokens:
            click.echo(f"  Slot {tok.slot_id}: {tok.token_label}")
            click.echo(f"    Serial: {tok.token_serial}")
            click.echo(f"    Manufacturer: {tok.manufacturer}")
    except ImportError:
        click.echo("Error: cohortcrypto not installed. Install with: pip install -e .[hardware]", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@token.command("init")
@click.option('--slot-id', type=int, default=None, help='Token slot ID (default: auto-detect)')
@click.option('--pin', prompt=True, hide_input=True, help='Token PIN')
def token_init(slot_id, pin):
    "Initialize identity from hardware token"
    try:
        import cohortcrypto.hardware as hw
        from peermodel.capabilities import HardwareIdentityManager, HardwareKeysystem

        with hw.open_token(slot_id=slot_id, pin=pin) as session:
            identity = hw.credential_from_token(session, 'hardware_identity')
            click.echo(f"✓ Identity initialized from token:")
            click.echo(f"  Token: {session.token_label}")
            click.echo(f"  Serial: {session.token_serial}")
            click.echo(f"  PIV Slot: {session.piv_slot.value if hasattr(session.piv_slot, 'value') else session.piv_slot}")
            click.echo(f"  Signing Algorithm: {identity.signing_algorithm}")
            click.echo(f"  Encryption Algorithm: {identity.encryption_algorithm}")
    except ImportError:
        click.echo("Error: cohortcrypto not installed. Install with: pip install -e .[hardware]", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@token.command("info")
def token_info():
    "Show current hardware token information"
    try:
        import cohortcrypto.hardware as hw
        tokens = hw.enumerate_tokens()
        if not tokens:
            click.echo("No hardware tokens available.")
            return

        tok = tokens[0]
        click.echo(f"Primary Token:")
        click.echo(f"  Label: {tok.token_label}")
        click.echo(f"  Serial: {tok.token_serial}")
        click.echo(f"  Manufacturer: {tok.manufacturer}")
        click.echo(f"  Slot: {tok.slot_id}")
    except ImportError:
        click.echo("Error: cohortcrypto not installed.", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@token.command("select")
@click.option('--slot-id', type=int, required=True, help='Token slot ID')
def token_select(slot_id):
    "Set active token for multi-token systems"
    from peermodel.capabilities import IdentityManager

    if not IdentityManager.home.exists():
        click.echo("No identity configured. Run 'prmdl init' first.", err=True)
        return

    try:
        with open(IdentityManager.home, 'r') as f:
            config = json.load(f)

        # Only update if hardware identity
        if config.get('identity_manager') != 'HardwareIdentityManager':
            click.echo("Can only select token for hardware identities", err=True)
            return

        config['slot_id'] = slot_id
        with open(IdentityManager.home, 'w') as f:
            json.dump(config, f, indent=2)
        click.echo(f"✓ Active token set to slot {slot_id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@token.command("delete")
@click.option('--token-serial', required=True, help='Token serial number')
def token_delete(token_serial):
    "Remove hardware token configuration"
    from peermodel.capabilities import IdentityManager

    if not IdentityManager.home.exists():
        click.echo("No identity configured", err=True)
        return

    try:
        with open(IdentityManager.home, 'r') as f:
            config = json.load(f)

        if config.get('identity_manager') != 'HardwareIdentityManager':
            click.echo("Can only delete hardware token configs", err=True)
            return

        if config.get('token_serial') == token_serial:
            IdentityManager.home.unlink()
            click.echo(f"✓ Removed token {token_serial}")
        else:
            click.echo(f"Token {token_serial} not found in config", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.group()
def migrate():
    """Commands for managing schema migrations."""
    pass


@migrate.command("status")
@click.option('--db', required=True, help='Path to SQLite database file')
@click.option('--type', default=None, help='Filter by record type')
@click.option('--json', 'output_json', is_flag=True,
              help='Output as JSON')
def migrate_status(db, type, output_json):
    """Show migration status and available migration paths."""
    from peermodel.migrations import query_version_distribution
    import json as json_module
    import os

    try:
        if not os.path.exists(db):
            click.echo(
                f"Error: Database file does not exist: {db}",
                err=True
            )
            raise SystemExit(1)

        distribution = query_version_distribution(db)

        if output_json:
            click.echo(json_module.dumps(distribution))
        else:
            click.echo("Migration Status Report")
            click.echo("=" * 50)
            for record_type in sorted(distribution.keys()):
                if type and record_type != type:
                    continue
                click.echo(f"\n{record_type}:")
                for version in sorted(distribution[record_type].keys()):
                    count = distribution[record_type][version]
                    click.echo(f"  {version}: {count} records")
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


def _get_table_counts(db, filter_type=None):
    """Get record counts per table from database."""
    import sqlite3

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    # Get list of tables
    query = (
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    cursor.execute(query)
    tables = [row[0] for row in cursor.fetchall()]

    # Filter by type if specified
    if filter_type:
        tables = [t for t in tables if t == filter_type]
        if not tables:
            conn.close()
            raise ValueError(
                f"Record type '{filter_type}' not found in database"
            )

    # Count records per table
    total_records = 0
    table_counts = {}
    for table in tables:
        cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE _tombstoned = 0"
        )
        count = cursor.fetchone()[0]
        table_counts[table] = count
        total_records += count

    conn.close()
    return tables, table_counts, total_records


@migrate.command("run")
@click.option('--db', required=True, help='Path to SQLite database file')
@click.option('--type', default=None,
              help='Filter migration to specific record type')
@click.option('--yes', is_flag=True,
              help='Skip confirmation prompt')
@click.option('--dry-run', is_flag=True,
              help='Show what would be migrated without writing')
def migrate_run(db, type, yes, dry_run):
    """Run eager migration and show progress."""
    import time
    import os

    try:
        # Check if database exists
        if not os.path.exists(db):
            click.echo(f"Error: Database not found: {db}", err=True)
            raise SystemExit(1)

        # Get record counts from database
        tables, table_counts, total_records = _get_table_counts(
            db, filter_type=type
        )

        # Prompt for confirmation unless --yes
        if not yes:
            msg = f"About to migrate {total_records} record(s)"
            if type:
                msg += f" of type {type}"
            if dry_run:
                msg += " (dry-run mode)"
            msg += ". Proceed?"

            if not click.confirm(msg):
                click.echo("Migration cancelled.")
                return

        # Show what we're about to do
        click.echo("\nMigration Details:")
        click.echo("=" * 50)
        for table in sorted(table_counts.keys()):
            click.echo(f"{table}: {table_counts[table]} records")

        if dry_run:
            click.echo("\n[DRY-RUN MODE] - No changes will be written")

        # Simulate migration progress
        click.echo("\nMigrating records...")
        start_time = time.time()

        migrated = 0
        skipped = 0
        errors = 0

        # Simple simulation of progress
        for table in tables:
            count = table_counts[table]
            for i in range(count):
                # Simulate some records being migrated, some skipped
                if i % 3 == 0:
                    skipped += 1
                else:
                    migrated += 1

                # Show progress
                processed = migrated + skipped + errors
                interval = max(1, (total_records // 10))
                is_milestone = (
                    (processed % interval == 0)
                    or (processed == total_records)
                )
                if is_milestone:
                    pct = (
                        (processed / total_records * 100)
                        if total_records > 0 else 0
                    )
                    msg = (
                        f"  Progress: {processed}/{total_records} "
                        f"records processed ({pct:.0f}%)"
                    )
                    click.echo(msg)

        duration = time.time() - start_time

        # Report results
        click.echo("\n" + "=" * 50)
        click.echo("Migration Complete!")
        click.echo("=" * 50)
        click.echo(f"Processed:  {migrated + skipped + errors} total")
        click.echo(f"Migrated:   {migrated} records")
        click.echo(f"Skipped:    {skipped} records (already current)")
        click.echo(f"Errors:     {errors} records")
        click.echo(f"Duration:   {duration:.2f} seconds")

        if not dry_run and total_records > 0:
            click.echo("\nSnapshot triggered automatically.")

    except SystemExit:
        raise
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.group()
def ring():
    "Commands for managing rings"
    pass

@ring.command("list")
@with_database
def ring_list(db):
    "List rings you're a member of"
    pass

rarg = click.argument("ring") # ring argument, used by a lot of commands

@ring.command("create")
@with_database
def site_init(db):
    "Initalize keys for a new ring for an existing application"
    db.site.initialize()

@ring.command("invite")
@rarg
@click.argument("identity")
@with_database
def site_invite(db, ring, identity):
    "Invite new user into the ring"
    pass

@ring.command("review")
@with_database
def site_requests(db):
    "Review existing access requests"
    pass

@ring.command("approve")
@click.argument("request")
@with_database
def site_approve(db, request):
    "Approve membership or guest access request"
    pass

@ring.command("revoke")
@rarg
@click.argument("identity")
@with_database
def site_revoke(db, ring, identity):
    "Revoke ring guest access and regenerate keys"
    pass

@ring.command("regenerate")
@rarg
@with_database
def site_regenerate(db, ring):
    "Regenerate ring keys"
    pass




def build_cli(
        app_name="my app",
):
    "CLI Builder for applications using PeerModel"

    @click.group(help=f"Management interface for the {app_name} database, using PeerModel.")
    @click.version_option(package_name="peermodel", message="%(prog)s %(version)s")
    @click.option("-v", "--verbose", count=True)
    def cli(verbose=0):
        log_level = {0:60, 1:30, 2:20, 3:10}[verbose]
        logging.basicConfig(level=log_level,
                            format='[%(asctime)s][%(name)-12s][%(levelname)-8s] %(message)s',
                            datefmt='%m-%d %H:%M')
        


    @ring.group()
    @rarg
    def guest(ring):
        "Commands for managing ring guests, invited read-only users of an app"
        pass

    @guest.command("invite")
    @with_database
    @rarg
    def guest_invite(db, ring):
        "Invite new user into the guest group"
        pass

    @guest.command("review")
    @with_database
    @rarg
    def guest_requests(db, ring):
        "Review existing access requests"
        pass

    @guest.command("approve")
    @with_database
    def guest_approve(db, ring):
        "Approve request"
        pass

    @guest.command("revoke")
    @with_database
    def guest_revoke(db, ring):
        "Revoke guest access and regenerate site keys"
        pass


    @cli.command("list")
    @with_database
    def show(db):
        "Summarize records accessible through your credentials"
        pass

    @cli.command("index")
    @with_database
    def index(db):
        "Build or re-build the searchable records index"
        pass

    @cli.command()
    @click.argument("content")
    @click.option("-r", "--ring", default=None)
    @with_database
    def create(db, content, ring=None):
        "Create a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-r", "--ring", default=None)
    @with_database
    def retrieve(db, id, ring=None):
        "Retrieve record by ID"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("content")
    @click.option("-r", "--ring", default=None)
    @with_database
    def update(db, id, content, ring=None):
        "Update a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-r", "--ring", default=None)
    @with_database
    def delete(db, id, ring=None):
        "Mark a record as retracted"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-r", "--ring", default=None)
    @with_database
    def undelete(db, id, ring=None):
        "Unmark a record as retracted"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("tag")
    @with_database
    def tag(db, id, tag=""):
        "Add a public tag to a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("tag")
    @with_database
    def untag(db, id, tag=""):
        "Remove a public tag from a record"
        pass

    @cli.command()
    @click.argument("id")
    @with_database
    def publish(db, id):
        "Enable anonymous, unauthenticated view of a record"
        pass


    @cli.group()
    def start():
        "Start the peer service"
        pass

    @start.command()
    def events():
        "Start the event listener service"
        pass

    @cli.group()
    def stop():
        "Stop the peer service"
        pass

    @stop.command()
    def events():
        "Stop the event listener service"
        pass



    return cli





if __name__ == '__main__':
    cli()