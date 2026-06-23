import click
from peermodel import with_database
from peermodel.migrations import query_version_distribution
import json
import logging
import os
from pathlib import Path


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
    "Commands for managing schema migrations"
    pass


def _compute_migration_paths(version_dist, engine=None):
    """Compute migration paths for each version."""
    paths = {}
    for record_type, versions_dict in version_dist.items():
        paths[record_type] = {}
        if not versions_dict:
            continue

        # Find latest version
        latest_version = max(versions_dict.keys(), key=lambda v: tuple(map(int, v.split('.'))))

        for version in versions_dict.keys():
            if version == latest_version:
                paths[record_type][version] = []
            else:
                # Try to find path using engine
                if engine:
                    try:
                        path = engine.find_path(version, latest_version)
                        paths[record_type][version] = path
                    except Exception:
                        paths[record_type][version] = None
                else:
                    paths[record_type][version] = None

    return paths


@migrate.command("status")
@click.option('--db', required=False, type=click.Path(exists=False),
              help='Path to SQLite database')
@click.option('--json', 'output_json', is_flag=True,
              help='Output as JSON')
@click.option('--type', 'record_type', default=None,
              help='Filter by record type')
def migrate_status(db, output_json, record_type):
    "Show migration status and version distribution"
    from peermodel.migrations import get_engine

    try:
        # Query version distribution (db can be None)
        if db is not None and not os.path.exists(db):
            click.echo(f"Error: database file not found: {db}", err=True)
            raise SystemExit(1)

        version_dist = query_version_distribution(db)

        # Filter by record type if specified
        if record_type:
            if record_type not in version_dist:
                click.echo(f"Error: record type '{record_type}' not found", err=True)
                raise SystemExit(1)
            version_dist = {record_type: version_dist[record_type]}

        # Get migration engine
        try:
            engine = get_engine('peermodel')
        except Exception as e:
            # Re-raise to be caught by outer exception handler
            raise RuntimeError(f"Failed to load migration engine: {e}") from e

        # Compute migration paths
        migration_paths = _compute_migration_paths(version_dist, engine)

        if output_json:
            # JSON output
            output_data = {}
            for rec_type, versions_dict in version_dist.items():
                if not versions_dict:
                    output_data[rec_type] = {}
                    continue

                total = sum(versions_dict.values())
                output_data[rec_type] = {}

                for version, count in sorted(versions_dict.items()):
                    percentage = (count / total * 100) if total > 0 else 0
                    path_info = migration_paths.get(rec_type, {}).get(version)

                    output_data[rec_type][version] = {
                        'count': count,
                        'percentage': round(percentage, 2),
                        'migration_path': path_info if path_info is not None else 'No path'
                    }

            click.echo(json.dumps(output_data, indent=2))
        else:
            # Text output
            if not version_dist or not any(version_dist.values()):
                click.echo("No records found in database.")
                return

            total_records_to_migrate = 0

            for rec_type in sorted(version_dist.keys()):
                versions_dict = version_dist[rec_type]
                if not versions_dict:
                    click.echo(f"\n{rec_type}: No records found")
                    continue

                # Header
                click.echo(f"\n{rec_type}:")
                click.echo(f"{'Version':<15} {'Count':<10} {'Percentage':<12} {'Migration Path':<30}")
                click.echo("-" * 70)

                total = sum(versions_dict.values())
                versions_sorted = sorted(versions_dict.keys())
                latest_version = versions_sorted[-1]

                records_at_old_versions = 0

                for version in versions_sorted:
                    count = versions_dict[version]
                    percentage = (count / total * 100) if total > 0 else 0

                    # Get migration path
                    path = migration_paths.get(rec_type, {}).get(version)
                    if path is None:
                        path_str = "NO PATH"
                    elif path == []:
                        path_str = "Latest version" if version == latest_version else "Ready"
                    else:
                        # Format path
                        path_steps = [version]
                        for from_v, to_v in path:
                            path_steps.append(to_v)
                        path_str = " -> ".join(path_steps)

                    click.echo(f"{version:<15} {count:<10} {percentage:>10.2f}%  {path_str:<30}")

                    # Count records needing migration
                    if version != latest_version:
                        records_at_old_versions += count

                total_records_to_migrate += records_at_old_versions

                # Summary
                if records_at_old_versions > 0:
                    click.echo(f"\n{records_at_old_versions} records need migration to {latest_version}")
                else:
                    click.echo(f"\nAll records are at latest version ({latest_version})")

            # Overall summary
            if total_records_to_migrate > 0:
                click.echo(f"\nTotal: {total_records_to_migrate} records need migration")
            else:
                click.echo("\nAll records are up to date!")

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